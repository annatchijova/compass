# COMPASS — All Things Agentic submission

Paste-ready text for Devpost. Fill the _bracketed_ items after deploy.

- **Category:** Collaborative Partner
- **Repository:** https://github.com/annatchijova/compass
- **Live web app:** https://compass-web-1028999311218.us-central1.run.app
- **Live backend API (Gemini/Vertex on Cloud Run):** https://compass-1028999311218.us-central1.run.app
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
- **Cloud Run** — hosts the FastAPI backend; Vertex serves Gemini through the
  service identity (no key stored).
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
| Public repo + README setup | `README.md` |
| Architecture diagram | `docs/ARCHITECTURE.md`, `README.md` |
| ~4-min demo video | _<video URL>_ |
