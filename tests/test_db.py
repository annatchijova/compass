"""Suite de db: versionado de esquema, constraints con dientes y atomicidad.

Los tests de constraints son controles negativos por diseño: insertan lo
que el esquema promete rechazar y asertan el rechazo. Si alguien borra un
CHECK o el PRAGMA de foreign keys, esto se pone rojo.
"""

import sqlite3

import pytest

from compass.db import (
    SCHEMA_VERSION,
    FutureSchemaError,
    atomic,
    open_db,
    utc_now_iso,
)


@pytest.fixture()
def db(tmp_path):
    conn = open_db(tmp_path / "compass.db")
    yield conn
    conn.close()


def _insert_hypothesis(conn, statement="hipótesis de prueba"):
    cur = conn.execute(
        "INSERT INTO hypothesis (statement, origin, created_at) "
        "VALUES (?, 'person', ?)",
        (statement, utc_now_iso()),
    )
    return cur.lastrowid


def _insert_evidence(conn, content='{"texto": "dato"}'):
    from compass.canonicalize import sha256_utf8
    cur = conn.execute(
        "INSERT INTO evidence (evidence_type, source, content, content_hash, "
        "created_at) VALUES ('self_report', 'test', ?, ?, ?)",
        (content, sha256_utf8(content), utc_now_iso()),
    )
    return cur.lastrowid


def test_crea_esquema_v1(db):
    version = db.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    assert int(version["value"]) == SCHEMA_VERSION == 1
    tablas = {
        r["name"]
        for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {
        "meta", "person", "evidence", "hypothesis", "hypothesis_evidence",
        "experiment", "observation", "reflection", "engine_config",
        "decision_record", "audit_chain",
    } <= tablas


def test_reabrir_es_idempotente(tmp_path):
    path = tmp_path / "compass.db"
    open_db(path).close()
    conn = open_db(path)  # segunda apertura: no debe intentar re-migrar
    assert conn.execute("SELECT COUNT(*) c FROM meta").fetchone()["c"] >= 2
    conn.close()


def test_wal_activado(db):
    assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_version_futura_rechazada_con_mensaje(tmp_path):
    path = tmp_path / "futura.db"
    conn = open_db(path)
    conn.execute("UPDATE meta SET value = '999' WHERE key = 'schema_version'")
    conn.close()
    with pytest.raises(FutureSchemaError, match="schema_version=999"):
        open_db(path)


def test_foreign_keys_con_dientes(db):
    # Vincular evidencia inexistente a hipótesis inexistente debe fallar.
    # Si alguien quita el PRAGMA foreign_keys, este test se pone rojo.
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO hypothesis_evidence "
            "(hypothesis_id, evidence_id, direction) VALUES (999, 999, 'supports')"
        )


def test_preregistro_forzado_por_esquema(db):
    # Un experimento sin criterio de fracaso no puede existir (§4).
    hid = _insert_hypothesis(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO experiment (hypothesis_id, design, success_criterion, "
            "failure_criterion, preregistered_at) VALUES (?, 'd', 's', NULL, ?)",
            (hid, utc_now_iso()),
        )


def test_experimento_no_puede_ser_su_propio_rival(db):
    hid = _insert_hypothesis(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO experiment (hypothesis_id, design, success_criterion, "
            "failure_criterion, rival_hypothesis_id, preregistered_at) "
            "VALUES (?, 'd', 's', 'f', ?, ?)",
            (hid, hid, utc_now_iso()),
        )


def test_tombstone_coherente_forzado(db):
    # deleted=1 exige content NULL y deleted_at presente; y viceversa.
    from compass.canonicalize import sha256_utf8
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO evidence (evidence_type, source, content, content_hash, "
            "created_at, deleted, deleted_at) "
            "VALUES ('self_report', 't', '{\"x\":1}', ?, ?, 1, ?)",
            (sha256_utf8('{"x":1}'), utc_now_iso(), utc_now_iso()),
        )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO evidence (evidence_type, source, content, content_hash, "
            "created_at, deleted) VALUES ('self_report', 't', NULL, ?, ?, 0)",
            (sha256_utf8(""), utc_now_iso()),
        )


def test_indice_e_engine_version_van_juntos(db):
    # Un índice sin versión de engine (o al revés) es un cálculo sin procedencia.
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO hypothesis (statement, origin, index_value, created_at) "
            "VALUES ('h', 'person', 500, ?)",
            (utc_now_iso(),),
        )


def test_metrica_de_observacion_restringida(db):
    hid = _insert_hypothesis(db)
    db.execute(
        "INSERT INTO experiment (hypothesis_id, design, success_criterion, "
        "failure_criterion, preregistered_at) VALUES (?, 'd', 's', 'f', ?)",
        (hid, utc_now_iso()),
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO observation (experiment_id, metric, value, recorded_at) "
            "VALUES (1, 'learning_velocity', 'alta', ?)",
            (utc_now_iso(),),
        )


def test_atomic_rollback_total(db):
    # Excepción a mitad de una operación lógica: nada queda escrito.
    class Boom(RuntimeError):
        pass

    antes = db.execute("SELECT COUNT(*) c FROM hypothesis").fetchone()["c"]
    with pytest.raises(Boom):
        with atomic(db):
            _insert_hypothesis(db, "primera")
            _insert_hypothesis(db, "segunda")
            raise Boom()
    despues = db.execute("SELECT COUNT(*) c FROM hypothesis").fetchone()["c"]
    assert despues == antes
    assert not db.in_transaction  # nada quedó a medio abrir


def test_atomic_reentrante(db):
    with atomic(db):
        with atomic(db):  # participa, no anida BEGIN
            _insert_hypothesis(db)
    assert db.execute("SELECT COUNT(*) c FROM hypothesis").fetchone()["c"] == 1
