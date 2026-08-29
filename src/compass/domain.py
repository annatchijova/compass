"""Operaciones de dominio de COMPASS: evidencia, hipótesis y el ciclo de
experimentos. Cada operación lógica escribe su fila de dominio Y su
entrada en la cadena de auditoría dentro de la misma transacción: caen o
persisten juntas.

Reglas que este módulo hace cumplir:
- Solo lo validado por la persona cuenta (el engine filtra validated=1);
  los candidatos propuestos por el extractor nacen validated=0.
- Borrar es borrar: el tombstone vacía el contenido y lo saca del
  cálculo; el hueco queda visible y honesto en la cadena.
- Descartar y reactivar hipótesis es potestad exclusiva de la persona.
- Completar un experimento exige declarar cuál de los criterios
  PREREGISTRADOS se cumplió, y genera la evidencia experiment_result
  correspondiente (supports si se cumplió el de éxito, contradicts si el
  de fracaso, ninguna si fue inconcluso) en el mismo acto.
"""

from __future__ import annotations

import json
import sqlite3

from .audit_chain import append
from .canonicalize import sha256_utf8
from .db import EVIDENCE_TYPES, OBSERVATION_METRICS, atomic, utc_now_iso


class DomainError(ValueError):
    pass


def _dump(content: dict) -> str:
    return json.dumps(content, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def _exists(conn: sqlite3.Connection, table: str, row_id: int) -> bool:
    return conn.execute(
        f"SELECT 1 FROM {table} WHERE id = ?", (row_id,)
    ).fetchone() is not None


# ------------------------------------------------------------------ person --

def person_set(conn: sqlite3.Connection, display_name: str) -> None:
    if not display_name.strip():
        raise DomainError("display_name vacío")
    with atomic(conn):
        conn.execute(
            "INSERT INTO person (id, display_name, created_at) VALUES (1, ?, ?) "
            "ON CONFLICT (id) DO UPDATE SET display_name = excluded.display_name",
            (display_name, utc_now_iso()),
        )
        append(conn, op="person_set", payload={"display_name": display_name})


# ---------------------------------------------------------------- evidence --

def evidence_add(
    conn: sqlite3.Connection,
    *,
    evidence_type: str,
    source: str,
    content: dict,
    validated: bool,
) -> int:
    """Registra evidencia. La que la persona ingresa directamente nace
    validada; los candidatos del extractor nacen validated=False y
    esperan su validación explícita."""
    if evidence_type not in EVIDENCE_TYPES:
        raise DomainError(f"evidence_type inválido: {evidence_type!r}")
    if not isinstance(content, dict) or not content:
        raise DomainError("content debe ser un dict no vacío")
    text = _dump(content)
    chash = sha256_utf8(text)
    now = utc_now_iso()
    with atomic(conn):
        cur = conn.execute(
            "INSERT INTO evidence (evidence_type, source, content, content_hash, "
            "validated, validated_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (evidence_type, source, text, chash,
             int(validated), now if validated else None, now),
        )
        eid = cur.lastrowid
        append(conn, op="evidence_added",
               payload={"evidence_id": eid, "evidence_type": evidence_type,
                        "source": source, "validated": validated},
               content_hashes=[chash])
    return eid


def evidence_validate(conn: sqlite3.Connection, evidence_id: int) -> None:
    with atomic(conn):
        row = conn.execute(
            "SELECT validated, deleted, content_hash FROM evidence WHERE id = ?",
            (evidence_id,),
        ).fetchone()
        if row is None:
            raise DomainError(f"evidence id={evidence_id} no existe")
        if row["deleted"]:
            raise DomainError(f"evidence id={evidence_id} fue borrada (tombstone)")
        if row["validated"]:
            raise DomainError(f"evidence id={evidence_id} ya estaba validada")
        conn.execute(
            "UPDATE evidence SET validated = 1, validated_at = ? WHERE id = ?",
            (utc_now_iso(), evidence_id),
        )
        append(conn, op="evidence_validated",
               payload={"evidence_id": evidence_id},
               content_hashes=[row["content_hash"]])


def evidence_tombstone(conn: sqlite3.Connection, evidence_id: int, reason: str) -> None:
    """Borrado honesto: el contenido se va, el hueco queda declarado.

    La evidencia borrada deja de contar para el engine. El chain registra
    QUE se borró (y por qué), nunca lo borrado.
    """
    if not reason.strip():
        raise DomainError("el borrado exige una razón declarada")
    with atomic(conn):
        row = conn.execute(
            "SELECT deleted FROM evidence WHERE id = ?", (evidence_id,)
        ).fetchone()
        if row is None:
            raise DomainError(f"evidence id={evidence_id} no existe")
        if row["deleted"]:
            raise DomainError(f"evidence id={evidence_id} ya era un tombstone")
        conn.execute(
            "UPDATE evidence SET content = NULL, deleted = 1, deleted_at = ? "
            "WHERE id = ?",
            (utc_now_iso(), evidence_id),
        )
        append(conn, op="evidence_tombstoned",
               payload={"evidence_id": evidence_id, "reason": reason})


def evidence_link(
    conn: sqlite3.Connection,
    *,
    hypothesis_id: int,
    evidence_id: int,
    direction: str,
) -> None:
    if direction not in ("supports", "contradicts"):
        raise DomainError(f"direction inválida: {direction!r}")
    with atomic(conn):
        if not _exists(conn, "hypothesis", hypothesis_id):
            raise DomainError(f"hypothesis id={hypothesis_id} no existe")
        if not _exists(conn, "evidence", evidence_id):
            raise DomainError(f"evidence id={evidence_id} no existe")
        conn.execute(
            "INSERT INTO hypothesis_evidence (hypothesis_id, evidence_id, "
            "direction) VALUES (?, ?, ?)",
            (hypothesis_id, evidence_id, direction),
        )
        append(conn, op="evidence_linked",
               payload={"hypothesis_id": hypothesis_id,
                        "evidence_id": evidence_id, "direction": direction})


# -------------------------------------------------------------- hypothesis --

def hypothesis_add(
    conn: sqlite3.Connection, *, statement: str, origin: str
) -> int:
    if origin not in ("person", "llm_abductor"):
        raise DomainError(f"origin inválido: {origin!r}")
    if not statement.strip():
        raise DomainError("statement vacío")
    with atomic(conn):
        cur = conn.execute(
            "INSERT INTO hypothesis (statement, origin, created_at) "
            "VALUES (?, ?, ?)",
            (statement, origin, utc_now_iso()),
        )
        hid = cur.lastrowid
        append(conn, op="hypothesis_added",
               payload={"hypothesis_id": hid, "statement": statement,
                        "origin": origin})
    return hid


def hypothesis_discard(conn: sqlite3.Connection, hypothesis_id: int,
                       reason: str) -> None:
    """Descartar es decisión de la persona; el engine jamás lo hace."""
    if not reason.strip():
        raise DomainError("descartar exige una razón declarada")
    with atomic(conn):
        if not _exists(conn, "hypothesis", hypothesis_id):
            raise DomainError(f"hypothesis id={hypothesis_id} no existe")
        conn.execute(
            "UPDATE hypothesis SET status = 'descartada' WHERE id = ?",
            (hypothesis_id,),
        )
        append(conn, op="hypothesis_discarded",
               payload={"hypothesis_id": hypothesis_id, "reason": reason})


def hypothesis_reactivate(conn: sqlite3.Connection, hypothesis_id: int) -> None:
    """Vuelve a 'latente'; el próximo recompute la reubica por evidencia."""
    with atomic(conn):
        row = conn.execute(
            "SELECT status FROM hypothesis WHERE id = ?", (hypothesis_id,)
        ).fetchone()
        if row is None:
            raise DomainError(f"hypothesis id={hypothesis_id} no existe")
        if row["status"] != "descartada":
            raise DomainError("solo se reactiva una hipótesis descartada")
        conn.execute(
            "UPDATE hypothesis SET status = 'latente' WHERE id = ?",
            (hypothesis_id,),
        )
        append(conn, op="hypothesis_reactivated",
               payload={"hypothesis_id": hypothesis_id})


# -------------------------------------------------------------- experiment --

def experiment_preregister(
    conn: sqlite3.Connection,
    *,
    hypothesis_id: int,
    design: str,
    success_criterion: str,
    failure_criterion: str,
    rival_hypothesis_id: int | None = None,
    duration: str | None = None,
) -> int:
    """El preregistro es el experimento: sin criterio de fracaso escrito
    ANTES de ejecutar, no hay experimento (el esquema además lo fuerza)."""
    for name, v in (("design", design), ("success_criterion", success_criterion),
                    ("failure_criterion", failure_criterion)):
        if not v.strip():
            raise DomainError(f"{name} vacío: el preregistro es obligatorio")
    with atomic(conn):
        if not _exists(conn, "hypothesis", hypothesis_id):
            raise DomainError(f"hypothesis id={hypothesis_id} no existe")
        cur = conn.execute(
            "INSERT INTO experiment (hypothesis_id, design, success_criterion, "
            "failure_criterion, rival_hypothesis_id, duration, preregistered_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (hypothesis_id, design, success_criterion, failure_criterion,
             rival_hypothesis_id, duration, utc_now_iso()),
        )
        xid = cur.lastrowid
        append(conn, op="experiment_preregistered",
               payload={"experiment_id": xid, "hypothesis_id": hypothesis_id,
                        "design": design, "success_criterion": success_criterion,
                        "failure_criterion": failure_criterion,
                        "rival_hypothesis_id": rival_hypothesis_id})
    return xid


def experiment_start(conn: sqlite3.Connection, experiment_id: int) -> None:
    _transition(conn, experiment_id, desde=("preregistrado",), hacia="en_curso",
                op="experiment_started")


def experiment_abandon(conn: sqlite3.Connection, experiment_id: int,
                       reason: str) -> None:
    if not reason.strip():
        raise DomainError("abandonar exige una razón declarada")
    _transition(conn, experiment_id, desde=("preregistrado", "en_curso"),
                hacia="abandonado", op="experiment_abandoned",
                extra={"reason": reason})


def _transition(conn, experiment_id, *, desde, hacia, op, extra=None):
    with atomic(conn):
        row = conn.execute(
            "SELECT status FROM experiment WHERE id = ?", (experiment_id,)
        ).fetchone()
        if row is None:
            raise DomainError(f"experiment id={experiment_id} no existe")
        if row["status"] not in desde:
            raise DomainError(
                f"transición inválida: {row['status']} -> {hacia}"
            )
        conn.execute(
            "UPDATE experiment SET status = ? WHERE id = ?", (hacia, experiment_id)
        )
        payload = {"experiment_id": experiment_id}
        payload.update(extra or {})
        append(conn, op=op, payload=payload)


OUTCOMES = ("exito", "fracaso", "inconcluso")


def experiment_complete(
    conn: sqlite3.Connection,
    *,
    experiment_id: int,
    outcome: str,
    notes: str = "",
) -> int | None:
    """Cierra el experimento contra sus criterios PREREGISTRADOS.

    outcome declara cuál criterio se cumplió: 'exito' (el de éxito),
    'fracaso' (el de fracaso) o 'inconcluso'. Genera y vincula la
    evidencia experiment_result correspondiente en la misma transacción
    (supports/contradicts); un resultado inconcluso no genera evidencia:
    no discriminó nada. Devuelve el id de la evidencia creada o None.
    """
    if outcome not in OUTCOMES:
        raise DomainError(f"outcome inválido: {outcome!r}; opciones: {OUTCOMES}")
    with atomic(conn):
        row = conn.execute(
            "SELECT hypothesis_id, status, design, success_criterion, "
            "failure_criterion FROM experiment WHERE id = ?",
            (experiment_id,),
        ).fetchone()
        if row is None:
            raise DomainError(f"experiment id={experiment_id} no existe")
        if row["status"] not in ("preregistrado", "en_curso"):
            raise DomainError(f"el experimento está {row['status']}, no se completa")
        conn.execute(
            "UPDATE experiment SET status = 'completado', completed_at = ? "
            "WHERE id = ?",
            (utc_now_iso(), experiment_id),
        )
        append(conn, op="experiment_completed",
               payload={"experiment_id": experiment_id, "outcome": outcome,
                        "notes": notes})
        if outcome == "inconcluso":
            return None
        criterio = (row["success_criterion"] if outcome == "exito"
                    else row["failure_criterion"])
        eid = evidence_add(
            conn,
            evidence_type="experiment_result",
            source=f"experiment:{experiment_id}",
            content={"experiment_id": experiment_id, "outcome": outcome,
                     "criterio_cumplido": criterio, "notes": notes},
            validated=True,  # la completa la persona: la validación es el acto
        )
        evidence_link(
            conn,
            hypothesis_id=row["hypothesis_id"],
            evidence_id=eid,
            direction="supports" if outcome == "exito" else "contradicts",
        )
        return eid


def observation_add(
    conn: sqlite3.Connection, *, experiment_id: int, metric: str, value: str
) -> int:
    if metric not in OBSERVATION_METRICS:
        raise DomainError(
            f"métrica inválida: {metric!r}; solo lo medible sin instrumentación "
            f"mágica: {OBSERVATION_METRICS}"
        )
    if not value.strip():
        raise DomainError("value vacío")
    with atomic(conn):
        if not _exists(conn, "experiment", experiment_id):
            raise DomainError(f"experiment id={experiment_id} no existe")
        cur = conn.execute(
            "INSERT INTO observation (experiment_id, metric, value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (experiment_id, metric, value, utc_now_iso()),
        )
        append(conn, op="observation_added",
               payload={"experiment_id": experiment_id, "metric": metric,
                        "value": value})
    return cur.lastrowid


def reflection_add(
    conn: sqlite3.Connection, *, experiment_id: int, question: str, answer: str
) -> int:
    if not question.strip() or not answer.strip():
        raise DomainError("question y answer no pueden estar vacías")
    with atomic(conn):
        if not _exists(conn, "experiment", experiment_id):
            raise DomainError(f"experiment id={experiment_id} no existe")
        cur = conn.execute(
            "INSERT INTO reflection (experiment_id, question, answer, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (experiment_id, question, answer, utc_now_iso()),
        )
        append(conn, op="reflection_added",
               payload={"experiment_id": experiment_id,
                        "question_hash": sha256_utf8(question),
                        "answer_hash": sha256_utf8(answer)})
    return cur.lastrowid
