"""Serialización canónica de COMPASS. Módulo único, fuente de verdad.

Regla del design doc (§3.2): dos objetos que significan cosas distintas
jamás serializan a los mismos bytes, y el mismo objeto serializa siempre
a bytes idénticos. Todo hash del sistema se computa sobre esta forma.

Propiedades:
- Tipada: bool, int, str, Fraction y bytes son distinguibles entre sí.
  (bool se chequea ANTES que int porque bool es subclase de int.)
- Ordenada: las claves de dict se ordenan; la forma etiquetada usa solo
  listas y strings, así que json.dumps no depende de ningún orden de
  iteración de dict/set.
- Versionada: CANONICALIZE_VERSION va embebida en el sobre canónico.
- Sin floats: un float en el path sellado es un error, no un valor.
  Usar fractions.Fraction o str.
- Unicode NFC: el mismo texto lógico produce los mismos bytes aunque
  llegue compuesto o descompuesto.

Formato etiquetado (interno, estable — el verificador externo no lo
necesita porque los sobres del ledger persisten el string canónico ya
producido):

    None            -> ["null"]
    True            -> ["bool", true]
    7               -> ["int", "7"]          (str: sin límite de tamaño)
    Fraction(3, 7)  -> ["frac", "3", "7"]    (siempre normalizada)
    "café"          -> ["str", "café"]       (NFC)
    b"\\x00"        -> ["bytes", "00"]        (hex)
    [x, y] / (x, y) -> ["list", [tag(x), tag(y)]]
    {k: v}          -> ["dict", [["k1", tag(v1)], ...]]  (pares ordenados)

Sobre canónico final: ["c14n", CANONICALIZE_VERSION, tag(payload)]
serializado con json.dumps(separators=(",", ":"), ensure_ascii=False,
sort_keys=True) y codificado UTF-8.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from fractions import Fraction

CANONICALIZE_VERSION = 1

_JSON_KW = {"sort_keys": True, "separators": (",", ":"), "ensure_ascii": False}


class CanonicalizeError(TypeError):
    """Un valor no admitido intentó entrar al path sellado."""


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _tag(obj: object, path: str) -> list:
    # bool antes que int: bool es subclase de int y colapsaría con él.
    if obj is None:
        return ["null"]
    if isinstance(obj, bool):
        return ["bool", obj]
    if isinstance(obj, float):
        raise CanonicalizeError(
            f"float prohibido en payload sellado (en {path}): "
            "los floats no son reproducibles bit a bit; "
            "usá fractions.Fraction o str"
        )
    if isinstance(obj, int):
        return ["int", str(obj)]
    if isinstance(obj, Fraction):
        return ["frac", str(obj.numerator), str(obj.denominator)]
    if isinstance(obj, str):
        return ["str", _nfc(obj)]
    if isinstance(obj, (bytes, bytearray)):
        return ["bytes", bytes(obj).hex()]
    if isinstance(obj, (list, tuple)):
        return ["list", [_tag(v, f"{path}[{i}]") for i, v in enumerate(obj)]]
    if isinstance(obj, dict):
        pairs: list[list] = []
        seen: set[str] = set()
        for k in obj:
            if not isinstance(k, str):
                raise CanonicalizeError(
                    f"clave de dict no-str en {path}: {type(k).__name__!r}; "
                    "solo claves str en payloads sellados"
                )
            nk = _nfc(k)
            if nk in seen:
                raise CanonicalizeError(
                    f"claves duplicadas tras normalización NFC en {path}: {nk!r}"
                )
            seen.add(nk)
            pairs.append([nk, _tag(obj[k], f"{path}.{nk}")])
        pairs.sort(key=lambda p: p[0])
        return ["dict", pairs]
    raise CanonicalizeError(
        f"tipo no serializable en payload sellado (en {path}): {type(obj).__name__!r}"
    )


def canonical_json(payload: object) -> str:
    """Forma canónica del payload como string JSON (determinística)."""
    envelope = ["c14n", CANONICALIZE_VERSION, _tag(payload, "$")]
    return json.dumps(envelope, **_JSON_KW)


def seal(payload: object) -> str:
    """SHA-256 hex sobre los bytes UTF-8 de la forma canónica."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def sha256_utf8(text: str) -> str:
    """SHA-256 hex del texto tal cual (bytes UTF-8, sin canonicalizar).

    Se usa como content_hash de contenido ya almacenado como string
    (p. ej. evidence.content): el verificador independiente puede
    recomputarlo sin conocer este módulo.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
