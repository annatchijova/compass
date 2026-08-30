# COMPASS

**An adaptive personal-navigation partner. A compass, not a mirror.**

COMPASS is a vocational-orientation tool built the opposite way round from
the usual one. Instead of asking you to rate yourself and returning a
confident profile, it treats "what should I dedicate myself to" as a **fit
between capabilities you have demonstrated and what a path actually
requires** — and it makes you go find out. Each capability is a hypothesis;
the system proposes a concrete, preregistered experiment that would
discriminate it, you run it in your life, and the outcome moves an index
that a deterministic engine — never a model — computes and seals.

Two invariants separate it from a personality test with a chatbot bolted on:

1. **No claim about the person exists without recorded, sealed evidence.**
2. **No number describing the person ever comes out of an LLM.** A
   deterministic engine computes and *seals* every index before any model
   is called.

The full design rationale is in [`docs/COMPASS-DESIGN-v0.md`](docs/COMPASS-DESIGN-v0.md).

---

## Hackathon — All Things Agentic

**Category: Collaborative Partner** — an interactive agent that walks the
person through the abductive cycle and learns from the sealed state between
turns.

The three mandatory boxes, all checked:

| Requirement | How COMPASS meets it |
|---|---|
| **Gemini model** (Gemini API or Vertex AI) | `GeminiBackend` (`src/compass/llm.py`) — one backend for both transports via the native `google-genai` env flags. The mandatory model, used only to *narrate* and *propose*. |
| **Google agent framework** | **ADK** — `compass.agent.root_agent` (`src/compass/agent/agent.py`): a Collaborative Partner whose authority is exactly its tool set. |
| **Google Cloud service** | **Cloud Run** hosts the FastAPI backend; **Vertex AI** serves Gemini through the service identity (no API key stored). See [`DEPLOY.md`](DEPLOY.md). |

- **Live backend (Cloud Run + Gemini/Vertex):** https://compass-1028999311218.us-central1.run.app
  ([`/health`](https://compass-1028999311218.us-central1.run.app/health) ·
  [`/api/state`](https://compass-1028999311218.us-central1.run.app/api/state) ·
  [`/docs`](https://compass-1028999311218.us-central1.run.app/docs))
- **Live web app (Cloud Run):** https://compass-web-1028999311218.us-central1.run.app
- **Demo video:** _to be filled_
- **Architecture diagram:** below, and in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

> Proven in production: `POST /api/narrate` with Gemini 2.5 Flash on Vertex
> returns the same state seal (`8fc1128…`) as the offline backend — the model
> changed the words, not a single sealed number. That is the whole thesis.

### Anyone can use it — judges and owner alike

The hosted service is multi-user with no login. Every browser gets its own
**isolated compass**, keyed by an opaque `X-Compass-User` id (a per-browser
session key, or one you pin to return to yours). Each id maps to its own
sealed SQLite base, seeded with a starter scenario so you land on something
you can immediately explore and modify without touching anyone else's. Each
base is snapshotted to Cloud Storage after every write and restored on
access, so your compass survives cold starts and redeploys. The id is
validated against a strict allowlist (`^[A-Za-z0-9_-]{1,64}$`) before it ever
touches a path. If storage is unreachable the service degrades to local-only
and says so on `/health` — a persistence failure never destroys a computed
result.

### Why this is an *architecturally disciplined* agent

The differentiator is not that an agent talks; it is **where the agent is
not allowed to be**. A language model can read the evidence correctly and
still reach the wrong conclusion under narrative pressure. So the model
never touches the decision path:

- The deterministic engine produces and **seals** every index *before* the
  agent or narrator is invoked. The model cannot influence a value that was
  already fixed.
- The ADK agent's authority is bounded by its tools. Only one tool
  (`recompute_indices`) produces numbers, and it runs the deterministic
  engine and seals the result *before returning it*: the agent reads the
  number, it does not fabricate one. There is deliberately **no tool** to
  validate evidence, discard a hypothesis, or declare an experiment's
  outcome — those are the person's acts.
- **Architecture test:** swapping the model backend (Gemini ↔ the offline
  `demo`/`fake` backend) changes only the wording — never a verdict, seal,
  or the chain of custody. This is enforced by
  `tests/test_hackathon_layer.py::test_swapping_narrator_backend_never_changes_the_seal`.

### What Gemini actually does here

Growing the model's presence means growing what it *proposes*, never what it
decides. Four roles, none with authority:

| Role | Proposes | Person's act |
|---|---|---|
| **Extractor** | candidate signals from a narrative | validating one is what makes it evidence |
| **Abductor** | rival hypotheses about a capability | keeping or discarding one |
| **Trajectory proposer** | candidate paths, composed **only** from hypotheses that already exist | accepting one creates it, through the ordinary endpoints |
| **Experiment designer** | a discriminating experiment for an open capability — design, success criterion, and the **failure criterion declared before running it** | editing it and preregistering it |
| **Resource finder** | concrete places to go *run* that experiment — a course, community, open project, reading, tool, or kind of person — found by Google Search on Vertex, each with its source | deciding whether any is worth their time |

The last three answer the question a vocational test usually dodges: not
"what are you like" but **"what do you do on Monday to find out"** — and the
trajectory proposer answers the one before it, *which paths are even worth
weighing*, so nobody starts at a blank page.

All three are proposals in the strict sense — asking for any of them writes
nothing, appends nothing to the chain, and moves no index. That is not a
convention, it is a test: `test_suggesting_moves_no_sealed_number` and
`test_proposing_trajectories_moves_no_sealed_number` compare the sealed
state, the chain length and a fresh recompute across the calls, and fail if
any of them budges. A negative control confirmed they go red the moment an
endpoint writes.

The trajectory proposer carries a guard of its own: **it may only cite
hypotheses that exist**. A model that could invent a hypothesis id could
invent the capability that makes a path look good, so every requirement is
checked against the person's real ids and an unknown one is rejected at the
boundary rather than created (proposing *new* capabilities is the abductor's
job, not this one's). Accepting a proposal runs the same two endpoints the
person would use by hand — the proposer gets no private write path.

Two honesty rules the resource finder carries, because it is the first
feature that reads the outside world:

- **Web content is data, never instruction.** It is parsed, validated
  against a closed schema (a fixed vocabulary of resource kinds, bounded
  lengths, the same no-percentages guard the narrator has), rendered as
  text and links, and never executed. Non-`http(s)` URLs are stripped at
  the boundary.
- **A search says it searched.** Backends that cannot search return
  `grounded: false` and the UI says so in as many words, with no URLs
  attached. Presenting a model's memory as a search would be exactly the
  unsupported claim this project exists to refuse. Nothing found is
  evidence: resources live outside the seal and never enter the ledger.

Searching sends the capability's wording to Google, so it is always an
explicit click — never something the system does on its own (design doc §6).

---

## Architecture

```mermaid
flowchart TD
    subgraph person["The person — the only source of validated truth"]
        P[Narratives, self-reports, experiment outcomes]
    end

    subgraph llm["LLM roles — NO authority (Gemini via ADK)"]
        EX[Extractor: narrative → candidate signals]
        AB[Abductor: rival hypotheses + discriminating experiments]
        NA[Narrator: puts the SEALED state into words]
    end

    subgraph core["Deterministic core — stdlib only, no float in the decision path"]
        DOM[Domain ops: evidence, hypotheses, experiments]
        ENG[Confidence Engine v1: Fraction math, integer 0-1000 index]
        SEAL[(Seal: SHA-256 over canonical bytes)]
        CHAIN[[Audit chain: append-only, hash-chained]]
    end

    subgraph gcp["Google Cloud"]
        RUN[Cloud Run: FastAPI domain API]
        ADKR[ADK agent: root_agent]
        VTX[Vertex AI: Gemini]
    end

    FE[Next.js frontend]

    P -->|validates candidates| DOM
    EX -.proposes.-> DOM
    AB -.proposes.-> DOM
    DOM --> ENG --> SEAL --> CHAIN
    SEAL -->|read-only compressed summary| NA
    NA -.prose stored beside the seal, by hash.-> CHAIN
    RUN --- core
    ADKR --- core
    ADKR --> VTX
    VTX --- llm
    FE -->|HTTP| RUN

    classDef noauth fill:#fff7ed,stroke:#f59e0b;
    classDef det fill:#eef2ff,stroke:#6366f1;
    class EX,AB,NA noauth;
    class DOM,ENG,SEAL,CHAIN det;
```

**Authority — who may assert what:**

| Component | Authority | May |
|---|---|---|
| Evidence ledger | the person + the facts | record validated evidence, never delete it silently |
| Confidence engine | versioned rules | compute indices, seal them |
| LLM (Gemini) | none | propose, abduce, narrate — never decide or score |

---

## Quickstart

The core is **pure Python stdlib**. It runs the entire cycle offline, with
no credential and no cloud, using a role-aware `demo` backend.

### 1. The core cycle (CLI, offline)

```bash
python3 -m pytest                          # 146 tests — see "Tests" for the extras
PYTHONPATH=src python3 -m compass init     # then: person, evidence, hyp, link, exp,
                                           # observe, reflect, recompute, compass,
                                           # traj, verify
python3 tools/verify_chain.py compass.db   # independent, stdlib-only verifier
```

`compass verify` reports the three chain signals separately — linkage,
integrity and content — and exits non-zero if any of them breaks. Its own
output strings are still Spanish-only (the API, the narrator and the web app
are bilingual EN/ES).

**Trajectories (vocational fit).** "What to dedicate yourself to" is treated as
a *fit* between demonstrated capabilities and what a path requires — never a
destiny percentage. A trajectory is a set of capability-requirements, each
backed by a hypothesis; `traj fit` projects, deterministically from the sealed
hypotheses, which requirements are met / supported / open / against / discarded
(counts, no probability), and `traj discriminate` names the cheapest open
capability whose experiment would separate two paths. It reuses the same
evidence and experiment machinery; it reads sealed hypotheses and moves no
index. See [`docs/ATTRIBUTIONS.md`](docs/ATTRIBUTIONS.md) for the validated,
openly-licensed instruments (IPIP, O*NET) the intake layer will draw on.

`tools/verify_chain.py` re-implements the seal spec on purpose, so
confirming the audit chain does not require trusting the code that wrote it.

### 2. The API + web app (local)

```bash
pip install '.[api]'                        # fastapi + uvicorn + google-cloud-storage
COMPASS_BACKEND=demo COMPASS_DB=/tmp/compass.db \
  uvicorn compass.api:app --reload --port 8080
# → http://localhost:8080/health  and  /docs
```

The API seeds a demo scenario on first boot, so the compass is populated
immediately. Then, in `frontend/`:

```bash
cd frontend && npm install
NEXT_PUBLIC_API_URL=http://localhost:8080 npm run dev   # → http://localhost:3000
```

The web app covers the evidence → hypothesis → experiment cycle, the audit
chain (linkage, integrity *and* content), the three LLM roles
(`extract` / `abduce` / `narrate`), and the trajectory fit — counts per
requirement, never a destiny percentage. The demo scenario seeds two rival
trajectories over the same sealed hypotheses, so the fit is explorable on the
first visit.

### 3. With the real Gemini model

```bash
pip install '.[gemini,adk]'
# Gemini API key:
export COMPASS_BACKEND=gemini GEMINI_API_KEY=...        COMPASS_MODEL=gemini-2.5-flash
# — or Vertex AI (no key stored):
export COMPASS_BACKEND=gemini GOOGLE_GENAI_USE_VERTEXAI=TRUE \
       GOOGLE_CLOUD_PROJECT=vigia-497422 GOOGLE_CLOUD_LOCATION=global
```

The ADK agent (`compass.agent.root_agent`) is a separate entry point from
the domain API. Run it interactively with the ADK dev UI, or deploy it with
ADK's first-class Cloud Run command:

```bash
adk web src/compass                 # dev UI, discovers the root_agent package
adk deploy cloud_run src/compass/agent   # containerize + deploy the agent
```

### 4. Deploy to Cloud Run

See [`DEPLOY.md`](DEPLOY.md) for the full recipe (project, APIs, env vars,
and the two Gemini-3.x gotchas). Short version:

```bash
gcloud run deploy compass --source . --region us-central1 --allow-unauthenticated \
  --session-affinity --min-instances 1 \
  --set-env-vars COMPASS_BACKEND=gemini,GOOGLE_GENAI_USE_VERTEXAI=TRUE,\
GOOGLE_CLOUD_PROJECT=vigia-497422,GOOGLE_CLOUD_LOCATION=global,\
COMPASS_MODEL=gemini-2.5-flash,COMPASS_GCS_BUCKET=compass-user-data-vigia-497422
```

---

## What the deterministic core guarantees

- **No float in the decision path.** `fractions.Fraction` for every weight,
  ratio, and accumulation; the integer 0–1000 index is an asymptotic floor
  (total certainty never exists — structural fallibilism). The index means
  "accumulation of evidence under versioned rules", and the UI never
  presents it as a probability.
- **Contradicting evidence weighs more than confirming** (×3/2). A system
  that can only raise confidence is a flattering mirror, not a compass.
- **Corroboration requires a discriminating experiment.** No volume of
  self-report corroborates a hypothesis; only `experiment_result` /
  `outcome_external` evidence can.
- **Canonical, typed, versioned serialization**, sealed with SHA-256 over
  the canonical bytes. `bool` is checked before `int` so `1`, `"1"`, `1.0`,
  `True` are distinguishable.
- **Append-only, hash-chained ledger** with a single genesis, a tail check
  before every append, and linkage/integrity reported *separately* (never
  collapsed into one boolean). Deleting content leaves an honest, visible
  tombstone in the chain, never a silent gap.
- **Referenced content is bound to the chain, not to a mutable column.**
  `verify_content` re-hashes live evidence against the `content_hashes` sealed
  *inside* each chain envelope, so editing the text and its `content_hash`
  together is still detected (Red Team Round 1, finding D1). Reported as a
  third, separate signal: `content_ok` on `/api/chain`, `chain_content_ok` on
  `/health`, and `contenido_ok` in `tools/verify_chain.py`.
- **The narrator cannot dress the index as a probability.** `validate_prose`
  fail-closed rejects any percentage in the narration before it is stored.
- **Schema creation is all-or-nothing, even under concurrent openers.** The
  migration chain runs in one transaction whose write lock is taken *before*
  the stored version is read, so several connections opening the same brand-new
  base — exactly what a first page load does, three requests in parallel —
  cannot observe a half-created schema. Locked in by
  `tests/test_db.py::test_schema_bootstrap_is_atomic_under_concurrent_openers`.
- **Determinism is proven, not asserted:** the same input produces the same
  seal bit-for-bit across fresh processes with a different `PYTHONHASHSEED`.

---

## Declared blind spots (the Daubert posture)

A known limitation is an asset. What this project does **not** yet claim:

- **Gemini's live coverage is one model, one transport, exercised by hand.**
  Gemini *has* now run in production (`gemini-2.5-flash` on Vertex, same seal
  as the offline backend), but no automated test makes a real call: the suite
  proves the contract against the offline backends only. Another model,
  region, or SDK version could still surface response-shape differences.
  (Same honesty the skeleton always kept about the Anthropic/Ollama backends.)
- **The grounded search path has never run against Vertex.** `GeminiBackend
  .search` and the citation extraction are written against `google-genai`
  2.x and covered by a stub backend in the suite; no real Google Search call
  has been made from this project yet. The parsing is deliberately
  defensive — missing grounding metadata yields no sources rather than
  invented ones — but the first live call is the one that will confirm the
  response shape.
- **The prompts (extractor/abductor/narrator) are v0, un-audited
  adversarially.** A model captured by a persuasive narrative can propose
  biased *candidates* — the structural mitigation is that nothing enters the
  ledger without the person's validation and no number leaves the model, but
  the quality of proposals is not measured.
- **The prose guard is syntactic, not semantic** (Red Team Round 1, finding A,
  partially fixed). `validate_prose` rejects percentages deterministically; it
  does not catch a smuggled certainty claim in words ("essentially certain").
  A semantic audit of the narration is v2.
- **The engine weights are PROVISIONAL** (`decision_record` #1 records the
  reopening condition: an audit with real data). They unblock the skeleton;
  they are not tuned.
- **Anti-flattery holds over the *linked* graph, not the whole picture**
  (Red Team Round 1, finding C). Contradicting evidence weighs more only where
  it is linked; unlinked disconfirming evidence simply does not count, so an
  incomplete graph can inflate a hypothesis by omission. There is no fully
  deterministic fix; the mitigation is to surface coverage (`/api/state`
  reports `validated_unlinked`) so the gap is visible, not hidden.
- **Persistence is snapshot-based, single-writer.** Per-user SQLite lives on
  local disk and is snapshotted to Cloud Storage after each write (restored on
  access). It is sized for one writer per compass (a person clicking through
  their own cycle) with Cloud Run session affinity; it is not a concurrent
  multi-writer store, and two instances racing on one id is last-writer-wins.
  Honest for the demo, reported on `/health`; a real multi-writer deployment
  would move to a managed database.
- **A writer with total DB access can rewrite history from genesis.** The
  chain makes tampering *detectable* against a verifier holding a prior tail
  hash, not impossible. Anchoring that hash off-machine is an open decision.

The adversarial audit behind several of these — five findings, their
falsification attempts, and what was fixed versus mitigated — is in
[`docs/RED_TEAM_ROUND1.md`](docs/RED_TEAM_ROUND1.md).

---

## Still open

Not blind spots (those are above, and are properties of the design) — this is
work that is simply not done yet.

| # | Open item | Where it bites |
|---|---|---|
| 1 | **Demo video not recorded.** | README and `docs/SUBMISSION.md` both still say *to be filled*. |
| 2 | **The demo scenario cannot exercise `discriminate`.** Both seeded hypotheses are already resolved (one corroborated, one weakened), and only an *unresolved* capability required by exactly one path can discriminate. | The trajectory comparison always lands on its honest empty case, so the cheapest-next-experiment logic is never demonstrated. Seeding a third, still-latent capability would fix it — and would also change the dashboard's "single next step". |
| 3 | **The CLI speaks Spanish only.** The API, narrator and frontend are bilingual EN/ES. | Mixed-language experience for anyone driving the core from a terminal. |
| 4 | **Engine weights still provisional.** `decision_record` #1 names the reopening condition: an audit against real data. | Every index is "accumulation under v1 rules", not a tuned measurement. |
| 5 | **Narration is not semantically audited** (Red Team finding A, partial). | A certainty claim in words can still slip past the percentage guard. |
| 6 | **Tail hash is not anchored off-machine.** | Tampering is detectable only by a verifier that already holds a prior tail. |
| 7 | **No self-perception-vs-data confrontation yet.** | The design's confrontation step (with a deliberately careful threshold) is unimplemented. |

---

## Tests

```bash
pip install pytest '.[api,gemini,adk]'
python3 -m pytest -q      # 146 tests, all green
```

**What each extra buys you.** The suite is layered like the code: the core
tests are stdlib-only, the rest need the extra whose surface they cover.

| Installed | Result (146 collected) |
|---|---|
| nothing (stdlib) | 130 pass · 7 fail + 7 error, all `ModuleNotFoundError: fastapi` · 2 skip |
| `.[api]` | 142 pass · 2 fail — the `GeminiBackend` fail-closed tests need `google-genai` · 2 skip |
| `.[api,gemini]` | 144 pass · 2 skip — the ADK tests need `google-adk` |
| `.[api,gemini,adk]` | 146 pass |

Failures in the first two rows are missing dependencies, not regressions; the
core's own tests never need anything but the stdlib.

Red-first: every negative control adulterates the source of truth and
asserts detection. Executed mutations are caught (dropping `prev_hash` from
the hash, collapsing `bool` into `int`, accepting future schemas, counting
unvalidated evidence, removing the anti-flattery factor, late sealing,
priority inversion in the next-step rules). Engine oracles are computed by
hand from the formula; a metamorphic invariant asserts that permuting load
order does not change the index.

## License

[Apache-2.0](LICENSE).
