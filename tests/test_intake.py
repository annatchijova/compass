"""Intake vocacional (Big Five + RIASEC): the questionnaire seeds hypotheses,
it never concludes. Integer scoring, no norms, no percentages.
"""

from __future__ import annotations

import json

import pytest

from compass import intake
from compass.db import SCHEMA_VERSION, connect, ensure_schema, open_db
from compass.db import _migrate_to_v1, _migrate_to_v2


# --------------------------------------------------- schema migration ------

def test_schema_is_v3_with_assessment_tables(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"assessment", "assessment_response"} <= tables
    assert SCHEMA_VERSION >= 3
    conn.close()


def test_v2_data_survives_migration_to_v3(tmp_path):
    """A v2 DB (with trajectory tables) migrates to v3 with data intact."""
    db = str(tmp_path / "legacy2.db")
    conn = connect(db)
    conn.execute("PRAGMA journal_mode = WAL")
    with conn:
        _migrate_to_v1(conn)
        _migrate_to_v2(conn)
        conn.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
        conn.execute("INSERT INTO person (id, display_name, created_at) "
                     "VALUES (1, 'V2 User', '2026-01-01T00:00:00')")
        conn.execute("INSERT INTO trajectory (name, description, created_at) "
                     "VALUES ('Path', '', '2026-01-01T00:00:00')")
    ensure_schema(conn)
    assert conn.execute("SELECT value FROM meta WHERE key='schema_version'"
                        ).fetchone()["value"] == str(SCHEMA_VERSION)
    assert conn.execute("SELECT display_name FROM person WHERE id=1"
                        ).fetchone()["display_name"] == "V2 User"
    assert conn.execute("SELECT COUNT(*) c FROM trajectory").fetchone()["c"] == 1
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"assessment", "assessment_response"} <= tables
    conn.close()


# ------------------------------------------------------------- items -------

def test_items_are_bilingual_and_stable():
    en = intake.items("riasec", "en")
    es = intake.items("riasec", "es")
    assert len(en) == len(es) == len(intake.RIASEC_ITEMS)
    # same codes/dimensions, different text
    assert [i["code"] for i in en] == [i["code"] for i in es]
    assert en[0]["text"] != es[0]["text"]


# ------------------------------------------------------------- scoring -----

@pytest.fixture
def db(tmp_path):
    conn = open_db(str(tmp_path / "s.db"))
    yield conn
    conn.close()


def test_high_investigative_proposes_that_hypothesis(db):
    aid = intake.start_assessment(db, "riasec")
    # Max out Investigative (I1,I2), floor the rest.
    for it in intake.items("riasec", "en"):
        intake.submit_response(db, aid, it["code"],
                               5 if it["dimension"] == "I" else 1)
    sc = intake.score(db, aid)
    items = intake.items("riasec", "en")
    n_i = sum(1 for it in items if it["dimension"] == "I")
    n_r = sum(1 for it in items if it["dimension"] == "R")
    assert sc["dimensions"]["I"]["raw"] == 5 * n_i   # all I at 5, integer
    assert sc["dimensions"]["R"]["raw"] == 1 * n_r   # all R at 1
    props = intake.proposed_hypotheses(db, aid)
    dims = {p["dimension"] for p in props["proposals"]}
    assert "I" in dims and "R" not in dims
    inv = next(p for p in props["proposals"] if p["dimension"] == "I")
    assert "Investigativo" in inv["statement"]


def test_scoring_is_integer_and_has_no_percentage(db):
    aid = intake.start_assessment(db, "big_five")
    for it in intake.items("big_five", "en"):
        intake.submit_response(db, aid, it["code"], 4)
    out = json.dumps(intake.proposed_hypotheses(db, aid))
    assert "%" not in out and "percent" not in out.lower()
    for d in intake.score(db, aid)["dimensions"].values():
        assert isinstance(d["raw"], int)


def test_reverse_scored_items(db):
    """A reverse item at 5 contributes like a 1 (6-5)."""
    aid = intake.start_assessment(db, "big_five")
    intake.submit_response(db, aid, "E1", 5)  # E+, contributes 5
    intake.submit_response(db, aid, "E2", 5)  # E- reverse, contributes 1
    assert intake.score(db, aid)["dimensions"]["E"]["raw"] == 6


def test_response_validation(db):
    aid = intake.start_assessment(db, "riasec")
    with pytest.raises(intake.IntakeError):
        intake.submit_response(db, aid, "I1", 6)          # out of range
    with pytest.raises(intake.IntakeError):
        intake.submit_response(db, aid, "O1", 3)          # Openness code (big_five only) on riasec
    with pytest.raises(intake.IntakeError):
        intake.start_assessment(db, "mbti")               # invalid instrument


def test_register_proposal_creates_pending_candidate(db):
    aid = intake.start_assessment(db, "riasec")
    for it in intake.items("riasec", "en"):
        intake.submit_response(db, aid, it["code"],
                               5 if it["dimension"] == "I" else 1)
    out = intake.register_proposal(db, aid, "I")
    h = db.execute("SELECT statement, origin FROM hypothesis WHERE id=?",
                   (out["hypothesis_id"],)).fetchone()
    assert "Investigativo" in h["statement"]
    e = db.execute("SELECT evidence_type, source, validated FROM evidence WHERE id=?",
                   (out["evidence_id"],)).fetchone()
    # self_report (min weight), PENDING, provenance recorded in source
    assert e["evidence_type"] == "self_report" and e["validated"] == 0
    assert e["source"] == "intake:riasec"
    link = db.execute("SELECT direction FROM hypothesis_evidence "
                      "WHERE hypothesis_id=? AND evidence_id=?",
                      (out["hypothesis_id"], out["evidence_id"])).fetchone()
    assert link["direction"] == "supports"


def test_register_rejects_a_low_dimension(db):
    aid = intake.start_assessment(db, "riasec")
    for it in intake.items("riasec", "en"):
        intake.submit_response(db, aid, it["code"], 1)  # all low -> no proposals
    with pytest.raises(intake.IntakeError):
        intake.register_proposal(db, aid, "I")


def test_proposing_persists_nothing(db):
    """Intake proposes; it must not write hypotheses/evidence or move an index."""
    aid = intake.start_assessment(db, "riasec")
    for it in intake.items("riasec", "en"):
        intake.submit_response(db, aid, it["code"], 5)
    before_hyp = db.execute("SELECT COUNT(*) c FROM hypothesis").fetchone()["c"]
    before_ev = db.execute("SELECT COUNT(*) c FROM evidence").fetchone()["c"]
    intake.proposed_hypotheses(db, aid)
    assert db.execute("SELECT COUNT(*) c FROM hypothesis").fetchone()["c"] == before_hyp
    assert db.execute("SELECT COUNT(*) c FROM evidence").fetchone()["c"] == before_ev


def test_api_intake_cycle(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPASS_DATA_DIR", str(tmp_path / "idata"))
    monkeypatch.setenv("COMPASS_BACKEND", "demo")
    monkeypatch.delenv("COMPASS_GCS_BUCKET", raising=False)
    import importlib

    from compass import storage as storage_module
    importlib.reload(storage_module)
    from compass import api as api_module
    importlib.reload(api_module)
    from fastapi.testclient import TestClient

    with TestClient(api_module.app) as c:
        items = c.get("/api/intake/items", params={"instrument": "riasec"}).json()["items"]
        assert len(items) == len(intake.RIASEC_ITEMS)
        aid = c.post("/api/intake/assessments", json={"instrument": "riasec"}
                     ).json()["assessment_id"]
        resp = [{"item_code": it["code"],
                 "value": 5 if it["dimension"] == "I" else 1} for it in items]
        c.post(f"/api/intake/assessments/{aid}/responses", json={"responses": resp})
        props = c.get(f"/api/intake/assessments/{aid}/proposals").json()["proposals"]
        assert any(p["dimension"] == "I" for p in props)
        reg = c.post(f"/api/intake/assessments/{aid}/register",
                     json={"dimension": "I"}).json()
        assert reg["hypothesis_id"] and reg["validated"] is False
