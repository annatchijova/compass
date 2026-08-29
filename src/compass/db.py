"""Base de datos de COMPASS: conexión, esquema v1 y migraciones.

Disciplinas aplicadas:
- Esquema versionado desde el día uno (tabla meta.schema_version).
  El loader detecta la versión y decide deliberadamente: actual → abrir;
  vieja → migrar hacia adelante por cadena de migradores; futura →
  rechazar con error claro (nunca cargar silenciosamente un formato
  que este código no conoce).
- Higiene de concurrencia: WAL (propiedad persistente, se fija al crear
  el archivo), busy_timeout y foreign_keys en cada conexión.
- atomic(): BEGIN IMMEDIATE — el write lock se toma al inicio de la
  operación lógica, no en la primera escritura, para que leer-y-mutar
  sea una unidad indivisible. Commit único al final, rollback ante
  cualquier excepción. Reentrante: si ya hay transacción abierta,
  participa en ella (el dueño externo decide el commit).

El preregistro de experimentos (design doc §4) está forzado por esquema:
success_criterion y failure_criterion son NOT NULL. Un experimento sin
criterio de fracaso no puede existir en la base.

El tombstone de evidencia (design doc §6) está forzado por CHECK:
deleted=1 exige content IS NULL y viceversa. Borrar contenido deja el
hueco visible; el content_hash y la cadena de auditoría lo recuerdan.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

SCHEMA_VERSION = 2

EVIDENCE_TYPES = (
    "self_report",
    "narrative_extracted",
    "behavioral",
    "experiment_result",
    "outcome_external",
)

HYPOTHESIS_STATUSES = ("latente", "activa", "corroborada", "debilitada", "descartada")

EXPERIMENT_STATUSES = ("preregistrado", "en_curso", "completado", "abandonado")

# Únicas métricas observables sin instrumentación mágica (design doc §5).
OBSERVATION_METRICS = (
    "completitud",
    "tiempo_voluntario",
    "retorno_espontaneo",
    "autoeval",
    "feedback_externo",
)


class SchemaError(RuntimeError):
    """Problema de versión o forma del esquema."""


class FutureSchemaError(SchemaError):
    """La base fue escrita por un esquema más nuevo que este código."""


def utc_now_iso() -> str:
    """Timestamp UTC ISO 8601 con microsegundos. Capturarlo UNA vez por uso."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def connect(path: str | Path) -> sqlite3.Connection:
    """Conexión con higiene aplicada. No crea ni migra el esquema."""
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def atomic(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Transacción todo-o-nada con lock de escritura tomado de entrada.

    Reentrante: dentro de una transacción existente participa sin abrir
    otra; el commit/rollback queda a cargo del dueño externo.
    """
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()


# ---------------------------------------------------------------------------
# Esquema v1
# ---------------------------------------------------------------------------

def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


_SCHEMA_V1 = f"""
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE person (
    id           INTEGER PRIMARY KEY CHECK (id = 1),  -- single-user en MVP
    display_name TEXT NOT NULL,
    created_at   TEXT NOT NULL
) STRICT;

CREATE TABLE evidence (
    id            INTEGER PRIMARY KEY,
    evidence_type TEXT NOT NULL CHECK (evidence_type IN ({_in_list(EVIDENCE_TYPES)})),
    source        TEXT NOT NULL,
    content       TEXT,                    -- JSON estructurado; NULL solo si tombstone
    content_hash  TEXT NOT NULL CHECK (length(content_hash) = 64),
    validated     INTEGER NOT NULL DEFAULT 0 CHECK (validated IN (0, 1)),
    validated_at  TEXT,
    created_at    TEXT NOT NULL,
    deleted       INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0, 1)),
    deleted_at    TEXT,
    CHECK ((deleted = 0 AND content IS NOT NULL AND deleted_at IS NULL)
        OR (deleted = 1 AND content IS NULL AND deleted_at IS NOT NULL))
) STRICT;
CREATE INDEX idx_evidence_created ON evidence (created_at);
CREATE INDEX idx_evidence_type ON evidence (evidence_type);

CREATE TABLE hypothesis (
    id             INTEGER PRIMARY KEY,
    statement      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'latente'
                   CHECK (status IN ({_in_list(HYPOTHESIS_STATUSES)})),
    origin         TEXT NOT NULL CHECK (origin IN ('person', 'llm_abductor')),
    index_value    INTEGER CHECK (index_value BETWEEN 0 AND 1000),
    engine_version TEXT,                   -- versión del engine del último cálculo
    created_at     TEXT NOT NULL,
    CHECK ((index_value IS NULL) = (engine_version IS NULL))
) STRICT;
CREATE INDEX idx_hypothesis_status ON hypothesis (status);

CREATE TABLE hypothesis_evidence (
    hypothesis_id  INTEGER NOT NULL REFERENCES hypothesis (id),
    evidence_id    INTEGER NOT NULL REFERENCES evidence (id),
    direction      TEXT NOT NULL CHECK (direction IN ('supports', 'contradicts')),
    weight_applied TEXT,                   -- Fraction "num/den" del último cálculo
    PRIMARY KEY (hypothesis_id, evidence_id)
) STRICT;

CREATE TABLE experiment (
    id                  INTEGER PRIMARY KEY,
    hypothesis_id       INTEGER NOT NULL REFERENCES hypothesis (id),
    design              TEXT NOT NULL,
    success_criterion   TEXT NOT NULL,     -- preregistro obligatorio (§4):
    failure_criterion   TEXT NOT NULL,     -- sin criterio de fracaso no hay experimento
    rival_hypothesis_id INTEGER REFERENCES hypothesis (id),
    duration            TEXT,
    status              TEXT NOT NULL DEFAULT 'preregistrado'
                        CHECK (status IN ({_in_list(EXPERIMENT_STATUSES)})),
    preregistered_at    TEXT NOT NULL,
    completed_at        TEXT,
    CHECK (rival_hypothesis_id IS NULL OR rival_hypothesis_id <> hypothesis_id)
) STRICT;

CREATE TABLE observation (
    id            INTEGER PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES experiment (id),
    metric        TEXT NOT NULL CHECK (metric IN ({_in_list(OBSERVATION_METRICS)})),
    value         TEXT NOT NULL,
    recorded_at   TEXT NOT NULL
) STRICT;

CREATE TABLE reflection (
    id            INTEGER PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES experiment (id),
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    recorded_at   TEXT NOT NULL
) STRICT;

CREATE TABLE engine_config (
    engine_version TEXT PRIMARY KEY,
    config         TEXT NOT NULL,          -- JSON; pesos como Fraction "num/den"
    config_hash    TEXT NOT NULL CHECK (length(config_hash) = 64),
    activated_at   TEXT NOT NULL
) STRICT;

CREATE TABLE decision_record (
    id               INTEGER PRIMARY KEY,
    title            TEXT NOT NULL,
    context          TEXT NOT NULL,
    decision         TEXT NOT NULL,
    alternatives     TEXT NOT NULL,        -- rechazadas y por qué
    reopen_condition TEXT NOT NULL,        -- qué evidencia reabriría la decisión
    created_at       TEXT NOT NULL
) STRICT;

CREATE TABLE audit_chain (
    seq            INTEGER PRIMARY KEY,    -- asignado explícitamente: last + 1
    op             TEXT NOT NULL,
    payload_c14n   TEXT NOT NULL,          -- string canónico exacto que se hasheó
    content_hashes TEXT NOT NULL,          -- JSON array de sha256 hex, ordenado
    ts             TEXT NOT NULL,          -- capturado una vez: hasheado = almacenado
    cv             INTEGER NOT NULL,       -- CANONICALIZE_VERSION del sobre
    prev_hash      TEXT NOT NULL CHECK (length(prev_hash) = 64),
    audit_hash     TEXT NOT NULL UNIQUE CHECK (length(audit_hash) = 64)
) STRICT;
"""


# ---------------------------------------------------------------------------
# Esquema v2: trayectorias (design doc §5, §7). Una trayectoria es un conjunto
# de capacidades-requisito verificables; cada requisito referencia la hipótesis
# (capacidad) que exige. El fit se proyecta determinísticamente del estado
# sellado de esas hipótesis — sin porcentajes de destino. Aditivo: no toca
# ninguna tabla v1, así que los datos v1 cargan intactos.
# ---------------------------------------------------------------------------

_SCHEMA_V2 = """
CREATE TABLE trajectory (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
) STRICT;

CREATE TABLE trajectory_requirement (
    id            INTEGER PRIMARY KEY,
    trajectory_id INTEGER NOT NULL REFERENCES trajectory (id),
    hypothesis_id INTEGER NOT NULL REFERENCES hypothesis (id),
    label         TEXT NOT NULL,   -- descripción humana de la capacidad exigida
    created_at    TEXT NOT NULL,
    UNIQUE (trajectory_id, hypothesis_id)
) STRICT;
CREATE INDEX idx_treq_trajectory ON trajectory_requirement (trajectory_id);
CREATE INDEX idx_treq_hypothesis ON trajectory_requirement (hypothesis_id);
"""


def _migrate_to_v1(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_V1)
    conn.execute(
        # Cada migrador fija SU versión de destino (1), no la global
        # SCHEMA_VERSION: acoplarlo a la global rompía la cadena de migración
        # al subir de versión. La cadena en ensure_schema actualiza el resto.
        "INSERT INTO meta (key, value) VALUES ('schema_version', '1')",
    )
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('created_at', ?)",
        (utc_now_iso(),),
    )


# Cadena de migradores: un paso por versión. v1 -> v2 se registrará acá
# cuando exista, y el loader los aplicará en secuencia. Los datos
# guardados por v1 deben cargar en v5.
def _migrate_to_v2(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_V2)


MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _migrate_to_v1,
    2: _migrate_to_v2,
}


def _stored_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'meta'"
    ).fetchone()
    if row is None:
        return 0
    got = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    if got is None:
        raise SchemaError(
            "existe la tabla meta pero no registra schema_version: "
            "base corrupta o escrita por un productor desconocido"
        )
    return int(got["value"])


def ensure_schema(conn: sqlite3.Connection) -> int:
    """Detecta la versión almacenada y migra hacia adelante si hace falta.

    Devuelve la versión final. Rechaza versiones futuras: los campos de
    un esquema que este código no conoce pueden no significar lo que
    este código asume.
    """
    version = _stored_version(conn)
    if version > SCHEMA_VERSION:
        raise FutureSchemaError(
            f"la base declara schema_version={version} pero este código "
            f"conoce hasta {SCHEMA_VERSION}; actualizá el software antes "
            "de abrir esta base (no se abre en modo best-effort)"
        )
    while version < SCHEMA_VERSION:
        target = version + 1
        migrator = MIGRATIONS.get(target)
        if migrator is None:
            raise SchemaError(f"no hay migrador registrado hacia v{target}")
        with atomic(conn):
            migrator(conn)
            if target > 1:
                conn.execute(
                    "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                    (str(target),),
                )
        version = target
    return version


def open_db(path: str | Path) -> sqlite3.Connection:
    """Abrir (o crear) una base COMPASS lista para usar.

    WAL se fija acá una única vez: es una propiedad persistente del
    archivo, no de la conexión.
    """
    creating = not Path(path).exists()
    conn = connect(path)
    if creating:
        conn.execute("PRAGMA journal_mode = WAL")
    ensure_schema(conn)
    return conn
