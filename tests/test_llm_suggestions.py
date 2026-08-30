"""Concrete suggestions from the LLM: experiment drafts and resources.

Both roles exist to make the vocational cycle actionable — "here is the
experiment that would settle this capability, and here is where to go run
it" — WITHOUT giving the model an inch of authority. The tests that matter
are the ones that would catch it acquiring some: neither call may write to
the ledger, and neither may move a sealed number.
"""

from __future__ import annotations

import json

import pytest

from compass import engine, seed_demo, views
from compass.db import open_db
from compass.llm import (MAX_RESOURCES, RESOURCE_FINDER_SYSTEM, DemoBackend,
                         LLMOutputError, ResourceFinder, SearchingBackend,
                         TrajectoryProposer, validate_resources,
                         validate_trajectory_proposals)


class _StubSearchBackend:
    """A backend that CAN search. Records what it was asked, returns fixtures."""

    def __init__(self, payload: str, sources: list[dict] | None = None):
        self._payload = payload
        self._sources = sources or [{"title": "Example", "uri": "https://example.org/a"}]
        self.asked: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:      # pragma: no cover
        raise AssertionError("a searching backend must use search(), not complete()")

    def search(self, system: str, user: str) -> tuple[str, list[dict]]:
        self.asked.append((system, user))
        return self._payload, self._sources


_GOOD = json.dumps([
    {"title": "Open-source project with public design review", "kind": "project",
     "why": "Contributing a design puts the capability in front of reviewers.",
     "url": "https://example.org/project"},
])


# ------------------------------------------------------- boundary ----------

def test_resources_are_rejected_when_kind_is_invented():
    """Closed vocabulary: a model cannot widen the taxonomy by asserting it."""
    with pytest.raises(LLMOutputError, match="vocabulario"):
        validate_resources(json.dumps([
            {"title": "X", "kind": "life_advice", "why": "y", "url": ""}]))


def test_resources_may_not_smuggle_a_percentage():
    """The percentage guard covers every model output about the person, not
    just the narration (Red Team R1, finding A)."""
    with pytest.raises(LLMOutputError, match="porcentaje"):
        validate_resources(json.dumps([
            {"title": "X", "kind": "course",
             "why": "Puts you in the top 10% of designers.", "url": ""}]))


def test_non_http_urls_are_dropped_not_rendered():
    """A javascript:/data: link never reaches the UI. The resource survives
    without its link; the link does not survive at all."""
    out = validate_resources(json.dumps([
        {"title": "X", "kind": "course", "why": "y", "url": "javascript:alert(1)"}]))
    assert out[0]["url"] == ""


def test_resources_are_capped():
    payload = json.dumps([
        {"title": f"r{i}", "kind": "reading", "why": "y", "url": ""}
        for i in range(MAX_RESOURCES + 1)])
    with pytest.raises(LLMOutputError, match="más de"):
        validate_resources(payload)


def test_empty_url_is_valid_because_inventing_one_is_worse():
    out = validate_resources(json.dumps([
        {"title": "X", "kind": "reading", "why": "y", "url": ""}]))
    assert out[0]["url"] == ""


# ------------------------------------------------------- grounding --------

def test_grounded_flag_distinguishes_a_real_search_from_model_memory():
    """Degrading silently — presenting the model's memory as a search — is the
    unsupported claim the rest of the system refuses. The flag must tell them
    apart, and only a searching backend may report sources."""
    searched = ResourceFinder(_StubSearchBackend(_GOOD)).find("Designs unaided")
    assert searched["grounded"] is True
    assert searched["sources"] == [{"title": "Example", "uri": "https://example.org/a"}]

    offline = ResourceFinder(DemoBackend()).find("Designs unaided")
    assert offline["grounded"] is False
    assert offline["sources"] == []
    assert all(r["url"] == "" for r in offline["resources"]), (
        "an offline backend must not emit URLs it cannot have found"
    )


def test_searching_backend_is_detected_by_capability_not_by_name():
    assert isinstance(_StubSearchBackend(_GOOD), SearchingBackend)
    assert not isinstance(DemoBackend(), SearchingBackend)


def test_the_capability_is_passed_as_data_under_the_resource_prompt():
    backend = _StubSearchBackend(_GOOD)
    ResourceFinder(backend).find("  Closes an architecture unaided  ")
    system, user = backend.asked[0]
    # the system prompt carries a language suffix (respond in EN/ES); the
    # capability itself is passed as the USER content, never in the prompt.
    assert system.startswith(RESOURCE_FINDER_SYSTEM)
    assert user == "Closes an architecture unaided"


def test_empty_capability_never_reaches_the_backend():
    backend = _StubSearchBackend(_GOOD)
    with pytest.raises(LLMOutputError):
        ResourceFinder(backend).find("   ")
    assert backend.asked == []


# ------------------------------------------------------- no authority -----

@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPASS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("COMPASS_BACKEND", "demo")
    monkeypatch.delenv("COMPASS_GCS_BUCKET", raising=False)
    import importlib

    from compass import storage as storage_module
    importlib.reload(storage_module)
    from compass import api as api_module
    importlib.reload(api_module)
    from fastapi.testclient import TestClient
    with TestClient(api_module.app) as c:
        yield c


def test_suggesting_moves_no_sealed_number(api_client):
    """THE test for both roles. Drafting an experiment and looking for
    resources are proposals: after either, the sealed state and a fresh
    recompute must be bit-for-bit what they were. Red-first — it fails the
    moment either endpoint writes to the ledger or touches the engine.
    """
    # /api/state and /api/recompute seal DIFFERENT material, so each is
    # compared against itself rather than against the other.
    before_state = api_client.get("/api/state").json()["seal"]
    before_recompute = api_client.post("/api/recompute").json()["seal"]
    before_chain = len(api_client.get("/api/chain").json()["entries"])

    drafted = api_client.post("/api/experiments/design", json={"hypothesis_id": 1})
    assert drafted.status_code == 200
    found = api_client.post("/api/resources", json={"hypothesis_id": 1})
    assert found.status_code == 200

    assert api_client.get("/api/state").json()["seal"] == before_state, (
        "a suggestion changed the sealed state"
    )
    assert len(api_client.get("/api/chain").json()["entries"]) == before_chain, (
        "a suggestion appended to the audit chain"
    )
    assert api_client.post("/api/recompute").json()["seal"] == before_recompute, (
        "a suggestion moved an index"
    )


def test_design_returns_a_declared_failure_criterion(api_client):
    """An experiment that can only turn out well discriminates nothing
    (design doc §4), so the draft carries its failure criterion from birth."""
    body = api_client.post("/api/experiments/design",
                           json={"hypothesis_id": 1}).json()
    draft = body["draft"]
    assert set(draft) == {"design", "success_criterion", "failure_criterion"}
    assert draft["failure_criterion"].strip()
    assert body["hypothesis_statement"]


def test_resources_endpoint_declares_it_did_not_search(api_client):
    """With the offline demo backend the API must SAY the resources were not
    searched, rather than let a caller assume they were."""
    body = api_client.post("/api/resources", json={"hypothesis_id": 1}).json()
    assert body["grounded"] is False
    assert body["sources"] == []
    assert body["capability"]
    assert 0 < len(body["resources"]) <= MAX_RESOURCES


def test_unknown_hypothesis_is_404_on_both(api_client):
    for path in ("/api/experiments/design", "/api/resources"):
        assert api_client.post(path, json={"hypothesis_id": 9999}).status_code == 404


# --------------------------------------------------- trajectory proposer ---

def test_a_proposal_may_only_cite_hypotheses_that_exist():
    """THE guard on this role. A model that could invent a hypothesis id
    could invent the capability that makes a path look good. Composing
    existing hypotheses is allowed; referencing anything else is not."""
    payload = json.dumps([{
        "name": "Invented path", "description": "d",
        "requirements": [{"hypothesis_id": 99, "label": "a capability"}],
    }])
    with pytest.raises(LLMOutputError, match="no es una hipótesis de esta persona"):
        validate_trajectory_proposals(payload, {1, 2})


def test_a_proposal_may_not_repeat_a_hypothesis_within_one_path():
    """The domain rejects two requirements backed by the same hypothesis, so
    the boundary rejects it before it becomes a guaranteed 400."""
    payload = json.dumps([{
        "name": "P", "description": "d",
        "requirements": [{"hypothesis_id": 1, "label": "a"},
                         {"hypothesis_id": 1, "label": "b"}],
    }])
    with pytest.raises(LLMOutputError, match="repetido"):
        validate_trajectory_proposals(payload, {1, 2})


def test_a_boolean_is_not_a_hypothesis_id():
    """bool is a subclass of int, so it is checked first — the same rule the
    canonicaliser applies to keep `1` and `True` distinguishable."""
    payload = json.dumps([{
        "name": "P", "description": "d",
        "requirements": [{"hypothesis_id": True, "label": "a"}],
    }])
    with pytest.raises(LLMOutputError, match="hypothesis_id debe ser int"):
        validate_trajectory_proposals(payload, {1, 2})


def test_proposing_with_no_hypotheses_never_reaches_the_backend():
    class _Boom:
        def complete(self, system: str, user: str) -> str:  # pragma: no cover
            raise AssertionError("must not call the model with nothing to compose")

    with pytest.raises(LLMOutputError, match="al menos una capacidad"):
        TrajectoryProposer(_Boom()).propose([])


def test_the_proposer_only_sees_the_ids_it_may_use():
    """What the model receives is what it may cite. Nothing else is in scope."""
    class _Capture:
        def __init__(self):
            self.user = ""

        def complete(self, system: str, user: str) -> str:
            self.user = user
            return json.dumps([{
                "name": "P", "description": "d",
                "requirements": [{"hypothesis_id": 7, "label": "a"}]}])

    backend = _Capture()
    out = TrajectoryProposer(backend).propose(
        [{"id": 7, "statement": "Designs unaided", "status": "activa"}])
    assert json.loads(backend.user) == [
        {"id": 7, "statement": "Designs unaided", "status": "activa"}]
    assert out[0]["requirements"][0]["hypothesis_id"] == 7


def test_proposing_trajectories_moves_no_sealed_number(api_client):
    """Same invariant as the other two roles: a proposal is not a write."""
    before_state = api_client.get("/api/state").json()["seal"]
    before_recompute = api_client.post("/api/recompute").json()["seal"]
    before_chain = len(api_client.get("/api/chain").json()["entries"])
    before_trajectories = len(
        api_client.get("/api/trajectories").json()["trajectories"])

    body = api_client.post("/api/trajectories/propose")
    assert body.status_code == 200
    proposals = body.json()["proposals"]
    assert proposals, "the demo backend must return something to look at"

    assert api_client.get("/api/state").json()["seal"] == before_state
    # The chain is measured BEFORE recomputing again: a recompute legitimately
    # appends, so checking it after would hide what the proposal did.
    assert len(api_client.get("/api/chain").json()["entries"]) == before_chain
    assert len(api_client.get("/api/trajectories").json()["trajectories"]) == (
        before_trajectories), "a proposal created a trajectory on its own"
    assert api_client.post("/api/recompute").json()["seal"] == before_recompute


def test_proposals_cite_only_this_persons_hypotheses(api_client):
    """End to end: whatever comes back is attachable, because every id in it
    is one the person actually has."""
    real = {h["id"] for h in api_client.get("/api/hypotheses").json()["hypotheses"]}
    proposals = api_client.post("/api/trajectories/propose").json()["proposals"]
    cited = {r["hypothesis_id"] for p in proposals for r in p["requirements"]}
    assert cited <= real, f"proposal cited unknown hypotheses: {cited - real}"


def test_a_proposal_is_accepted_through_the_ordinary_endpoints(api_client):
    """Accepting is the person's act, done with the same endpoints they would
    use by hand — the proposer gets no private write path."""
    proposal = api_client.post("/api/trajectories/propose").json()["proposals"][0]
    tid = api_client.post("/api/trajectories", json={
        "name": proposal["name"], "description": proposal["description"],
    }).json()["trajectory_id"]
    for req in proposal["requirements"]:
        assert api_client.post(
            f"/api/trajectories/{tid}/requirements", json=req).status_code == 200
    fit = api_client.get(f"/api/trajectories/{tid}/fit").json()
    assert fit["summary"]["total"] == len(proposal["requirements"])
