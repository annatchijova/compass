"""O*NET occupations -> trajectories: 'what to dedicate yourself to' with hard,
evidence-based data. Adopting an occupation seeds candidate hypotheses; it
concludes nothing.
"""

from __future__ import annotations

import pytest

from compass import onet, trajectories
from compass.audit_chain import verify_chain
from compass.db import open_db


@pytest.fixture
def db(tmp_path):
    conn = open_db(str(tmp_path / "o.db"))
    yield conn
    conn.close()


def test_occupations_cover_the_riasec_space():
    codes = {o["riasec"][0] for o in onet.list_occupations()}
    # first letter of each occupation's RIASEC code — I,S,A,E present at least
    assert {"I", "S", "A", "E"} <= codes
    assert len(onet.list_occupations()) == len(onet.OCCUPATIONS)


def test_occupation_detail_is_bilingual_and_attributed():
    en = onet.occupation("15-2051.00", "en")
    es = onet.occupation("15-2051.00", "es")
    assert en["title"] == "Data Scientist" and es["title"] == "Científica de datos"
    assert en["requirements"] != es["requirements"]
    assert "CC BY 4.0" in en["attribution"] and "USDOL/ETA" in en["attribution"]
    with pytest.raises(onet.OccupationError):
        onet.occupation("00-0000.00")


def test_adopt_creates_trajectory_with_candidate_hypotheses(db):
    reqs = onet.occupation("15-2051.00", "es")["requirements"]
    out = onet.adopt_occupation(db, "15-2051.00", "es")
    # one hypothesis + one requirement per O*NET capability
    assert len(out["requirements"]) == len(reqs)
    fit = trajectories.trajectory_fit(db, out["trajectory_id"])
    assert fit["summary"]["total"] == len(reqs)
    # fresh hypotheses, no evidence yet -> all requirements are open
    assert fit["summary"]["open"] == len(reqs)
    # each requirement is backed by a real hypothesis row
    for r in fit["requirements"]:
        assert db.execute("SELECT 1 FROM hypothesis WHERE id=?",
                          (r["hypothesis_id"],)).fetchone() is not None


def test_adopt_is_chained_and_atomic(db):
    onet.adopt_occupation(db, "25-2021.00", "en")
    rep = verify_chain(db)
    assert rep.linkage_ok and rep.integrity_ok
    with pytest.raises(onet.OccupationError):
        onet.adopt_occupation(db, "99-9999.99")


def test_api_onet_adopt_cycle(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPASS_DATA_DIR", str(tmp_path / "odata"))
    monkeypatch.setenv("COMPASS_BACKEND", "demo")
    monkeypatch.delenv("COMPASS_GCS_BUCKET", raising=False)
    import importlib

    from compass import storage as storage_module
    importlib.reload(storage_module)
    from compass import api as api_module
    importlib.reload(api_module)
    from fastapi.testclient import TestClient

    with TestClient(api_module.app) as c:
        occ = c.get("/api/onet/occupations", params={"lang": "es"}).json()
        assert len(occ["occupations"]) == len(onet.OCCUPATIONS)
        code = occ["occupations"][0]["code"]
        adopted = c.post("/api/onet/adopt", json={"code": code, "lang": "es"}).json()
        tid = adopted["trajectory_id"]
        fit = c.get(f"/api/trajectories/{tid}/fit").json()
        assert fit["summary"]["total"] == len(adopted["requirements"])
