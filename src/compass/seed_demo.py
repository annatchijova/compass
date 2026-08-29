"""Escenario de demostración de COMPASS, construido SOLO con operaciones
reales del dominio (nada se inyecta a mano en la base).

Existe por dos razones:

1. La URL hosteada del hackathon no debe mostrar una brújula vacía: al
   arrancar, la API siembra este escenario si la base no tiene persona.
2. Es dogfooding honesto (design doc §8): "usuaria cero: vos". El
   escenario recorre el ciclo abductivo completo —evidencia de varios
   tipos, dos hipótesis rivales, un experimento preregistrado y cerrado
   contra su criterio, y un recompute sellado— de modo que los índices y
   la cadena de auditoría que ve la interfaz son PRODUCIDOS por el motor
   determinístico, no escritos como decorado.

Idempotente: si ya hay persona, no hace nada.
"""

from __future__ import annotations

import sqlite3

from . import domain, engine


def is_seeded(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM person WHERE id = 1").fetchone() is not None


def seed(conn: sqlite3.Connection) -> dict:
    """Siembra el escenario de la usuaria cero. Devuelve un resumen.

    No sella nada por su cuenta más allá de lo que sellan las propias
    operaciones de dominio y el recompute final.
    """
    if is_seeded(conn):
        return {"seeded": False, "reason": "ya había una persona registrada"}

    engine.seed_default_config(conn)
    domain.person_set(conn, "Anna (usuaria cero)")

    # Dos hipótesis RIVALES sobre una misma señal observada: el sistema
    # sostiene ambas vivas hasta que un experimento discrimine (design §3.4).
    h_diseno = domain.hypothesis_add(
        conn,
        statement="Tiene capacidad de diseño de sistemas: cierra arquitecturas "
        "de extremo a extremo sin ayuda, no solo escribe funciones.",
        origin="person",
    )
    h_ejecucion = domain.hypothesis_add(
        conn,
        statement="La señal se explica por pura ejecución rápida bajo deadline, "
        "no por diseño: rinde con andamio ajeno, no diseñando el propio.",
        origin="person",
    )

    # Evidencia de varios tipos. La contradictoria pesa más (anti-halago).
    e_self = domain.evidence_add(
        conn, evidence_type="self_report", source="onboarding",
        content={"texto": "Siento que entiendo sistemas completos, no partes."},
        validated=True,
    )
    e_behav = domain.evidence_add(
        conn, evidence_type="behavioral", source="registro-propio",
        content={"texto": "Volvió sola a rediseñar el motor tres noches "
                 "seguidas sin que nadie se lo pidiera.",
                 "metric": "retorno_espontaneo"},
        validated=True,
    )
    e_extern = domain.evidence_add(
        conn, evidence_type="outcome_external", source="merge-upstream",
        content={"texto": "PR de arquitectura aceptada y mergeada por "
                 "mantenedores externos (cel-go #1445)."},
        validated=True,
    )

    domain.evidence_link(conn, hypothesis_id=h_diseno, evidence_id=e_self,
                         direction="supports")
    domain.evidence_link(conn, hypothesis_id=h_diseno, evidence_id=e_behav,
                         direction="supports")
    domain.evidence_link(conn, hypothesis_id=h_diseno, evidence_id=e_extern,
                         direction="supports")
    # La misma conducta, leída como rival: sostiene la hipótesis de ejecución.
    domain.evidence_link(conn, hypothesis_id=h_ejecucion, evidence_id=e_self,
                         direction="contradicts")

    # Un experimento DISCRIMINANTE, preregistrado con criterio de fracaso
    # ANTES de ejecutarlo (design §4). Discrimina diseño vs. ejecución.
    xid = domain.experiment_preregister(
        conn,
        hypothesis_id=h_diseno,
        design="Diseñar desde cero la arquitectura de autoridad de un sistema "
        "nuevo (sin andamio ajeno) y que un tercero la audite.",
        success_criterion="Un revisor independiente confirma que la arquitectura "
        "cierra sola y sostiene sus invariantes bajo crítica.",
        failure_criterion="El diseño depende de estructura provista por otro o "
        "colapsa al primer contraejemplo del revisor.",
        rival_hypothesis_id=h_ejecucion,
        duration="1 semana",
    )
    domain.experiment_start(conn, xid)
    domain.observation_add(conn, experiment_id=xid, metric="tiempo_voluntario",
                           value="20+ horas sin pedido externo")
    domain.observation_add(conn, experiment_id=xid, metric="feedback_externo",
                           value="revisor confirma cierre arquitectónico")
    # Cerrar contra el criterio de ÉXITO preregistrado: genera evidencia
    # experiment_result (discriminante) vinculada supports en el mismo acto.
    domain.experiment_complete(conn, experiment_id=xid, outcome="exito",
                               notes="El revisor confirmó el cierre; el diseño "
                               "no dependía de andamio ajeno.")
    domain.reflection_add(conn, experiment_id=xid,
                          question="¿Qué evidencia reabriría esto?",
                          answer="Un diseño propio que colapse ante un revisor "
                          "competente en un dominio nuevo.")

    result = engine.recompute_all(conn)
    return {"seeded": True, "seal": result["seal"],
            "hypotheses": [h_diseno, h_ejecucion],
            "results": result["results"]}
