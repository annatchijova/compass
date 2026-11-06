"""Regresiones de Red Team Round 2 (docs/RED_TEAM_ROUND2.md): R2-1 y R2-6.

Cada arreglo se prueba con su control: tiene que cerrar el camino reportado
sin cerrar el legítimo.
"""

from __future__ import annotations

import importlib
import sqlite3

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

OWN = {"X-Compass-User": "u-r2fixes0001"}


@pytest.fixture
def api_module(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPASS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("COMPASS_BACKEND", "demo")
    monkeypatch.delenv("COMPASS_GCS_BUCKET", raising=False)
    from compass import storage as storage_module
    importlib.reload(storage_module)
    from compass import api
    importlib.reload(api)
    return api


@pytest.fixture
def client(api_module):
    with TestClient(api_module.app) as c:
        yield c


def _hyp(c, statement):
    return c.post("/api/hypotheses", json={"statement": statement},
                  headers=OWN).json()["hypothesis_id"]


def _evidence(c, etype, text):
    return c.post("/api/evidence", json={"evidence_type": etype, "source": "t",
                                         "content": {"t": text}}, headers=OWN)


def _link(c, hid, eid):
    r = c.post("/api/link", json={"hypothesis_id": hid, "evidence_id": eid,
                                  "direction": "supports"}, headers=OWN)
    assert r.status_code == 200, r.text


def _status(c, hid):
    rec = c.post("/api/recompute", headers=OWN).json()
    return next(r for r in rec["results"] if r["hypothesis_id"] == hid)


# ------------------------------------------------------------------ R2-1 ----

@pytest.mark.parametrize("etype", ["outcome_external", "experiment_result"])
def test_r21_api_rejects_gate_types(client, etype):
    r = _evidence(client, etype, "declared by the client")
    assert r.status_code == 400, r.text
    assert etype in r.json()["detail"]


def test_r21_other_types_still_accepted(client):
    """Control: el resto de los tipos sigue entrando por la API."""
    for etype in ("self_report", "narrative_extracted", "behavioral"):
        assert _evidence(client, etype, etype).status_code == 200


def test_r21_real_experiment_still_corroborates(client):
    """Control del arreglo: el camino legítimo (experimento preregistrado y
    completado con éxito) sigue abriendo la puerta de corroboración."""
    hid = _hyp(client, "capability under a real experiment")
    xid = client.post("/api/experiments", json={
        "hypothesis_id": hid, "design": "d", "success_criterion": "s",
        "failure_criterion": "f"}, headers=OWN).json()["experiment_id"]
    done = client.post(f"/api/experiments/{xid}/complete",
                       json={"outcome": "exito"}, headers=OWN)
    assert done.status_code == 200, done.text
    for i in range(12):
        _link(client, hid, _evidence(client, "behavioral", f"b{i}").json()["evidence_id"])
    res = _status(client, hid)
    assert res["index"] >= 600
    assert res["status"] == "corroborada"


def test_r21_same_index_without_experiment_stays_activa(client):
    """Mismo índice, sin experimento: sin un tipo discriminante declarable a
    mano, el volumen solo no corroba."""
    hid = _hyp(client, "capability with volume only")
    for i in range(19):
        _link(client, hid, _evidence(client, "self_report", f"s{i}").json()["evidence_id"])
    res = _status(client, hid)
    assert res["index"] >= 600
    assert res["status"] == "activa"


def test_r21_domain_function_enforces_the_rule(tmp_path):
    """La regla vive en domain, no solo en la ruta: el CLI usa la misma."""
    from compass import domain, engine
    from compass.db import open_db

    conn = open_db(str(tmp_path / "c.db"))
    engine.seed_default_config(conn)
    with pytest.raises(domain.DomainError):
        domain.evidence_add_by_person(
            conn, evidence_type="outcome_external", source="t",
            content={"t": "x"}, validated=True)
    eid = domain.evidence_add_by_person(
        conn, evidence_type="behavioral", source="t",
        content={"t": "x"}, validated=True)
    assert isinstance(eid, int)


# ------------------------------------------------------------------ R2-6 ----

def _demo_live_evidence(c):
    return [e["id"] for e in c.get("/api/evidence").json()["evidence"]
            if not e["deleted"]]


def test_r26_write_without_header_is_forbidden(client):
    before = _demo_live_evidence(client)
    r = client.post(f"/api/evidence/{before[0]}/forget", json={"reason": "x"})
    assert r.status_code == 403, r.text
    assert _demo_live_evidence(client) == before


def test_r26_explicit_demo_header_is_forbidden_too(client):
    r = client.post("/api/hypotheses", json={"statement": "x"},
                    headers={"X-Compass-User": "demo"})
    assert r.status_code == 403


def test_r26_own_compass_still_writable(client):
    """Control: la misma escritura con un id propio funciona y no toca la
    vitrina."""
    before = _demo_live_evidence(client)
    r = client.post(f"/api/evidence/{before[0]}/forget", json={"reason": "x"},
                    headers=OWN)
    assert r.status_code == 200, r.text
    assert _demo_live_evidence(client) == before


def test_r26_showcase_still_readable(client):
    assert client.get("/api/state").status_code == 200
    assert client.get("/api/chain").json()["linkage_ok"] is True
    assert client.get("/health").json()["chain_integrity_ok"] is True


def test_r26_showcase_connection_fails_closed(api_module, client):
    """Capa estructural: aunque una ruta futura olvide declarar write=True, la
    conexión de la vitrina no acepta escrituras."""
    with api_module._db("demo") as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE person SET display_name = 'x' WHERE id = 1")
