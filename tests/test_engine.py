"""Suite del Confidence Engine.

Oráculos exactos computados A MANO desde la fórmula (independientes del
código): con pesos provisorios v1 y half_saturation=300,

    1 experiment_result a favor: net=180 -> floor(1000·180/480) = 375
    + 1 self_report en contra:   contra=40·3/2=60, net=120
                                 -> floor(1000·120/420) = 285

Más invariantes: permutar el orden de carga no cambia el índice; la
evidencia no validada o borrada no cuenta; descartada es pegajosa;
corroborar exige evidencia discriminante.
"""

import pytest

from compass import domain
from compass.engine import (
    DEFAULT_CONFIG_V1,
    EngineConfigError,
    activate_config,
    load_config,
    recompute_all,
    seed_default_config,
    validate_config,
)
from compass.audit_chain import verify_chain
from compass.db import open_db


@pytest.fixture()
def db(tmp_path):
    conn = open_db(tmp_path / "compass.db")
    seed_default_config(conn)
    yield conn
    conn.close()


def _hyp(conn, statement="pensamiento sistémico"):
    return domain.hypothesis_add(conn, statement=statement, origin="person")


def _ev(conn, tipo="experiment_result", validated=True, n=1):
    ids = []
    for i in range(n):
        ids.append(domain.evidence_add(
            conn, evidence_type=tipo, source="test",
            content={"n": i, "tipo": tipo}, validated=validated,
        ))
    return ids


def _index_of(conn, hid):
    row = conn.execute(
        "SELECT index_value, status FROM hypothesis WHERE id = ?", (hid,)
    ).fetchone()
    return row["index_value"], row["status"]


# ------------------------------------------------------------------ config --

def test_seed_idempotente_y_registrado(db):
    h1 = seed_default_config(db)  # segunda llamada: no duplica
    assert h1 == seed_default_config(db)
    assert db.execute("SELECT COUNT(*) c FROM engine_config").fetchone()["c"] == 1
    dr = db.execute("SELECT * FROM decision_record").fetchone()
    assert "PROVISORIOS" in dr["context"]
    assert "reapertura" in dr["reopen_condition"] or "Auditoría" in dr["reopen_condition"]
    ops = [r["op"] for r in db.execute("SELECT op FROM audit_chain")]
    assert "engine_config_activated" in ops


@pytest.mark.parametrize("romper, match", [
    (lambda c: c.pop("half_saturation"), "faltan"),
    (lambda c: c.update(extra=1), "sobran"),
    (lambda c: c["weights"].update(self_report="0"), "> 0"),
    (lambda c: c["weights"].update(self_report="0.5"), "fracción válida"),
    (lambda c: c.update(contradicts_factor="1/2"), "anti-halago"),
    (lambda c: c.update(activation_threshold=True), "entero 0-1000"),
    (lambda c: c.update(activation_threshold=700), "debe ser <"),
    (lambda c: c.update(corroboration_requires=["astrologia"]), "tipos de evidencia"),
])
def test_config_invalida_rechazada_en_frontera(romper, match):
    import copy
    cfg = copy.deepcopy(DEFAULT_CONFIG_V1)
    romper(cfg)
    with pytest.raises(EngineConfigError, match=match):
        validate_config(cfg)


def test_config_duplicada_rechazada(db):
    with pytest.raises(Exception):
        activate_config(db, DEFAULT_CONFIG_V1)  # v1 ya sembrada por fixture


# ----------------------------------------------------------------- cálculo --

def test_indice_oraculo_exacto_a_mano(db):
    hid = _hyp(db)
    (eid,) = _ev(db, "experiment_result")
    domain.evidence_link(db, hypothesis_id=hid, evidence_id=eid,
                         direction="supports")
    recompute_all(db)
    index, status = _index_of(db, hid)
    assert index == 375          # floor(1000·180/(180+300)), calculado a mano
    assert status == "activa"    # 375 >= 150, < 600


def test_contradiccion_pesa_mas(db):
    hid = _hyp(db)
    (a,) = _ev(db, "experiment_result")
    (b,) = _ev(db, "self_report")
    domain.evidence_link(db, hypothesis_id=hid, evidence_id=a, direction="supports")
    domain.evidence_link(db, hypothesis_id=hid, evidence_id=b, direction="contradicts")
    recompute_all(db)
    index, _ = _index_of(db, hid)
    assert index == 285          # net=180-60=120 -> floor(1000·120/420)


def test_net_negativo_debilitada_indice_cero(db):
    hid = _hyp(db)
    (a,) = _ev(db, "self_report")
    (b,) = _ev(db, "behavioral")
    domain.evidence_link(db, hypothesis_id=hid, evidence_id=a, direction="supports")
    domain.evidence_link(db, hypothesis_id=hid, evidence_id=b, direction="contradicts")
    recompute_all(db)
    index, status = _index_of(db, hid)
    assert index == 0            # net = 40 - 180 < 0
    assert status == "debilitada"


def test_corroborar_exige_evidencia_discriminante(db):
    # Volumen de self-report: índice alto pero JAMÁS corrobora.
    hid = _hyp(db)
    for eid in _ev(db, "self_report", n=23):     # net=920 -> índice 754
        domain.evidence_link(db, hypothesis_id=hid, evidence_id=eid,
                             direction="supports")
    recompute_all(db)
    index, status = _index_of(db, hid)
    assert index == 754 and status == "activa"   # >= 600 pero sin discriminante
    # Un solo experimento discriminante cambia el estado.
    (xe,) = _ev(db, "experiment_result")
    domain.evidence_link(db, hypothesis_id=hid, evidence_id=xe,
                         direction="supports")
    recompute_all(db)
    _, status = _index_of(db, hid)
    assert status == "corroborada"


def test_no_validada_y_tombstone_no_cuentan(db):
    hid = _hyp(db)
    (sin_validar,) = _ev(db, "outcome_external", validated=False)
    (viva,) = _ev(db, "self_report")
    (borrada,) = _ev(db, "outcome_external")
    for eid in (sin_validar, viva, borrada):
        domain.evidence_link(db, hypothesis_id=hid, evidence_id=eid,
                             direction="supports")
    domain.evidence_tombstone(db, borrada, "test de borrado")
    recompute_all(db)
    index, _ = _index_of(db, hid)
    assert index == 117          # solo la self_report viva: floor(1000·40/340)
    # weight_applied de los vínculos que no cuentan queda en NULL.
    rows = {r["evidence_id"]: r["weight_applied"] for r in db.execute(
        "SELECT evidence_id, weight_applied FROM hypothesis_evidence"
    )}
    assert rows[viva] == "40"
    assert rows[sin_validar] is None and rows[borrada] is None


def test_weight_applied_con_signo_para_contradicts(db):
    hid = _hyp(db)
    (b,) = _ev(db, "self_report")
    domain.evidence_link(db, hypothesis_id=hid, evidence_id=b,
                         direction="contradicts")
    recompute_all(db)
    w = db.execute(
        "SELECT weight_applied FROM hypothesis_evidence WHERE evidence_id = ?",
        (b,),
    ).fetchone()["weight_applied"]
    assert w == "-60"            # -40 · 3/2


def test_descartada_es_pegajosa(db):
    hid = _hyp(db)
    (eid,) = _ev(db, "outcome_external")
    domain.evidence_link(db, hypothesis_id=hid, evidence_id=eid,
                         direction="supports")
    domain.hypothesis_discard(db, hid, "no me interesa este camino")
    recompute_all(db)
    index, status = _index_of(db, hid)
    assert status == "descartada"        # el engine no la resucita
    assert index == 454                  # floor(1000·250/550): el índice se
                                         # calcula igual, el estado no cambia
    domain.hypothesis_reactivate(db, hid)
    recompute_all(db)
    _, status = _index_of(db, hid)
    assert status == "activa"            # la persona la reactivó; la evidencia manda


def test_determinismo_y_permutacion_metamorfica(db):
    # Mismo conjunto de evidencia, cargado en órdenes distintos, en dos
    # hipótesis: mismo índice. Y recompute dos veces: mismo seal.
    h1, h2 = _hyp(db, "h uno"), _hyp(db, "h dos")
    tipos = ["self_report", "behavioral", "experiment_result"]
    for hid, orden in ((h1, tipos), (h2, list(reversed(tipos)))):
        for t in orden:
            (eid,) = _ev(db, t)
            domain.evidence_link(db, hypothesis_id=hid, evidence_id=eid,
                                 direction="supports")
    r1 = recompute_all(db)
    idx = {r["hypothesis_id"]: r["index"] for r in r1["results"]}
    assert idx[h1] == idx[h2]
    r2 = recompute_all(db)
    assert r1["seal"] == r2["seal"]      # bit a bit, dos corridas


def test_recompute_sella_en_la_cadena_y_verifica(db):
    hid = _hyp(db)
    (eid,) = _ev(db)
    domain.evidence_link(db, hypothesis_id=hid, evidence_id=eid,
                         direction="supports")
    recompute_all(db)
    ops = [r["op"] for r in db.execute("SELECT op FROM audit_chain")]
    assert "recompute" in ops
    assert verify_chain(db).ok


def test_recompute_sin_config_falla_claro(tmp_path):
    conn = open_db(tmp_path / "sin_config.db")
    with pytest.raises(EngineConfigError, match="no hay config"):
        load_config(conn)
    conn.close()
