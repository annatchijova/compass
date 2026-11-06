"""Red Team Round 2 — reproducible inductions (docs/RED_TEAM_ROUND2.md).

Each experiment prints its PREDICTION before the OBSERVED result. Runs fully
offline against a temp dir: GCS is replaced by a local-directory fake bucket
shared between simulated Cloud Run instances, and google.adk is stubbed so the
Autopilot module imports without the ADK dependency. Touches no deployed
service.

    pip install fastapi httpx
    python3 -I tools/redteam_round2.py
"""
import os, sys, shutil, tempfile, types, json
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
WORK = tempfile.mkdtemp(prefix="r2-")
os.environ["COMPASS_DATA_DIR"] = os.path.join(WORK, "inst_A")
os.environ["COMPASS_BACKEND"] = "demo"

# stub google.adk para poder importar compass.agent.autopilot sin ADK
g = sys.modules.setdefault("google", types.ModuleType("google"))
adk = types.ModuleType("google.adk"); adk.Agent = lambda **kw: kw
tools = types.ModuleType("google.adk.tools"); tools.google_search = None
sys.modules["google.adk"] = adk; sys.modules["google.adk.tools"] = tools

from fastapi.testclient import TestClient
from compass import storage, api, views
from compass.db import open_db
from compass.audit_chain import verify_chain, verify_content
from compass.llm import validate_prose, LLMOutputError, DemoBackend

def hdr(uid): return {"X-Compass-User": uid}
def banner(t): print("\n" + "=" * 72 + "\n" + t + "\n" + "=" * 72)

# ---- fake GCS bucket compartido (dir local) -------------------------------
BUCKET = os.path.join(WORK, "bucket"); os.makedirs(BUCKET)
class Blob:
    def __init__(s, n): s.name = n; s.p = os.path.join(BUCKET, n)
    def exists(s): return os.path.exists(s.p)
    def download_to_filename(s, f): shutil.copyfile(s.p, f)
    def upload_from_filename(s, f): shutil.copyfile(f, s.p)
class Bucket:
    def blob(s, n): return Blob(n)
    def list_blobs(s): return [Blob(n) for n in sorted(os.listdir(BUCKET))]
storage.GCS_BUCKET = "fake"
storage._bucket = lambda: Bucket()
gc = types.ModuleType("google.cloud"); gcs = types.ModuleType("google.cloud.storage")
gcs.Client = lambda: types.SimpleNamespace(bucket=lambda name: Bucket())
gc.storage = gcs; g.cloud = gc
sys.modules["google.cloud"] = gc; sys.modules["google.cloud.storage"] = gcs
def instance(name):
    storage.DATA_DIR = os.path.join(WORK, name); os.makedirs(storage.DATA_DIR, exist_ok=True)

instance("inst_A")
client = TestClient(api.app)

# ===========================================================================
banner("E1 — relabel: 'outcome_external' auto-declarado corrobora sin experimento")
uid = "u-e1relabel0001"
h = client.post("/api/hypotheses", json={"statement": "Soy excelente negociando"}, headers=hdr(uid)).json()["hypothesis_id"]
for i in range(3):
    eid = client.post("/api/evidence", json={"evidence_type": "outcome_external", "source": "yo",
        "content": {"text": f"me dije a mí misma que negocié bien #{i}"}}, headers=hdr(uid)).json()["evidence_id"]
    client.post("/api/link", json={"hypothesis_id": h, "evidence_id": eid, "direction": "supports"}, headers=hdr(uid))
rec = client.post("/api/recompute", headers=hdr(uid)).json()
r = next(x for x in rec["results"] if x["hypothesis_id"] == h)
exps = client.get("/api/experiments", headers=hdr(uid)).json()["experiments"]
n_exp = sum(1 for x in exps if x["hypothesis_id"] == h)
print("PREDICTION: status=corroborada, index>=600, 0 experimentos sobre la hipótesis")
print(f"OBSERVED:   status={r['status']} index={r['index']} experimentos={n_exp} seal={rec['seal'][:16]}…")

# ===========================================================================
banner("E2 — reuso: UN experiment_result vinculado a hipótesis ajenas al experimento")
uid = "u-e2reuse00001"
hs = [client.post("/api/hypotheses", json={"statement": f"capacidad {k}"}, headers=hdr(uid)).json()["hypothesis_id"] for k in "ABC"]
x = client.post("/api/experiments", json={"hypothesis_id": hs[0], "design": "d", "success_criterion": "s",
    "failure_criterion": "f"}, headers=hdr(uid)).json()["experiment_id"]
ev = client.post(f"/api/experiments/{x}/complete", json={"outcome": "exito"}, headers=hdr(uid)).json()["generated_evidence_id"]
for hh in hs[1:]:
    client.post("/api/link", json={"hypothesis_id": hh, "evidence_id": ev, "direction": "supports"}, headers=hdr(uid))
    for i in range(3):  # self_report barato para cruzar el umbral
        e = client.post("/api/evidence", json={"evidence_type": "self_report", "source": "yo",
            "content": {"t": f"{hh}-{i}"}}, headers=hdr(uid)).json()["evidence_id"]
        client.post("/api/link", json={"hypothesis_id": hh, "evidence_id": e, "direction": "supports"}, headers=hdr(uid))
    # outcome_external no: queremos ver si el ÚNICO discriminante es el reusado
rec = client.post("/api/recompute", headers=hdr(uid)).json()
print("PREDICTION: hipótesis B y C cuentan el experiment_result del experimento de A (peso 180 c/u)")
for res in rec["results"]:
    if res["hypothesis_id"] in hs:
        print(f"OBSERVED:   h{res['hypothesis_id']} support={res['support']} index={res['index']} status={res['status']}")
# empujarla a corroborada con self_report puro + el discriminante reusado
hh = hs[1]
for i in range(20):
    e = client.post("/api/evidence", json={"evidence_type": "self_report", "source": "yo",
        "content": {"t": f"extra-{i}"}}, headers=hdr(uid)).json()["evidence_id"]
    client.post("/api/link", json={"hypothesis_id": hh, "evidence_id": e, "direction": "supports"}, headers=hdr(uid))
rec = client.post("/api/recompute", headers=hdr(uid)).json()
res = next(z for z in rec["results"] if z["hypothesis_id"] == hh)
print("PREDICTION: B llega a 'corroborada' con 0 experimentos propios (discriminante prestado + 23 self_report)")
print(f"OBSERVED:   h{hh} index={res['index']} status={res['status']}")

# ===========================================================================
banner("E3 — preregistro post-hoc: preregistrar y cerrar en el mismo instante")
x = client.post("/api/experiments", json={"hypothesis_id": hs[2], "design": "ya lo hice ayer",
    "success_criterion": "lo que pasó", "failure_criterion": "lo que no pasó"}, headers=hdr(uid)).json()["experiment_id"]
client.post(f"/api/experiments/{x}/complete", json={"outcome": "exito"}, headers=hdr(uid))
row = next(z for z in client.get("/api/experiments", headers=hdr(uid)).json()["experiments"] if z["id"] == x)
print("PREDICTION: aceptado; preregistered_at y completed_at separados por milisegundos")
print(f"OBSERVED:   status={row['status']} prereg={row['preregistered_at']} completed={row['completed_at']}")

# ===========================================================================
banner("E4 — lost update entre dos instancias de Cloud Run (GCS last-write-wins)")
uid = "u-e4race000001"
instance("inst_A"); client.post("/api/recompute", headers=hdr(uid))          # crea + sube
instance("inst_B"); client.get("/api/state", headers=hdr(uid))                # B restaura copia
instance("inst_A")
ea = client.post("/api/evidence", json={"evidence_type": "behavioral", "source": "A",
    "content": {"t": "escrito en A"}}, headers=hdr(uid)).json()["evidence_id"]
instance("inst_B")
hb = client.post("/api/hypotheses", json={"statement": "escrito en B"}, headers=hdr(uid)).json()["hypothesis_id"]
instance("inst_C")  # cold start: restaura lo que haya en GCS
conn = open_db(storage.ensure_local(uid))
has_a = conn.execute("SELECT COUNT(*) FROM evidence WHERE source='A'").fetchone()[0]
has_b = conn.execute("SELECT COUNT(*) FROM hypothesis WHERE statement='escrito en B'").fetchone()[0]
rep, cnt = verify_chain(conn), verify_content(conn); conn.close()
print("PREDICTION: la escritura de A se pierde en silencio; la cadena sobreviviente verifica OK")
print(f"OBSERVED:   evidencia_de_A={has_a} hipotesis_de_B={has_b} linkage={rep.linkage_ok} "
      f"integrity={rep.integrity_ok} content={cnt.content_ok} issues={len(rep.issues)+len(cnt.issues)}")

banner("E4b — el Autopilot y la web se pisan: la fila autopilot_briefing desaparece")
from compass.agent import autopilot
uid = "u-e4bauto00001"
instance("inst_WEB"); client.post("/api/recompute", headers=hdr(uid))
instance("inst_JOB"); autopilot.sweep(backend=DemoBackend(), data_dir=storage.DATA_DIR)
def count_auto(dirname):
    instance(dirname); c = open_db(storage.ensure_local(uid))
    n = c.execute("SELECT COUNT(*) FROM audit_chain WHERE op='autopilot_briefing'").fetchone()[0]; c.close(); return n
print(f"  tras sweep, en GCS: autopilot_briefing={count_auto('inst_CHK1')}")
instance("inst_WEB")  # instancia web caliente: su copia local es anterior al sweep
client.post("/api/hypotheses", json={"statement": "escrito por la persona en la web"}, headers=hdr(uid))
print("PREDICTION: tras la escritura web, GCS ya no contiene la fila autopilot_briefing")
print(f"OBSERVED:   autopilot_briefing en GCS={count_auto('inst_CHK2')}")

# ===========================================================================
banner("E5 — amplificación de costo: uids anónimos ilimitados → llamadas LLM del Autopilot")
class Counting:
    def __init__(s): s.inner = DemoBackend(); s.n = 0
    def complete(s, system, user): s.n += 1; return s.inner.complete(system, user)
    def __getattr__(s, a): return getattr(s.inner, a)
instance("inst_WEB2")
N = 25
for i in range(N):
    client.post("/api/recompute", headers=hdr(f"u-flood{i:06d}"))  # 1 POST sin cuerpo por uid
cb = Counting()
instance("inst_JOB2")
before = len(os.listdir(BUCKET))
res = autopilot.sweep(backend=cb, data_dir=storage.DATA_DIR)
flood = [r for r in res if r["uid"].startswith("u-flood")]
print(f"PREDICTION: cada uid creado con UN POST anónimo entra al barrido y cuesta >=1 llamada LLM")
print(f"OBSERVED:   blobs en bucket={before} uids_flood_barridos={len(flood)}/{N} "
      f"llamadas_backend_totales={cb.n} (≈{cb.n/max(len(res),1):.1f} por brújula)")
# también: un GET anónimo crea base local (memoria en Cloud Run /tmp)
instance("inst_WEB3")
for i in range(N): client.get("/health"); client.get("/api/state", headers=hdr(f"u-get{i:06d}"))
files = [f for f in os.listdir(storage.DATA_DIR) if f.startswith("compass_u-get") and f.endswith(".db")]
sz = sum(os.path.getsize(os.path.join(storage.DATA_DIR, f)) for f in os.listdir(storage.DATA_DIR) if f.startswith("compass_u-get"))
print(f"  GET-only: {len(files)} bases locales creadas, {sz//1024} KiB en DATA_DIR (/tmp = RAM en Cloud Run)")

# ===========================================================================
banner("E6 — variantes del guard de prosa (finding A, variant analysis)")
samples = [
    "Your design capability is 97% certain.",
    "Your design capability is 97 percent certain.",
    "Your design capability is 97 per cent certain.",
    "Your design capability is 97 pct.",
    "Tu capacidad de diseño está al noventa y siete por ciento.",
    "Your design capability is 97％ certain.",
    "There is a 0.97 probability you have design capability.",
    "Your design index is 950/1000 — essentially certain.",
    "You are almost certainly a gifted systems designer; this is settled.",
]
print("PREDICTION: solo pasan el filtro las variantes sin dígito+'%|percent|por ciento' contiguos")
for s in samples:
    try: validate_prose(s); verdict = "ACEPTADA"
    except LLMOutputError: verdict = "rechazada"
    print(f"OBSERVED:   {verdict:9s} | {s}")

# ===========================================================================
banner("E7 — sin header: escrituras anónimas caen en la vitrina compartida 'demo'")
instance("inst_A")
ev = client.get("/api/evidence").json()["evidence"]
target = next(e for e in ev if not e["deleted"])
r = client.post(f"/api/evidence/{target['id']}/forget", json={"reason": "vandalismo"})
after = next(e for e in client.get("/api/evidence").json()["evidence"] if e["id"] == target["id"])
print("PREDICTION: un request sin X-Compass-User borra evidencia de la vitrina que ve todo juez")
print(f"OBSERVED:   http={r.status_code} evidencia#{target['id']} deleted={after['deleted']}")

print("\nWORK DIR:", WORK)
