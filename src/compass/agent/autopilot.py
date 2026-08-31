"""COMPASS Autopilot: el equipo trabajando en BACKGROUND, sin supervisión.

Categoría del hackathon (thesis "runs async, does the heavy lifting"): el
mismo equipo que en el chat ADK (Analyst, Activity Scout, Reflector) corre
acá de forma DESATENDIDA — un job async (Cloud Run Job + Cloud Scheduler)
que, mientras la persona duerme, hace el trabajo pesado del próximo paso:

    1. lee el estado YA sellado (read-only),
    2. nombra el gap determinístico (qué capacidad testear),
    3. PROPONE el próximo experimento discriminante (Abductor),
    4. PROPONE actividades concretas para ejecutarlo (Activity Scout /
       Google Search),
    5. lo pone en palabras (Narrador),
    6. y de paso vigila el sello (Sentinel: verify_chain + verify_content).

La persona despierta, revisa y DECIDE. El trabajo ya está hecho.

Invariante que el autopilot NO puede violar (design §2, llm-out-of-the-loop,
agent-trust-boundaries) — es EL MISMO que el del equipo interactivo:

    El autopilot PROPONE y VIGILA; jamás valida evidencia, jamás vincula,
    jamás cierra un experimento y jamás mueve ni sella un índice.

Se hace cumplir de tres maneras:

- Por construcción: solo llama a lecturas selladas (views.sealed_state),
  a roles-sin-autoridad (Abductor, ResourceFinder, Narrador) y al
  verificador. No importa `domain`, así que no tiene ninguna palanca de
  escritura de dominio.
- Por guardia fail-closed en tiempo de ejecución: se toma el sello y todos
  los índices ANTES y DESPUÉS de la corrida; si algo se movió, se levanta
  `AutopilotBoundaryError` — la arquitectura estaría rota (ese es el test).
- Por almacenamiento AL LADO del sello, nunca adentro: el briefing es un
  artefacto separado; en la cadena solo queda su HASH (igual que la prosa
  del narrador en views.narrate_compass). El esquema NO cambia — la base
  sigue en su versión, así los servicios ya desplegados la siguen abriendo.

Cambiar el backend cambia la redacción del briefing y las actividades
propuestas — jamás un índice sellado ni el resultado del Sentinel.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path

from .. import storage, trajectories, views
from ..audit_chain import append, verify_chain, verify_content
from ..canonicalize import sha256_utf8
from ..db import atomic, open_db
from ..llm import (Abductor, Backend, LLMOutputError, Narrator, ResourceFinder,
                   backend_from_kind)

logger = logging.getLogger(__name__)


class AutopilotBoundaryError(RuntimeError):
    """El trabajo autónomo movió un valor sellado: la arquitectura está rota.

    No es un error recuperable ni un WARN: es la violación del invariante
    que separa a COMPASS de un horóscopo. Fail-closed y ruidoso.
    """


# ---------------------------------------------------------------- lectura ---

def _indices_snapshot(conn: sqlite3.Connection) -> dict:
    """Foto {hypothesis_id: index_value} para probar que nada se movió."""
    return {row["id"]: row["index_value"]
            for row in conn.execute("SELECT id, index_value FROM hypothesis")}


def collect_gaps(conn: sqlite3.Connection) -> list[dict]:
    """Capacidades-requisito ABIERTAS o EN CONTRA por trayectoria: el gap real
    de la persona, lo que conviene testear. Solo LEE estado sellado."""
    out: list[dict] = []
    for tr in trajectories.list_trajectories(conn):
        fit = trajectories.trajectory_fit(conn, tr["id"])
        for r in fit["requirements"]:
            if r["fit"] in ("open", "against"):
                out.append({"trajectory": tr["name"], "label": r["label"],
                            "fit": r["fit"], "hypothesis_id": r["hypothesis_id"]})
    return out


def _focus(conn: sqlite3.Connection, summary: dict,
           gaps: list[dict]) -> tuple[int | None, str | None, str | None]:
    """Elige UNA capacidad para enriquecer, sin decidir nada.

    Prioriza la hipótesis que el próximo paso determinístico ya señala; si
    el paso no apunta a una hipótesis, cae al primer gap de trayectoria.
    Devuelve (hypothesis_id, statement, label) o (None, None, None) si no
    hay foco computable — un ABSTAIN honesto, no una invención.
    """
    step = summary.get("next_step") or {}
    hid = step.get("hypothesis_id")
    if isinstance(hid, int):
        row = conn.execute(
            "SELECT statement FROM hypothesis WHERE id = ?", (hid,)
        ).fetchone()
        if row is not None:
            return hid, row["statement"], row["statement"]
    if gaps:
        g = gaps[0]
        row = conn.execute(
            "SELECT statement FROM hypothesis WHERE id = ?",
            (g["hypothesis_id"],),
        ).fetchone()
        statement = row["statement"] if row is not None else g["label"]
        return g["hypothesis_id"], statement, g["label"]
    return None, None, None


# --------------------------------------------------------------- briefing ---

def run_briefing(conn: sqlite3.Connection, *, backend: Backend,
                 language: str = "English") -> dict:
    """Arma el briefing del próximo paso. NO escribe dominio, NO sella.

    Orden llm-out-of-the-loop: estado -> seal -> resumen -> modelo. El seal
    se computa ANTES de invocar cualquier rol. Cada enriquecimiento del
    modelo es opcional y degrada honesto: si el Abductor, el Scout o el
    Narrador fallan (red, esquema), el briefing determinístico sigue siendo
    válido y el fallo queda anotado — un fallo no crítico no destruye el
    trabajo válido (§5.3).
    """
    sealed = views.sealed_state(conn)                 # 1. seal ANTES del modelo
    summary = views.compressed_summary(sealed)        # 2. resumen comprimido
    gaps = collect_gaps(conn)
    hid, statement, label = _focus(conn, summary, gaps)

    notes: list[str] = []

    proposed_experiment = None
    if statement:
        try:                                           # 3. Abductor: PROPONE
            proposed_experiment = Abductor(backend).design_experiment(
                statement, language)
        except (LLMOutputError, RuntimeError) as exc:
            notes.append(f"no se pudo proponer experimento: {exc}")
    else:
        notes.append("sin hipótesis en foco: no hay experimento que proponer "
                     "(ABSTAIN honesto)")

    activities = None
    if label:
        try:                                           # 4. Scout: PROPONE
            activities = ResourceFinder(backend).find(label, language)
        except (LLMOutputError, RuntimeError) as exc:
            notes.append(f"no se pudieron buscar actividades: {exc}")

    try:                                               # 5. Narrador: PONE EN PALABRAS
        prose = Narrator(backend).narrate(summary, language)
    except (LLMOutputError, RuntimeError) as exc:
        prose = ("[narración no disponible en esta corrida; el estado sellado y "
                 "el próximo paso de abajo son la fuente de verdad]")
        notes.append(f"no se pudo narrar: {exc}")

    return {
        "generated_against_seal": sealed["seal"],
        "focus_hypothesis_id": hid,
        "focus_capability": label,
        "next_step": summary["next_step"],
        "gaps": gaps,
        "proposed_experiment": proposed_experiment,
        "activities": activities,
        "prose": prose,
        "notes": notes,
    }


# --------------------------------------------------------------- sentinel ---

def run_sentinel(conn: sqlite3.Connection) -> dict:
    """Vigila el sello: TRES señales por separado (linkage, integrity,
    content) más los problemas. Solo LEE. 'tampering es detectable, no
    imposible' — ahora vigilado solo, sin que nadie tenga que acordarse."""
    r = verify_chain(conn)
    c = verify_content(conn)
    return {
        "linkage_ok": r.linkage_ok,
        "integrity_ok": r.integrity_ok,
        "content_ok": c.content_ok,
        "tombstones": c.tombstones,
        "ok": r.ok and c.content_ok,
        "issues": r.issues + c.issues,
    }


# ------------------------------------------------- registro AL LADO del sello

def _briefing_hash(briefing: dict) -> str:
    """Hash canónico del briefing, para anclarlo en la cadena sin meter la
    prosa adentro (mismo patrón que el prose_hash de views.narrate_compass)."""
    material = json.dumps(briefing, ensure_ascii=False, sort_keys=True)
    return sha256_utf8(material)


def record_in_chain(conn: sqlite3.Connection, *, seal: str, briefing: dict,
                    sentinel: dict) -> dict:
    """Anexa a la cadena existente el RASTRO del acto autónomo: solo hashes y
    banderas, ningún índice. No sube el schema_version (es un INSERT de fila),
    así los servicios ya desplegados siguen abriendo la base."""
    payload = {
        "state_seal": seal,
        "briefing_sha256": _briefing_hash(briefing),
        "sentinel_ok": bool(sentinel["ok"]),
        "linkage_ok": bool(sentinel["linkage_ok"]),
        "integrity_ok": bool(sentinel["integrity_ok"]),
        "content_ok": bool(sentinel["content_ok"]),
    }
    with atomic(conn):
        return append(conn, op="autopilot_briefing", payload=payload)


def _render_markdown(uid: str, briefing: dict, sentinel: dict) -> str:
    """Briefing legible por humanos. Es material de consulta que vive FUERA del
    sello: no es evidencia, no valida nada, no mueve ningún índice."""
    lines = [f"# COMPASS autopilot briefing — {uid}", ""]
    lines.append(f"Estado sellado: `{briefing['generated_against_seal']}`")
    sig = ("linkage={linkage_ok} integrity={integrity_ok} content={content_ok}"
           .format(**sentinel))
    lines.append(f"Sentinel: {'OK' if sentinel['ok'] else 'ALERTA'} ({sig})")
    if not sentinel["ok"]:
        for issue in sentinel["issues"]:
            lines.append(f"  - {issue}")
    lines += ["", "## Próximo paso (determinístico)", ""]
    step = briefing["next_step"]
    lines.append(f"- **{step.get('kind')}** — {step.get('detail', '')}")
    if briefing["focus_capability"]:
        lines += ["", "## Capacidad en foco", "",
                  f"- {briefing['focus_capability']}"]
    exp = briefing["proposed_experiment"]
    if exp:
        lines += ["", "## Experimento propuesto (para que VOS lo preregistres)", "",
                  f"- Diseño: {exp['design']}",
                  f"- Éxito: {exp['success_criterion']}",
                  f"- Fracaso: {exp['failure_criterion']}"]
    act = briefing["activities"]
    if act and act.get("resources"):
        grounded = "buscadas en la web" if act.get("grounded") else \
            "NO buscadas (backend sin búsqueda): tratar como sugerencia"
        lines += ["", f"## Actividades para testear ({grounded})", ""]
        for r in act["resources"]:
            url = f" — {r['url']}" if r.get("url") else ""
            lines.append(f"- [{r['kind']}] {r['title']}: {r['why']}{url}")
    lines += ["", "## Narración", "", briefing["prose"]]
    if briefing["notes"]:
        lines += ["", "## Notas (degradación honesta)", ""]
        lines += [f"- {n}" for n in briefing["notes"]]
    lines += ["", "> El autopilot PROPONE y VIGILA. No validó, no vinculó, no "
              "cerró nada y no movió ningún índice. La decisión es tuya.", ""]
    return "\n".join(lines)


def store_briefing_beside(uid: str, briefing: dict, sentinel: dict, *,
                          data_dir: str) -> str:
    """Escribe el briefing como artefacto AL LADO de la base (nunca adentro).
    Devuelve la ruta. Un directorio hermano `briefings/`; el archivo se
    sobrescribe con el último briefing de cada usuario."""
    out_dir = Path(data_dir) / "briefings"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"compass_{uid}.briefing.md"
    path.write_text(_render_markdown(uid, briefing, sentinel), encoding="utf-8")
    return str(path)


# ----------------------------------------------------------- una corrida ----

def autopilot_once(conn: sqlite3.Connection, *, backend: Backend,
                   language: str = "English", uid: str = "local",
                   data_dir: str | None = None, record: bool = True) -> dict:
    """Una corrida del autopilot sobre una base. Vigila, arma el briefing y lo
    guarda al lado — con la GUARDIA fail-closed de que nada sellado se movió.
    """
    seal_before = views.sealed_state(conn)["seal"]
    indices_before = _indices_snapshot(conn)

    sentinel = run_sentinel(conn)                      # vigila como la dejaron
    briefing = run_briefing(conn, backend=backend, language=language)

    # GUARDIA: el trabajo autónomo NO tocó ningún número sellado. Si lo hizo,
    # la arquitectura está rota y se levanta ANTES de persistir nada.
    seal_after = views.sealed_state(conn)["seal"]
    indices_after = _indices_snapshot(conn)
    if seal_after != seal_before or indices_after != indices_before:
        raise AutopilotBoundaryError(
            "el autopilot movió un valor sellado: "
            f"seal {seal_before} -> {seal_after}, "
            f"índices {indices_before} -> {indices_after}"
        )

    artifact = None
    if data_dir is not None:
        artifact = store_briefing_beside(uid, briefing, sentinel,
                                         data_dir=data_dir)
    chain_entry = record_in_chain(conn, seal=seal_before, briefing=briefing,
                                  sentinel=sentinel) if record else None

    logger.info("autopilot ran uid=%s seal=%s sentinel_ok=%s next=%s",
                uid, seal_before, sentinel["ok"],
                briefing["next_step"].get("kind"))
    return {"uid": uid, "seal": seal_before, "sentinel": sentinel,
            "briefing": briefing, "artifact": artifact,
            "chain_entry": chain_entry}


# ------------------------------------------------------- barrido multi-user -

def enumerate_uids(data_dir: str) -> list[str]:
    """Lista los uid con base local en data_dir (compass_<uid>.db), ordenados.
    El job restaura desde GCS antes de barrer (ver sweep)."""
    d = Path(data_dir)
    if not d.exists():
        return []
    uids = []
    for p in sorted(d.glob("compass_*.db")):
        uid = p.name[len("compass_"):-len(".db")]
        if storage.valid_uid(uid):
            uids.append(uid)
    return uids


def _restore_all_from_gcs(data_dir: str) -> None:
    """Trae cada base del bucket a disco local, para poder barrerlas. Degrada
    honesto: sin bucket o sin SDK, no hace nada y se barre lo que haya local."""
    if not storage.GCS_BUCKET:
        return
    try:
        from google.cloud import storage as gcs
        bucket = gcs.Client().bucket(storage.GCS_BUCKET)
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        for blob in bucket.list_blobs():
            name = blob.name
            if name.startswith("compass_") and name.endswith(".db"):
                uid = name[len("compass_"):-len(".db")]
                if storage.valid_uid(uid):
                    storage.ensure_local(uid)
    except Exception as exc:  # honest degradation: se barre lo local
        logger.warning("no se pudo listar/restaurar desde GCS (%s); "
                       "se barre solo lo local.", exc)


def sweep(*, backend: Backend, data_dir: str | None = None,
          language: str = "English") -> list[dict]:
    """Barre TODAS las brújulas: por cada una, corre el autopilot una vez,
    guarda el briefing al lado y la snapshotea de vuelta a GCS. El acto
    async, en background, "across many users" del thesis del hackathon."""
    data_dir = data_dir or storage.DATA_DIR
    _restore_all_from_gcs(data_dir)
    uids = enumerate_uids(data_dir)
    logger.info("autopilot sweep: %d compass(es) en %s", len(uids), data_dir)
    results: list[dict] = []
    for uid in uids:
        path = storage.ensure_local(uid)
        conn = open_db(path)
        try:
            out = autopilot_once(conn, backend=backend, language=language,
                                 uid=uid, data_dir=data_dir)
        except Exception as exc:  # una base no puede tumbar el barrido entero
            logger.exception("autopilot falló para uid=%s: %s", uid, exc)
            results.append({"uid": uid, "error": str(exc)})
            continue
        finally:
            conn.close()
        storage.snapshot(uid)   # persiste la fila de cadena + briefing (o degrada)
        results.append({"uid": uid, "seal": out["seal"],
                        "sentinel_ok": out["sentinel"]["ok"],
                        "next_step": out["briefing"]["next_step"].get("kind"),
                        "artifact": out["artifact"]})
    return results


def main(argv: list[str] | None = None) -> int:
    """Entrypoint del Cloud Run Job: barre todas las brújulas y sale.

    Backend por COMPASS_BACKEND (gemini en el deploy; demo offline). Idioma
    por COMPASS_LANGUAGE (English por defecto)."""
    logging.basicConfig(level=logging.INFO)
    backend = backend_from_kind(os.environ.get("COMPASS_BACKEND", "demo"))
    language = os.environ.get("COMPASS_LANGUAGE", "English")
    results = sweep(backend=backend, language=language)
    print(json.dumps({"swept": len(results), "results": results},
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
