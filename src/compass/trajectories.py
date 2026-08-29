"""Trayectorias de COMPASS (design doc §5, §7): navegación vocacional
honesta — a qué dedicarse deja de ser un TIPO y pasa a ser un FIT entre
capacidades demostradas y lo que un camino requiere.

Una trayectoria es un conjunto de capacidades-requisito verificables. Cada
requisito referencia la hipótesis (capacidad) que exige. El fit se PROYECTA
determinísticamente del estado sellado de esas hipótesis: qué requisitos
tienen evidencia (met/supported), cuáles no (open), cuáles la evidencia
contradice (against). NUNCA un porcentaje de destino — solo estructura.

Discriminar entre dos trayectorias: encontrar las capacidades que las
separan y que todavía no están resueltas, y señalar la más barata de testear
(economía peirceana). El experimento sale de la maquinaria que ya existe.

Autoridad: las trayectorias y sus requisitos los define la PERSONA (o el
abductor los propone como candidatos, a validar). El fit no puede mover un
índice: solo lee hipótesis ya selladas. Nada de floats.
"""

from __future__ import annotations

import sqlite3

from .audit_chain import append
from .db import atomic, utc_now_iso


class TrajectoryError(ValueError):
    pass


# Estado de un requisito, función determinística del estado de su hipótesis.
_FIT_FROM_HYPOTHESIS = {
    "corroborada": "met",        # tiene evidencia discriminante a favor
    "activa": "supported",       # evidencia, aún no corroborada
    "latente": "open",           # sin evidencia mínima
    "debilitada": "against",     # la evidencia contradice
    "descartada": "discarded",   # la persona la rechazó
}

FIT_STATES = ("met", "supported", "open", "against", "discarded")
# "resuelto": el requisito ya no discrimina (o está cerrado a favor/en contra).
_RESOLVED = {"met", "against", "discarded"}


def _exists(conn: sqlite3.Connection, table: str, row_id: int) -> bool:
    return conn.execute(
        f"SELECT 1 FROM {table} WHERE id = ?", (row_id,)
    ).fetchone() is not None


# ------------------------------------------------------------- escritura ----

def trajectory_add(conn: sqlite3.Connection, *, name: str,
                   description: str = "") -> int:
    if not name.strip():
        raise TrajectoryError("name vacío")
    with atomic(conn):
        cur = conn.execute(
            "INSERT INTO trajectory (name, description, created_at) "
            "VALUES (?, ?, ?)",
            (name, description, utc_now_iso()),
        )
        tid = cur.lastrowid
        append(conn, op="trajectory_added",
               payload={"trajectory_id": tid, "name": name})
    return tid


def requirement_add(conn: sqlite3.Connection, *, trajectory_id: int,
                    hypothesis_id: int, label: str) -> int:
    """Agrega una capacidad-requisito a una trayectoria: la vincula con la
    hipótesis que la representa. UNIQUE impide requisitos duplicados."""
    if not label.strip():
        raise TrajectoryError("label vacío")
    with atomic(conn):
        if not _exists(conn, "trajectory", trajectory_id):
            raise TrajectoryError(f"trajectory id={trajectory_id} no existe")
        if not _exists(conn, "hypothesis", hypothesis_id):
            raise TrajectoryError(f"hypothesis id={hypothesis_id} no existe")
        dup = conn.execute(
            "SELECT 1 FROM trajectory_requirement WHERE trajectory_id = ? "
            "AND hypothesis_id = ?", (trajectory_id, hypothesis_id)
        ).fetchone()
        if dup:
            raise TrajectoryError(
                "esa capacidad ya es un requisito de la trayectoria")
        cur = conn.execute(
            "INSERT INTO trajectory_requirement (trajectory_id, hypothesis_id, "
            "label, created_at) VALUES (?, ?, ?, ?)",
            (trajectory_id, hypothesis_id, label, utc_now_iso()),
        )
        rid = cur.lastrowid
        append(conn, op="requirement_added",
               payload={"requirement_id": rid, "trajectory_id": trajectory_id,
                        "hypothesis_id": hypothesis_id, "label": label})
    return rid


# --------------------------------------------------------------- lectura ----

def list_trajectories(conn: sqlite3.Connection) -> list[dict]:
    return [
        {"id": r["id"], "name": r["name"], "description": r["description"]}
        for r in conn.execute(
            "SELECT id, name, description FROM trajectory ORDER BY id ASC")
    ]


def _requirements(conn: sqlite3.Connection, trajectory_id: int) -> list[dict]:
    """Requisitos de una trayectoria con el estado sellado de su hipótesis.
    Orden determinístico por id de requisito."""
    rows = conn.execute(
        "SELECT tr.id AS requirement_id, tr.hypothesis_id, tr.label, "
        "h.statement, h.status, h.index_value "
        "FROM trajectory_requirement tr "
        "JOIN hypothesis h ON h.id = tr.hypothesis_id "
        "WHERE tr.trajectory_id = ? ORDER BY tr.id ASC",
        (trajectory_id,),
    ).fetchall()
    out = []
    for r in rows:
        out.append({
            "requirement_id": r["requirement_id"],
            "hypothesis_id": r["hypothesis_id"],
            "label": r["label"],
            "hypothesis_statement": r["statement"],
            "hypothesis_status": r["status"],
            "index": r["index_value"],
            "fit": _FIT_FROM_HYPOTHESIS[r["status"]],
        })
    return out


def trajectory_fit(conn: sqlite3.Connection, trajectory_id: int) -> dict:
    """Fit determinístico de una trayectoria: por requisito y en resumen.
    Sin porcentaje de destino — cuentas por estado, nada más."""
    traj = conn.execute(
        "SELECT id, name, description FROM trajectory WHERE id = ?",
        (trajectory_id,),
    ).fetchone()
    if traj is None:
        raise TrajectoryError(f"trajectory id={trajectory_id} no existe")
    reqs = _requirements(conn, trajectory_id)
    summary = {state: 0 for state in FIT_STATES}
    for r in reqs:
        summary[r["fit"]] += 1
    summary["total"] = len(reqs)
    return {
        "trajectory": {"id": traj["id"], "name": traj["name"],
                       "description": traj["description"]},
        "requirements": reqs,
        "summary": summary,
    }


def discriminating_requirements(
    conn: sqlite3.Connection, trajectory_a: int, trajectory_b: int
) -> dict:
    """Qué capacidades separan dos trayectorias y cuál conviene testear primero.

    Distinguen las capacidades exigidas por EXACTAMENTE UNA de las dos y que
    aún NO están resueltas (open/supported): su resultado empuja hacia una
    trayectoria o revela que no es el camino. La sugerencia es la más barata
    de discriminar: la de menor índice (menos evidencia), desempate por id.
    """
    fit_a = trajectory_fit(conn, trajectory_a)
    fit_b = trajectory_fit(conn, trajectory_b)
    by_hyp_a = {r["hypothesis_id"]: r for r in fit_a["requirements"]}
    by_hyp_b = {r["hypothesis_id"]: r for r in fit_b["requirements"]}
    ids_a, ids_b = set(by_hyp_a), set(by_hyp_b)

    shared = sorted(ids_a & ids_b)
    distinguishing = []
    for hid in sorted(ids_a ^ ids_b):  # exigidas por exactamente una
        r = by_hyp_a.get(hid) or by_hyp_b.get(hid)
        if r["fit"] in _RESOLVED:
            continue  # ya no discrimina
        distinguishing.append({
            "hypothesis_id": hid,
            "label": r["label"],
            "only_in": "a" if hid in ids_a else "b",
            "fit": r["fit"],
            "index": r["index"] or 0,
        })
    # Economía de investigación: la de menor índice primero.
    distinguishing.sort(key=lambda d: (d["index"], d["hypothesis_id"]))
    suggested = distinguishing[0] if distinguishing else None
    return {
        "trajectory_a": fit_a["trajectory"],
        "trajectory_b": fit_b["trajectory"],
        "shared_requirements": shared,
        "distinguishing": distinguishing,
        "suggested_experiment_target": suggested,
        "note": ("Diseñá un experimento para la capacidad sugerida: su "
                 "resultado discrimina entre las dos trayectorias."
                 if suggested else
                 "No hay capacidad abierta que discrimine: las trayectorias "
                 "no se separan por evidencia faltante en este momento."),
    }
