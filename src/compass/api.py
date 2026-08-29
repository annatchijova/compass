"""API HTTP de COMPASS (FastAPI) para el frontend y la URL hosteada.

Es una capa DELGADA sobre el dominio determinístico: cada endpoint resuelve
la base DEL USUARIO, delega en `domain`/`engine`/`views` y devuelve JSON. La
API no tiene lógica de decisión propia — no puede: los índices los produce y
sella el motor, y el orden inviolable de la narración (estado -> seal ->
resumen -> narrador) vive en `views.narrate_compass`, no acá.

Multi-usuario (para que los jueces lo usen y la persona lo use de verdad):
- Cada request trae un `compass id` en el header `X-Compass-User` (session id
  del navegador, o uno fijado por la persona). Ese id selecciona una base
  SQLite AISLADA por usuario (`storage.py`). Sin login: abrir la URL alcanza.
- El id se valida contra una allowlist estricta antes de tocar una ruta.
- Cada base nueva se siembra con el escenario de demostración, así un juez
  cae en una brújula poblada que puede modificar sin pisar la de nadie.
- Tras cada escritura, la base se snapshotea a GCS (`storage.snapshot`) para
  sobrevivir cold starts; una falla de persistencia degrada honestamente y
  nunca destruye el resultado ya calculado.

Frontera de confianza (agent-trust-boundaries): los roles LLM NO tienen
autoridad. El extractor persiste candidatos `validated=0`; validarlos es un
acto EXPLÍCITO de la persona. Ningún texto de modelo mueve un índice.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager, contextmanager
from typing import Iterator, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import domain, engine, seed_demo, storage, views
from .audit_chain import verify_chain
from .db import EVIDENCE_TYPES, open_db
from .llm import (Abductor, Extractor, LLMOutputError, Narrator,
                  backend_from_env)


@contextmanager
def _db(uid: str, write: bool = False) -> Iterator["object"]:
    """Abre la base AISLADA del usuario (restaurándola de GCS si hace falta),
    la siembra si está vacía, y —si hubo escritura— la snapshotea a GCS al
    salir. El snapshot ocurre fuera de la transacción, después del commit."""
    path = storage.ensure_local(uid)
    conn = open_db(path)
    try:
        seed_demo.seed(conn)  # idempotente: no hace nada si ya hay persona
        yield conn
    finally:
        conn.close()
    if write:
        storage.snapshot(uid)


def get_uid(x_compass_user: str = Header(default=storage.DEMO_UID,
                                         alias="X-Compass-User")) -> str:
    """Resuelve y valida el compass id del request (default: la vitrina)."""
    try:
        return storage.require_uid(x_compass_user)
    except storage.InvalidUserId as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Al arrancar: siembra la brújula vitrina (`demo`) si está vacía, para
    que la URL hosteada no muestre una brújula vacía."""
    with _db(storage.DEMO_UID) as conn:
        seed_demo.seed(conn)
    yield


app = FastAPI(
    title="COMPASS",
    description="Navegación personal adaptativa. Núcleo determinístico, "
    "LLM sin autoridad. API multi-usuario sobre el dominio sellado.",
    version="0.1.0",
    lifespan=_lifespan,
)

# El frontend Next.js vive en otro origen (otro servicio de Cloud Run):
# CORS abierto para el demo. El header X-Compass-User debe estar permitido.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("COMPASS_CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _domain_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# --------------------------------------------------------------- salud ------

@app.get("/health")
def health() -> dict:
    backend_kind = os.environ.get("COMPASS_BACKEND", "fake")
    with _db(storage.DEMO_UID) as conn:
        report = verify_chain(conn)
    vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() in ("TRUE", "1")
    return {
        "status": "ok",
        "service": "compass",
        "llm_backend": backend_kind,
        "model": os.environ.get("COMPASS_MODEL",
                                "gemini-2.5-flash" if backend_kind == "gemini"
                                else None),
        "gemini_transport": ("vertex-ai" if vertex else "gemini-api")
        if backend_kind == "gemini" else None,
        "persistence": storage.persistence_mode(),
        "chain_linkage_ok": report.linkage_ok,
        "chain_integrity_ok": report.integrity_ok,
    }


# ---------------------------------------------------------------- lectura ---

@app.get("/api/state")
def get_state(uid: str = Depends(get_uid)) -> dict:
    """Estado sellado: el seal existe ANTES de cualquier narrador."""
    with _db(uid) as conn:
        return views.sealed_state(conn)


@app.get("/api/evidence")
def list_evidence(uid: str = Depends(get_uid)) -> dict:
    with _db(uid) as conn:
        rows = conn.execute(
            "SELECT id, evidence_type, source, content, validated, deleted, "
            "created_at, validated_at FROM evidence ORDER BY id ASC"
        ).fetchall()
    return {"evidence": [dict(r) for r in rows]}


@app.get("/api/hypotheses")
def list_hypotheses(uid: str = Depends(get_uid)) -> dict:
    with _db(uid) as conn:
        rows = conn.execute(
            "SELECT id, statement, status, origin, index_value, engine_version "
            "FROM hypothesis ORDER BY COALESCE(index_value, 0) DESC, id ASC"
        ).fetchall()
    return {"hypotheses": [dict(r) for r in rows]}


@app.get("/api/experiments")
def list_experiments(uid: str = Depends(get_uid)) -> dict:
    with _db(uid) as conn:
        rows = conn.execute(
            "SELECT id, hypothesis_id, design, success_criterion, "
            "failure_criterion, rival_hypothesis_id, status, preregistered_at, "
            "completed_at FROM experiment ORDER BY id ASC"
        ).fetchall()
    return {"experiments": [dict(r) for r in rows]}


@app.get("/api/chain")
def get_chain(uid: str = Depends(get_uid)) -> dict:
    """La cadena completa + el reporte del verificador (linkage e integrity
    por separado, jamás colapsados en un booleano)."""
    with _db(uid) as conn:
        rows = conn.execute(
            "SELECT seq, op, ts, audit_hash, prev_hash FROM audit_chain "
            "ORDER BY seq ASC"
        ).fetchall()
        report = verify_chain(conn)
    return {
        "entries": [dict(r) for r in rows],
        "linkage_ok": report.linkage_ok,
        "integrity_ok": report.integrity_ok,
        "issues": report.issues,
    }


# ------------------------------------------------------------- escritura ----

class EvidenceIn(BaseModel):
    evidence_type: str = Field(..., description=f"uno de {EVIDENCE_TYPES}")
    source: str
    content: dict
    validated: bool = True


@app.post("/api/evidence")
def add_evidence(body: EvidenceIn, uid: str = Depends(get_uid)) -> dict:
    with _db(uid, write=True) as conn:
        try:
            eid = domain.evidence_add(
                conn, evidence_type=body.evidence_type, source=body.source,
                content=body.content, validated=body.validated,
            )
        except domain.DomainError as exc:
            raise _domain_error(exc)
    return {"evidence_id": eid, "validated": body.validated}


@app.post("/api/evidence/{evidence_id}/validate")
def validate_evidence(evidence_id: int, uid: str = Depends(get_uid)) -> dict:
    """Validación: acto EXPLÍCITO de la persona. Ningún modelo la hace."""
    with _db(uid, write=True) as conn:
        try:
            domain.evidence_validate(conn, evidence_id)
        except domain.DomainError as exc:
            raise _domain_error(exc)
    return {"evidence_id": evidence_id, "validated": True}


class ForgetIn(BaseModel):
    reason: str


@app.post("/api/evidence/{evidence_id}/forget")
def forget_evidence(evidence_id: int, body: ForgetIn,
                    uid: str = Depends(get_uid)) -> dict:
    with _db(uid, write=True) as conn:
        try:
            domain.evidence_tombstone(conn, evidence_id, body.reason)
        except domain.DomainError as exc:
            raise _domain_error(exc)
    return {"evidence_id": evidence_id, "tombstoned": True}


class HypothesisIn(BaseModel):
    statement: str


@app.post("/api/hypotheses")
def add_hypothesis(body: HypothesisIn, uid: str = Depends(get_uid)) -> dict:
    with _db(uid, write=True) as conn:
        try:
            hid = domain.hypothesis_add(conn, statement=body.statement,
                                        origin="person")
        except domain.DomainError as exc:
            raise _domain_error(exc)
    return {"hypothesis_id": hid}


class LinkIn(BaseModel):
    hypothesis_id: int
    evidence_id: int
    direction: str = Field(..., description="supports | contradicts")


@app.post("/api/link")
def link_evidence(body: LinkIn, uid: str = Depends(get_uid)) -> dict:
    with _db(uid, write=True) as conn:
        try:
            domain.evidence_link(conn, hypothesis_id=body.hypothesis_id,
                                 evidence_id=body.evidence_id,
                                 direction=body.direction)
        except domain.DomainError as exc:
            raise _domain_error(exc)
    return {"linked": True}


class ExperimentIn(BaseModel):
    hypothesis_id: int
    design: str
    success_criterion: str
    failure_criterion: str
    rival_hypothesis_id: Optional[int] = None
    duration: Optional[str] = None


@app.post("/api/experiments")
def preregister_experiment(body: ExperimentIn,
                           uid: str = Depends(get_uid)) -> dict:
    with _db(uid, write=True) as conn:
        try:
            xid = domain.experiment_preregister(
                conn, hypothesis_id=body.hypothesis_id, design=body.design,
                success_criterion=body.success_criterion,
                failure_criterion=body.failure_criterion,
                rival_hypothesis_id=body.rival_hypothesis_id,
                duration=body.duration,
            )
        except domain.DomainError as exc:
            raise _domain_error(exc)
    return {"experiment_id": xid}


class CompleteIn(BaseModel):
    outcome: str = Field(..., description=f"uno de {domain.OUTCOMES}")
    notes: str = ""


@app.post("/api/experiments/{experiment_id}/complete")
def complete_experiment(experiment_id: int, body: CompleteIn,
                        uid: str = Depends(get_uid)) -> dict:
    with _db(uid, write=True) as conn:
        try:
            eid = domain.experiment_complete(
                conn, experiment_id=experiment_id, outcome=body.outcome,
                notes=body.notes,
            )
        except domain.DomainError as exc:
            raise _domain_error(exc)
    return {"experiment_id": experiment_id, "generated_evidence_id": eid}


@app.post("/api/recompute")
def recompute(uid: str = Depends(get_uid)) -> dict:
    """Recalcula TODOS los índices y sella. El seal se computa acá, antes
    de que cualquier narrador vea el resultado."""
    with _db(uid, write=True) as conn:
        return engine.recompute_all(conn)


# ------------------------------------------------------------- roles LLM ----

class NarrativeIn(BaseModel):
    narrative: str


@app.post("/api/extract")
def extract_signals(body: NarrativeIn, uid: str = Depends(get_uid)) -> dict:
    """Extractor (rol LLM SIN autoridad): propone candidatos a señal desde
    una narrativa y los PERSISTE como evidencia pendiente (`validated=0`).
    Validarlos es un acto aparte de la persona; ningún índice se mueve acá.
    """
    backend = backend_from_env()
    try:
        candidates = Extractor(backend).extract(body.narrative)
    except LLMOutputError as exc:
        raise HTTPException(status_code=422,
                            detail=f"salida del modelo rechazada en frontera: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"error del backend LLM: {exc}")
    created = []
    with _db(uid, write=True) as conn:
        for c in candidates:
            eid = domain.evidence_add(
                conn, evidence_type="narrative_extracted",
                source="llm_extractor",
                content={"señal": c["señal"], "cita": c["cita"]},
                validated=False,
            )
            created.append({"evidence_id": eid, **c})
    return {"candidates": created,
            "note": "candidatos pendientes de validación; ningún índice se "
            "movió hasta que la persona valide"}


@app.post("/api/abduce")
def abduce_hypotheses(uid: str = Depends(get_uid)) -> dict:
    """Abductor (rol LLM SIN autoridad): dado el resumen sellado, propone
    hipótesis rivales. NO las persiste ni les asigna confianza."""
    with _db(uid) as conn:
        sealed = views.sealed_state(conn)
        summary = views.compressed_summary(sealed)
    backend = backend_from_env()
    try:
        proposals = Abductor(backend).abduce_hypotheses(summary)
    except LLMOutputError as exc:
        raise HTTPException(status_code=422,
                            detail=f"salida del modelo rechazada en frontera: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"error del backend LLM: {exc}")
    return {"proposals": proposals, "state_seal": sealed["seal"]}


@app.post("/api/narrate")
def narrate(language: str = "English", uid: str = Depends(get_uid)) -> dict:
    """Narrador (rol LLM SIN autoridad): sella, resume, narra y registra la
    prosa por su hash JUNTO al seal. Cambiar de backend (o de idioma) cambia
    la prosa y ningún número — ese es el test de arquitectura. `language`:
    English (default) | Spanish."""
    backend = backend_from_env()
    with _db(uid, write=True) as conn:
        try:
            out = views.narrate_compass(conn, Narrator(backend), language)
        except LLMOutputError as exc:
            raise HTTPException(status_code=422,
                                detail=f"narración rechazada en frontera: {exc}")
        except Exception as exc:
            raise HTTPException(status_code=502,
                                detail=f"error del backend LLM: {exc}")
    return out
