"""Suite de audit_chain.

El corazón son los controles negativos: cada modo de ataque que el diseño
promete detectar se ejecuta de verdad contra la base y se aserta que el
verificador lo encuentra — y que reporta linkage e integrity POR SEPARADO.
Un verificador nunca visto en rojo no verifica nada.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from compass.audit_chain import (
    GENESIS_PREV,
    AuditChainError,
    append,
    verify_chain,
)
from compass.canonicalize import CanonicalizeError, sha256_utf8
from compass.db import atomic, open_db, utc_now_iso

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture()
def db(tmp_path):
    conn = open_db(tmp_path / "compass.db")
    yield conn
    conn.close()


def _poblar(conn, n=5):
    resultados = []
    for i in range(n):
        resultados.append(
            append(conn, op=f"op_{i}", payload={"i": i, "nota": f"entrada {i}"})
        )
    return resultados


# ---------------------------------------------------------------- génesis --

def test_genesis_unico_y_correcto(db):
    r = append(db, op="inicio", payload={"hola": "mundo"})
    assert r["seq"] == 1
    fila = db.execute("SELECT * FROM audit_chain WHERE seq = 1").fetchone()
    assert fila["prev_hash"] == GENESIS_PREV
    assert r["tail_warning"] is None


def test_cadena_sana_verifica(db):
    _poblar(db)
    reporte = verify_chain(db)
    assert reporte.linkage_ok and reporte.integrity_ok
    assert reporte.issues == []


def test_determinismo_mismos_inputs_mismo_hash(tmp_path):
    ts = "2026-08-27T12:00:00.000000+00:00"
    hashes = []
    for name in ("a.db", "b.db"):
        conn = open_db(tmp_path / name)
        r = append(conn, op="op", payload={"x": [1, "dos"]},
                   content_hashes=[sha256_utf8("contenido")], now=ts)
        hashes.append(r["audit_hash"])
        conn.close()
    assert hashes[0] == hashes[1]


def test_orden_de_content_hashes_irrelevante(tmp_path):
    ts = "2026-08-27T12:00:00.000000+00:00"
    h1, h2 = sha256_utf8("a"), sha256_utf8("b")
    hashes = []
    for name, ch in (("a.db", [h1, h2]), ("b.db", [h2, h1])):
        conn = open_db(tmp_path / name)
        hashes.append(append(conn, op="op", payload=1,
                             content_hashes=ch, now=ts)["audit_hash"])
        conn.close()
    assert hashes[0] == hashes[1]


# ----------------------------------------------------- entradas inválidas --

def test_float_en_payload_rechazado(db):
    with pytest.raises(CanonicalizeError, match="float prohibido"):
        append(db, op="op", payload={"peso": 0.5})
    assert db.execute("SELECT COUNT(*) c FROM audit_chain").fetchone()["c"] == 0


def test_content_hash_invalido_rechazado(db):
    with pytest.raises(AuditChainError, match="content_hash inválido"):
        append(db, op="op", payload=1, content_hashes=["no-es-hex"])


# ------------------------------------------------- controles negativos ----

def test_negativo_edicion_in_place_rompe_integrity_no_linkage(db):
    """Editar un campo hasheado: integrity cae, linkage sigue intacto.

    Esto verifica que los dos chequeos son independientes de verdad:
    colapsarlos en un booleano escondería qué ataque ocurrió.
    """
    _poblar(db)
    db.execute(
        "UPDATE audit_chain SET payload_c14n = '[\"c14n\",1,[\"str\",\"adulterado\"]]' "
        "WHERE seq = 3"
    )
    reporte = verify_chain(db)
    assert reporte.integrity_ok is False
    assert reporte.linkage_ok is True
    assert [i["seq"] for i in reporte.issues] == [3]
    assert reporte.issues[0]["kind"] == "integrity"


def test_negativo_edicion_de_timestamp_detectada(db):
    # Regla: el ts hasheado es el ts almacenado. Cambiarlo rompe la recomputación.
    _poblar(db, 3)
    db.execute("UPDATE audit_chain SET ts = ? WHERE seq = 2", (utc_now_iso(),))
    reporte = verify_chain(db)
    assert reporte.integrity_ok is False
    assert any(i["seq"] == 2 and i["kind"] == "integrity" for i in reporte.issues)


def test_negativo_delecion_del_medio_rompe_linkage(db):
    _poblar(db)
    db.execute("DELETE FROM audit_chain WHERE seq = 3")
    reporte = verify_chain(db)
    assert reporte.linkage_ok is False
    kinds = {i["kind"] for i in reporte.issues}
    assert "gap" in kinds


def test_negativo_reordenamiento_detectado(db):
    """Intercambiar el contenido de dos entradas conservando sus seq."""
    _poblar(db)
    f2 = dict(db.execute("SELECT * FROM audit_chain WHERE seq = 2").fetchone())
    f3 = dict(db.execute("SELECT * FROM audit_chain WHERE seq = 3").fetchone())
    # El swap directo choca con la UNIQUE de audit_hash (defensa en
    # profundidad bienvenida); el atacante lo esquiva con un valor
    # transitorio, así que eso es lo que se simula.
    db.execute(
        "UPDATE audit_chain SET audit_hash = ? WHERE seq = 2", ("f" * 64,)
    )
    for destino, origen in ((3, f2), (2, f3)):
        db.execute(
            "UPDATE audit_chain SET op=?, payload_c14n=?, content_hashes=?, "
            "ts=?, cv=?, prev_hash=?, audit_hash=? WHERE seq=?",
            (origen["op"], origen["payload_c14n"], origen["content_hashes"],
             origen["ts"], origen["cv"], origen["prev_hash"],
             origen["audit_hash"], destino),
        )
    reporte = verify_chain(db)
    assert reporte.ok is False  # integrity (seq hasheado) y/o linkage caen


def test_negativo_reescritura_consistente_de_una_entrada_rompe_el_eslabon(db):
    """Adulterar una entrada RECOMPUTANDO su hash: la entrada queda
    internamente coherente, pero el eslabón siguiente la delata."""
    from compass.audit_chain import _envelope_material, compute_hash
    _poblar(db)
    fila = db.execute("SELECT * FROM audit_chain WHERE seq = 2").fetchone()
    nuevo_payload = '["c14n",1,["str","historia reescrita"]]'
    material = _envelope_material(
        seq=2, op=fila["op"], payload_c14n=nuevo_payload,
        content_hashes=json.loads(fila["content_hashes"]),
        ts=fila["ts"], cv=fila["cv"],
    )
    nuevo_hash = compute_hash(material, fila["prev_hash"])
    db.execute(
        "UPDATE audit_chain SET payload_c14n = ?, audit_hash = ? WHERE seq = 2",
        (nuevo_payload, nuevo_hash),
    )
    reporte = verify_chain(db)
    assert reporte.integrity_ok is True   # la fila 2 recomputa bien...
    assert reporte.linkage_ok is False    # ...pero la 3 ya no encadena con ella
    assert any(i["seq"] == 3 and i["kind"] == "linkage" for i in reporte.issues)


def test_cola_rota_se_reporta_y_no_se_lava(db):
    _poblar(db, 4)
    db.execute("UPDATE audit_chain SET ts = 'adulterado' WHERE seq = 4")
    r = append(db, op="posterior", payload={"nota": "tras el quiebre"})
    # La operación quedó registrada...
    assert r["seq"] == 5
    # ...pero el quiebre fue advertido en el momento...
    assert r["tail_warning"] is not None
    assert any(i["seq"] == 4 for i in r["tail_warning"]["issues"])
    # ...y una verificación completa lo sigue encontrando (no hubo lavado).
    reporte = verify_chain(db)
    assert reporte.integrity_ok is False
    assert any(i["seq"] == 4 for i in reporte.issues)


# ------------------------------------------------------------ atomicidad --

def test_append_participa_en_transaccion_externa(db):
    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom):
        with atomic(db):
            db.execute(
                "INSERT INTO decision_record (title, context, decision, "
                "alternatives, reopen_condition, created_at) "
                "VALUES ('t', 'c', 'd', 'a', 'r', ?)",
                (utc_now_iso(),),
            )
            append(db, op="decision_registrada", payload={"title": "t"})
            raise Boom()
    # Ni la escritura de dominio ni la entrada de la cadena persistieron.
    assert db.execute("SELECT COUNT(*) c FROM decision_record").fetchone()["c"] == 0
    assert db.execute("SELECT COUNT(*) c FROM audit_chain").fetchone()["c"] == 0


# ------------------------------------- verificador externo independiente --

def _correr_verificador(db_path):
    return subprocess.run(
        [sys.executable, str(REPO / "tools" / "verify_chain.py"), str(db_path)],
        capture_output=True, text=True,
    )


def test_verificador_externo_acuerda_en_sano(tmp_path):
    path = tmp_path / "sano.db"
    conn = open_db(path)
    _poblar(conn)
    conn.close()
    out = _correr_verificador(path)
    assert out.returncode == 0
    assert "VERIFICA" in out.stdout


def test_verificador_externo_detecta_quiebre(tmp_path):
    path = tmp_path / "roto.db"
    conn = open_db(path)
    _poblar(conn)
    conn.execute("UPDATE audit_chain SET op = 'otro' WHERE seq = 2")
    conn.commit()
    conn.close()
    out = _correr_verificador(path)
    assert out.returncode == 1
    assert "QUIEBRE DETECTADO" in out.stdout
    assert "integrity" in out.stdout


def test_verificador_externo_detecta_edicion_de_contenido_referenciado(tmp_path):
    """El ataque que un hash de solo-ids no ve: editar la fila referenciada.

    La cadena sella content_hashes; el verificador recomputa el contenido
    vivo contra su hash sellado y encuentra la edición.
    """
    path = tmp_path / "contenido.db"
    conn = open_db(path)
    contenido = '{"texto": "lo que la persona validó"}'
    conn.execute(
        "INSERT INTO evidence (evidence_type, source, content, content_hash, "
        "validated, validated_at, created_at) "
        "VALUES ('self_report', 'test', ?, ?, 1, ?, ?)",
        (contenido, sha256_utf8(contenido), utc_now_iso(), utc_now_iso()),
    )
    append(conn, op="evidence_added", payload={"evidence_id": 1},
           content_hashes=[sha256_utf8(contenido)])
    # Edición posterior del contenido referenciado: la cadena recomputa
    # perfecto, pero el contenido ya no es el que se selló.
    conn.execute("UPDATE evidence SET content = '{\"texto\": \"editado\"}' WHERE id = 1")
    conn.commit()
    conn.close()
    out = _correr_verificador(path)
    assert out.returncode == 1
    assert "content" in out.stdout
