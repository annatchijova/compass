"""Multi-agent team (ADK): a Companion orchestrator + specialists. More agents
must mean more PROPOSALS, never more authority — no agent may move a sealed
index. Locks the team composition and the authority boundary across the team.
"""

from __future__ import annotations

import pytest

pytest.importorskip("google.adk")

from compass.agent import agent as team  # noqa: E402


def _tool_names(agent) -> set:
    return {getattr(t, "__name__", type(t).__name__) for t in agent.tools}


def test_team_composition():
    root = team.root_agent
    assert root.name == "compass_companion"
    assert {s.name for s in root.sub_agents} == {"analyst", "activity_scout",
                                                 "reflector"}


def test_no_agent_can_move_a_sealed_index():
    """The whole point of many agents without becoming a horoscope: NONE gets a
    scoring lever. link_evidence (Red Team B') must not appear anywhere, and the
    only number-producing tool (recompute_indices) is a pure deterministic run
    that seals before returning — and lives only on the Companion."""
    root = team.root_agent
    everywhere = set()
    for ag in [root, *root.sub_agents]:
        everywhere |= _tool_names(ag)
    assert "link_evidence" not in everywhere
    # recompute is the only number producer, and only the Companion holds it
    assert "recompute_indices" in _tool_names(root)
    for sub in root.sub_agents:
        assert "recompute_indices" not in _tool_names(sub)


def test_specialists_are_propose_or_read_only():
    subs = {s.name: _tool_names(s) for s in team.root_agent.sub_agents}
    # analyst reads state + gaps; reflector asks; scout searches. None writes
    # to the ledger except the extractor path, which lives on the Companion.
    assert "get_compass_state" in subs["analyst"]
    assert "narrative_prompts" in subs["reflector"]
    for tools in subs.values():
        assert "extract_signals_from_narrative" not in tools  # Companion-only
        assert "preregister_experiment" not in tools
