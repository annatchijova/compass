"""COMPASS demonstration scenario, built ONLY from real domain operations
(nothing is injected into the database by hand).

It exists for two reasons:

1. The hackathon's hosted URL must not show an empty compass: on startup
   the API seeds this scenario if the database has no person.
2. It is honest dogfooding (design doc §8): "user zero: you". The scenario
   walks the full abductive cycle — evidence of several types, two rival
   hypotheses, one preregistered experiment closed against its criterion,
   and a sealed recompute — so the indices and the audit chain the UI shows
   are PRODUCED by the deterministic engine, not written as decoration.

Content is English-primary (the product's primary language); user-authored
records in a real deployment are whatever the person types.

Idempotent: if a person already exists, it does nothing.
"""

from __future__ import annotations

import sqlite3

from . import domain, engine


def is_seeded(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM person WHERE id = 1").fetchone() is not None


def seed(conn: sqlite3.Connection) -> dict:
    """Seed the user-zero scenario. Returns a summary.

    It seals nothing on its own beyond what the domain operations and the
    final recompute seal.
    """
    if is_seeded(conn):
        return {"seeded": False, "reason": "a person was already registered"}

    engine.seed_default_config(conn)
    domain.person_set(conn, "Anna (user zero)")

    # Two RIVAL hypotheses about one observed signal: the system holds both
    # alive until an experiment discriminates (design §3.4).
    h_design = domain.hypothesis_add(
        conn,
        statement="Has systems-design capability: closes end-to-end "
        "architectures unaided, not just writes functions.",
        origin="person",
    )
    h_execution = domain.hypothesis_add(
        conn,
        statement="The signal is explained by fast execution under a deadline, "
        "not by design: performs on someone else's scaffold, not designing "
        "her own.",
        origin="person",
    )

    # Evidence of several types. Contradicting evidence weighs more (anti-flattery).
    e_self = domain.evidence_add(
        conn, evidence_type="self_report", source="onboarding",
        content={"text": "I feel I understand whole systems, not just parts."},
        validated=True,
    )
    e_behav = domain.evidence_add(
        conn, evidence_type="behavioral", source="self-log",
        content={"text": "Returned on her own to redesign the engine three "
                 "nights in a row with no one asking.",
                 "metric": "spontaneous_return"},
        validated=True,
    )
    e_extern = domain.evidence_add(
        conn, evidence_type="outcome_external", source="upstream-merge",
        content={"text": "Architecture PR accepted and merged by external "
                 "maintainers (cel-go #1445)."},
        validated=True,
    )

    domain.evidence_link(conn, hypothesis_id=h_design, evidence_id=e_self,
                         direction="supports")
    domain.evidence_link(conn, hypothesis_id=h_design, evidence_id=e_behav,
                         direction="supports")
    domain.evidence_link(conn, hypothesis_id=h_design, evidence_id=e_extern,
                         direction="supports")
    # The same behaviour, read as the rival: supports the execution hypothesis.
    domain.evidence_link(conn, hypothesis_id=h_execution, evidence_id=e_self,
                         direction="contradicts")

    # A DISCRIMINATING experiment, preregistered with a failure criterion
    # written BEFORE running it (design §4). It separates design vs execution.
    xid = domain.experiment_preregister(
        conn,
        hypothesis_id=h_design,
        design="Design a new system's authority architecture from scratch "
        "(no external scaffold) and have a third party audit it.",
        success_criterion="An independent reviewer confirms the architecture "
        "closes on its own and holds its invariants under critique.",
        failure_criterion="The design depends on structure provided by someone "
        "else, or collapses at the reviewer's first counter-example.",
        rival_hypothesis_id=h_execution,
        duration="1 week",
    )
    domain.experiment_start(conn, xid)
    domain.observation_add(conn, experiment_id=xid, metric="tiempo_voluntario",
                           value="20+ hours, unprompted")
    domain.observation_add(conn, experiment_id=xid, metric="feedback_externo",
                           value="reviewer confirms architectural closure")
    # Close against the preregistered SUCCESS criterion: generates the
    # discriminating experiment_result evidence, linked supports, in one act.
    domain.experiment_complete(conn, experiment_id=xid, outcome="exito",
                               notes="The reviewer confirmed the closure; the "
                               "design did not depend on external scaffold.")
    domain.reflection_add(conn, experiment_id=xid,
                          question="What evidence would reopen this?",
                          answer="A self-authored design that collapses under a "
                          "competent reviewer in a new domain.")

    result = engine.recompute_all(conn)
    return {"seeded": True, "seal": result["seal"],
            "hypotheses": [h_design, h_execution],
            "results": result["results"]}
