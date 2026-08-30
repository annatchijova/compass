"""Regression tests for Red Team Round 1 (docs/RED_TEAM_ROUND1.md).

Each test is written to FAIL on the vulnerable state and PASS after the fix
(the red-team-auditing discipline: the test earns its keep by failing first).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

import pytest
from pathlib import Path

from compass import seed_demo
from compass.db import open_db

REPO = Path(__file__).resolve().parent.parent
VERIFIER = REPO / "tools" / "verify_chain.py"


def _seed(db: str) -> None:
    conn = open_db(db)
    seed_demo.seed(conn)
    conn.close()


def _run_verifier(db: str) -> int:
    return subprocess.run(
        [sys.executable, str(VERIFIER), db], capture_output=True, text=True
    ).returncode


# --------------------------------------------------------------- D1 --------

def test_d1_dual_column_content_forgery_is_detected(tmp_path):
    """FINDING D1: editing evidence.content AND evidence.content_hash together
    must be detected, because the verifier binds live content to the value
    SEALED IN THE CHAIN, not to the mutable evidence.content_hash column."""
    db = str(tmp_path / "d1.db")
    _seed(db)
    assert _run_verifier(db) == 0, "baseline must verify clean"

    forged = '{"text":"FORGED - never validated"}'
    new_hash = hashlib.sha256(forged.encode("utf-8")).hexdigest()
    conn = open_db(db)
    with conn:
        conn.execute(
            "UPDATE evidence SET content = ?, content_hash = ? WHERE id = 1",
            (forged, new_hash),
        )
    conn.close()

    # Vulnerable state returns 0 (VERIFICA); the fix must return 1 (breach).
    assert _run_verifier(db) == 1, (
        "dual-column content forgery must be detected against the sealed "
        "chain value, not the mutable column"
    )


def test_d1_single_column_edit_still_detected(tmp_path):
    """Guard: the fix must not regress single-column detection."""
    db = str(tmp_path / "d1b.db")
    _seed(db)
    conn = open_db(db)
    with conn:
        conn.execute("UPDATE evidence SET content = ? WHERE id = 1",
                     ('{"text":"edited"}',))
    conn.close()
    assert _run_verifier(db) == 1


def test_d1_clean_db_still_verifies(tmp_path):
    """Guard: a legitimate seeded DB must still verify after the fix."""
    db = str(tmp_path / "d1c.db")
    _seed(db)
    assert _run_verifier(db) == 0


# --------------------------------------------------------------- B' --------

def test_bprime_agent_has_no_scoring_authority():
    """FINDING B': the ADK agent must not be able to choose the evidence->
    hypothesis graph. `link_evidence` (with a caller-chosen supports/contradicts
    direction) let the model fix an arbitrary sealed index; linking is a human
    act, like validation. The tool must not be exposed to the agent."""
    import pytest
    pytest.importorskip("google.adk")
    from compass.agent import agent as agent_module

    tool_names = {getattr(t, "__name__", "") for t in agent_module.root_agent.tools}
    assert "link_evidence" not in tool_names, (
        "the agent must not choose the scoring graph (Red Team R1, B')"
    )
    # It keeps its propose/read/narrate tools.
    assert "get_compass_state" in tool_names
    assert "add_hypothesis" in tool_names


# --------------------------------------------------------------- A ---------

class _FixedBackend:
    def __init__(self, text: str):
        self._text = text

    def complete(self, system: str, user: str) -> str:
        return self._text


def test_a_narrator_rejects_percentage_prose():
    """FINDING A (partial fix): the index is an accumulation of evidence, NEVER
    a probability/percentage. The narrator must not present a percentage; prose
    that does is rejected at the boundary, fail-closed."""
    import pytest

    from compass.llm import LLMOutputError, Narrator

    for lying in ("Your design capability is 97 percent — essentially certain.",
                  "Confidence level: 50%.",
                  "Estás en un 80 por ciento de certeza."):
        with pytest.raises(LLMOutputError):
            Narrator(_FixedBackend(lying)).narrate({"state_seal": "x"})


def test_a_clean_prose_still_passes():
    from compass.llm import Narrator

    ok = ("Your design hypothesis is corroborated by a discriminating "
          "experiment; the rival execution hypothesis is weakened. The next "
          "step is to design an experiment for the hypothesis with least evidence.")
    assert Narrator(_FixedBackend(ok)).narrate({"state_seal": "x"}) == ok


# --------------------------------------------------------------- D2 --------

def test_d2_verify_content_binds_to_sealed_chain(tmp_path):
    """FINDING D2: the in-package path (used by the API) must also verify
    referenced content against the chain-sealed hash, so the dashboard badge
    can cover content — not only chain linkage/integrity."""
    from compass.audit_chain import verify_content

    db = str(tmp_path / "d2.db")
    _seed(db)
    conn = open_db(db)
    assert verify_content(conn).content_ok is True

    forged = '{"text":"FORGED"}'
    new_hash = hashlib.sha256(forged.encode("utf-8")).hexdigest()
    with conn:
        conn.execute("UPDATE evidence SET content = ?, content_hash = ? WHERE id = 1",
                     (forged, new_hash))
    rep = verify_content(conn)
    conn.close()
    assert rep.content_ok is False and rep.issues, (
        "in-package content verification must catch the dual-column forge"
    )


def test_d2_api_surfaces_content_ok(tmp_path, monkeypatch):
    """The dashboard's data source (/api/chain, /health) must report content
    integrity, not only chain linkage/integrity."""
    monkeypatch.setenv("COMPASS_DATA_DIR", str(tmp_path / "d2data"))
    monkeypatch.setenv("COMPASS_BACKEND", "demo")
    monkeypatch.delenv("COMPASS_GCS_BUCKET", raising=False)
    import importlib

    from compass import storage as storage_module
    importlib.reload(storage_module)
    from compass import api as api_module
    importlib.reload(api_module)
    from fastapi.testclient import TestClient

    with TestClient(api_module.app) as c:
        assert c.get("/api/chain").json()["content_ok"] is True
        assert c.get("/health").json()["chain_content_ok"] is True

        forged = '{"text":"FORGED"}'
        dbp = storage_module.local_path(storage_module.DEMO_UID)
        conn = open_db(dbp)
        with conn:
            conn.execute("UPDATE evidence SET content = ?, content_hash = ? WHERE id = 1",
                         (forged, hashlib.sha256(forged.encode("utf-8")).hexdigest()))
        conn.close()
        assert c.get("/api/chain").json()["content_ok"] is False


# --------------------------------------------------------------- C ---------

def test_c_state_surfaces_unlinked_coverage(tmp_path, monkeypatch):
    """FINDING C: anti-flattery is defeated by omission (unlinked contradicting
    evidence does not count). The state surfaces the unlinked count so the gap
    is visible; this changes no index (display-only, outside the seal)."""
    monkeypatch.setenv("COMPASS_DATA_DIR", str(tmp_path / "cdata"))
    monkeypatch.setenv("COMPASS_BACKEND", "demo")
    monkeypatch.delenv("COMPASS_GCS_BUCKET", raising=False)
    import importlib

    from compass import storage as storage_module
    importlib.reload(storage_module)
    from compass import api as api_module
    importlib.reload(api_module)
    from fastapi.testclient import TestClient

    with TestClient(api_module.app) as c:
        before = c.get("/api/state").json()
        base = before["coverage"]["validated_unlinked"]
        idx_before = {h["id"]: h["index"] for h in before["state"]["hypotheses"]}
        c.post("/api/evidence", json={"evidence_type": "self_report", "source": "t",
                                      "content": {"text": "unlinked"}, "validated": True})
        after = c.get("/api/state").json()
        assert after["coverage"]["validated_unlinked"] == base + 1
        # Unlinked evidence moves NO hypothesis index — that is exactly the
        # gap C names: it does not count until linked. Coverage surfaces it.
        idx_after = {h["id"]: h["index"] for h in after["state"]["hypotheses"]}
        assert idx_after == idx_before


# --------------------------------------------------------------- D3 --------

def _run_cli_verify(db: str) -> subprocess.CompletedProcess:
    """Run the in-package verifier exactly as a CLI-only user would."""
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}
    return subprocess.run(
        [sys.executable, "-m", "compass", "--db", db, "verify"],
        capture_output=True, text=True, env=env,
    )


def test_d3_cli_verify_covers_content_not_only_the_chain(tmp_path):
    """FINDING D3 (follow-on to D1/D2): `compass verify` reported only
    linkage + integrity, so a CLI-only user saw True/True on a database whose
    referenced content had been forged. Content is a THIRD signal and the CLI
    must report it and fail on it, like tools/verify_chain.py and /api/chain."""
    db = str(tmp_path / "d3.db")
    _seed(db)
    baseline = _run_cli_verify(db)
    assert baseline.returncode == 0, "baseline must verify clean"
    assert "contenido_ok" in baseline.stdout, (
        "the CLI must report content as its own signal, never collapse it "
        "into linkage/integrity"
    )

    forged = '{"text":"FORGED via the CLI blind spot"}'
    conn = open_db(db)
    with conn:
        conn.execute(
            "UPDATE evidence SET content = ?, content_hash = ? WHERE id = 1",
            (forged, hashlib.sha256(forged.encode("utf-8")).hexdigest()),
        )
    conn.close()

    # Vulnerable state exits 0 (linkage/integrity untouched); the fix exits 1.
    forged_run = _run_cli_verify(db)
    assert forged_run.returncode == 1, (
        "dual-column content forgery must make `compass verify` fail, not "
        "just the independent verifier"
    )
    assert "contenido_ok : False" in forged_run.stdout


def test_d3_cli_verify_keeps_the_three_signals_separate(tmp_path):
    """A clean base reports all three signals independently — the README
    invariant is that they are never collapsed into one boolean."""
    db = str(tmp_path / "d3clean.db")
    _seed(db)
    out = _run_cli_verify(db).stdout
    for signal in ("linkage_ok", "integrity_ok", "contenido_ok"):
        assert signal in out, f"{signal} must be reported on its own line"


def test_d3_agent_verify_tool_also_reports_content(tmp_path, monkeypatch):
    """The agent's own verifier had the same blind spot as the CLI: it read
    linkage and integrity only, so a forged evidence row looked clean to the
    Collaborative Partner. The agent has no scoring authority, but it must not
    report a healthy chain over tampered content either."""
    pytest.importorskip("google.adk")
    monkeypatch.setenv("COMPASS_DB", str(tmp_path / "agent.db"))
    import importlib

    from compass.agent import agent as agent_module
    importlib.reload(agent_module)

    _seed(str(tmp_path / "agent.db"))
    clean = agent_module.verify_audit_chain()
    assert clean["content_ok"] is True
    assert {"linkage_ok", "integrity_ok", "content_ok"} <= set(clean)

    forged = '{"text":"FORGED past the agent"}'
    conn = open_db(str(tmp_path / "agent.db"))
    with conn:
        conn.execute(
            "UPDATE evidence SET content = ?, content_hash = ? WHERE id = 1",
            (forged, hashlib.sha256(forged.encode("utf-8")).hexdigest()),
        )
    conn.close()

    broken = agent_module.verify_audit_chain()
    assert broken["content_ok"] is False, (
        "the agent reported a clean chain over forged content"
    )
    assert broken["issues"], "the breach must be listed, not just flagged"
