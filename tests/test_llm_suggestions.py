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
                         validate_resources)


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
    assert system == RESOURCE_FINDER_SYSTEM
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
