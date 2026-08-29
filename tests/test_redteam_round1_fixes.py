"""Regression tests for Red Team Round 1 (docs/RED_TEAM_ROUND1.md).

Each test is written to FAIL on the vulnerable state and PASS after the fix
(the red-team-auditing discipline: the test earns its keep by failing first).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
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
