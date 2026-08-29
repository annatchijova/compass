"""Per-user persistence for the hosted COMPASS: one isolated SQLite base
per user id, snapshotted to Google Cloud Storage after every write.

Why this shape, and not a mounted bucket or a rewrite to Firestore:

- The whole deterministic core (sealed engine, hash-chained ledger, the
  independent verifier) is SQLite. Keeping SQLite intact means the sealing
  and verification guarantees are untouched — the multi-user layer is
  strictly additive.
- SQLite over a GCS-FUSE mount is unreliable (SQLite does many small random
  writes; object stores rewrite whole files on close). So the base lives on
  the container's LOCAL disk (WAL works, POSIX locking works) and is
  snapshotted to GCS as a single self-contained file after each write, and
  restored on first access. Each user's base is tiny (KBs), so a full-file
  snapshot is cheap and simple — no WAL-shipping machinery.

Isolation: the user id is validated against a strict allowlist before it
ever touches a path (no traversal). An unknown/blank id is rejected at the
API boundary, not guessed.

Honest degradation (design doc §5.3): if no bucket is configured, or GCS is
unreachable, the service keeps working on local disk and says so — a write
that cannot be persisted is logged, never silently dropped, and the
in-instance result is still returned. `/health` reports the persistence
mode.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get("COMPASS_DATA_DIR", "/tmp/compass-data")
GCS_BUCKET = os.environ.get("COMPASS_GCS_BUCKET")  # sin gs://; None = solo local

# Un id de usuario es una etiqueta opaca elegida por el cliente (session id
# de localStorage, o uno fijado por la persona). Allowlist estricta: nada
# que pueda salir del directorio de datos ni nombrar otro archivo.
_UID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

DEMO_UID = "demo"  # la brújula vitrina, sembrada con el escenario de ejemplo


class InvalidUserId(ValueError):
    pass


def valid_uid(uid: str) -> bool:
    return isinstance(uid, str) and bool(_UID_RE.match(uid))


def require_uid(uid: str) -> str:
    if not valid_uid(uid):
        raise InvalidUserId(
            "compass id inválido: solo [A-Za-z0-9_-], 1 a 64 caracteres"
        )
    return uid


def local_path(uid: str) -> str:
    require_uid(uid)
    return os.path.join(DATA_DIR, f"compass_{uid}.db")


def _blob_name(uid: str) -> str:
    return f"compass_{uid}.db"


def _bucket():
    """Cliente GCS perezoso; None si no hay bucket o falta el SDK."""
    if not GCS_BUCKET:
        return None
    try:
        from google.cloud import storage
    except ImportError:  # pragma: no cover - depende del entorno
        logger.warning("COMPASS_GCS_BUCKET set but google-cloud-storage is "
                       "not installed; running local-only (ephemeral).")
        return None
    try:
        return storage.Client().bucket(GCS_BUCKET)
    except Exception as exc:  # credenciales/red: degradar, no romper
        logger.warning("GCS bucket unreachable (%s); running local-only.", exc)
        return None


def ensure_local(uid: str) -> str:
    """Devuelve la ruta local de la base del usuario, restaurándola desde GCS
    si no existe localmente. No crea el esquema (lo hace open_db)."""
    path = local_path(uid)
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    if os.path.exists(path):
        return path
    bucket = _bucket()
    if bucket is not None:
        blob = bucket.blob(_blob_name(uid))
        try:
            if blob.exists():
                blob.download_to_filename(path)
                logger.info("restored %s from gs://%s/%s",
                            uid, GCS_BUCKET, _blob_name(uid))
        except Exception as exc:  # restore falla: arrancar limpio, avisar
            logger.warning("could not restore %s from GCS (%s); starting fresh.",
                           uid, exc)
    return path


def snapshot(uid: str) -> bool:
    """Consolida el WAL en el archivo principal y sube UN archivo self-contained
    a GCS. Devuelve True si persistió, False si degradó a local. Nunca lanza:
    una falla de persistencia no debe destruir el resultado ya calculado."""
    bucket = _bucket()
    if bucket is None:
        return False
    path = local_path(uid)
    if not os.path.exists(path):
        return False
    try:
        # Checkpoint TRUNCATE: mezcla el WAL en el .db y lo vacía, para que el
        # snapshot sea un único archivo consistente.
        conn = sqlite3.connect(path, isolation_level=None)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            conn.close()
        bucket.blob(_blob_name(uid)).upload_from_filename(path)
        return True
    except Exception as exc:  # honest degradation: se avisa, no se rompe
        logger.warning("snapshot of %s to GCS failed (%s); result kept "
                       "in-instance only.", uid, exc)
        return False


def persistence_mode() -> str:
    if not GCS_BUCKET:
        return "local-only (ephemeral: resets on cold start)"
    return f"gcs:{GCS_BUCKET}" if _bucket() is not None else \
        "local-only (GCS configured but unreachable)"
