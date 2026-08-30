"""Confidence Engine v1 de COMPASS. Determinístico, sellado, sin autoridad LLM.

El índice de una hipótesis es un ENTERO 0-1000 con semántica explícita:
"acumulación de evidencia bajo las reglas de esta versión del engine".
No es una probabilidad calibrada y la interfaz jamás lo presenta como tal.

Fórmula v1 (toda la aritmética en fractions.Fraction; el único redondeo
es el floor final a entero):

    support = Σ peso(tipo)                      evidencia validada, viva, supports
    contra  = contradicts_factor · Σ peso(tipo) evidencia validada, viva, contradicts
    net     = support - contra
    pos     = max(net, 0)
    index   = floor(1000 · pos / (pos + half_saturation))

Propiedades: asintótico a 1000 sin alcanzarlo nunca (la certeza total no
existe: falibilismo estructural); la evidencia contradictoria pesa más
que la confirmatoria (anti-halago); la evidencia no validada o borrada
(tombstone) no cuenta — borrado es borrado, aunque el hueco quede
visible en la cadena.

Estados (función determinística del índice + composición de evidencia):

    descartada  -> pegajosa: solo la persona descarta y solo la persona
                   reactiva; el engine nunca resucita ni destruye.
    debilitada  -> net < 0.
    corroborada -> index >= corroboration_threshold Y existe al menos una
                   evidencia discriminante a favor (experiment_result u
                   outcome_external): solo un experimento discriminante
                   confirma; ningún volumen de self-report corrobora.
    activa      -> index >= activation_threshold.
    latente     -> el resto.

Los VALORES de la configuración v1 son PROVISORIOS (design doc §9,
decisión abierta): se siembran con un decision_record cuya condición de
reapertura es la auditoría con datos reales.
"""

from __future__ import annotations

import json
import re
import sqlite3
from fractions import Fraction
from typing import Mapping

from .audit_chain import append
from .canonicalize import seal, sha256_utf8
from .db import EVIDENCE_TYPES, atomic, utc_now_iso

ENGINE_VERSION_V1 = "v1"

# ---------------------------------------------------------------------------
# Configuración: valores PROVISORIOS, sujetos a auditoría (design doc §9).
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_V1: dict = {
    "engine_version": ENGINE_VERSION_V1,
    "weights": {
        "self_report": "40",
        "narrative_extracted": "60",
        "behavioral": "120",
        "experiment_result": "180",
        "outcome_external": "250",
    },
    "contradicts_factor": "3/2",
    "half_saturation": "300",
    "activation_threshold": 150,
    "corroboration_threshold": 600,
    "corroboration_requires": ["experiment_result", "outcome_external"],
}

_CONFIG_KEYS = set(DEFAULT_CONFIG_V1.keys())


class EngineConfigError(ValueError):
    """La configuración del engine no pasa la validación de frontera."""


_FRACTION_RE = re.compile(r"^-?[0-9]+(/[1-9][0-9]*)?$")


def _parse_fraction(raw: object, field: str, *, positive: bool = True) -> Fraction:
    if not isinstance(raw, str):
        raise EngineConfigError(
            f"{field}: se espera Fraction como string 'num' o 'num/den', "
            f"llegó {type(raw).__name__} — los floats no entran al path sellado"
        )
    if not _FRACTION_RE.fullmatch(raw):
        raise EngineConfigError(
            f"{field}: {raw!r} no es una fracción válida en forma canónica "
            "'num' o 'num/den' (los decimales como '0.5' se rechazan: dos "
            "escrituras de la misma fracción no deben producir dos hashes)"
        )
    value = Fraction(raw)
    if positive and value <= 0:
        raise EngineConfigError(f"{field}: debe ser > 0, llegó {value}")
    return value


def validate_config(config: Mapping) -> dict:
    """Valida en la frontera y devuelve la config normalizada (parseada).

    Estricta a propósito: claves exactas, tipos exactos, rangos con
    sentido. Una config malformada es un error ruidoso acá, no un índice
    silenciosamente corrido después.
    """
    if set(config.keys()) != _CONFIG_KEYS:
        faltan = _CONFIG_KEYS - set(config.keys())
        sobran = set(config.keys()) - _CONFIG_KEYS
        raise EngineConfigError(
            f"claves de config inválidas; faltan={sorted(faltan)} sobran={sorted(sobran)}"
        )
    if config["engine_version"] != ENGINE_VERSION_V1:
        raise EngineConfigError(
            f"este código implementa el engine {ENGINE_VERSION_V1!r}; "
            f"la config declara {config['engine_version']!r}"
        )
    weights_raw = config["weights"]
    if set(weights_raw.keys()) != set(EVIDENCE_TYPES):
        raise EngineConfigError(
            f"weights debe cubrir exactamente {sorted(EVIDENCE_TYPES)}"
        )
    weights = {
        t: _parse_fraction(weights_raw[t], f"weights.{t}") for t in EVIDENCE_TYPES
    }
    factor = _parse_fraction(config["contradicts_factor"], "contradicts_factor")
    if factor < 1:
        raise EngineConfigError(
            "contradicts_factor debe ser >= 1: la evidencia en contra nunca "
            "pesa menos que la de a favor (anti-halago estructural)"
        )
    half = _parse_fraction(config["half_saturation"], "half_saturation")
    act = config["activation_threshold"]
    corr = config["corroboration_threshold"]
    for name, v in (("activation_threshold", act), ("corroboration_threshold", corr)):
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 1000:
            raise EngineConfigError(f"{name}: entero 0-1000, llegó {v!r}")
    if act >= corr:
        raise EngineConfigError("activation_threshold debe ser < corroboration_threshold")
    reqs = config["corroboration_requires"]
    if (not isinstance(reqs, list) or not reqs
            or not set(reqs) <= set(EVIDENCE_TYPES)):
        raise EngineConfigError(
            "corroboration_requires: lista no vacía de tipos de evidencia válidos"
        )
    return {
        "engine_version": ENGINE_VERSION_V1,
        "weights": weights,
        "contradicts_factor": factor,
        "half_saturation": half,
        "activation_threshold": act,
        "corroboration_threshold": corr,
        "corroboration_requires": sorted(reqs),
    }


def config_hash(config: Mapping) -> str:
    """Seal canónico de la config tal como se persiste (strings/ints)."""
    return seal(dict(config))


def activate_config(conn: sqlite3.Connection, config: Mapping) -> str:
    """Sella y activa una config; registra la decisión y la cadena.

    Devuelve el config_hash. La activación, el decision_record y la
    entrada del chain caen o persisten juntos.
    """
    validate_config(config)  # frontera primero
    chash = config_hash(config)
    config_json = json.dumps(config, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False)
    with atomic(conn):
        now = utc_now_iso()
        conn.execute(
            "INSERT INTO engine_config (engine_version, config, config_hash, "
            "activated_at) VALUES (?, ?, ?, ?)",
            (config["engine_version"], config_json, chash, now),
        )
        conn.execute(
            "INSERT INTO decision_record (title, context, decision, alternatives, "
            "reopen_condition, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                f"Configuración del engine {config['engine_version']}",
                "Valores PROVISORIOS puestos para desbloquear el esqueleto "
                "(design doc §9, decisión abierta).",
                f"config_hash={chash}",
                "No se evaluaron alternativas numéricas: cualquier valor "
                "inicial es arbitrario hasta tener datos propios.",
                "Auditoría de Anna con datos reales de la usuaria cero; "
                "cualquier cambio implica nueva engine_version y recálculo total.",
                now,
            ),
        )
        append(conn, op="engine_config_activated",
               payload={"engine_version": config["engine_version"],
                        "config_hash": chash})
    return chash


def seed_default_config(conn: sqlite3.Connection) -> str:
    """Siembra la config v1 provisoria si no existe. Idempotente.

    Deja asentada también la política PROVISORIA de confrontación: es otro
    valor sin justificar (design doc §9) y merece el mismo decision_record
    con condición de reapertura que los pesos.
    """
    from .confrontation import record_policy_decision

    row = conn.execute(
        "SELECT config_hash FROM engine_config WHERE engine_version = ?",
        (ENGINE_VERSION_V1,),
    ).fetchone()
    if row is not None:
        record_policy_decision(conn)
        return row["config_hash"]
    chash = activate_config(conn, DEFAULT_CONFIG_V1)
    record_policy_decision(conn)
    return chash


def load_config(conn: sqlite3.Connection, engine_version: str = ENGINE_VERSION_V1) -> dict:
    row = conn.execute(
        "SELECT config FROM engine_config WHERE engine_version = ?",
        (engine_version,),
    ).fetchone()
    if row is None:
        raise EngineConfigError(
            f"no hay config {engine_version!r} activada; corré seed/activate primero"
        )
    return validate_config(json.loads(row["config"]))


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------

def _index_from_net(net: Fraction, half: Fraction) -> int:
    pos = net if net > 0 else Fraction(0)
    if pos == 0:
        return 0
    return int(1000 * pos / (pos + half))  # int() sobre Fraction positiva = floor


def compute_hypothesis(
    conn: sqlite3.Connection, hypothesis_id: int, cfg: Mapping
) -> dict:
    """Calcula soporte, contra, net, índice y status de UNA hipótesis.

    Agrega en SQL (COUNT por dirección y tipo) y multiplica en Python con
    Fraction: el trabajo de filas queda en la base, la aritmética exacta
    acá. No escribe nada.
    """
    rows = conn.execute(
        "SELECT he.direction, e.evidence_type, COUNT(*) AS n "
        "FROM hypothesis_evidence he JOIN evidence e ON e.id = he.evidence_id "
        "WHERE he.hypothesis_id = ? AND e.validated = 1 AND e.deleted = 0 "
        "GROUP BY he.direction, e.evidence_type",
        (hypothesis_id,),
    ).fetchall()
    support = Fraction(0)
    contra_base = Fraction(0)
    discriminante_a_favor = False
    for row in rows:
        subtotal = cfg["weights"][row["evidence_type"]] * row["n"]
        if row["direction"] == "supports":
            support += subtotal
            if row["evidence_type"] in cfg["corroboration_requires"]:
                discriminante_a_favor = True
        else:
            contra_base += subtotal
    contra = contra_base * cfg["contradicts_factor"]
    net = support - contra
    index = _index_from_net(net, cfg["half_saturation"])

    actual = conn.execute(
        "SELECT status FROM hypothesis WHERE id = ?", (hypothesis_id,)
    ).fetchone()
    if actual is None:
        raise ValueError(f"hypothesis id={hypothesis_id} no existe")
    if actual["status"] == "descartada":
        status = "descartada"  # pegajosa: solo la persona reactiva
    elif net < 0:
        status = "debilitada"
    elif index >= cfg["corroboration_threshold"] and discriminante_a_favor:
        status = "corroborada"
    elif index >= cfg["activation_threshold"]:
        status = "activa"
    else:
        status = "latente"

    return {
        "hypothesis_id": hypothesis_id,
        "support": str(support),
        "contra": str(contra),
        "net": str(net),
        "index": index,
        "status": status,
    }


def _persist_weights_applied(
    conn: sqlite3.Connection, hypothesis_id: int, cfg: Mapping
) -> None:
    # Reset primero: un vínculo cuya evidencia dejó de contar (tombstone,
    # no validada) no debe conservar un peso viejo como si siguiera vigente.
    conn.execute(
        "UPDATE hypothesis_evidence SET weight_applied = NULL "
        "WHERE hypothesis_id = ?",
        (hypothesis_id,),
    )
    links = conn.execute(
        "SELECT he.evidence_id, he.direction, e.evidence_type "
        "FROM hypothesis_evidence he JOIN evidence e ON e.id = he.evidence_id "
        "WHERE he.hypothesis_id = ? AND e.validated = 1 AND e.deleted = 0",
        (hypothesis_id,),
    ).fetchall()
    for link in links:
        w = cfg["weights"][link["evidence_type"]]
        applied = -w * cfg["contradicts_factor"] if link["direction"] == "contradicts" else w
        conn.execute(
            "UPDATE hypothesis_evidence SET weight_applied = ? "
            "WHERE hypothesis_id = ? AND evidence_id = ?",
            (str(applied), hypothesis_id, link["evidence_id"]),
        )


def recompute_all(
    conn: sqlite3.Connection, engine_version: str = ENGINE_VERSION_V1
) -> dict:
    """Recalcula TODAS las hipótesis bajo la config dada, persiste y sella.

    Todo-o-nada: índices, pesos aplicados y la entrada del chain caen o
    persisten juntos. Devuelve {"engine_version", "config_hash",
    "results": [...], "seal"} — el seal se computa acá, ANTES de que
    cualquier narrador vea el resultado.
    """
    cfg = load_config(conn, engine_version)
    persisted = conn.execute(
        "SELECT config_hash FROM engine_config WHERE engine_version = ?",
        (engine_version,),
    ).fetchone()["config_hash"]

    with atomic(conn):
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM hypothesis ORDER BY id ASC"
        )]
        results = []
        for hid in ids:
            res = compute_hypothesis(conn, hid, cfg)
            conn.execute(
                "UPDATE hypothesis SET index_value = ?, engine_version = ?, "
                "status = ? WHERE id = ?",
                (res["index"], engine_version, res["status"], hid),
            )
            _persist_weights_applied(conn, hid, cfg)
            results.append(res)
        payload = {
            "engine_version": engine_version,
            "config_hash": persisted,
            "results": results,
        }
        payload["seal"] = seal({k: payload[k] for k in
                                ("engine_version", "config_hash", "results")})
        append(conn, op="recompute",
               payload=payload,
               content_hashes=[sha256_utf8(json.dumps(results, sort_keys=True))])
    return payload
