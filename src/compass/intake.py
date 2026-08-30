"""Intake vocacional de COMPASS: Big Five (ítems IPIP, dominio público) +
RIASEC (ítems ORIGINALES, Apache-2.0 — el modelo de Holland es libre; solo los
instrumentos comerciales están protegidos, y el O*NET Interest Profiler es
CC BY-ND, que prohíbe traducir, incompatible con una app bilingüe).

Invariante que lo mantiene honesto (no es un test que dictamina):

    El intake NO concluye. Produce evidencia self_report (el peso MÍNIMO del
    engine) y PROPONE hipótesis-candidatas a testear. La persona valida; el
    experimento discrimina. "Los mismos inputs que los tests de personalidad,
    tratados como hipótesis, no como veredictos."

Scoring: SUMA ENTERA por dimensión (ítems reversos: 6 - valor). SIN normas ni
percentiles — un percentil necesitaría una tabla de normas y presentaría el
resultado como "estás en el 68%", exactamente el horóscopo que este proyecto
rechaza. El puntaje crudo se etiqueta como crudo.

Los ítems son estáticos y versionados acá (no en la base); INTAKE_VERSION sube
si cambian, para que un assessment viejo se lea con sus ítems.

NOTA: set INICIAL (para probar el pipeline end-to-end). Se expande a IPIP-50 +
RIASEC-60 completos; agregar ítems es solo extender estas listas.
"""

from __future__ import annotations

import sqlite3

from . import domain
from .audit_chain import append
from .db import atomic, utc_now_iso

INTAKE_VERSION = 1

# Escala Likert 1-5 (Big Five: en desacuerdo→de acuerdo; RIASEC: me disgusta→
# me gusta). MID no aporta ni resta.
LIKERT_MIN, LIKERT_MAX = 1, 5

# Big Five (OCEAN). Ítems IPIP (dominio público). reverse=True se puntúa 6-v.
# Factores: O(penness) C(onscientiousness) E(xtraversion) A(greeableness)
# N(euroticism).
BIG_FIVE_ITEMS = [
    ("E1", "E", False, "Am the life of the party.", "Soy el alma de la fiesta."),
    ("E2", "E", True, "Don't talk a lot.", "No hablo mucho."),
    ("A1", "A", False, "Sympathize with others' feelings.",
     "Empatizo con lo que sienten los demás."),
    ("A2", "A", True, "Am not interested in other people's problems.",
     "No me interesan los problemas de otros."),
    ("C1", "C", False, "Get chores done right away.",
     "Hago las tareas pendientes enseguida."),
    ("C2", "C", True, "Often forget to put things back in their proper place.",
     "A menudo me olvido de devolver las cosas a su lugar."),
    ("N1", "N", False, "Get stressed out easily.", "Me estreso con facilidad."),
    ("N2", "N", True, "Am relaxed most of the time.",
     "Estoy relajada la mayor parte del tiempo."),
    ("O1", "O", False, "Have a vivid imagination.", "Tengo una imaginación vívida."),
    ("O2", "O", True, "Am not interested in abstract ideas.",
     "No me interesan las ideas abstractas."),
]

# RIASEC (Holland). Ítems ORIGINALES (nuestros): preferencia por una actividad.
# R(ealistic) I(nvestigative) A(rtistic) S(ocial) E(nterprising) C(onventional).
RIASEC_ITEMS = [
    ("R1", "R", False, "Repair a broken machine or appliance.",
     "Reparar una máquina o un aparato roto."),
    ("R2", "R", False, "Work outdoors with tools and my hands.",
     "Trabajar al aire libre con herramientas y las manos."),
    ("I1", "I", False, "Investigate why a system behaves the way it does.",
     "Investigar por qué un sistema se comporta como se comporta."),
    ("I2", "I", False, "Read about a scientific discovery for fun.",
     "Leer sobre un descubrimiento científico por placer."),
    ("A1", "A", False, "Design something that has no single right answer.",
     "Diseñar algo que no tiene una única respuesta correcta."),
    ("A2", "A", False, "Express an idea through writing, images, or music.",
     "Expresar una idea con escritura, imágenes o música."),
    ("S1", "S", False, "Help someone learn a difficult skill.",
     "Ayudar a alguien a aprender una habilidad difícil."),
    ("S2", "S", False, "Listen to a person work through a problem.",
     "Escuchar a alguien mientras resuelve un problema."),
    ("E1", "E", False, "Persuade a group to back a plan I believe in.",
     "Convencer a un grupo de apoyar un plan en el que creo."),
    ("E2", "E", False, "Start and lead a new project.",
     "Arrancar y liderar un proyecto nuevo."),
    ("C1", "C", False, "Organize records so nothing gets lost.",
     "Organizar registros para que nada se pierda."),
    ("C2", "C", False, "Follow a clear procedure precisely.",
     "Seguir un procedimiento claro con precisión."),
]

_INSTRUMENTS = {
    "big_five": {"items": BIG_FIVE_ITEMS,
                 "dimensions": ("O", "C", "E", "A", "N")},
    "riasec": {"items": RIASEC_ITEMS,
               "dimensions": ("R", "I", "A", "S", "E", "C")},
}

# Cada dimensión alta propone UNA hipótesis-candidata (capacidad/interés a
# testear) + una glosa. Statement en castellano (contenido del dominio).
_DIMENSION_HYPOTHESIS = {
    "O": "Apertura alta: encaja en trabajo exploratorio y no rutinario.",
    "C": "Escrupulosidad alta: sostiene ejecución ordenada y de largo aliento.",
    "E": "Extraversión alta: rinde en roles con alta carga social.",
    "A": "Amabilidad alta: fuerte en roles de cuidado y colaboración.",
    "N": "Reactividad emocional alta: sensible al estrés; a chequear en contexto.",
    "R": "Interés Realista: se energiza construyendo y arreglando cosas concretas.",
    "I": "Interés Investigativo: se energiza analizando y entendiendo sistemas.",
    "A_riasec": "Interés Artístico: se energiza creando con final abierto.",
    "S": "Interés Social: se energiza enseñando y acompañando personas.",
    "E_riasec": "Interés Emprendedor: se energiza persuadiendo y liderando.",
    "C_riasec": "Interés Convencional: se energiza ordenando y sistematizando.",
}


class IntakeError(ValueError):
    pass


def instruments() -> list[str]:
    return list(_INSTRUMENTS)


def _instrument(instrument: str) -> dict:
    if instrument not in _INSTRUMENTS:
        raise IntakeError(f"instrument inválido: {instrument!r}; "
                          f"opciones: {list(_INSTRUMENTS)}")
    return _INSTRUMENTS[instrument]


def items(instrument: str, lang: str = "en") -> list[dict]:
    """Los ítems del instrumento en el idioma pedido (en|es). El código y la
    dimensión son estables; solo cambia el texto."""
    idx = 4 if lang == "es" else 3
    return [{"code": c, "dimension": dim, "text": it[idx]}
            for (c, dim, rev, *_texts) in _instrument(instrument)["items"]
            for it in [(c, dim, rev, _texts[0], _texts[1])]]


def _dimension_key(instrument: str, dim: str) -> str:
    # A/E/C existen en ambos; se desambigua la glosa RIASEC con sufijo.
    if instrument == "riasec" and dim in ("A", "E", "C"):
        return f"{dim}_riasec"
    return dim


# ------------------------------------------------------------- escritura ----

def start_assessment(conn: sqlite3.Connection, instrument: str) -> int:
    _instrument(instrument)
    with atomic(conn):
        cur = conn.execute(
            "INSERT INTO assessment (instrument, created_at) VALUES (?, ?)",
            (instrument, utc_now_iso()),
        )
        aid = cur.lastrowid
        append(conn, op="assessment_started",
               payload={"assessment_id": aid, "instrument": instrument,
                        "intake_version": INTAKE_VERSION})
    return aid


def submit_response(conn: sqlite3.Connection, assessment_id: int,
                    item_code: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) \
            or not LIKERT_MIN <= value <= LIKERT_MAX:
        raise IntakeError(f"value debe ser entero {LIKERT_MIN}-{LIKERT_MAX}")
    with atomic(conn):
        row = conn.execute(
            "SELECT instrument FROM assessment WHERE id = ?", (assessment_id,)
        ).fetchone()
        if row is None:
            raise IntakeError(f"assessment id={assessment_id} no existe")
        valid_codes = {it[0] for it in _instrument(row["instrument"])["items"]}
        if item_code not in valid_codes:
            raise IntakeError(f"item_code {item_code!r} no pertenece al "
                              f"instrumento {row['instrument']!r}")
        conn.execute(
            "INSERT INTO assessment_response (assessment_id, item_code, value) "
            "VALUES (?, ?, ?) ON CONFLICT (assessment_id, item_code) "
            "DO UPDATE SET value = excluded.value",
            (assessment_id, item_code, value),
        )


# --------------------------------------------------------------- scoring ----

def score(conn: sqlite3.Connection, assessment_id: int) -> dict:
    """Suma entera por dimensión. Devuelve, por dimensión, el crudo, el máximo
    posible respondido, y cuántos ítems se respondieron. Sin normas."""
    row = conn.execute(
        "SELECT instrument FROM assessment WHERE id = ?", (assessment_id,)
    ).fetchone()
    if row is None:
        raise IntakeError(f"assessment id={assessment_id} no existe")
    instrument = row["instrument"]
    spec = _instrument(instrument)
    by_code = {it[0]: it for it in spec["items"]}
    responses = {
        r["item_code"]: r["value"]
        for r in conn.execute(
            "SELECT item_code, value FROM assessment_response "
            "WHERE assessment_id = ?", (assessment_id,))
    }
    dims = {d: {"raw": 0, "max": 0, "answered": 0} for d in spec["dimensions"]}
    for code, value in responses.items():
        _c, dim, reverse, *_ = by_code[code]
        contrib = (LIKERT_MAX + LIKERT_MIN - value) if reverse else value
        dims[dim]["raw"] += contrib
        dims[dim]["max"] += LIKERT_MAX
        dims[dim]["answered"] += 1
    return {"assessment_id": assessment_id, "instrument": instrument,
            "intake_version": INTAKE_VERSION, "dimensions": dims}


def _is_high(raw: int, max_: int) -> bool:
    # "Alta" = crudo >= 70% del máximo respondido, con enteros (sin floats).
    return max_ > 0 and 10 * raw >= 7 * max_


def proposed_hypotheses(conn: sqlite3.Connection, assessment_id: int) -> dict:
    """Traduce el score en PROPUESTAS: por cada dimensión alta, una hipótesis-
    candidata a testear. NO persiste nada ni mueve un índice — la persona
    decide cuáles registrar (entrarían como self_report, el peso mínimo)."""
    sc = score(conn, assessment_id)
    proposals = []
    for dim, s in sc["dimensions"].items():
        if s["answered"] and _is_high(s["raw"], s["max"]):
            key = _dimension_key(sc["instrument"], dim)
            proposals.append({
                "dimension": dim,
                "raw": s["raw"], "max": s["max"],
                "statement": _DIMENSION_HYPOTHESIS[key],
            })
    return {"assessment_id": assessment_id, "instrument": sc["instrument"],
            "proposals": proposals,
            "note": "Propuestas para testear, no un veredicto. Registrar una "
            "la agrega como hipótesis con evidencia self_report (peso mínimo); "
            "un experimento discriminante es lo que la confirma o la debilita."}


def register_proposal(conn: sqlite3.Connection, assessment_id: int,
                      dimension: str) -> dict:
    """La persona ACEPTA una propuesta: crea la hipótesis-candidata y una
    evidencia self_report PENDIENTE (peso mínimo) vinculada supports. Consistente
    con el extractor: la propuesta entra como pendiente y la persona la valida
    en el ledger; nada se sella como veredicto. Todo-o-nada. La procedencia
    (intake) queda en el source de la evidencia."""
    proposal = None
    for p in proposed_hypotheses(conn, assessment_id)["proposals"]:
        if p["dimension"] == dimension:
            proposal = p
            break
    if proposal is None:
        raise IntakeError(
            f"la dimensión {dimension!r} no es una propuesta alta de este "
            "assessment (solo se registran dimensiones altas)")
    instrument = score(conn, assessment_id)["instrument"]
    with atomic(conn):
        hid = domain.hypothesis_add(conn, statement=proposal["statement"],
                                    origin="person")
        eid = domain.evidence_add(
            conn, evidence_type="self_report",
            source=f"intake:{instrument}",
            content={"assessment_id": assessment_id, "dimension": dimension,
                     "raw": proposal["raw"], "max": proposal["max"],
                     "intake_version": INTAKE_VERSION},
            validated=False,  # pendiente: la persona valida en el ledger
        )
        domain.evidence_link(conn, hypothesis_id=hid, evidence_id=eid,
                             direction="supports")
        append(conn, op="intake_proposal_registered",
               payload={"assessment_id": assessment_id, "dimension": dimension,
                        "hypothesis_id": hid, "evidence_id": eid})
    return {"hypothesis_id": hid, "evidence_id": eid, "validated": False}
