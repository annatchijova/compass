"""Ocupaciones O*NET → trayectorias (design doc §5): a qué dedicarse con dato
DURO. Elegís una ocupación real y COMPASS arma la trayectoria con sus
capacidades-requisito reales, cada una respaldada por una hipótesis a testear.

Fuente: O*NET 31.0 Database (USDOL/ETA), CC BY 4.0. Las capacidades-requisito
de abajo están DESTILADAS/reformuladas de las Skills/Knowledge/Abilities que
O*NET lista por ocupación — CC BY 4.0 permite derivados con atribución (a
diferencia del Interest Profiler, que es CC BY-ND). Ver docs/ATTRIBUTIONS.md.

Adoptar una ocupación NO dictamina nada: crea hipótesis-candidatas (capacidades
a testear) y una trayectoria que mide el fit contra tu evidencia. El
experimento es el que confirma; el intake/O*NET solo siembran.

Set curado inicial (6 ocupaciones que cubren el espacio RIASEC); se expande
agregando entradas — es solo dato.
"""

from __future__ import annotations

import sqlite3

from . import domain, trajectories
from .audit_chain import append
from .db import atomic

ONET_ATTRIBUTION = (
    "Requirements derived from the O*NET 31.0 Database by the U.S. Department "
    "of Labor, Employment and Training Administration (USDOL/ETA), used under "
    "the CC BY 4.0 license (https://creativecommons.org/licenses/by/4.0/). "
    "COMPASS has distilled and reworded this information. USDOL/ETA has not "
    "approved, endorsed, or tested these modifications. O*NET is a trademark "
    "of USDOL/ETA."
)

# (code, title_en, title_es, riasec, [(label_en, label_es), ...])
OCCUPATIONS = [
    ("15-2051.00", "Data Scientist", "Científica de datos", "IC", [
        ("Applies mathematics and statistics to solve problems.",
         "Aplica matemática y estadística para resolver problemas."),
        ("Reasons deductively and inductively from data to conclusions.",
         "Razona de forma deductiva e inductiva desde los datos a conclusiones."),
        ("Uses logic and critical thinking to weigh alternative solutions.",
         "Usa lógica y pensamiento crítico para sopesar soluciones alternativas."),
        ("Works fluently with computers, software, and data tools.",
         "Maneja con fluidez computadoras, software y herramientas de datos."),
        ("Communicates findings clearly, speaking and in writing.",
         "Comunica hallazgos con claridad, al hablar y por escrito."),
        ("Keeps learning as new information and methods appear.",
         "Sigue aprendiendo a medida que aparecen información y métodos nuevos."),
    ]),
    ("15-1252.00", "Software Developer", "Desarrolladora de software", "IC", [
        ("Writes programs to solve problems.",
         "Escribe programas para resolver problemas."),
        ("Determines how systems should work and respond to change.",
         "Determina cómo deben funcionar los sistemas y responder al cambio."),
        ("Develops and evaluates solutions to complex, multi-part problems.",
         "Desarrolla y evalúa soluciones a problemas complejos de varias partes."),
        ("Reasons deductively from general rules to specific answers.",
         "Razona deductivamente de reglas generales a respuestas concretas."),
        ("Adapts technology to meet real user requirements.",
         "Adapta la tecnología a los requisitos reales de las personas usuarias."),
        ("Keeps learning as tools and information change.",
         "Sigue aprendiendo a medida que cambian herramientas e información."),
    ]),
    ("25-2021.00", "Elementary School Teacher", "Maestra de primaria", "S", [
        ("Chooses teaching strategies that fit what someone needs to learn.",
         "Elige estrategias de enseñanza adecuadas a lo que alguien necesita aprender."),
        ("Explains ideas clearly so others understand.",
         "Explica ideas con claridad para que otros entiendan."),
        ("Listens actively and asks clarifying questions.",
         "Escucha activamente y hace preguntas para clarificar."),
        ("Monitors progress and adjusts to improve outcomes.",
         "Monitorea el progreso y ajusta para mejorar resultados."),
        ("Understands human behavior, learning, and motivation.",
         "Entiende la conducta humana, el aprendizaje y la motivación."),
        ("Notices when something is wrong before it becomes a problem.",
         "Nota cuando algo anda mal antes de que sea un problema."),
    ]),
    ("29-1141.00", "Registered Nurse", "Enfermera", "SCI", [
        ("Listens actively and asks the right questions.",
         "Escucha activamente y hace las preguntas adecuadas."),
        ("Uses critical thinking to weigh options under pressure.",
         "Usa pensamiento crítico para sopesar opciones bajo presión."),
        ("Recognizes when something is wrong or likely to go wrong.",
         "Reconoce cuando algo anda mal o está por salir mal."),
        ("Communicates clearly, speaking and in writing.",
         "Comunica con claridad, al hablar y por escrito."),
        ("Applies knowledge of the body, health, and care.",
         "Aplica conocimiento del cuerpo, la salud y el cuidado."),
        ("Monitors a situation and adjusts to improve it.",
         "Monitorea una situación y ajusta para mejorarla."),
    ]),
    ("27-1024.00", "Graphic Designer", "Diseñadora gráfica", "AC", [
        ("Generates many original ideas.",
         "Genera muchas ideas originales."),
        ("Applies design techniques, tools, and principles.",
         "Aplica técnicas, herramientas y principios de diseño."),
        ("Works fluently with design software and tools.",
         "Maneja con fluidez software y herramientas de diseño."),
        ("Composes visual elements until they work.",
         "Compone elementos visuales hasta que funcionan."),
        ("Understands how to communicate through media.",
         "Entiende cómo comunicar a través de los medios."),
        ("Listens to grasp what a brief actually needs.",
         "Escucha para captar lo que un encargo realmente necesita."),
    ]),
    ("11-1021.00", "Operations Manager", "Gerenta de operaciones", "EC", [
        ("Motivates and directs people.",
         "Motiva y dirige a las personas."),
        ("Coordinates actions across people and teams.",
         "Coordina acciones entre personas y equipos."),
        ("Evaluates costs and benefits to make decisions.",
         "Evalúa costos y beneficios para tomar decisiones."),
        ("Solves complex problems: identifies the issue, implements a solution.",
         "Resuelve problemas complejos: identifica la cuestión, implementa una solución."),
        ("Plans strategically and allocates resources.",
         "Planifica estratégicamente y asigna recursos."),
        ("Manages time — their own and others'.",
         "Gestiona el tiempo, el propio y el de los demás."),
    ]),
    ("27-3043.00", "Writer / Author", "Escritora", "AE", [
        ("Communicates effectively in writing for an audience.",
         "Comunica con eficacia por escrito para una audiencia."),
        ("Generates many ideas about a topic.",
         "Genera muchas ideas sobre un tema."),
        ("Reads and understands complex text.",
         "Lee y entiende textos complejos."),
        ("Uses critical thinking to shape an argument.",
         "Usa pensamiento crítico para dar forma a un argumento."),
        ("Applies knowledge of language structure and composition.",
         "Aplica conocimiento de la estructura del lenguaje y la composición."),
        ("Listens and observes to gather material.",
         "Escucha y observa para juntar material."),
    ]),
    ("27-2042.00", "Musician / Singer", "Música", "AE", [
        ("Composes, produces, or performs works of music.",
         "Compone, produce o interpreta obras musicales."),
        ("Hears fine differences in pitch and sound.",
         "Distingue diferencias finas de tono y sonido."),
        ("Focuses on one sound among distractions.",
         "Se concentra en un sonido entre distracciones."),
        ("Sustains disciplined practice to improve.",
         "Sostiene práctica disciplinada para mejorar."),
        ("Communicates and connects with an audience.",
         "Comunica y conecta con una audiencia."),
        ("Reads and interprets a score or arrangement.",
         "Lee e interpreta una partitura o un arreglo."),
    ]),
    ("27-2011.00", "Actor", "Actriz", "ASE", [
        ("Memorizes and delivers lines and cues.",
         "Memoriza y ejecuta líneas y señales."),
        ("Expresses ideas and emotion so an audience understands.",
         "Expresa ideas y emoción para que una audiencia entienda."),
        ("Reads people's reactions and adjusts.",
         "Lee las reacciones de la gente y ajusta."),
        ("Applies the craft of performance and the arts.",
         "Aplica el oficio de la actuación y las artes."),
        ("Speaks clearly and expressively.",
         "Habla con claridad y expresividad."),
        ("Understands human behavior and motivation.",
         "Entiende la conducta humana y la motivación."),
    ]),
    ("47-2111.00", "Electrician", "Electricista", "RC", [
        ("Installs, repairs, and maintains electrical systems.",
         "Instala, repara y mantiene sistemas eléctricos."),
        ("Recognizes when something is wrong or unsafe.",
         "Reconoce cuando algo anda mal o es inseguro."),
        ("Reasons deductively from codes and rules to a fix.",
         "Razona deductivamente de códigos y reglas a una solución."),
        ("Applies knowledge of construction and mechanics.",
         "Aplica conocimiento de construcción y mecánica."),
        ("Works precisely with close-range detail.",
         "Trabaja con precisión en el detalle de cerca."),
        ("Follows procedures and keeps things organized.",
         "Sigue procedimientos y mantiene el orden."),
    ]),
    ("13-2011.00", "Accountant / Auditor", "Contadora", "CEI", [
        ("Keeps detailed, accurate financial records.",
         "Lleva registros financieros detallados y exactos."),
        ("Applies mathematics and accounting principles.",
         "Aplica matemática y principios contables."),
        ("Reasons inductively and deductively from figures.",
         "Razona inductiva y deductivamente desde las cifras."),
        ("Reads and understands complex documents.",
         "Lee y entiende documentos complejos."),
        ("Applies knowledge of law and regulations.",
         "Aplica conocimiento de leyes y regulaciones."),
        ("Uses critical thinking to weigh options.",
         "Usa pensamiento crítico para sopesar opciones."),
    ]),
    ("29-1123.00", "Physical Therapist", "Fisioterapeuta", "SIR", [
        ("Listens actively and asks clarifying questions.",
         "Escucha activamente y hace preguntas para clarificar."),
        ("Applies knowledge of the body, therapy, and rehab.",
         "Aplica conocimiento del cuerpo, la terapia y la rehabilitación."),
        ("Recognizes and evaluates what needs improvement.",
         "Reconoce y evalúa qué necesita mejorar."),
        ("Communicates clearly and supportively.",
         "Comunica con claridad y apoyo."),
        ("Reasons from general rules to a specific case.",
         "Razona de reglas generales a un caso concreto."),
        ("Monitors progress and adjusts the plan.",
         "Monitorea el progreso y ajusta el plan."),
    ]),
]

_BY_CODE = {o[0]: o for o in OCCUPATIONS}


class OccupationError(ValueError):
    pass


def list_occupations(lang: str = "en") -> list[dict]:
    return [{"code": c, "title": (t_es if lang == "es" else t_en),
             "riasec": riasec, "requirement_count": len(reqs)}
            for (c, t_en, t_es, riasec, reqs) in OCCUPATIONS]


def occupation(code: str, lang: str = "en") -> dict:
    if code not in _BY_CODE:
        raise OccupationError(f"ocupación desconocida: {code!r}")
    c, t_en, t_es, riasec, reqs = _BY_CODE[code]
    idx = 1 if lang == "es" else 0
    return {"code": c, "title": (t_es if lang == "es" else t_en),
            "riasec": riasec,
            "requirements": [r[idx] for r in reqs],
            "attribution": ONET_ATTRIBUTION}


def adopt_occupation(conn: sqlite3.Connection, code: str,
                     lang: str = "es") -> dict:
    """Crea la trayectoria de una ocupación: por cada capacidad-requisito, una
    hipótesis-candidata (a testear) y su requisito. Todo-o-nada. NO valida nada
    ni mueve un índice — solo siembra estructura basada en evidencia O*NET."""
    if code not in _BY_CODE:
        raise OccupationError(f"ocupación desconocida: {code!r}")
    c, t_en, t_es, riasec, reqs = _BY_CODE[code]
    title = t_es if lang == "es" else t_en
    idx = 1 if lang == "es" else 0
    with atomic(conn):
        tid = trajectories.trajectory_add(
            conn, name=title,
            description=f"O*NET {code} ({riasec}). {ONET_ATTRIBUTION}")
        created = []
        for r in reqs:
            label = r[idx]
            hid = domain.hypothesis_add(conn, statement=label, origin="person")
            rid = trajectories.requirement_add(
                conn, trajectory_id=tid, hypothesis_id=hid, label=label)
            created.append({"requirement_id": rid, "hypothesis_id": hid,
                            "label": label})
        append(conn, op="occupation_adopted",
               payload={"trajectory_id": tid, "onet_code": code,
                        "requirements": len(created)})
    return {"trajectory_id": tid, "title": title, "onet_code": code,
            "requirements": created}
