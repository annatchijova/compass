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

from . import (confrontation, domain, engine, intake, onet, prompts, seed_demo,
               storage, trajectories, views)
from .audit_chain import verify_chain, verify_content
from .db import EVIDENCE_TYPES, open_db
from .llm import (AVAILABLE_BACKENDS, Abductor, Extractor, LLMOutputError,
                  Narrator, ResourceFinder, TrajectoryProposer,
                  backend_from_env, backend_from_kind)


def _selectable_backends() -> list[str]:
    """Los backends que un usuario PUEDE elegir en este deploy. Por defecto: el
    del proceso + el demo offline (para mostrar el invariante swap→mismo seal
    sin exponer vendors sin credencial). Se amplía con COMPASS_ALLOWED_BACKENDS."""
    default = os.environ.get("COMPASS_BACKEND", "fake")
    allowed = os.environ.get("COMPASS_ALLOWED_BACKENDS")
    if allowed:
        picks = [b.strip() for b in allowed.split(",")
                 if b.strip() in AVAILABLE_BACKENDS]
        return picks or [default]
    return sorted({default, "demo"})


def _resolve_backend(requested: Optional[str]):
    """Backend a usar para un request: el pedido si está permitido, si no el
    del proceso. Nunca deja elegir un backend fuera de la allowlist."""
    default = os.environ.get("COMPASS_BACKEND", "fake")
    if requested and requested in _selectable_backends():
        return backend_from_kind(requested)
    return backend_from_kind(default)


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
        content = verify_content(conn)
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
        "chain_content_ok": content.content_ok,
    }


# ---------------------------------------------------------------- lectura ---

@app.get("/api/state")
def get_state(uid: str = Depends(get_uid)) -> dict:
    """Estado sellado: el seal existe ANTES de cualquier narrador.

    Agrega `coverage` (display-only, FUERA del sello): cuánta evidencia
    validada no está vinculada a ninguna hipótesis. La anti-adulación pesa
    sobre el grafo linkeado; evidencia sin linkear no cuenta, así que un
    grafo incompleto puede inflar por omisión (Red Team Round 1, finding C).
    Superficiar el faltante es la mitigación honesta; no cambia ningún índice.
    """
    with _db(uid) as conn:
        sealed = views.sealed_state(conn)
        unlinked = conn.execute(
            "SELECT COUNT(*) AS n FROM evidence e WHERE e.validated = 1 "
            "AND e.deleted = 0 AND NOT EXISTS (SELECT 1 FROM hypothesis_evidence he "
            "WHERE he.evidence_id = e.id)"
        ).fetchone()["n"]
    sealed["coverage"] = {"validated_unlinked": unlinked}
    return sealed


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
        content = verify_content(conn)
    return {
        "entries": [dict(r) for r in rows],
        "linkage_ok": report.linkage_ok,
        "integrity_ok": report.integrity_ok,
        "content_ok": content.content_ok,
        "issues": report.issues + content.issues,
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


# --------------------------------------------------- guía de narrativa ------

@app.get("/api/prompts")
def narrative_prompts(lang: str = "en", tier: Optional[str] = None) -> dict:
    """Preguntas-guía para que nadie se trabe frente a una caja en blanco. Dos
    niveles: 'easy' (rampa suave) y 'deeper' (episódicas). Sin `tier`, vienen
    todas (las fáciles primero). La respuesta va al extractor; no concluye nada."""
    return {"prompts": prompts.starter_prompts(lang, tier)}


# --------------------------------------------------------------- intake -----
# Intake vocacional (Big Five + RIASEC): siembra hipótesis, no dictamina. Las
# propuestas entran como pendientes (self_report, peso mínimo); la persona
# valida en el ledger. Ningún índice se mueve acá.

@app.get("/api/intake/items")
def intake_items(instrument: str, lang: str = "en") -> dict:
    try:
        return {"instrument": instrument, "lang": lang,
                "items": intake.items(instrument, lang)}
    except intake.IntakeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class AssessmentIn(BaseModel):
    instrument: str = Field(..., description="big_five | riasec")


@app.post("/api/intake/assessments")
def start_assessment(body: AssessmentIn, uid: str = Depends(get_uid)) -> dict:
    with _db(uid, write=True) as conn:
        try:
            aid = intake.start_assessment(conn, body.instrument)
        except intake.IntakeError as exc:
            raise _domain_error(exc)
    return {"assessment_id": aid}


class ResponseItem(BaseModel):
    item_code: str
    value: int


class ResponsesIn(BaseModel):
    responses: list[ResponseItem]


@app.post("/api/intake/assessments/{assessment_id}/responses")
def submit_responses(assessment_id: int, body: ResponsesIn,
                     uid: str = Depends(get_uid)) -> dict:
    with _db(uid, write=True) as conn:
        try:
            for r in body.responses:
                intake.submit_response(conn, assessment_id, r.item_code, r.value)
        except intake.IntakeError as exc:
            raise _domain_error(exc)
    return {"submitted": len(body.responses)}


@app.get("/api/intake/assessments/{assessment_id}/proposals")
def intake_proposals(assessment_id: int, uid: str = Depends(get_uid)) -> dict:
    with _db(uid) as conn:
        try:
            return intake.proposed_hypotheses(conn, assessment_id)
        except intake.IntakeError as exc:
            raise HTTPException(status_code=404, detail=str(exc))


class RegisterIn(BaseModel):
    dimension: str


@app.post("/api/intake/assessments/{assessment_id}/register")
def register_proposal(assessment_id: int, body: RegisterIn,
                      uid: str = Depends(get_uid)) -> dict:
    """La persona acepta una propuesta: crea la hipótesis-candidata + evidencia
    self_report PENDIENTE. Validarla queda como acto de la persona en el ledger."""
    with _db(uid, write=True) as conn:
        try:
            return intake.register_proposal(conn, assessment_id, body.dimension)
        except intake.IntakeError as exc:
            raise _domain_error(exc)


# ---------------------------------------------------------- trayectorias ----
# Navegación vocacional (design doc §5): a qué dedicarse como FIT entre
# capacidades demostradas y lo que un camino requiere — sin porcentaje de
# destino. El fit solo LEE hipótesis ya selladas; no mueve ningún índice.

@app.get("/api/onet/occupations")
def onet_occupations(lang: str = "en") -> dict:
    """Ocupaciones O*NET (dato basado en evidencia, CC BY 4.0) para armar
    trayectorias con capacidades-requisito reales."""
    return {"occupations": onet.list_occupations(lang),
            "attribution": onet.ONET_ATTRIBUTION}


@app.get("/api/onet/occupations/{code}")
def onet_occupation(code: str, lang: str = "en") -> dict:
    try:
        return onet.occupation(code, lang)
    except onet.OccupationError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class AdoptIn(BaseModel):
    code: str
    lang: str = "es"


@app.post("/api/onet/adopt")
def adopt_occupation(body: AdoptIn, uid: str = Depends(get_uid)) -> dict:
    """Adopta una ocupación: crea su trayectoria con hipótesis-candidatas por
    capacidad-requisito. No valida nada; mide el fit contra tu evidencia."""
    with _db(uid, write=True) as conn:
        try:
            return onet.adopt_occupation(conn, body.code, body.lang)
        except onet.OccupationError as exc:
            raise _domain_error(exc)


@app.get("/api/trajectories")
def list_trajectories(uid: str = Depends(get_uid)) -> dict:
    with _db(uid) as conn:
        return {"trajectories": trajectories.list_trajectories(conn)}


class TrajectoryIn(BaseModel):
    name: str
    description: str = ""


@app.post("/api/trajectories")
def add_trajectory(body: TrajectoryIn, uid: str = Depends(get_uid)) -> dict:
    with _db(uid, write=True) as conn:
        try:
            tid = trajectories.trajectory_add(conn, name=body.name,
                                              description=body.description)
        except trajectories.TrajectoryError as exc:
            raise _domain_error(exc)
    return {"trajectory_id": tid}


class RequirementIn(BaseModel):
    hypothesis_id: int
    label: str


@app.post("/api/trajectories/{trajectory_id}/requirements")
def add_requirement(trajectory_id: int, body: RequirementIn,
                    uid: str = Depends(get_uid)) -> dict:
    with _db(uid, write=True) as conn:
        try:
            rid = trajectories.requirement_add(
                conn, trajectory_id=trajectory_id,
                hypothesis_id=body.hypothesis_id, label=body.label,
            )
        except trajectories.TrajectoryError as exc:
            raise _domain_error(exc)
    return {"requirement_id": rid}


@app.get("/api/trajectories/{trajectory_id}/fit")
def trajectory_fit(trajectory_id: int, uid: str = Depends(get_uid)) -> dict:
    with _db(uid) as conn:
        try:
            return trajectories.trajectory_fit(conn, trajectory_id)
        except trajectories.TrajectoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/trajectories/discriminate")
def discriminate(a: int, b: int, uid: str = Depends(get_uid)) -> dict:
    """Qué capacidad conviene testear para separar las trayectorias a y b."""
    with _db(uid) as conn:
        try:
            return trajectories.discriminating_requirements(conn, a, b)
        except trajectories.TrajectoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/confrontations")
def get_confrontations(uid: str = Depends(get_uid)) -> dict:
    """Confrontación autopercepción vs. datos (design doc §5).

    Devuelve DATOS —cuentas de cada lado— y la política con la que se
    evaluaron, nunca prosa: la frase la arma una plantilla fija en la
    interfaz. Ningún modelo decide si hay discrepancia ni la redacta,
    porque bajo presión narrativa podría convertirla en un veredicto sobre
    quién es la persona, que es exactamente lo que §5 prohíbe.

    Proyección de solo lectura: no escribe, no anexa a la cadena y no mueve
    ningún índice. La política es PROVISORIA (§9); viene en la respuesta
    para que se pueda discutir el umbral y no la conclusión.
    """
    with _db(uid) as conn:
        return confrontation.confrontations(conn)


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


class HypothesisRefIn(BaseModel):
    hypothesis_id: int


def _hypothesis_statement(conn, hypothesis_id: int) -> str:
    row = conn.execute("SELECT statement FROM hypothesis WHERE id = ?",
                       (hypothesis_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404,
                            detail=f"hypothesis id={hypothesis_id} no existe")
    return row["statement"]


@app.post("/api/trajectories/propose")
def propose_trajectories(uid: str = Depends(get_uid)) -> dict:
    """Trazador (rol LLM SIN autoridad): propone caminos candidatos
    componiendo las hipótesis que YA existen.

    Ataca la hoja en blanco sin regalarle capacidades al modelo: se le
    pasan las hipótesis de la persona —TODAS, incluidas las latentes, que
    el estado sellado oculta (§3.2) y que son justamente las que un camino
    nuevo necesita— y solo puede citar esos ids. Un id inventado se rechaza
    en frontera.

    No persiste nada: crear la trayectoria y sus requisitos es un acto de
    la persona, con las ediciones que quiera.
    """
    with _db(uid) as conn:
        rows = conn.execute(
            "SELECT id, statement, status FROM hypothesis "
            "WHERE status != 'descartada' ORDER BY id ASC"
        ).fetchall()
    hypotheses = [dict(r) for r in rows]
    if not hypotheses:
        raise HTTPException(
            status_code=409,
            detail="no hay hipótesis con las que armar una trayectoria: "
                   "registrá al menos una capacidad primero")
    backend = backend_from_env()
    try:
        proposals = TrajectoryProposer(backend).propose(hypotheses)
    except LLMOutputError as exc:
        raise HTTPException(status_code=422,
                            detail=f"salida del modelo rechazada en frontera: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"error del backend LLM: {exc}")
    return {"proposals": proposals,
            "note": "propuestas: no se creó ninguna trayectoria y ningún "
            "índice se movió; aceptá la que te sirva"}


@app.post("/api/experiments/design")
def design_experiment(body: HypothesisRefIn, uid: str = Depends(get_uid)) -> dict:
    """Diseñador de experimentos (rol LLM SIN autoridad): dada una hipótesis,
    REDACTA un borrador de experimento discriminante con su criterio de
    fracaso declarado de antemano.

    Es un borrador y nada más: no persiste, no preregistra y no mueve ningún
    índice. Preregistrarlo (POST /api/experiments), con o sin ediciones, es
    un acto de la persona. Que el criterio de fracaso venga escrito desde el
    borrador es justamente lo que evita el confirmation-only testing que el
    esquema bloquea (design doc §4).
    """
    with _db(uid) as conn:
        statement = _hypothesis_statement(conn, body.hypothesis_id)
    backend = backend_from_env()
    try:
        draft = Abductor(backend).design_experiment(statement)
    except LLMOutputError as exc:
        raise HTTPException(status_code=422,
                            detail=f"salida del modelo rechazada en frontera: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"error del backend LLM: {exc}")
    return {"hypothesis_id": body.hypothesis_id,
            "hypothesis_statement": statement,
            "draft": draft,
            "note": "borrador: nada se preregistró y ningún índice se movió; "
            "editalo y preregistralo vos"}


@app.post("/api/resources")
def find_resources(body: HypothesisRefIn, uid: str = Depends(get_uid)) -> dict:
    """Buscador de recursos (rol LLM SIN autoridad): dónde ir a EJECUTAR el
    experimento de una capacidad.

    Lo que devuelve es material de consulta: vive fuera del sello, no entra
    al ledger, nadie lo valida y no mueve ningún índice. `grounded` dice si
    los recursos salieron de una búsqueda real (con `sources` citables) o de
    la memoria del modelo; la UI TIENE que mostrar esa diferencia en vez de
    presentar como buscado algo que no lo fue.

    Privacidad (design doc §6): con un backend que busca, esta llamada manda
    el enunciado de la capacidad a Google. Por eso es una acción explícita de
    la persona y no algo que el sistema haga solo.
    """
    with _db(uid) as conn:
        statement = _hypothesis_statement(conn, body.hypothesis_id)
    backend = backend_from_env()
    try:
        found = ResourceFinder(backend).find(statement)
    except LLMOutputError as exc:
        raise HTTPException(status_code=422,
                            detail=f"salida del modelo rechazada en frontera: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"error del backend LLM: {exc}")
    return {"hypothesis_id": body.hypothesis_id,
            "capability": statement,
            **found,
            "note": "recursos de consulta: no son evidencia, no entran al "
            "ledger y no movieron ningún índice"}


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
