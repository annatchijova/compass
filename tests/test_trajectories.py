"""Trajectories (design doc §5, §7): vocational fit as verifiable
capability-requirements — no destiny percentages.

A trajectory is a set of required capabilities (each backed by a hypothesis).
The fit is a deterministic, per-requirement projection of the SEALED
hypotheses; discrimination between two trajectories points at the cheapest
open capability that separates them.
"""

from __future__ import annotations

import sqlite3

import pytest

from compass import domain, engine
from compass.db import (SCHEMA_VERSION, _migrate_to_v1, connect, ensure_schema,
                        open_db)


# --------------------------------------------------- schema migration ------

def test_schema_version_is_2():
    assert SCHEMA_VERSION == 2


def test_open_db_creates_trajectory_tables(tmp_path):
    conn = open_db(str(tmp_path / "t.db"))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"trajectory", "trajectory_requirement"} <= tables
    conn.close()


def test_v1_data_survives_migration_to_v2(tmp_path):
    """Data written under v1 must load under v2 (design doc §7: v1 data must
    load in v5). Build a v1 DB by hand, then let ensure_schema migrate it."""
    db = str(tmp_path / "legacy.db")
    conn = connect(db)
    conn.execute("PRAGMA journal_mode = WAL")
    with conn:
        _migrate_to_v1(conn)  # DB is now exactly schema v1
    assert conn.execute("SELECT value FROM meta WHERE key='schema_version'"
                        ).fetchone()["value"] == "1"
    with conn:
        conn.execute("INSERT INTO person (id, display_name, created_at) "
                     "VALUES (1, 'Legacy User', '2026-01-01T00:00:00')")

    ensure_schema(conn)  # migrate v1 -> v2

    assert conn.execute("SELECT value FROM meta WHERE key='schema_version'"
                        ).fetchone()["value"] == str(SCHEMA_VERSION)
    # old data intact
    assert conn.execute("SELECT display_name FROM person WHERE id=1"
                        ).fetchone()["display_name"] == "Legacy User"
    # new tables present
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"trajectory", "trajectory_requirement"} <= tables
    conn.close()


# ------------------------------------------------------- fit + domain ------

from compass import seed_demo, trajectories  # noqa: E402
from compass.audit_chain import verify_chain  # noqa: E402


@pytest.fixture
def scenario(tmp_path):
    """Seeded demo (h1 corroborated, h2 weakened) + a fresh latent h3."""
    conn = open_db(str(tmp_path / "s.db"))
    seed_demo.seed(conn)                       # h1=met, h2=against after recompute
    h3 = domain.hypothesis_add(conn, statement="A third, untested capability.",
                               origin="person")
    engine.recompute_all(conn)                 # h3 stays latent (no evidence)
    return conn, h3


def test_fit_projects_hypothesis_status_deterministically(scenario):
    conn, h3 = scenario
    tid = trajectories.trajectory_add(conn, name="Systems architect")
    trajectories.requirement_add(conn, trajectory_id=tid, hypothesis_id=1,
                                 label="Designs systems end to end")
    trajectories.requirement_add(conn, trajectory_id=tid, hypothesis_id=2,
                                 label="Not merely fast execution")
    trajectories.requirement_add(conn, trajectory_id=tid, hypothesis_id=h3,
                                 label="A third capability")
    fit = trajectories.trajectory_fit(conn, tid)
    by_hyp = {r["hypothesis_id"]: r["fit"] for r in fit["requirements"]}
    assert by_hyp[1] == "met"        # corroborated -> met
    assert by_hyp[2] == "against"    # weakened -> against
    assert by_hyp[h3] == "open"      # latent -> open
    assert fit["summary"] == {"met": 1, "supported": 0, "open": 1,
                              "against": 1, "discarded": 0, "total": 3}
    # NO percentage anywhere in the fit output.
    import json
    assert "%" not in json.dumps(fit)


def test_fit_is_insertion_order_invariant(scenario):
    """Metamorphic: the fit summary does not depend on requirement order."""
    conn, h3 = scenario
    t1 = trajectories.trajectory_add(conn, name="A")
    for hid, lab in [(1, "a"), (2, "b"), (h3, "c")]:
        trajectories.requirement_add(conn, trajectory_id=t1, hypothesis_id=hid, label=lab)
    t2 = trajectories.trajectory_add(conn, name="B")
    for hid, lab in [(h3, "c"), (2, "b"), (1, "a")]:  # reversed
        trajectories.requirement_add(conn, trajectory_id=t2, hypothesis_id=hid, label=lab)
    assert (trajectories.trajectory_fit(conn, t1)["summary"]
            == trajectories.trajectory_fit(conn, t2)["summary"])


def test_discrimination_points_at_the_cheapest_open_capability(scenario):
    conn, h3 = scenario
    h4 = domain.hypothesis_add(conn, statement="A fourth capability.",
                               origin="person")
    engine.recompute_all(conn)
    a = trajectories.trajectory_add(conn, name="Path A")
    trajectories.requirement_add(conn, trajectory_id=a, hypothesis_id=1, label="shared")
    trajectories.requirement_add(conn, trajectory_id=a, hypothesis_id=h3, label="only A")
    b = trajectories.trajectory_add(conn, name="Path B")
    trajectories.requirement_add(conn, trajectory_id=b, hypothesis_id=1, label="shared")
    trajectories.requirement_add(conn, trajectory_id=b, hypothesis_id=h4, label="only B")

    d = trajectories.discriminating_requirements(conn, a, b)
    assert d["shared_requirements"] == [1]
    distinguishing_ids = {x["hypothesis_id"] for x in d["distinguishing"]}
    assert distinguishing_ids == {h3, h4}          # the two open, unique reqs
    assert 1 not in distinguishing_ids             # shared (and met) never distinguishes
    # cheapest first: both latent (index 0), tie broken by lower hypothesis id
    assert d["suggested_experiment_target"]["hypothesis_id"] == min(h3, h4)


def test_requirement_add_validates_and_dedups(scenario):
    conn, _ = scenario
    tid = trajectories.trajectory_add(conn, name="T")
    with pytest.raises(trajectories.TrajectoryError):
        trajectories.requirement_add(conn, trajectory_id=tid,
                                     hypothesis_id=999, label="missing hyp")
    with pytest.raises(trajectories.TrajectoryError):
        trajectories.requirement_add(conn, trajectory_id=999,
                                     hypothesis_id=1, label="missing traj")
    trajectories.requirement_add(conn, trajectory_id=tid, hypothesis_id=1, label="ok")
    with pytest.raises(trajectories.TrajectoryError):
        trajectories.requirement_add(conn, trajectory_id=tid, hypothesis_id=1,
                                     label="dup")


def test_trajectory_writes_audit_chain(scenario):
    conn, _ = scenario
    trajectories.trajectory_add(conn, name="Chained")
    rep = verify_chain(conn)
    assert rep.linkage_ok and rep.integrity_ok


def test_api_trajectories_cycle(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPASS_DATA_DIR", str(tmp_path / "tdata"))
    monkeypatch.setenv("COMPASS_BACKEND", "demo")
    monkeypatch.delenv("COMPASS_GCS_BUCKET", raising=False)
    import importlib

    from compass import storage as storage_module
    importlib.reload(storage_module)
    from compass import api as api_module
    importlib.reload(api_module)
    from fastapi.testclient import TestClient

    with TestClient(api_module.app) as c:  # seeds demo (h1 met, h2 against)
        tid = c.post("/api/trajectories", json={"name": "Systems architect"}
                     ).json()["trajectory_id"]
        c.post(f"/api/trajectories/{tid}/requirements",
               json={"hypothesis_id": 1, "label": "Designs end to end"})
        fit = c.get(f"/api/trajectories/{tid}/fit").json()
        assert fit["summary"]["met"] == 1
        assert [t["id"] for t in c.get("/api/trajectories").json()["trajectories"]] == [tid]
        # duplicate requirement -> 400 at the boundary
        dup = c.post(f"/api/trajectories/{tid}/requirements",
                     json={"hypothesis_id": 1, "label": "again"})
        assert dup.status_code == 400
