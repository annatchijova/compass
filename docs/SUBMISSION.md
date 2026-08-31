# COMPASS — All Things Agentic submission

Paste-ready text for Devpost. Fill the _bracketed_ items after deploy.

- **Category:** Collaborative Partner
- **Repository:** https://github.com/annatchijova/compass
- **Live web app:** https://compass-web-1028999311218.us-central1.run.app
- **Live backend API (Gemini/Vertex on Cloud Run):** https://compass-1028999311218.us-central1.run.app
- **Live multi-agent chat (Google ADK Web UI, Cloud Run):** https://compass-agent-1028999311218.us-central1.run.app — pick `compass_companion` and talk to the team (Companion + Analyst + Activity Scout + Reflector).
- **Autonomous background job (Cloud Run Job + Cloud Scheduler):** `compass-autopilot` — the same team, unattended: on a cron it sweeps every sealed compass, watches the seal, and leaves a next-step briefing waiting. No URL because it is batch work; proof is in the demo video (job execution + logs) and `deploy/autopilot/`.
- **Demo video (~4 min):** _<video URL>_

## Inspiration

Career and self-discovery tools ship confident numbers — "Spatial reasoning:
68%" — with no defensible mechanism behind them. If a model emits that number,
it is an invented value wearing the costume of precision: not reproducible, not
auditable, and it drifts under narrative pressure. Over a system whose output
is a claim about a person's identity, that is unacceptable. COMPASS is the
inversion: a compass, not a mirror.

## What it does

COMPASS helps a person discover capabilities and direction from evidence of
their own life, walking them through an abductive cycle — rival hypotheses →
discriminating experiment → observation → update. It surfaces one deterministic
next step, holds rival explanations alive until an experiment separates them,
and weights contradicting evidence *more* than confirming evidence so it can
never become a flattering mirror.

## The autonomous layer (Autopilot): action without crossing the boundary

Most agents earn the word "autonomous" by taking the decision away from the
person. COMPASS's whole thesis forbids that — the person validates evidence,
links it, and closes experiments; the engine seals. So the autonomy we added is
autonomy over the *heavy lifting*, never over the *decision*.

`compass autopilot` (module `compass.agent.autopilot`) is the same no-authority
team, running **unattended in the background** as a Cloud Run Job on a Cloud
Scheduler cron. While the person is away it, per user:

1. reads the *already-sealed* state (read-only);
2. names the deterministic gap — the capability worth testing;
3. **proposes** the next discriminating experiment (the Abductor role);
4. **proposes** concrete activities to run it (the Activity Scout, via Gemini +
   Google Search, grounded with real sources);
5. puts it into words (the Narrator);
6. and, as a Sentinel, **verifies the audit chain of every compass** (linkage,
   integrity, content) so tampering is not just *detectable* but actively
   *watched* — unattended, across many users.

The person wakes up to a briefing that is ready to act on. The heavy lifting —
gap analysis, web search, drafting, chain verification across the whole fleet —
happened asynchronously while they slept. This is the "runs in the background,
handles the heavy lifting, async" thesis, delivered *without* surrendering the
architectural invariant that makes COMPASS trustworthy.

Three guards keep the autonomous actor on the right side of the boundary:

- **By construction** it imports only sealed reads, the no-authority roles, and
  the verifier — it holds no domain-write lever at all.
- **By a fail-closed runtime guard**: the seal and every index are snapshotted
  before and after each run; if anything moved, it raises `AutopilotBoundaryError`
  — the architecture would be broken. `tests/test_autopilot.py` locks this in,
  including the backend-swap test (Gemini ↔ offline) that must change only the
  wording, never the seal.
- **By storing the briefing BESIDE the seal, never inside it**: the briefing is a
  separate artifact; only its hash goes into the append-only chain (exactly like
  the narrator's prose). The schema never changes, so the already deployed
  services keep opening the same bases untouched.

## How we built it

Two invariants drove every decision:

1. **No claim about the person exists without recorded, sealed evidence.**
2. **No number describing the person ever comes out of an LLM.**

A deterministic core (pure Python stdlib) computes an integer 0–1000 index with
`fractions.Fraction` — no float anywhere in the decision path — and seals it
with SHA-256 over canonical, type-tagged, versioned bytes into an append-only,
hash-chained ledger with an independent stdlib-only verifier. Gemini enters
only as three roles with **no authority**: an extractor that proposes signals
the person must validate, an abductor that proposes rival hypotheses and
experiments, and a narrator that puts the *already-sealed* state into words.
The ADK agent is a Collaborative Partner whose authority is exactly its tool
set; the only tool that produces numbers runs the engine and seals the result
before the agent ever sees it.

## Tech stack

- **Gemini** via **Vertex AI** (and Gemini API) — the mandatory model, used
  only to narrate and propose.
- **Google ADK** — `compass.agent.root_agent`, a tool-bounded agent.
- **Cloud Run** — hosts the FastAPI backend and the ADK Web UI; Vertex serves
  Gemini through the service identity (no key stored).
- **Cloud Run Jobs + Cloud Scheduler** — run the Autopilot as a scheduled,
  async background sweep (`deploy/autopilot/`): the autonomous, unattended layer.
- **Cloud Storage** — per-user isolated SQLite bases snapshotted for durability
  (multi-user with no login: every browser gets its own sealed compass).
- Python stdlib deterministic core + SQLite; **Next.js** frontend (bilingual
  EN/ES, judge quick-tour + example inputs).

## The architectural test we are proud of

Swap the model backend (Gemini ↔ an offline backend) and only the *wording*
changes — never a verdict, a seal, or the chain of custody. It is enforced by a
test that fails closed if the model could ever move a sealed number. That test
*is* the thesis.

## Challenges

- Keeping the model provably out of the decision path while still making it feel
  like a genuine collaborative partner — solved by making the agent's authority
  its tool set, and putting the seal before the narrator by construction.
- Determinism hygiene: no float, canonical typed serialization, `bool` before
  `int`, seal reproducible bit-for-bit across fresh processes.

## What we learned

A known limitation is an asset. COMPASS ships its blind spots in the README (the
Daubert posture): provisional engine weights, un-audited v0 prompts, ephemeral
demo storage, and a threat model where tampering is *detectable*, not
impossible. An honest WARN beats a false PASS.

## What's next

Trajectories (capability-requirement maps, no destiny percentages) now ship in
the CLI and the API; giving them a screen in the web app is next. Then a
self-perception-vs-data confrontation with a careful threshold, off-machine
anchoring of the tail hash, and tuning the provisional weights against real
dogfooding data. The full list is under "Still open" in the README.

## Hackathon checklist

| Requirement | Where |
|---|---|
| Gemini 3.5+ (Gemini API or Vertex AI) | `src/compass/llm.py` `GeminiBackend`; deployed on Vertex |
| Google agent framework (ADK) | `src/compass/agent/agent.py` `root_agent` |
| Google Cloud service (Cloud Run) | `DEPLOY.md` |
| Autonomous background action (Cloud Run Jobs + Cloud Scheduler) | `deploy/autopilot/`, `compass.agent.autopilot` |
| Public repo + README setup | `README.md` |
| Architecture diagram | `docs/ARCHITECTURE.md`, `README.md` |
| ~4-min demo video | _<video URL>_ |
