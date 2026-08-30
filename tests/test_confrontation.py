"""Confrontación autopercepción vs. datos (design doc §5, política §9 v0).

El momento más riesgoso del producto, así que los tests que importan son los
que prueban que NO dispara: cada condición mínima de §5 se verifica por
separado sacándola de a una y viendo desaparecer la confrontación. Un
disparador que solo se prueba en el caso que sí anda no prueba nada.
"""

from __future__ import annotations

import pytest

from compass import confrontation, domain, engine
from compass.confrontation import (CONFRONTATION_POLICY_V0,
                                   KIND_RECORD_EXCEEDS_SELF,
                                   KIND_SELF_EXCEEDS_RECORD,
                                   ConfrontationPolicyError, confrontations,
                                   record_policy_decision, validate_partition)
from compass.db import EVIDENCE_TYPES, open_db


def _base(tmp_path, name="c.db"):
    conn = open_db(str(tmp_path / name))
    engine.seed_default_config(conn)
    domain.person_set(conn, "Tester")
    return conn


def _link(conn, hid, etype, direction, source="t"):
    eid = domain.evidence_add(conn, evidence_type=etype, source=source,
                              content={"text": f"{etype}-{direction}-{source}"},
                              validated=True)
    domain.evidence_link(conn, hypothesis_id=hid, evidence_id=eid,
                         direction=direction)
    return eid


def _doubting_person(tmp_path, name="c.db"):
    """The person's own account pushes AGAINST; the record supports.

    Three distinct evidence types and a high index, so every §5 condition
    is met at once — this is the scenario the others subtract from.
    """
    conn = _base(tmp_path, name)
    hid = domain.hypothesis_add(
        conn, statement="Can hold an architecture under expert critique.",
        origin="person")
    _link(conn, hid, "self_report", "contradicts")
    _link(conn, hid, "behavioral", "supports")
    _link(conn, hid, "experiment_result", "supports")
    _link(conn, hid, "outcome_external", "supports")
    engine.recompute_all(conn)
    return conn, hid


# ------------------------------------------------------------- partition ---

def test_every_evidence_type_has_a_declared_side():
    """A type nobody assigned would silently drop out of the comparison and
    bias the confrontation by omission."""
    validate_partition(EVIDENCE_TYPES)


def test_an_unassigned_evidence_type_is_rejected_loudly():
    with pytest.raises(ConfrontationPolicyError, match="sin lado asignado"):
        validate_partition(EVIDENCE_TYPES + ("peer_review",))


# ---------------------------------------------------------------- fires ----

def test_it_fires_when_every_minimum_condition_is_met(tmp_path):
    conn, hid = _doubting_person(tmp_path)
    out = confrontations(conn)
    assert len(out["confrontations"]) == 1
    c = out["confrontations"][0]
    assert c["hypothesis_id"] == hid
    assert c["kind"] == KIND_RECORD_EXCEEDS_SELF
    assert c["self_contradicts"] == 1 and c["self_supports"] == 0
    assert c["record_supports"] == 3
    assert c["distinct_types"] >= CONFRONTATION_POLICY_V0["min_distinct_types"]
    assert c["index"] >= CONFRONTATION_POLICY_V0["index_threshold"]


def test_the_opposite_direction_is_recognised_too(tmp_path):
    """The person asserts it; the record pushes back. Same machinery."""
    conn = _base(tmp_path)
    hid = domain.hypothesis_add(conn, statement="Ships fast under pressure.",
                                origin="person")
    _link(conn, hid, "self_report", "supports")
    _link(conn, hid, "narrative_extracted", "supports")
    _link(conn, hid, "behavioral", "contradicts")
    engine.recompute_all(conn)
    tally = confrontation._tally(conn, hid)
    assert confrontation._kind(tally) == KIND_SELF_EXCEEDS_RECORD


# ------------------------------------------------ each gate, on its own ----

def test_it_stays_silent_below_the_index_threshold(tmp_path):
    """Same discrepancy, thin evidence: §5 requires a high index."""
    conn, _ = _doubting_person(tmp_path)
    assert confrontations(conn)["confrontations"], "baseline must fire"

    strict = dict(CONFRONTATION_POLICY_V0, index_threshold=100000)
    assert confrontations(conn, strict)["confrontations"] == []


def test_it_stays_silent_with_too_few_distinct_types(tmp_path):
    """§5 literal: at least three distinct kinds of evidence."""
    conn = _base(tmp_path)
    hid = domain.hypothesis_add(conn, statement="One-sided record.",
                                origin="person")
    _link(conn, hid, "self_report", "contradicts")
    # Three external supports, but all of ONE type.
    for i in range(3):
        _link(conn, hid, "outcome_external", "supports", source=f"s{i}")
    engine.recompute_all(conn)

    tally = confrontation._tally(conn, hid)
    assert tally["distinct_types"] == 2
    assert confrontation._kind(tally) is not None, (
        "the discrepancy itself exists; only the type-diversity gate is missing"
    )
    assert confrontations(conn)["confrontations"] == []


def test_agreement_is_not_a_discrepancy(tmp_path):
    """The seeded demo lands here: person and record point the same way."""
    conn = _base(tmp_path)
    hid = domain.hypothesis_add(conn, statement="Both sides agree.",
                                origin="person")
    _link(conn, hid, "self_report", "supports")
    _link(conn, hid, "behavioral", "supports")
    _link(conn, hid, "experiment_result", "supports")
    _link(conn, hid, "outcome_external", "supports")
    engine.recompute_all(conn)
    assert confrontations(conn)["confrontations"] == []


def test_silence_on_one_side_is_not_a_discrepancy(tmp_path):
    """If the person never said anything about it, there is nothing to
    confront them with — that is a gap, not a contradiction."""
    conn = _base(tmp_path)
    hid = domain.hypothesis_add(conn, statement="Person never weighed in.",
                                origin="person")
    _link(conn, hid, "behavioral", "supports")
    _link(conn, hid, "experiment_result", "supports")
    _link(conn, hid, "outcome_external", "supports")
    engine.recompute_all(conn)
    assert confrontations(conn)["confrontations"] == []


def test_unvalidated_evidence_cannot_trigger_a_confrontation(tmp_path):
    """The confrontation may not lean on anything the index did not count."""
    conn, hid = _doubting_person(tmp_path)
    before = confrontations(conn)["confrontations"]
    assert before

    eid = domain.evidence_add(conn, evidence_type="self_report", source="pending",
                              content={"text": "not validated"}, validated=False)
    domain.evidence_link(conn, hypothesis_id=hid, evidence_id=eid,
                         direction="supports")
    after = confrontations(conn)["confrontations"][0]
    assert after["self_supports"] == 0, (
        "pending evidence was counted into the confrontation"
    )


# -------------------------------------------------------- policy + seal ----

def test_only_one_is_surfaced_and_the_rest_are_counted_not_hidden(tmp_path):
    conn, _ = _doubting_person(tmp_path)
    hid2 = domain.hypothesis_add(conn, statement="A second discrepancy.",
                                 origin="person")
    _link(conn, hid2, "self_report", "contradicts", source="b")
    _link(conn, hid2, "behavioral", "supports", source="b")
    _link(conn, hid2, "experiment_result", "supports", source="b")
    _link(conn, hid2, "outcome_external", "supports", source="b")
    engine.recompute_all(conn)

    out = confrontations(conn)
    assert len(out["confrontations"]) == CONFRONTATION_POLICY_V0["max_surfaced"] == 1
    assert out["held_back"] == 1, "the others must be counted, never dropped"


def test_reading_a_confrontation_moves_nothing(tmp_path):
    """Read-only projection, like the vocational fit."""
    from compass import views
    conn, _ = _doubting_person(tmp_path)
    state_before = views.sealed_state(conn)["seal"]
    chain_before = conn.execute("SELECT COUNT(*) c FROM audit_chain").fetchone()["c"]

    confrontations(conn)
    confrontations(conn)

    assert views.sealed_state(conn)["seal"] == state_before
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_chain").fetchone()["c"] == chain_before


def test_the_provisional_policy_is_recorded_with_its_reopening_condition(tmp_path):
    """An unjustified number is registered as an open decision, not left as a
    mute constant — the same treatment the engine weights get."""
    conn = _base(tmp_path)
    row = conn.execute(
        "SELECT title, reopen_condition FROM decision_record "
        "WHERE title LIKE 'Política de confrontación%'").fetchone()
    assert row is not None, "the provisional policy was never recorded"
    assert "no están justificados" in row["reopen_condition"]


def test_recording_the_policy_is_idempotent(tmp_path):
    conn = _base(tmp_path)
    assert record_policy_decision(conn) is False, "seeding already recorded it"
    n = conn.execute("SELECT COUNT(*) c FROM decision_record "
                     "WHERE title LIKE 'Política de confrontación%'").fetchone()["c"]
    assert n == 1


# ------------------------------------------------------------------ api ----

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


def test_the_api_returns_the_policy_alongside_the_verdict(api_client):
    """The threshold travels with the result, so a reader can argue with the
    policy instead of arguing with the conclusion."""
    body = api_client.get("/api/confrontations").json()
    assert body["policy"]["policy_version"].endswith("provisional")
    assert body["policy"]["index_threshold"] == (
        CONFRONTATION_POLICY_V0["index_threshold"])
    assert "confrontations" in body and "held_back" in body


def test_the_seeded_demo_reports_no_discrepancy(api_client):
    """In the demo scenario the person and the record agree, so the API must
    say so plainly rather than manufacture something to show."""
    assert api_client.get("/api/confrontations").json()["confrontations"] == []


def test_asking_for_confrontations_moves_nothing(api_client):
    before_state = api_client.get("/api/state").json()["seal"]
    before_chain = len(api_client.get("/api/chain").json()["entries"])
    api_client.get("/api/confrontations")
    assert api_client.get("/api/state").json()["seal"] == before_state
    assert len(api_client.get("/api/chain").json()["entries"]) == before_chain
