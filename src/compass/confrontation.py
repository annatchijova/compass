"""Confrontación autopercepción vs. datos (design doc §5).

El momento más potente del concepto y el más riesgoso: decirle a alguien
"tu autoevaluación dice X; el registro muestra Y". Por eso está construido
con la restricción más dura del proyecto:

**Ningún modelo participa.** Ni decide si hay discrepancia, ni la redacta.
El motor determinístico evalúa las condiciones y devuelve DATOS —cuentas
por lado—; la interfaz los pone en una plantilla fija. Un LLM redactando
este texto podría, bajo presión narrativa, convertir una discrepancia en un
veredicto sobre quién es la persona, que es exactamente lo que §5 prohíbe.

Es una proyección de SOLO LECTURA sobre hipótesis ya selladas: no escribe,
no anexa a la cadena y no mueve ningún índice, igual que el fit vocacional.

--------------------------------------------------------------------------
POLÍTICA PROVISORIA v0 — design doc §9, decisión abierta
--------------------------------------------------------------------------
§5 fija las condiciones MÍNIMAS y no son negociables acá: índice alto,
evidencia de al menos tres tipos distintos, y formulación como discrepancia
y nunca como veredicto. Lo que §9 deja abierto —el umbral exacto, la
frecuencia y el tono— se resuelve acá con valores PROVISORIOS, puestos para
desbloquear la función, no medidos:

- `index_threshold = 600`. Se reusa el `corroboration_threshold` del engine
  v1 en vez de inventar un número nuevo: "índice alto" significa lo mismo
  que ya significaba en el resto del sistema.
- `min_distinct_types = 3`. Es la condición de §5, literal.
- `max_surfaced = 1`. Frecuencia: se muestra UNA por vez, siguiendo el
  principio del "único siguiente paso". Las demás se cuentan, no se ocultan.

Condición de reapertura: la primera vez que una persona real reciba una
confrontación y se registre si la leyó como discrepancia o como juicio.
Hasta entonces estos números no están justificados por nada.
"""

from __future__ import annotations

import sqlite3

# Las dos cuentas que se comparan. SELF es lo que la persona DICE de sí
# (su reporte y lo extraído de sus narrativas); RECORD es lo que quedó
# observado o medido. Un tipo nuevo de evidencia tiene que entrar
# explícitamente en uno de los dos lados: la partición se valida abajo
# contra EVIDENCE_TYPES para que agregar un tipo y olvidarse rompa fuerte.
SELF_TYPES = ("self_report", "narrative_extracted")
RECORD_TYPES = ("behavioral", "experiment_result", "outcome_external")

# PROVISORIO (§9). Ver el docstring del módulo.
CONFRONTATION_POLICY_V0 = {
    "policy_version": "confrontation-v0-provisional",
    "index_threshold": 600,
    "min_distinct_types": 3,
    "max_surfaced": 1,
}

# Clases de discrepancia. Describen QUÉ diverge, nunca qué significa.
KIND_RECORD_EXCEEDS_SELF = "record_exceeds_self"
KIND_SELF_EXCEEDS_RECORD = "self_exceeds_record"


class ConfrontationPolicyError(ValueError):
    """La partición de tipos no cubre exactamente los tipos que existen."""


def validate_partition(evidence_types: tuple[str, ...]) -> None:
    """Todo tipo de evidencia cae en SELF o en RECORD, y en uno solo.

    Control negativo vivo: si alguien agrega un tipo de evidencia y no
    decide de qué lado está, esto explota en vez de dejarlo fuera de la
    comparación en silencio (que sesgaría la confrontación por omisión).
    """
    partition = set(SELF_TYPES) | set(RECORD_TYPES)
    overlap = set(SELF_TYPES) & set(RECORD_TYPES)
    missing = set(evidence_types) - partition
    extra = partition - set(evidence_types)
    if overlap:
        raise ConfrontationPolicyError(
            f"tipos en ambos lados de la partición: {sorted(overlap)}")
    if missing:
        raise ConfrontationPolicyError(
            f"tipos de evidencia sin lado asignado: {sorted(missing)}")
    if extra:
        raise ConfrontationPolicyError(
            f"la partición nombra tipos que no existen: {sorted(extra)}")


def _tally(conn: sqlite3.Connection, hypothesis_id: int) -> dict:
    """Cuentas por lado y dirección sobre evidencia VALIDADA y vinculada.

    Mismo filtro que usa el motor (`validated = 1 AND deleted = 0`): la
    confrontación no puede apoyarse en nada que el índice no haya contado.
    """
    tally = {"self_supports": 0, "self_contradicts": 0,
             "record_supports": 0, "record_contradicts": 0}
    types_seen: set[str] = set()
    for row in conn.execute(
        "SELECT he.direction, e.evidence_type, COUNT(*) AS n "
        "FROM hypothesis_evidence he JOIN evidence e ON e.id = he.evidence_id "
        "WHERE he.hypothesis_id = ? AND e.validated = 1 AND e.deleted = 0 "
        "GROUP BY he.direction, e.evidence_type",
        (hypothesis_id,),
    ):
        types_seen.add(row["evidence_type"])
        side = "self" if row["evidence_type"] in SELF_TYPES else "record"
        key = f"{side}_{'supports' if row['direction'] == 'supports' else 'contradicts'}"
        tally[key] += row["n"]
    tally["distinct_types"] = len(types_seen)
    return tally


def _kind(tally: dict) -> str | None:
    """La discrepancia: las dos cuentas apuntan en direcciones opuestas.

    Si un lado no se pronuncia, NO hay discrepancia — hay silencio, que es
    otra cosa y no se confronta.
    """
    self_net_positive = tally["self_supports"] > tally["self_contradicts"]
    self_net_negative = tally["self_contradicts"] > tally["self_supports"]
    rec_net_positive = tally["record_supports"] > tally["record_contradicts"]
    rec_net_negative = tally["record_contradicts"] > tally["record_supports"]
    if self_net_negative and rec_net_positive:
        return KIND_RECORD_EXCEEDS_SELF
    if self_net_positive and rec_net_negative:
        return KIND_SELF_EXCEEDS_RECORD
    return None


def confrontations(conn: sqlite3.Connection, policy: dict | None = None) -> dict:
    """Discrepancias que cumplen TODAS las condiciones de §5.

    Devuelve datos, no prosa: por qué se disparó, con qué cuentas de cada
    lado, y la política con la que se evaluó, para que quien la lea pueda
    discutir el umbral en vez de discutir la conclusión. Determinístico:
    orden por índice descendente y luego por id.
    """
    pol = policy or CONFRONTATION_POLICY_V0
    found = []
    for row in conn.execute(
        "SELECT id, statement, status, index_value FROM hypothesis "
        "WHERE status != 'descartada' AND index_value IS NOT NULL "
        "ORDER BY index_value DESC, id ASC"
    ):
        if row["index_value"] < pol["index_threshold"]:
            continue
        tally = _tally(conn, row["id"])
        if tally["distinct_types"] < pol["min_distinct_types"]:
            continue
        kind = _kind(tally)
        if kind is None:
            continue
        found.append({
            "hypothesis_id": row["id"],
            "hypothesis_statement": row["statement"],
            "status": row["status"],
            "index": row["index_value"],
            "kind": kind,
            "self_supports": tally["self_supports"],
            "self_contradicts": tally["self_contradicts"],
            "record_supports": tally["record_supports"],
            "record_contradicts": tally["record_contradicts"],
            "distinct_types": tally["distinct_types"],
        })
    surfaced = found[: pol["max_surfaced"]]
    return {
        "confrontations": surfaced,
        "held_back": len(found) - len(surfaced),
        "policy": dict(pol),
        "note": "proyección de solo lectura sobre hipótesis ya selladas: "
                "no movió ningún índice ni anexó a la cadena",
    }


def record_policy_decision(conn: sqlite3.Connection) -> bool:
    """Deja asentada la política PROVISORIA y su condición de reapertura.

    Mismo trato que los pesos del engine: un valor sin justificar se
    registra como decisión abierta, con lo que la reabriría, en vez de
    quedar como constante muda en el código. Idempotente. La fila y la
    entrada de cadena caen o persisten juntas.
    """
    from .audit_chain import append
    from .db import atomic, utc_now_iso

    title = f"Política de confrontación {CONFRONTATION_POLICY_V0['policy_version']}"
    if conn.execute("SELECT 1 FROM decision_record WHERE title = ?",
                    (title,)).fetchone() is not None:
        return False
    with atomic(conn):
        now = utc_now_iso()
        conn.execute(
            "INSERT INTO decision_record (title, context, decision, alternatives, "
            "reopen_condition, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                title,
                "El design doc §5 fija las condiciones mínimas de la "
                "confrontación autopercepción/datos y deja el umbral, la "
                "frecuencia y el tono como decisión abierta (§9).",
                f"index_threshold={CONFRONTATION_POLICY_V0['index_threshold']} "
                f"(reusa el corroboration_threshold del engine v1), "
                f"min_distinct_types={CONFRONTATION_POLICY_V0['min_distinct_types']} "
                f"(condición literal de §5), "
                f"max_surfaced={CONFRONTATION_POLICY_V0['max_surfaced']} "
                f"(una por vez, como el único siguiente paso). "
                "El texto lo arma una plantilla fija: ningún modelo decide "
                "ni redacta la discrepancia.",
                "Dejar que el narrador la redacte: rechazado, un modelo bajo "
                "presión narrativa puede convertir una discrepancia en un "
                "veredicto sobre la persona, que es lo que §5 prohíbe. "
                "Inventar un umbral nuevo: rechazado, 'índice alto' ya tenía "
                "significado en el engine y cambiarlo acá lo haría ambiguo.",
                "La primera confrontación entregada a una persona real, "
                "registrando si la leyó como discrepancia o como juicio. "
                "Hasta entonces estos valores no están justificados por nada.",
                now,
            ),
        )
        append(conn, op="confrontation_policy_recorded",
               payload={"policy_version": CONFRONTATION_POLICY_V0["policy_version"],
                        "index_threshold": CONFRONTATION_POLICY_V0["index_threshold"],
                        "min_distinct_types": CONFRONTATION_POLICY_V0["min_distinct_types"],
                        "max_surfaced": CONFRONTATION_POLICY_V0["max_surfaced"]})
    return True
