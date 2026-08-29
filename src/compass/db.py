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
import time
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


def _statements(script: str) -> list[str]:
    """Parte un script DDL en sentencias completas.

    `executescript` NO sirve dentro de una transacción: emite un COMMIT
    implícito antes de correr el script, lo que soltaba el write lock que
    `atomic()` había tomado y dejaba una ventana donde otra conexión veía
    la tabla `meta` sin su fila schema_version (base a medio crear).
    `sqlite3.complete_statement` corta como corta SQLite, así que un
    punto y coma dentro de un literal no termina la sentencia.
    """
    stmts: list[str] = []
    buf = ""
    for line in script.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            stmts.append(buf.strip())
            buf = ""
    # Lo que sobra solo puede ser espacio o comentarios; una sentencia sin
    # cerrar es un error del esquema, no algo para ignorar en silencio.
    resto = "\n".join(
        ln for ln in buf.splitlines()
        if ln.strip() and not ln.strip().startswith("--")
    )
    if resto:
        raise SchemaError(f"sentencia DDL sin cerrar en el esquema: {resto[:60]!r}")
    return stmts


def _run_script(conn: sqlite3.Connection, script: str) -> None:
    for stmt in _statements(script):
        conn.execute(stmt)


def _migrate_to_v1(conn: sqlite3.Connection) -> None:
    _run_script(conn, _SCHEMA_V1)
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
    _run_script(conn, _SCHEMA_V2)


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
    def _reject_future(v: int) -> None:
        if v > SCHEMA_VERSION:
            raise FutureSchemaError(
                f"la base declara schema_version={v} pero este código "
                f"conoce hasta {SCHEMA_VERSION}; actualizá el software antes "
                "de abrir esta base (no se abre en modo best-effort)"
            )

    version = _stored_version(conn)
    _reject_future(version)
    if version == SCHEMA_VERSION:
        return version              # nada que migrar: no se toma write lock

    # Migrar: primero el write lock, y RECIÉN adentro se relee la versión.
    # Dos conexiones que abren la misma base nueva leen ambas version=0; sin
    # la relectura, la perdedora repetía una migración que la ganadora ya
    # había commiteado ("table meta already exists"). Toda la cadena va en
    # UNA transacción: o la base queda en SCHEMA_VERSION, o no cambia.
    with atomic(conn):
        version = _stored_version(conn)
        _reject_future(version)
        while version < SCHEMA_VERSION:
            target = version + 1
            migrator = MIGRATIONS.get(target)
            if migrator is None:
                raise SchemaError(f"no hay migrador registrado hacia v{target}")
            migrator(conn)
            if target > 1:
                conn.execute(
                    "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                    (str(target),),
                )
            version = target
    return version


def _journal_mode(conn: sqlite3.Connection) -> str:
    return str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()


def _ensure_wal(conn: sqlite3.Connection, timeout_s: float = 5.0) -> None:
    """Deja el archivo en WAL, tolerando que otra conexión llegue primero.

    Cambiar journal_mode necesita un lock exclusivo momentáneo, y a
    diferencia de una escritura común NO lo espera vía busy_timeout: si
    varias conexiones abren la misma base recién creada a la vez, todas
    menos una reciben "database is locked" y ninguna la ve todavía en WAL.
    Lo que importa es el estado FINAL del archivo, así que se reintenta
    dentro del mismo presupuesto que busy_timeout y se verifica el
    resultado. Si al vencer sigue sin quedar en WAL, el error sube: correr
    en otro journal_mode es una degradación que se declara, no se tapa.
    """
    last: sqlite3.OperationalError | None = None
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError as exc:
            last = exc
        if _journal_mode(conn) == "wal":
            return
        if time.monotonic() >= deadline:
            raise last or SchemaError(
                "no se pudo dejar la base en WAL y no quedó en WAL"
            )
        time.sleep(0.005)


def open_db(path: str | Path) -> sqlite3.Connection:
    """Abrir (o crear) una base COMPASS lista para usar.

    WAL se fija acá una única vez: es una propiedad persistente del
    archivo, no de la conexión.
    """
    creating = not Path(path).exists()
    conn = connect(path)
    if creating:
        _ensure_wal(conn)
    ensure_schema(conn)
    return conn
