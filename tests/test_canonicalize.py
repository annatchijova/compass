"""Suite de canonicalize.

Oráculos: invariantes (orden de claves irrelevante, NFC) y distinguibilidad
exacta de tipos. Incluye el control del leak clásico: determinismo entre
procesos con PYTHONHASHSEED distinto.
"""

import os
import subprocess
import sys
from fractions import Fraction

import pytest

from compass.canonicalize import (
    CanonicalizeError,
    canonical_json,
    seal,
    sha256_utf8,
)


def test_orden_de_claves_irrelevante():
    a = {"z": 1, "a": [1, 2], "m": {"y": None, "x": "hola"}}
    b = {"m": {"x": "hola", "y": None}, "a": [1, 2], "z": 1}
    assert seal(a) == seal(b)


def test_tipos_distinguibles_entre_si():
    # bool, int, str y Fraction con el mismo "valor" deben sellar distinto.
    sellos = {seal(True), seal(1), seal("1"), seal(Fraction(1, 1))}
    assert len(sellos) == 4


def test_bool_no_colapsa_con_int_dentro_de_estructuras():
    # bool es subclase de int: el bug clásico es que {True: ...} y {1: ...}
    # o [True] y [1] colapsen. Acá las claves son str, pero los valores no.
    assert seal([True, False]) != seal([1, 0])


def test_float_rechazado_con_mensaje_claro():
    with pytest.raises(CanonicalizeError, match="float prohibido"):
        seal({"peso": 0.5})


def test_float_rechazado_anidado_con_ruta():
    with pytest.raises(CanonicalizeError, match=r"\$\.a\[1\]"):
        seal({"a": [1, 2.5]})


def test_fraction_normalizada():
    assert seal(Fraction(2, 4)) == seal(Fraction(1, 2))


def test_int_gigante_estable():
    n = 2**300 + 7
    assert seal(n) == seal(int(str(n)))


def test_nfc_mismo_texto_mismos_bytes():
    compuesto = "caf\u00e9"          # é precompuesta
    descompuesto = "cafe\u0301"      # e + combining acute
    assert compuesto != descompuesto            # strings distintos en Python
    assert seal(compuesto) == seal(descompuesto)  # mismo texto lógico


def test_nfc_tambien_en_claves():
    assert seal({"caf\u00e9": 1}) == seal({"cafe\u0301": 1})


def test_claves_duplicadas_post_nfc_rechazadas():
    with pytest.raises(CanonicalizeError, match="duplicadas"):
        canonical_json({"caf\u00e9": 1, "cafe\u0301": 2})


def test_clave_no_str_rechazada():
    with pytest.raises(CanonicalizeError, match="clave de dict no-str"):
        seal({1: "x"})


def test_tipo_no_soportado_rechazado():
    with pytest.raises(CanonicalizeError, match="no serializable"):
        seal({"x": object()})


def test_tupla_y_lista_equivalentes():
    assert seal((1, 2, "a")) == seal([1, 2, "a"])


def test_bytes_soportados():
    assert seal(b"\x00\xff") == seal(bytearray(b"\x00\xff"))
    assert seal(b"\x00") != seal("00")  # bytes y su hex como str no colapsan


def test_none_distinto_de_string_null():
    assert seal(None) != seal("null")


def test_version_embebida_en_el_sobre():
    assert canonical_json(1).startswith('["c14n",1,')


def test_sha256_utf8_conocido():
    # Valor de referencia computado independientemente (echo -n "" | sha256sum).
    assert sha256_utf8("") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_determinismo_entre_procesos_con_hashseed_distinto():
    """El leak clásico: orden de iteración dependiente de PYTHONHASHSEED.

    El mismo payload debe sellar idéntico en procesos frescos con seeds
    de hash distintas.
    """
    payload_expr = (
        "{'z': [1, 'ñ'], 'a': {'k2': None, 'k1': True}, "
        "'f': __import__('fractions').Fraction(3, 7)}"
    )
    code = (
        "import sys; sys.path.insert(0, 'src'); "
        "from compass.canonicalize import seal; "
        f"print(seal({payload_expr}))"
    )
    sellos = set()
    for seed in ("0", "1", "424242"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        out = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, env=env,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            check=True,
        )
        sellos.add(out.stdout.strip())
    assert len(sellos) == 1
