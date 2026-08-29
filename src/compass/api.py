"""API HTTP de COMPASS (FastAPI) para el frontend y la URL hosteada.

Es una capa DELGADA sobre el dominio determinístico: cada endpoint abre
la base, delega en `domain`/`engine`/`views` y devuelve JSON. La API no
tiene lógica de decisión propia — no puede: los índices los produce y
sella el motor, y el orden inviolable de la narración (estado -> seal ->
resumen -> narrador) vive en `views.narrate_compass`, no acá.

Frontera de confianza (agent-trust-boundaries):
- Los roles LLM (extractor, abductor, narrador) NO tienen autoridad. El
  extractor devuelve candidatos que nacen `validated=0`: entran a la base
  como pendientes, y validarlos es un acto EXPLÍCITO de la persona (un
  endpoint distinto). Ningún texto de modelo escribe evidencia validada
  ni mueve un índice.
- El backend LLM se elige por `COMPASS_BACKEND` (fake por defecto: la API
  arranca y sirve el ciclo completo sin credencial). Con `gemini` usa
  Vertex AI/Gemini API — el modelo obligatorio del hackathon.

Persistencia: SQLite local (`COMPASS_DB`). En Cloud Run el disco es
efímero; por eso al arrancar se siembra el escenario de demostración si
la base está vacía, y `/health` declara honestamente que la durabilidad
depende del entorno.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from typing import Iterator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import domain, engine, seed_demo, views
from .audit_chain import verify_chain
from .db import EVIDENCE_TYPES, open_db
from .llm import (Abductor, Extractor, LLMOutputError, Narrator,
                  backend_from_env)

DB_PATH = os.environ.get("COMPASS_DB", "compass.db")


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Al arrancar: siembra el escenario de demostración si la base está
    vacía, para que la URL hosteada no muestre una brújula vacía."""
    with _db() as conn:
        seed_demo.seed(conn)
    yield


app = FastAPI(
    title="COMPASS",
    description="Navegación personal adaptativa. Núcleo determinístico, "
    "LLM sin autoridad. API sobre el dominio sellado.",
    version="0.1.0",
    lifespan=_lifespan,
)

# El frontend Next.js vive en otro origen (otro servicio de Cloud Run):
# CORS abierto para el demo. Endurecer antes de exponer la URL ampliamente.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("COMPASS_CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    conn = open_db(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _domain_error(exc: Exception) -> HTTPException:
    """Traduce un error de dominio (frontera) a 400; el resto sube a 500."""
    return HTTPException(status_code=400, detail=str(exc))


# --------------------------------------------------------------- salud ------

@app.get("/health")
def health() -> dict:
    backend_kind = os.environ.get("COMPASS_BACKEND", "fake")
    with _db() as conn:
        report = verify_chain(conn)
        seeded = seed_demo.is_seeded(conn)
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
        "db_path": DB_PATH,
        "db_durability": "ephemeral (Cloud Run local disk)"
        if DB_PATH.startswith("/tmp") or os.environ.get("K_SERVICE")
        else "local file",
        "seeded": seeded,
        "chain_linkage_ok": report.linkage_ok,
        "chain_integrity_ok": report.integrity_ok,
    }


# ---------------------------------------------------------------- lectura ---

@app.get("/api/state")
def get_state() -> dict:
    """Estado sellado: el seal existe ANTES de cualquier narrador."""
    with _db() as conn:
        return views.sealed_state(conn)


@app.get("/api/evidence")
def list_evidence() -> dict:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, evidence_type, source, content, validated, deleted, "
            "created_at, validated_at FROM evidence ORDER BY id ASC"
        ).fetchall()
    return {"evidence": [dict(r) for r in rows]}


@app.get("/api/hypotheses")
def list_hypotheses() -> dict:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, statement, status, origin, index_value, engine_version "
            "FROM hypothesis ORDER BY COALESCE(index_value, 0) DESC, id ASC"
        ).fetchall()
    return {"hypotheses": [dict(r) for r in rows]}


@app.get("/api/experiments")
def list_experiments() -> dict:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, hypothesis_id, design, success_criterion, "
            "failure_criterion, rival_hypothesis_id, status, preregistered_at, "
            "completed_at FROM experiment ORDER BY id ASC"
        ).fetchall()
    return {"experiments": [dict(r) for r in rows]}


@app.get("/api/chain")
def get_chain() -> dict:
    """La cadena completa + el reporte del verificador (linkage e integrity
    por separado, jamás colapsados en un booleano)."""
    with _db() as conn:
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
def add_evidence(body: EvidenceIn) -> dict:
    with _db() as conn:
        try:
            eid = domain.evidence_add(
                conn, evidence_type=body.evidence_type, source=body.source,
                content=body.content, validated=body.validated,
            )
        except domain.DomainError as exc:
            raise _domain_error(exc)
    return {"evidence_id": eid, "validated": body.validated}


@app.post("/api/evidence/{evidence_id}/validate")
def validate_evidence(evidence_id: int) -> dict:
    """Validación: acto EXPLÍCITO de la persona. Ningún modelo la hace."""
    with _db() as conn:
        try:
            domain.evidence_validate(conn, evidence_id)
        except domain.DomainError as exc:
            raise _domain_error(exc)
    return {"evidence_id": evidence_id, "validated": True}


class ForgetIn(BaseModel):
    reason: str


@app.post("/api/evidence/{evidence_id}/forget")
def forget_evidence(evidence_id: int, body: ForgetIn) -> dict:
    with _db() as conn:
        try:
            domain.evidence_tombstone(conn, evidence_id, body.reason)
        except domain.DomainError as exc:
            raise _domain_error(exc)
    return {"evidence_id": evidence_id, "tombstoned": True}


class HypothesisIn(BaseModel):
    statement: str


@app.post("/api/hypotheses")
def add_hypothesis(body: HypothesisIn) -> dict:
    with _db() as conn:
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
def link_evidence(body: LinkIn) -> dict:
    with _db() as conn:
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
def preregister_experiment(body: ExperimentIn) -> dict:
    with _db() as conn:
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
def complete_experiment(experiment_id: int, body: CompleteIn) -> dict:
    with _db() as conn:
        try:
            eid = domain.experiment_complete(
                conn, experiment_id=experiment_id, outcome=body.outcome,
                notes=body.notes,
            )
        except domain.DomainError as exc:
            raise _domain_error(exc)
    return {"experiment_id": experiment_id, "generated_evidence_id": eid}


@app.post("/api/recompute")
def recompute() -> dict:
    """Recalcula TODOS los índices y sella. El seal se computa acá, antes
    de que cualquier narrador vea el resultado."""
    with _db() as conn:
        return engine.recompute_all(conn)


# ------------------------------------------------------------- roles LLM ----

class NarrativeIn(BaseModel):
    narrative: str


@app.post("/api/extract")
def extract_signals(body: NarrativeIn) -> dict:
    """Extractor (rol LLM SIN autoridad): propone candidatos a señal desde
    una narrativa. Los candidatos se PERSISTEN como evidencia pendiente
    (`validated=0`, tipo `narrative_extracted`): entran a la cola de
    validación, no al cálculo. Validarlos es un acto aparte de la persona.
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
    with _db() as conn:
        for c in candidates:
            eid = domain.evidence_add(
                conn, evidence_type="narrative_extracted",
                source="llm_extractor",
                content={"señal": c["señal"], "cita": c["cita"]},
                validated=False,  # nace pendiente: la persona valida
            )
            created.append({"evidence_id": eid, **c})
    return {"candidates": created,
            "note": "candidatos pendientes de validación; ningún índice se "
            "movió hasta que la persona valide"}


@app.post("/api/abduce")
def abduce_hypotheses() -> dict:
    """Abductor (rol LLM SIN autoridad): dado el resumen sellado, propone
    hipótesis rivales. NO las persiste ni les asigna confianza; la persona
    decide cuáles registrar."""
    with _db() as conn:
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
def narrate(language: str = "English") -> dict:
    """Narrador (rol LLM SIN autoridad): sella, resume, narra y registra la
    prosa por su hash JUNTO al seal. Cambiar de backend (o de idioma) cambia
    la prosa y ningún número — ese es el test de arquitectura. `language`:
    English (default) | Spanish."""
    backend = backend_from_env()
    with _db() as conn:
        try:
            out = views.narrate_compass(conn, Narrator(backend), language)
        except LLMOutputError as exc:
            raise HTTPException(status_code=422,
                                detail=f"narración rechazada en frontera: {exc}")
        except Exception as exc:
            raise HTTPException(status_code=502,
                                detail=f"error del backend LLM: {exc}")
    return out
