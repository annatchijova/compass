"""Cadena de auditoría de COMPASS: append-only, tamper-evident.

Construcción:

    material   = json.dumps(sobre, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=False)
    audit_hash = sha256(utf8(material) + utf8(prev_hash))

donde el sobre es exactamente:

    {"content_hashes": [...], "cv": <int>, "op": <str>,
     "payload_c14n": <str>, "seq": <int>, "ts": <str>}

Cada campo alimentado al hash es una columna almacenada, capturada una
sola vez — la cadena es recomputable desde datos persistidos, siempre.
El string canónico del payload (payload_c14n) se persiste tal cual se
hasheó, de modo que un verificador externo NO necesita reimplementar la
canonicalización: solo el sobre de arriba (stdlib pura). La spec vive
duplicada a propósito en tools/verify_chain.py.

Reglas que este módulo hace cumplir:
1. content_hashes van DENTRO del payload hasheado: editar el contenido
   referenciado rompe la recomputación aunque los ids no cambien.
2. ts se captura una vez; el valor hasheado es el valor almacenado.
3. El verificador reporta linkage e integrity por separado: una cadena
   puede estar enlazada con un campo adulterado, o íntegra con un
   eslabón roto — colapsarlos en un booleano esconde qué ataque pasó.
4. Hay exactamente un génesis, para siempre. append lee el último hash
   y continúa; ninguna otra ruta crea un génesis.
5. Antes de anexar se verifica la cola. Si ya está rota, se anexa igual
   (la operación debe quedar registrada) pero el quiebre se devuelve y
   se loguea ruidosamente — jamás se lava encadenando por encima en
   silencio.
6. El payload es determinístico por construcción (canonicalize rechaza
   floats y ordena todo).
7. El verificador independiente vive en tools/verify_chain.py y no
   importa este paquete.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from .canonicalize import CANONICALIZE_VERSION, canonical_json
from .db import atomic, utc_now_iso

import hashlib

logger = logging.getLogger(__name__)

GENESIS_PREV = "0" * 64
TAIL_CHECK_N = 16

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

_JSON_KW = {"sort_keys": True, "separators": (",", ":"), "ensure_ascii": False}


class AuditChainError(RuntimeError):
    pass


def _envelope_material(
    *,
    seq: int,
    op: str,
    payload_c14n: str,
    content_hashes: Sequence[str],
    ts: str,
    cv: int,
) -> str:
    envelope = {
        "content_hashes": list(content_hashes),
        "cv": cv,
        "op": op,
        "payload_c14n": payload_c14n,
        "seq": seq,
        "ts": ts,
    }
    return json.dumps(envelope, **_JSON_KW)


def compute_hash(material: str, prev_hash: str) -> str:
    return hashlib.sha256(
        material.encode("utf-8") + prev_hash.encode("utf-8")
    ).hexdigest()


@dataclass
class VerifyReport:
    linkage_ok: bool
    integrity_ok: bool
    issues: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.linkage_ok and self.integrity_ok


def _row_material(row: Mapping) -> str:
    return _envelope_material(
        seq=row["seq"],
        op=row["op"],
        payload_c14n=row["payload_c14n"],
        content_hashes=json.loads(row["content_hashes"]),
        ts=row["ts"],
        cv=row["cv"],
    )


def verify_rows(rows_asc: Sequence[Mapping]) -> VerifyReport:
    """Verifica linkage e integrity de filas ya ordenadas por seq ASC.

    - integrity: cada audit_hash recomputa desde las columnas de su fila.
    - linkage: prev_hash de cada fila es el audit_hash de la anterior,
      el génesis es único y correcto, y los seq son contiguos (un hueco
      de seq delata una deleción incluso antes de mirar los hashes).
    """
    report = VerifyReport(linkage_ok=True, integrity_ok=True)
    prev_row: Mapping | None = None
    for row in rows_asc:
        recomputed = compute_hash(_row_material(row), row["prev_hash"])
        if recomputed != row["audit_hash"]:
            report.integrity_ok = False
            report.issues.append(
                {"seq": row["seq"], "kind": "integrity",
                 "detail": "audit_hash no recomputa desde las columnas almacenadas"}
            )
        if prev_row is None:
            if row["seq"] != 1:
                report.linkage_ok = False
                report.issues.append(
                    {"seq": row["seq"], "kind": "gap",
                     "detail": f"la cadena empieza en seq={row['seq']}, no en 1"}
                )
            if row["prev_hash"] != GENESIS_PREV:
                report.linkage_ok = False
                report.issues.append(
                    {"seq": row["seq"], "kind": "genesis",
                     "detail": "la primera entrada no apunta al génesis"}
                )
        else:
            if row["seq"] != prev_row["seq"] + 1:
                report.linkage_ok = False
                report.issues.append(
                    {"seq": row["seq"], "kind": "gap",
                     "detail": f"hueco de seq: {prev_row['seq']} -> {row['seq']}"}
                )
            if row["prev_hash"] != prev_row["audit_hash"]:
                report.linkage_ok = False
                report.issues.append(
                    {"seq": row["seq"], "kind": "linkage",
                     "detail": "prev_hash no coincide con el audit_hash anterior"}
                )
        prev_row = row
    return report


def fetch_all_asc(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM audit_chain ORDER BY seq ASC").fetchall()


def verify_chain(conn: sqlite3.Connection) -> VerifyReport:
    return verify_rows(fetch_all_asc(conn))


def _verify_tail(conn: sqlite3.Connection, n: int = TAIL_CHECK_N) -> VerifyReport | None:
    """Verifica las últimas n entradas antes de anexar.

    Sobre una ventana, el primer eslabón no puede validarse contra su
    anterior (queda fuera de la ventana), así que solo se chequean
    integrity de todas y linkage entre las visibles.
    """
    rows = conn.execute(
        "SELECT * FROM audit_chain ORDER BY seq DESC LIMIT ?", (n,)
    ).fetchall()
    if not rows:
        return None
    rows_asc = list(reversed(rows))
    report = VerifyReport(linkage_ok=True, integrity_ok=True)
    prev_row: Mapping | None = None
    for row in rows_asc:
        recomputed = compute_hash(_row_material(row), row["prev_hash"])
        if recomputed != row["audit_hash"]:
            report.integrity_ok = False
            report.issues.append(
                {"seq": row["seq"], "kind": "integrity",
                 "detail": "audit_hash no recomputa desde las columnas almacenadas"}
            )
        if prev_row is not None:
            if row["seq"] != prev_row["seq"] + 1:
                report.linkage_ok = False
                report.issues.append(
                    {"seq": row["seq"], "kind": "gap",
                     "detail": f"hueco de seq: {prev_row['seq']} -> {row['seq']}"}
                )
            elif row["prev_hash"] != prev_row["audit_hash"]:
                report.linkage_ok = False
                report.issues.append(
                    {"seq": row["seq"], "kind": "linkage",
                     "detail": "prev_hash no coincide con el audit_hash anterior"}
                )
        prev_row = row
    return report


def _validate_content_hashes(content_hashes: Iterable[str]) -> list[str]:
    validated = []
    for h in content_hashes:
        if not isinstance(h, str) or not _HEX64.fullmatch(h):
            raise AuditChainError(
                f"content_hash inválido: {h!r} (se espera sha256 hex minúscula)"
            )
        validated.append(h)
    return sorted(validated)


def append(
    conn: sqlite3.Connection,
    *,
    op: str,
    payload: object,
    content_hashes: Iterable[str] = (),
    now: str | None = None,
) -> dict:
    """Anexa una entrada a la cadena. Devuelve seq, audit_hash, ts y
    tail_warning (None si la cola estaba sana).

    Corre dentro de atomic(): si el caller ya abrió una transacción,
    participa en ella y la entrada cae o persiste junto con las
    escrituras de dominio de esa misma operación lógica.

    `now` existe solo para tests de determinismo; en producción el
    timestamp se captura acá, una única vez.
    """
    if not op or not isinstance(op, str):
        raise AuditChainError("op debe ser un string no vacío")
    hashes = _validate_content_hashes(content_hashes)
    payload_c14n = canonical_json(payload)  # rechaza floats y tipos no aptos

    with atomic(conn):
        tail_report = _verify_tail(conn)
        tail_warning = None
        if tail_report is not None and not tail_report.ok:
            tail_warning = {
                "linkage_ok": tail_report.linkage_ok,
                "integrity_ok": tail_report.integrity_ok,
                "issues": tail_report.issues,
            }
            logger.error(
                "audit_chain: la cola de la cadena YA está rota antes de "
                "anexar (issues=%s). Se anexa igual para registrar la "
                "operación, pero el quiebre queda reportado y una "
                "verificación completa lo seguirá encontrando.",
                tail_report.issues,
            )

        last = conn.execute(
            "SELECT seq, audit_hash FROM audit_chain ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if last is None:
            seq, prev_hash = 1, GENESIS_PREV
        else:
            seq, prev_hash = last["seq"] + 1, last["audit_hash"]

        ts = now if now is not None else utc_now_iso()
        material = _envelope_material(
            seq=seq, op=op, payload_c14n=payload_c14n,
            content_hashes=hashes, ts=ts, cv=CANONICALIZE_VERSION,
        )
        audit_hash = compute_hash(material, prev_hash)
        conn.execute(
            "INSERT INTO audit_chain "
            "(seq, op, payload_c14n, content_hashes, ts, cv, prev_hash, audit_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (seq, op, payload_c14n, json.dumps(hashes, **_JSON_KW), ts,
             CANONICALIZE_VERSION, prev_hash, audit_hash),
        )

    return {"seq": seq, "audit_hash": audit_hash, "ts": ts,
            "tail_warning": tail_warning}
