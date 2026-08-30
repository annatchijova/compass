"""Narrative guide: scaffolding so no one stalls at a blank box. Two tiers
(easy on-ramp + deeper episodic), bilingual, one at a time."""

from __future__ import annotations

from compass import prompts


def test_two_tiers_easy_first():
    all_es = prompts.starter_prompts("es")
    easy = prompts.starter_prompts("es", "easy")
    deeper = prompts.starter_prompts("es", "deeper")
    assert len(all_es) == len(easy) + len(deeper) == len(prompts.STARTER_PROMPTS)
    assert easy and deeper
    # easy come first in the unfiltered list (the gentle door)
    assert all_es[0]["tier"] == "easy"
    assert all(p["tier"] in prompts.TIERS for p in all_es)


def test_codes_are_unique_and_bilingual():
    codes = [p["code"] for p in prompts.starter_prompts("en")]
    assert len(codes) == len(set(codes))  # no duplicate codes
    en = prompts.starter_prompts("en")
    es = prompts.starter_prompts("es")
    assert [p["code"] for p in en] == [p["code"] for p in es]
    assert en[0]["text"] != es[0]["text"]  # actually translated


def test_easy_prompts_are_short():
    # the easy tier must stay low-activation: short questions, not essays
    for p in prompts.starter_prompts("es", "easy"):
        assert len(p["text"]) <= 80, p["text"]
