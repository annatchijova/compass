"""Vista COMPASS: el estado actual, sellado, y UN único siguiente paso.

Orden inviolable del flujo de narración (llm-out-of-the-loop):

    estado -> seal -> resumen comprimido de solo lectura -> narrador

El seal se computa ANTES de invocar cualquier modelo; el narrador recibe
un resumen comprimido, no el estado interno completo; la prosa se
registra JUNTO al seal (hash de la prosa en la cadena), nunca dentro de
él. Si cambiar de backend narrador pudiera cambiar un número, la
arquitectura está rota — ese es el test.

El "siguiente paso" es una REGLA determinística explícita (v0), no una
opinión. Reglas, en orden; la primera que aplica gana; los desempates
son por antigüedad (menor id):

    1. Hay experimento en_curso        -> registrar observaciones y cerrarlo.
    2. Hay experimento preregistrado   -> ejecutarlo.
    3. Hay evidencia sin validar       -> validarla o rechazarla.
    4. Hay hipótesis activa/debilitada
       sin experimento completado      -> diseñar un experimento para la de
                                          menor índice (menos discriminada).
    5. Nada de lo anterior             -> ABSTAIN explícito: registrar
                                          evidencia o una hipótesis.

Un ABSTAIN es un veredicto válido; un modelo decidiendo el caso borde en
silencio, no.
"""

from __future__ import annotations

import sqlite3

from .audit_chain import append
from .canonicalize import seal, sha256_utf8
from .db import atomic


def next_step(conn: sqlite3.Connection) -> dict:
    """Aplica las reglas 1-5 documentadas arriba. Determinístico."""
    en_curso = conn.execute(
        "SELECT id, design FROM experiment WHERE status = 'en_curso' "
        "ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if en_curso:
        return {"kind": "completar_experimento",
                "experiment_id": en_curso["id"],
                "detail": ("Registrá observaciones y cerrá el experimento "
                           f"#{en_curso['id']} contra sus criterios "
                           "preregistrados.")}
    prereg = conn.execute(
        "SELECT id FROM experiment WHERE status = 'preregistrado' "
        "ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if prereg:
        return {"kind": "ejecutar_experimento",
                "experiment_id": prereg["id"],
                "detail": f"Ejecutá el experimento #{prereg['id']} ya preregistrado."}
    pendientes = conn.execute(
        "SELECT COUNT(*) AS n FROM evidence WHERE validated = 0 AND deleted = 0"
    ).fetchone()["n"]
    if pendientes:
        return {"kind": "validar_evidencia",
                "count": pendientes,
                "detail": (f"Hay {pendientes} candidato(s) de evidencia sin "
                           "validar: revisalos, editalos o rechazalos.")}
    sin_experimento = conn.execute(
        "SELECT h.id, h.statement, h.index_value FROM hypothesis h "
        "WHERE h.status IN ('activa', 'debilitada') AND NOT EXISTS ("
        "  SELECT 1 FROM experiment x WHERE x.hypothesis_id = h.id "
        "  AND x.status = 'completado') "
        "ORDER BY COALESCE(h.index_value, 0) ASC, h.id ASC LIMIT 1"
    ).fetchone()
    if sin_experimento:
        return {"kind": "diseñar_experimento",
                "hypothesis_id": sin_experimento["id"],
                "detail": ("Diseñá un experimento discriminante para la "
                           f"hipótesis #{sin_experimento['id']} "
                           f"({sin_experimento['statement']!r}): es la activa "
                           "con menos evidencia.")}
    return {"kind": "abstain",
            "detail": ("No hay siguiente paso computable con las reglas v0: "
                       "registrá evidencia o una hipótesis.")}


def compass_state(conn: sqlite3.Connection) -> dict:
    """Estado actual, determinístico y canonicalizable (sin floats).

    Muestra hipótesis no-latentes y no-descartadas con su índice;
    latentes y descartadas solo se cuentan: una hipótesis sin evidencia
    mínima no existe públicamente (design doc §3.2).
    """
    person = conn.execute(
        "SELECT display_name FROM person WHERE id = 1"
    ).fetchone()
    visibles = [
        {"id": r["id"], "statement": r["statement"], "status": r["status"],
         "index": r["index_value"], "engine_version": r["engine_version"]}
        for r in conn.execute(
            "SELECT id, statement, status, index_value, engine_version "
            "FROM hypothesis WHERE status IN "
            "('activa', 'corroborada', 'debilitada') "
            "ORDER BY COALESCE(index_value, 0) DESC, id ASC"
        )
    ]
    counts = {
        row["status"]: row["n"]
        for row in conn.execute(
            "SELECT status, COUNT(*) AS n FROM hypothesis GROUP BY status"
        )
    }
    experimentos = {
        row["status"]: row["n"]
        for row in conn.execute(
            "SELECT status, COUNT(*) AS n FROM experiment GROUP BY status"
        )
    }
    pendientes = conn.execute(
        "SELECT COUNT(*) AS n FROM evidence WHERE validated = 0 AND deleted = 0"
    ).fetchone()["n"]
    evidencia_viva = conn.execute(
        "SELECT COUNT(*) AS n FROM evidence WHERE validated = 1 AND deleted = 0"
    ).fetchone()["n"]
    return {
        "person": person["display_name"] if person else None,
        "hypotheses": visibles,
        "hypothesis_counts": counts,
        "experiment_counts": experimentos,
        "evidence_validated": evidencia_viva,
        "evidence_pending": pendientes,
        "next_step": next_step(conn),
    }


def sealed_state(conn: sqlite3.Connection) -> dict:
    """Computa el estado y lo sella. El seal existe antes que cualquier
    narrador."""
    state = compass_state(conn)
    return {"state": state, "seal": seal(state)}


_SUMMARY_KEYS = ("person", "top_hypotheses", "hypothesis_counts",
                 "experiment_counts", "evidence_validated",
                 "evidence_pending", "next_step", "state_seal")


def compressed_summary(sealed: dict) -> dict:
    """Resumen comprimido de SOLO LECTURA para el narrador.

    Deliberadamente menos que el estado completo: la decisión, los
    números de cabecera y las pocas contribuciones que vale la pena
    explicar. Cuanto menos material crudo recibe el modelo, menos puede
    "reinterpretar".
    """
    state = sealed["state"]
    return {
        "person": state["person"],
        "top_hypotheses": state["hypotheses"][:5],
        "hypothesis_counts": state["hypothesis_counts"],
        "experiment_counts": state["experiment_counts"],
        "evidence_validated": state["evidence_validated"],
        "evidence_pending": state["evidence_pending"],
        "next_step": state["next_step"],
        "state_seal": sealed["seal"],
    }


def narrate_compass(conn: sqlite3.Connection, narrator) -> dict:
    """Sella, resume, narra y registra. En ese orden, siempre.

    La prosa queda registrada por su hash JUNTO al seal del estado; el
    seal del estado no depende de la prosa: un verificador confirma el
    resultado sin confiar en las palabras que lo envuelven.
    """
    sealed = sealed_state(conn)            # 1. seal ANTES del modelo
    summary = compressed_summary(sealed)   # 2. vista comprimida, solo lectura
    prose = narrator.narrate(summary)      # 3. recién ahora habla el modelo
    with atomic(conn):
        append(conn, op="narrated",
               payload={"state_seal": sealed["seal"],
                        "prose_hash": sha256_utf8(prose)})
    return {"seal": sealed["seal"], "summary": summary, "prose": prose}
