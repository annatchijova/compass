"""Suite de dominio y vistas: el ciclo experimento -> evidencia, las
reglas del siguiente paso en orden, el ABSTAIN, y el orden inviolable
seal -> resumen -> narrador."""

import pytest

from compass import domain, views
from compass.canonicalize import seal, sha256_utf8
from compass.db import open_db
from compass.domain import DomainError
from compass.engine import seed_default_config
from compass.llm import FakeBackend, Narrator


@pytest.fixture()
def db(tmp_path):
    conn = open_db(tmp_path / "compass.db")
    seed_default_config(conn)
    yield conn
    conn.close()


def _hyp(conn, statement="hipótesis"):
    return domain.hypothesis_add(conn, statement=statement, origin="person")


def _exp(conn, hid):
    return domain.experiment_preregister(
        conn, hypothesis_id=hid, design="visualizar un concepto complejo",
        success_criterion="lo termina y quiere seguir",
        failure_criterion="lo abandona antes de 10 minutos",
    )


# ----------------------------------------------------------------- dominio --

def test_experimento_exitoso_genera_evidencia_supports(db):
    hid = _hyp(db)
    xid = _exp(db, hid)
    domain.experiment_start(db, xid)
    eid = domain.experiment_complete(db, experiment_id=xid, outcome="exito")
    link = db.execute(
        "SELECT direction FROM hypothesis_evidence WHERE evidence_id = ?",
        (eid,),
    ).fetchone()
    assert link["direction"] == "supports"
    ev = db.execute("SELECT * FROM evidence WHERE id = ?", (eid,)).fetchone()
    assert ev["evidence_type"] == "experiment_result" and ev["validated"] == 1
    assert "lo termina y quiere seguir" in ev["content"]  # criterio preregistrado


def test_experimento_fracasado_genera_evidencia_contradicts(db):
    hid = _hyp(db)
    xid = _exp(db, hid)
    eid = domain.experiment_complete(db, experiment_id=xid, outcome="fracaso")
    link = db.execute(
        "SELECT direction FROM hypothesis_evidence WHERE evidence_id = ?",
        (eid,),
    ).fetchone()
    assert link["direction"] == "contradicts"


def test_experimento_inconcluso_no_genera_evidencia(db):
    hid = _hyp(db)
    xid = _exp(db, hid)
    assert domain.experiment_complete(db, experiment_id=xid,
                                      outcome="inconcluso") is None
    assert db.execute("SELECT COUNT(*) c FROM evidence").fetchone()["c"] == 0


def test_transiciones_invalidas(db):
    hid = _hyp(db)
    xid = _exp(db, hid)
    domain.experiment_complete(db, experiment_id=xid, outcome="exito")
    with pytest.raises(DomainError, match="no se completa"):
        domain.experiment_complete(db, experiment_id=xid, outcome="exito")
    with pytest.raises(DomainError, match="transición inválida"):
        domain.experiment_start(db, xid)


def test_metrica_no_medible_rechazada(db):
    hid = _hyp(db)
    xid = _exp(db, hid)
    with pytest.raises(DomainError, match="instrumentación mágica"):
        domain.observation_add(db, experiment_id=xid,
                               metric="learning_velocity", value="alta")


def test_borrar_y_descartar_exigen_razon(db):
    hid = _hyp(db)
    eid = domain.evidence_add(db, evidence_type="self_report", source="p",
                              content={"x": 1}, validated=True)
    with pytest.raises(DomainError, match="razón"):
        domain.evidence_tombstone(db, eid, "   ")
    with pytest.raises(DomainError, match="razón"):
        domain.hypothesis_discard(db, hid, "")


def test_reflexion_registra_hashes_no_contenido(db):
    # La reflexión puede ser íntima: la cadena registra QUE ocurrió (hashes),
    # el contenido queda solo en la tabla, borrable con tombstone futuro.
    hid = _hyp(db)
    xid = _exp(db, hid)
    domain.reflection_add(db, experiment_id=xid,
                          question="¿qué te aburrió?", answer="nada")
    fila = db.execute(
        "SELECT payload_c14n FROM audit_chain WHERE op = 'reflection_added'"
    ).fetchone()
    assert "¿qué te aburrió?" not in fila["payload_c14n"]
    assert sha256_utf8("¿qué te aburrió?") in fila["payload_c14n"]


# ------------------------------------------------------------------ vistas --

def test_next_step_reglas_en_orden(db):
    # 5) ABSTAIN con la base vacía.
    assert views.next_step(db)["kind"] == "abstain"
    # 4) hipótesis activa sin experimento completado.
    hid = _hyp(db)
    eid = domain.evidence_add(db, evidence_type="experiment_result", source="t",
                              content={"x": 1}, validated=True)
    domain.evidence_link(db, hypothesis_id=hid, evidence_id=eid,
                         direction="supports")
    from compass.engine import recompute_all
    recompute_all(db)
    paso = views.next_step(db)
    assert paso["kind"] == "diseñar_experimento" and paso["hypothesis_id"] == hid
    # 3) evidencia sin validar le gana a la regla 4.
    pend = domain.evidence_add(db, evidence_type="narrative_extracted",
                               source="extractor", content={"señal": "x"},
                               validated=False)
    assert views.next_step(db)["kind"] == "validar_evidencia"
    domain.evidence_validate(db, pend)
    # 2) experimento preregistrado le gana a todo lo anterior.
    xid = _exp(db, hid)
    paso = views.next_step(db)
    assert paso["kind"] == "ejecutar_experimento" and paso["experiment_id"] == xid
    # 1) experimento en curso le gana al preregistrado.
    xid2 = _exp(db, hid)
    domain.experiment_start(db, xid)
    paso = views.next_step(db)
    assert paso["kind"] == "completar_experimento" and paso["experiment_id"] == xid


def test_estado_solo_muestra_no_latentes(db):
    _hyp(db, "latente sin evidencia")
    state = views.compass_state(db)
    assert state["hypotheses"] == []
    assert state["hypothesis_counts"].get("latente") == 1


def test_sealed_state_estable_y_sensible(db):
    s1 = views.sealed_state(db)
    s2 = views.sealed_state(db)
    assert s1["seal"] == s2["seal"]              # estable sin cambios
    assert s1["seal"] == seal(s2["state"])       # recomputable por un tercero
    _hyp(db)
    assert views.sealed_state(db)["seal"] != s1["seal"]  # sensible al cambio


def test_narrar_sella_antes_y_registra_junto_no_dentro(db):
    _hyp(db)
    backend = FakeBackend("El estado está sellado; este texto solo lo narra.")
    out = views.narrate_compass(db, Narrator(backend))
    # El seal es recomputable desde el estado actual: la prosa no participa.
    assert out["seal"] == views.sealed_state(db)["seal"]
    # El narrador RECIBIÓ el seal en su entrada: prueba de que el sellado
    # ocurrió antes de invocar al modelo, no después.
    assert out["seal"] in backend.calls[0][1]
    # El resumen que vio el modelo es el comprimido, con el seal adentro.
    assert out["summary"]["state_seal"] == out["seal"]
    assert "hypotheses" not in out["summary"]    # recibe top_hypotheses, no todo
    # La cadena registró prosa JUNTO al seal, por hash, nunca el texto.
    fila = db.execute(
        "SELECT payload_c14n FROM audit_chain WHERE op = 'narrated'"
    ).fetchone()
    assert out["seal"] in fila["payload_c14n"]
    assert sha256_utf8(out["prose"]) in fila["payload_c14n"]
    assert out["prose"] not in fila["payload_c14n"]


def test_backend_intercambiable_no_cambia_numeros(db):
    # El test arquitectónico de llm-out-of-the-loop: cambiar el narrador
    # cambia la prosa y nada más.
    hid = _hyp(db)
    eid = domain.evidence_add(db, evidence_type="behavioral", source="t",
                              content={"x": 1}, validated=True)
    domain.evidence_link(db, hypothesis_id=hid, evidence_id=eid,
                         direction="supports")
    from compass.engine import recompute_all
    recompute_all(db)
    a = views.narrate_compass(db, Narrator(FakeBackend("narración A")))
    b = views.narrate_compass(db, Narrator(FakeBackend("otra narración B")))
    assert a["prose"] != b["prose"]
    assert a["seal"] == b["seal"]
    assert a["summary"]["top_hypotheses"] == b["summary"]["top_hypotheses"]
