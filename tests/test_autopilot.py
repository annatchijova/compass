"""Autopilot: el equipo en background. PROPONE y VIGILA; nunca decide ni sella.

Estos tests bloquean el invariante que separa a COMPASS de un horóscopo,
ahora también para el actor autónomo:

- una corrida del autopilot no mueve NI un índice NI el sello (la guardia
  fail-closed lo hace cumplir en vivo);
- cambiar el backend cambia la prosa y las propuestas, jamás un número;
- el Sentinel detecta una edición de contenido sellada;
- el briefing se guarda AL LADO (artefacto + hash en la cadena), sin subir
  el esquema ni romper la verificación;
- sin hipótesis, degrada a un ABSTAIN honesto en vez de inventar.
"""

from __future__ import annotations

import sqlite3

from compass import seed_demo, views
from compass.agent import autopilot
from compass.audit_chain import verify_chain, verify_content
from compass.db import open_db
from compass.llm import DemoBackend, FakeBackend


def _seeded(path) -> sqlite3.Connection:
    conn = open_db(str(path))
    seed_demo.seed(conn)
    return conn


def test_autopilot_no_mueve_ni_un_indice_ni_el_sello(tmp_path):
    conn = _seeded(tmp_path / "c.db")
    seal_before = views.sealed_state(conn)["seal"]
    indices_before = autopilot._indices_snapshot(conn)

    out = autopilot.autopilot_once(conn, backend=DemoBackend(),
                                   uid="u1", data_dir=str(tmp_path))

    assert views.sealed_state(conn)["seal"] == seal_before
    assert autopilot._indices_snapshot(conn) == indices_before
    assert out["seal"] == seal_before
    # y produjo trabajo real: propuso experimento y actividades (backend demo)
    assert out["briefing"]["proposed_experiment"] is not None
    assert out["briefing"]["activities"]["resources"]


def test_cambiar_backend_no_cambia_el_sello(tmp_path):
    """El test de arquitectura, para el actor autónomo: dos backends distintos
    -> misma redacción no, mismo SELLO sí. Si un número se moviera, la
    guardia habría levantado AutopilotBoundaryError."""
    conn_a = _seeded(tmp_path / "a.db")
    conn_b = _seeded(tmp_path / "b.db")
    seal_a = autopilot.autopilot_once(conn_a, backend=DemoBackend(),
                                      uid="a", data_dir=str(tmp_path))["seal"]
    seal_b = autopilot.autopilot_once(conn_b, backend=FakeBackend("prosa fija"),
                                      uid="b", data_dir=str(tmp_path))["seal"]
    assert seal_a == seal_b


def test_sentinel_detecta_edicion_de_contenido(tmp_path):
    conn = _seeded(tmp_path / "c.db")
    assert autopilot.run_sentinel(conn)["ok"] is True

    # Edición directa de una fila de evidencia SIN pasar por el dominio: la
    # cadena selló otro content_hash, así que el Sentinel debe cantar el
    # quiebre de content (linkage/integrity siguen bien).
    conn.execute("UPDATE evidence SET content = ? WHERE id = "
                 "(SELECT id FROM evidence WHERE deleted = 0 LIMIT 1)",
                 ('{"text": "tampered"}',))
    conn.commit()

    s = autopilot.run_sentinel(conn)
    assert s["ok"] is False
    assert s["content_ok"] is False
    assert s["linkage_ok"] is True and s["integrity_ok"] is True
    assert any(i["kind"] == "content" for i in s["issues"])


def test_briefing_se_guarda_al_lado_no_adentro(tmp_path):
    conn = _seeded(tmp_path / "c.db")
    rows_before = conn.execute("SELECT COUNT(*) AS n FROM audit_chain").fetchone()["n"]
    version_before = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'").fetchone()["value"]

    out = autopilot.autopilot_once(conn, backend=DemoBackend(),
                                   uid="u1", data_dir=str(tmp_path))

    # 1. Artefacto AL LADO de la base, no una tabla nueva adentro.
    import os
    assert os.path.exists(out["artifact"])
    assert out["artifact"].endswith("compass_u1.briefing.md")

    # 2. El esquema NO subió: los servicios ya desplegados siguen abriendo v3.
    version_after = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'").fetchone()["value"]
    assert version_after == version_before

    # 3. Exactamente UNA fila nueva, op autopilot_briefing, y la cadena sigue
    # verificando (linkage, integrity y content).
    rows_after = conn.execute("SELECT COUNT(*) AS n FROM audit_chain").fetchone()["n"]
    assert rows_after == rows_before + 1
    op = conn.execute("SELECT op FROM audit_chain ORDER BY seq DESC LIMIT 1"
                      ).fetchone()["op"]
    assert op == "autopilot_briefing"
    assert verify_chain(conn).ok is True
    assert verify_content(conn).content_ok is True


def test_degrada_honesto_sin_hipotesis(tmp_path):
    from compass import engine
    conn = open_db(str(tmp_path / "empty.db"))
    engine.seed_default_config(conn)   # base válida pero sin hipótesis

    out = autopilot.autopilot_once(conn, backend=DemoBackend(),
                                   uid="empty", data_dir=str(tmp_path))

    assert out["briefing"]["proposed_experiment"] is None
    assert any("ABSTAIN" in n or "abstain" in n for n in out["briefing"]["notes"])
    # y no rompió nada: el sello existe y la corrida se registró
    assert out["seal"]
    assert out["chain_entry"] is not None
