"""Tests de la capa del hackathon: DemoBackend, GeminiBackend (fail-closed),
la invariante de arquitectura a nivel API, y un smoke del ciclo HTTP.

No prueban Gemini EN VIVO (punto ciego declarado, como Anthropic/Ollama):
prueban el contrato y las fronteras que sí se pueden verificar sin red.
"""

from __future__ import annotations

import os

import pytest

from compass import llm, seed_demo
from compass.db import open_db
from compass.views import sealed_state


# --------------------------------------------------------- DemoBackend ------

def test_demo_backend_extractor_returns_valid_candidates():
    b = llm.DemoBackend()
    raw = b.complete(llm.EXTRACTOR_SYSTEM, "vuelvo solo a lo que me obsesiona")
    candidates = llm.validate_signal_candidates(raw)  # pasa la validación real
    assert candidates and all({"señal", "cita"} == set(c) for c in candidates)


def test_demo_backend_abductor_returns_rival_hypotheses():
    b = llm.DemoBackend()
    raw = b.complete(llm.ABDUCTOR_HYPOTHESES_SYSTEM, "{}")
    props = llm.validate_hypothesis_proposals(raw)
    assert len(props) >= 2  # rivales: nunca una sola (tunnel vision)


def test_demo_backend_experiment_has_declared_failure_criterion():
    b = llm.DemoBackend()
    raw = b.complete(llm.ABDUCTOR_EXPERIMENT_SYSTEM, "hipótesis X")
    design = llm.validate_experiment_design(raw)
    assert design["failure_criterion"].strip()  # preregistro con dientes


def test_demo_backend_narrator_is_prose_not_json():
    b = llm.DemoBackend()
    prose = llm.validate_prose(b.complete(llm.NARRATOR_SYSTEM, "{}"))
    assert "sealed" in prose.lower()


# ------------------------------------------------- GeminiBackend fronteras --

def test_gemini_backend_fails_closed_without_credential(monkeypatch):
    """Sin key ni Vertex, no se intenta ninguna llamada de red."""
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI",
                "GOOGLE_CLOUD_PROJECT"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="credencial|GEMINI_API_KEY"):
        llm.GeminiBackend()._client()


def test_gemini_vertex_requires_project(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        llm.GeminiBackend()._client()


def test_backend_from_env_selects_each_kind(monkeypatch):
    for kind, cls in (("fake", llm.FakeBackend), ("demo", llm.DemoBackend),
                      ("gemini", llm.GeminiBackend)):
        monkeypatch.setenv("COMPASS_BACKEND", kind)
        assert isinstance(llm.backend_from_env(), cls)


# --------------------------------- invariante de arquitectura (a nivel API) -

def test_swapping_narrator_backend_never_changes_the_seal(tmp_path):
    """El seal del estado se computa ANTES del narrador: cambiar de backend
    cambia la prosa y ningún número. Es el test de llm-out-of-the-loop."""
    db = str(tmp_path / "arch.db")
    conn = open_db(db)
    seed_demo.seed(conn)

    seal_before = sealed_state(conn)["seal"]

    from compass.views import narrate_compass
    from compass.llm import Narrator

    out_fake = narrate_compass(conn, Narrator(llm.FakeBackend("prosa A")))
    out_demo = narrate_compass(conn, Narrator(llm.DemoBackend()))

    # Mismo seal de estado con los dos backends; prosa distinta.
    assert out_fake["seal"] == out_demo["seal"] == seal_before
    assert out_fake["prose"] != out_demo["prose"]
    conn.close()


# ------------------------------------------------------------ API smoke -----

def test_api_full_cycle_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPASS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("COMPASS_BACKEND", "demo")
    monkeypatch.delenv("COMPASS_GCS_BUCKET", raising=False)
    # reimportar storage y api DESPUÉS de fijar el env: leen el dir al import.
    import importlib

    from compass import storage as storage_module
    importlib.reload(storage_module)
    from compass import api as api_module
    importlib.reload(api_module)
    from fastapi.testclient import TestClient

    with TestClient(api_module.app) as c:
        assert c.get("/health").json()["status"] == "ok"
        st = c.get("/api/state").json()
        assert st["state"]["hypotheses"], "el seed debe poblar hipótesis"
        assert c.get("/api/chain").json()["integrity_ok"] is True
        ex = c.post("/api/extract", json={"narrative": "vuelvo solo a lo que me obsesiona"})
        assert ex.status_code == 200 and ex.json()["candidates"]
        assert c.post("/api/recompute").json()["seal"]


def test_api_isolates_users(tmp_path, monkeypatch):
    """Dos compass ids distintos son bases distintas: lo que uno escribe no
    aparece en el otro."""
    monkeypatch.setenv("COMPASS_DATA_DIR", str(tmp_path / "data2"))
    monkeypatch.setenv("COMPASS_BACKEND", "demo")
    monkeypatch.delenv("COMPASS_GCS_BUCKET", raising=False)
    import importlib

    from compass import storage as storage_module
    importlib.reload(storage_module)
    from compass import api as api_module
    importlib.reload(api_module)
    from fastapi.testclient import TestClient

    with TestClient(api_module.app) as c:
        a = {"X-Compass-User": "alice"}
        b = {"X-Compass-User": "bob"}
        hid = c.post("/api/hypotheses", json={"statement": "alice-only hypothesis"},
                     headers=a).json()["hypothesis_id"]
        a_ids = [h["id"] for h in c.get("/api/hypotheses", headers=a).json()["hypotheses"]]
        b_stmts = [h["statement"] for h in
                   c.get("/api/hypotheses", headers=b).json()["hypotheses"]]
        assert hid in a_ids
        assert "alice-only hypothesis" not in b_stmts
        # id inválido: rechazado en la frontera, no adivinado
        assert c.get("/api/state", headers={"X-Compass-User": "../etc"}).status_code == 400
