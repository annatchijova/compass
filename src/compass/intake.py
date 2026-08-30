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

INTAKE_VERSION = 2

# Escala Likert 1-5 (Big Five: en desacuerdo→de acuerdo; RIASEC: me disgusta→
# me gusta). MID no aporta ni resta.
LIKERT_MIN, LIKERT_MAX = 1, 5

# Big Five (OCEAN). Ítems IPIP (dominio público). reverse=True se puntúa 6-v.
# Factores: O(penness) C(onscientiousness) E(xtraversion) A(greeableness)
# N(euroticism).
BIG_FIVE_ITEMS = [
    # Extraversion
    ("E1", "E", False, "Am the life of the party.", "Soy el alma de la fiesta."),
    ("E2", "E", True, "Don't talk a lot.", "No hablo mucho."),
    ("E3", "E", False, "Feel comfortable around people.",
     "Me siento cómoda rodeada de gente."),
    ("E4", "E", True, "Keep in the background.", "Me quedo en segundo plano."),
    ("E5", "E", False, "Start conversations.", "Inicio conversaciones."),
    ("E6", "E", True, "Have little to say.", "Tengo poco para decir."),
    ("E7", "E", False, "Talk to a lot of different people at parties.",
     "Hablo con mucha gente distinta en las fiestas."),
    ("E8", "E", True, "Don't like to draw attention to myself.",
     "No me gusta llamar la atención."),
    ("E9", "E", False, "Don't mind being the center of attention.",
     "No me molesta ser el centro de atención."),
    ("E10", "E", True, "Am quiet around strangers.",
     "Soy callada con desconocidos."),
    # Agreeableness
    ("A1", "A", True, "Feel little concern for others.",
     "Me preocupo poco por los demás."),
    ("A2", "A", False, "Am interested in people.", "Me interesa la gente."),
    ("A3", "A", True, "Insult people.", "Insulto a la gente."),
    ("A4", "A", False, "Sympathize with others' feelings.",
     "Empatizo con lo que sienten los demás."),
    ("A5", "A", True, "Am not interested in other people's problems.",
     "No me interesan los problemas de otros."),
    ("A6", "A", False, "Have a soft heart.", "Tengo el corazón blando."),
    ("A7", "A", True, "Am not really interested in others.",
     "En realidad no me interesan los demás."),
    ("A8", "A", False, "Take time out for others.",
     "Me hago tiempo para los demás."),
    ("A9", "A", False, "Feel others' emotions.",
     "Siento las emociones de los demás."),
    ("A10", "A", False, "Make people feel at ease.",
     "Hago que la gente se sienta cómoda."),
    # Conscientiousness
    ("C1", "C", False, "Am always prepared.", "Siempre estoy preparada."),
    ("C2", "C", True, "Leave my belongings around.",
     "Dejo mis cosas tiradas por ahí."),
    ("C3", "C", False, "Pay attention to details.",
     "Presto atención a los detalles."),
    ("C4", "C", True, "Make a mess of things.", "Hago un lío con las cosas."),
    ("C5", "C", False, "Get chores done right away.",
     "Hago las tareas pendientes enseguida."),
    ("C6", "C", True, "Often forget to put things back in their proper place.",
     "A menudo me olvido de devolver las cosas a su lugar."),
    ("C7", "C", False, "Like order.", "Me gusta el orden."),
    ("C8", "C", True, "Shirk my duties.", "Eludo mis obligaciones."),
    ("C9", "C", False, "Follow a schedule.", "Sigo un cronograma."),
    ("C10", "C", False, "Am exacting in my work.",
     "Soy exigente en mi trabajo."),
    # Neuroticism
    ("N1", "N", False, "Get stressed out easily.", "Me estreso con facilidad."),
    ("N2", "N", True, "Am relaxed most of the time.",
     "Estoy relajada la mayor parte del tiempo."),
    ("N3", "N", False, "Worry about things.", "Me preocupo por las cosas."),
    ("N4", "N", True, "Seldom feel blue.", "Rara vez me siento decaída."),
    ("N5", "N", False, "Am easily disturbed.", "Me perturbo con facilidad."),
    ("N6", "N", False, "Get upset easily.", "Me altero con facilidad."),
    ("N7", "N", False, "Change my mood a lot.", "Cambio mucho de humor."),
    ("N8", "N", False, "Have frequent mood swings.",
     "Tengo cambios de humor frecuentes."),
    ("N9", "N", False, "Get irritated easily.", "Me irrito con facilidad."),
    ("N10", "N", False, "Often feel blue.", "A menudo me siento decaída."),
    # Openness / Intellect
    ("O1", "O", False, "Have a rich vocabulary.", "Tengo un vocabulario rico."),
    ("O2", "O", True, "Have difficulty understanding abstract ideas.",
     "Me cuesta entender ideas abstractas."),
    ("O3", "O", False, "Have a vivid imagination.",
     "Tengo una imaginación vívida."),
    ("O4", "O", True, "Am not interested in abstract ideas.",
     "No me interesan las ideas abstractas."),
    ("O5", "O", False, "Have excellent ideas.", "Tengo excelentes ideas."),
    ("O6", "O", True, "Do not have a good imagination.",
     "No tengo buena imaginación."),
    ("O7", "O", False, "Am quick to understand things.",
     "Entiendo las cosas rápido."),
    ("O8", "O", False, "Use difficult words.", "Uso palabras difíciles."),
    ("O9", "O", False, "Spend time reflecting on things.",
     "Paso tiempo reflexionando sobre las cosas."),
    ("O10", "O", False, "Am full of ideas.", "Estoy llena de ideas."),
]

# RIASEC (Holland). Ítems ORIGINALES (nuestros): preferencia por una actividad.
# R(ealistic) I(nvestigative) A(rtistic) S(ocial) E(nterprising) C(onventional).
RIASEC_ITEMS = [
    # Realistic — hands-on, tools, machines, physical, outdoors
    ("R1", "R", False, "Repair a broken machine or appliance.",
     "Reparar una máquina o un aparato roto."),
    ("R2", "R", False, "Work outdoors with tools and my hands.",
     "Trabajar al aire libre con herramientas y las manos."),
    ("R3", "R", False, "Assemble furniture or equipment from parts.",
     "Armar muebles o equipos a partir de piezas."),
    ("R4", "R", False, "Operate a machine or power tool.",
     "Operar una máquina o una herramienta eléctrica."),
    ("R5", "R", False, "Fix a bicycle, an engine, or plumbing.",
     "Arreglar una bici, un motor o una cañería."),
    ("R6", "R", False, "Build something physical from a plan.",
     "Construir algo físico a partir de un plano."),
    ("R7", "R", False, "Grow plants or care for animals.",
     "Cultivar plantas o cuidar animales."),
    ("R8", "R", False, "Take a device apart to see how it works.",
     "Desarmar un aparato para ver cómo funciona."),
    ("R9", "R", False, "Do physical work that keeps me moving.",
     "Hacer trabajo físico que me mantenga en movimiento."),
    ("R10", "R", False, "Wire or install electronics or hardware.",
     "Cablear o instalar electrónica o hardware."),
    # Investigative — analyze, research, understand, science, math
    ("I1", "I", False, "Investigate why a system behaves the way it does.",
     "Investigar por qué un sistema se comporta como se comporta."),
    ("I2", "I", False, "Read about a scientific discovery for fun.",
     "Leer sobre un descubrimiento científico por placer."),
    ("I3", "I", False, "Solve a hard logic or math problem.",
     "Resolver un problema difícil de lógica o matemática."),
    ("I4", "I", False, "Analyze data to find a pattern.",
     "Analizar datos para encontrar un patrón."),
    ("I5", "I", False, "Run an experiment to test an idea.",
     "Correr un experimento para probar una idea."),
    ("I6", "I", False, "Track down the root cause of a bug or failure.",
     "Rastrear la causa raíz de un error o una falla."),
    ("I7", "I", False, "Compare two theories to see which fits the evidence.",
     "Comparar dos teorías para ver cuál encaja con la evidencia."),
    ("I8", "I", False, "Learn how something works in deep detail.",
     "Aprender en detalle profundo cómo funciona algo."),
    ("I9", "I", False, "Model a process to predict what happens next.",
     "Modelar un proceso para predecir qué pasa después."),
    ("I10", "I", False, "Question an assumption everyone takes for granted.",
     "Cuestionar un supuesto que todos dan por sentado."),
    # Artistic — create, design, express, open-ended
    ("A1", "A", False, "Design something that has no single right answer.",
     "Diseñar algo que no tiene una única respuesta correcta."),
    ("A2", "A", False, "Express an idea through writing, images, or music.",
     "Expresar una idea con escritura, imágenes o música."),
    ("A3", "A", False, "Come up with an original concept from scratch.",
     "Inventar un concepto original desde cero."),
    ("A4", "A", False, "Improvise instead of following a set script.",
     "Improvisar en vez de seguir un guion fijo."),
    ("A5", "A", False, "Arrange colors, shapes, or sounds until they feel right.",
     "Componer colores, formas o sonidos hasta que queden bien."),
    ("A6", "A", False, "Write a story, a poem, or a song.",
     "Escribir un cuento, un poema o una canción."),
    ("A7", "A", False, "Reimagine something ordinary in a new way.",
     "Reimaginar algo común de una manera nueva."),
    ("A8", "A", False, "Work on a project with no fixed rules.",
     "Trabajar en un proyecto sin reglas fijas."),
    ("A9", "A", False, "Design the look and feel of a space or product.",
     "Diseñar la estética de un espacio o un producto."),
    ("A10", "A", False, "Find beauty in how an idea is put together.",
     "Encontrar belleza en cómo se arma una idea."),
    # Social — help, teach, listen, care, collaborate
    ("S1", "S", False, "Help someone learn a difficult skill.",
     "Ayudar a alguien a aprender una habilidad difícil."),
    ("S2", "S", False, "Listen to a person work through a problem.",
     "Escuchar a alguien mientras resuelve un problema."),
    ("S3", "S", False, "Explain a hard idea until it clicks for someone.",
     "Explicar una idea difícil hasta que a alguien le hace clic."),
    ("S4", "S", False, "Support someone going through a hard time.",
     "Acompañar a alguien que la está pasando mal."),
    ("S5", "S", False, "Mediate a disagreement between two people.",
     "Mediar en un desacuerdo entre dos personas."),
    ("S6", "S", False, "Volunteer for a cause I care about.",
     "Ser voluntaria en una causa que me importa."),
    ("S7", "S", False, "Mentor someone who is starting out.",
     "Guiar a alguien que recién empieza."),
    ("S8", "S", False, "Work closely as part of a team.",
     "Trabajar codo a codo en un equipo."),
    ("S9", "S", False, "Notice when someone needs help before they ask.",
     "Darme cuenta de que alguien necesita ayuda antes de que la pida."),
    ("S10", "S", False, "Bring a group together around a shared goal.",
     "Unir a un grupo en torno a un objetivo común."),
    # Enterprising — persuade, lead, initiate, sell, risk
    ("E1", "E", False, "Persuade a group to back a plan I believe in.",
     "Convencer a un grupo de apoyar un plan en el que creo."),
    ("E2", "E", False, "Start and lead a new project.",
     "Arrancar y liderar un proyecto nuevo."),
    ("E3", "E", False, "Negotiate a deal or an agreement.",
     "Negociar un trato o un acuerdo."),
    ("E4", "E", False, "Pitch an idea to win people over.",
     "Presentar una idea para ganarme a la gente."),
    ("E5", "E", False, "Take charge when no one else will.",
     "Tomar las riendas cuando nadie más lo hace."),
    ("E6", "E", False, "Set an ambitious goal and chase it.",
     "Ponerme una meta ambiciosa e ir por ella."),
    ("E7", "E", False, "Sell something I believe in.",
     "Vender algo en lo que creo."),
    ("E8", "E", False, "Take a calculated risk for a big payoff.",
     "Correr un riesgo calculado por una recompensa grande."),
    ("E9", "E", False, "Rally people to make something happen.",
     "Movilizar a la gente para que algo pase."),
    ("E10", "E", False, "Compete to be the best at something.",
     "Competir por ser la mejor en algo."),
    # Conventional — organize, order, procedures, records, detail
    ("C1", "C", False, "Organize records so nothing gets lost.",
     "Organizar registros para que nada se pierda."),
    ("C2", "C", False, "Follow a clear procedure precisely.",
     "Seguir un procedimiento claro con precisión."),
    ("C3", "C", False, "Keep detailed, accurate accounts.",
     "Llevar cuentas detalladas y exactas."),
    ("C4", "C", False, "Sort and label things into a tidy system.",
     "Ordenar y etiquetar cosas en un sistema prolijo."),
    ("C5", "C", False, "Double-check work for small errors.",
     "Revisar el trabajo en busca de errores chicos."),
    ("C6", "C", False, "Build a checklist and work through it.",
     "Armar una checklist y recorrerla."),
    ("C7", "C", False, "Manage a schedule down to the detail.",
     "Manejar un cronograma hasta el detalle."),
    ("C8", "C", False, "Enter and maintain data carefully.",
     "Cargar y mantener datos con cuidado."),
    ("C9", "C", False, "Set up a process others can follow.",
     "Armar un proceso que otros puedan seguir."),
    ("C10", "C", False, "Keep files and money in strict order.",
     "Mantener archivos y dinero en orden estricto."),
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
