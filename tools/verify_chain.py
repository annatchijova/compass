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


def _tagged_dict_get_int(tagged: object, key: str):
    """Extract an integer value for `key` from a canonical tagged dict.

    payload_c14n is ["c14n", <cv>, tag(payload)]; tag(dict) is
    ["dict", [[k, tag(v)], ...]] and tag(int) is ["int", "<n>"]. This reads
    the sealed evidence_id straight from the chain payload — stdlib only, no
    dependency on the producing package.
    """
    if not (isinstance(tagged, list) and len(tagged) == 2 and tagged[0] == "dict"):
        return None
    for pair in tagged[1]:
        if isinstance(pair, list) and len(pair) == 2 and pair[0] == key:
            v = pair[1]
            if isinstance(v, list) and len(v) == 2 and v[0] == "int":
                return int(v[1])
    return None


def _sealed_hashes_by_evidence(rows) -> dict:
    """Map evidence_id -> set of content hashes SEALED IN THE CHAIN for it.

    These come from the tamper-evident audit_chain (content_hashes is inside
    each row's hashed envelope), NOT from the mutable evidence.content_hash
    column. Binding live content to this value is what makes editing the
    referenced content detectable even when content_hash is edited to match.
    """
    sealed: dict = {}
    for row in rows:
        hashes = json.loads(row["content_hashes"])
        if not hashes:
            continue
        envelope = json.loads(row["payload_c14n"])  # ["c14n", cv, tag(payload)]
        eid = _tagged_dict_get_int(envelope[2], "evidence_id") if len(envelope) == 3 else None
        if eid is None:
            continue
        sealed.setdefault(eid, set()).update(hashes)
    return sealed


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

    # Contenido referenciado: la cadena sella content_hashes DENTRO del sobre
    # hasheado. Se recomputa sha256(contenido vivo) y se compara contra el
    # valor SELLADO EN LA CADENA para ese evidence_id — no contra la columna
    # mutable evidence.content_hash. Comparar contra la columna dejaba pasar
    # una edición de dos columnas (content + content_hash juntos): Red Team
    # Round 1, finding D1.
    content_issues = []
    tombstones = 0
    has_evidence = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence'"
    ).fetchone()
    if has_evidence:
        sealed_by_id = _sealed_hashes_by_evidence(rows)
        for ev in conn.execute(
            "SELECT id, content, content_hash, deleted FROM evidence"
        ):
            if ev["deleted"]:
                tombstones += 1
                continue
            got = hashlib.sha256(ev["content"].encode("utf-8")).hexdigest()
            sealed = sealed_by_id.get(ev["id"])
            if sealed is None:
                content_issues.append(
                    (ev["id"], "content",
                     "evidence no tiene content_hash sellado en la cadena"))
            elif got not in sealed:
                content_issues.append(
                    (ev["id"], "content",
                     "evidence.content no coincide con el content_hash SELLADO "
                     "en la cadena (edición de la fila referenciada)"))

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
