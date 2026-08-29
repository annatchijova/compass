#!/usr/bin/env python3
"""Verificador independiente de la cadena de auditoría de COMPASS.

REGLA: este script NO importa el paquete compass. Un verificador que
importa la lógica del productor hereda los bugs del productor. La spec
del sobre está reimplementada acá a propósito, desde el documento de
diseño:

    material   = json.dumps({"content_hashes": [...], "cv": <int>,
                             "op": <str>, "payload_c14n": <str>,
                             "seq": <int>, "ts": <str>},
                            sort_keys=True, separators=(",", ":"),
                            ensure_ascii=False)
    audit_hash = sha256(utf8(material) + utf8(prev_hash))
    génesis    : prev_hash = "0" * 64, seq = 1, único para siempre.

Verifica y reporta POR SEPARADO:
  - integrity : cada audit_hash recomputa desde las columnas de su fila
                (detecta ediciones in-place de cualquier campo hasheado).
  - linkage   : prev_hash[i] == audit_hash[i-1], génesis correcto y seq
                contiguos (detecta reordenamiento, inserción y deleción).
  - contenido : si existe la tabla evidence, recomputa
                sha256(utf8(content)) contra content_hash (detecta
                edición del contenido referenciado aunque la cadena
                recompute bien). Los tombstones (deleted=1) se informan,
                no son error: el borrado honesto deja el hueco visible.

Uso:
    python3 tools/verify_chain.py ruta/a/compass.db
Salida: reporte por stdout. Exit 0 si todo verifica, 1 si hay quiebres,
2 ante error de uso.
"""

import hashlib
import json
import sqlite3
import sys

GENESIS_PREV = "0" * 64
_JSON_KW = {"sort_keys": True, "separators": (",", ":"), "ensure_ascii": False}


def compute_hash(row: sqlite3.Row) -> str:
    envelope = {
        "content_hashes": json.loads(row["content_hashes"]),
        "cv": row["cv"],
        "op": row["op"],
        "payload_c14n": row["payload_c14n"],
        "seq": row["seq"],
        "ts": row["ts"],
    }
    material = json.dumps(envelope, **_JSON_KW)
    return hashlib.sha256(
        material.encode("utf-8") + row["prev_hash"].encode("utf-8")
    ).hexdigest()


def verify(db_path: str) -> int:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT * FROM audit_chain ORDER BY seq ASC").fetchall()
    issues = []
    linkage_ok = True
    integrity_ok = True

    prev = None
    for row in rows:
        if compute_hash(row) != row["audit_hash"]:
            integrity_ok = False
            issues.append((row["seq"], "integrity",
                           "audit_hash no recomputa desde las columnas"))
        if prev is None:
            if row["seq"] != 1:
                linkage_ok = False
                issues.append((row["seq"], "gap",
                               f"la cadena empieza en seq={row['seq']}, no en 1"))
            if row["prev_hash"] != GENESIS_PREV:
                linkage_ok = False
                issues.append((row["seq"], "genesis",
                               "la primera entrada no apunta al génesis"))
        else:
            if row["seq"] != prev["seq"] + 1:
                linkage_ok = False
                issues.append((row["seq"], "gap",
                               f"hueco de seq: {prev['seq']} -> {row['seq']}"))
            if row["prev_hash"] != prev["audit_hash"]:
                linkage_ok = False
                issues.append((row["seq"], "linkage",
                               "prev_hash no coincide con el audit_hash anterior"))
        prev = row

    # Contenido referenciado: la cadena sella content_hashes; acá se
    # comprueba que el contenido vivo siga siendo el que se selló.
    content_issues = []
    tombstones = 0
    has_evidence = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence'"
    ).fetchone()
    if has_evidence:
        for ev in conn.execute(
            "SELECT id, content, content_hash, deleted FROM evidence"
        ):
            if ev["deleted"]:
                tombstones += 1
                continue
            got = hashlib.sha256(ev["content"].encode("utf-8")).hexdigest()
            if got != ev["content_hash"]:
                content_issues.append(
                    (ev["id"], "content",
                     "evidence.content no coincide con su content_hash sellado"))

    print(f"entradas en la cadena : {len(rows)}")
    print(f"linkage_ok            : {linkage_ok}")
    print(f"integrity_ok          : {integrity_ok}")
    if has_evidence:
        print(f"contenido_ok          : {not content_issues} "
              f"({tombstones} tombstone(s) declarados)")
    for seq, kind, detail in issues:
        print(f"  [seq {seq}] {kind}: {detail}")
    for eid, kind, detail in content_issues:
        print(f"  [evidence {eid}] {kind}: {detail}")

    ok = linkage_ok and integrity_ok and not content_issues
    print("VEREDICTO             :", "VERIFICA" if ok else "QUIEBRE DETECTADO")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    return verify(argv[1])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
