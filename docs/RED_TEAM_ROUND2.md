# Security Audit — COMPASS

## Red Team Round 2

**Date:** 2026-11-06
**Method:** the `annatchijova/SKILLS` red-team collection — `METHODOLOGY.md`
(assessment contract), `red-team-auditing`, `discriminating-proof`,
`invariant-hunting`, `authorization-surface-mapping`, `concurrency-reasoning`,
`distributed-write-atomicity`, `remediation-driven-reporting`,
`finding-custody`.
**Scope:** what landed after Round 1 (`675fe3c`): the multi-user API, GCS
snapshot persistence, the Autopilot (Cloud Run Job + Scheduler), the deployed
ADK agent service; plus a re-attack of the corroboration gate and a variant
analysis of Round-1 finding A.
**Permitted actions:** reading the repository; running the code locally.
**Not permitted / not done:** contacting the live deployment; modifying source
code. **Stop condition:** minimum evidence for each proposition.
**Base:** `main` @ `85d8d2e` **Runtime:** Python 3.13.18, fastapi + httpx from
pip (no `google-adk` / `google-genai` installed).
**Reproducer:** `python3 -I tools/redteam_round2.py` — offline, ~5 s, prints
PREDICTION → test column → negative-control column → binary ORACLE for each
proposition, then a summary table.

### Finding status vocabulary

Findings: **CANDIDATE · CONFIRMED · REFUTED · NOT TESTED**. Every CONFIRMED in
this report has the same system scope unless stated otherwise: **the code at
`85d8d2e`, executed locally under the accommodations below.** None is a claim
about the live deployment; where impact on the deployment is stated, it is an
*inference* from the deploy configuration (CODE FACT) and is labelled as such.
Controls are reported separately as **PASS / WARN / FAIL** against a named test.

### Environment accommodations (each would not change the result)

| Accommodation | Why it does not change the result |
|---|---|
| GCS replaced by a local-directory fake bucket | `storage.snapshot` uses a whole-object upload with no precondition (`storage.py:130`); the fake has exactly those semantics. A real bucket would differ only if a generation precondition were used, and none is. |
| Cloud Run instances = separate `COMPASS_DATA_DIR`s | Cloud Run instances do not share local disk; `ensure_local` returns the local copy when it exists (`storage.py:96`). |
| `google.adk` stubbed (`Agent = kwargs dict`) | The ADK tool functions under test are plain Python and run unmodified; ADK only routes calls to them and never passes a session id to them (`agent.py:49-50`). |
| LLM backend = offline `demo` | No finding depends on model behavior; R2-4 counts calls, it does not need their content. |

**Harness defect, recorded:** the first controlled run printed `R2-1 REFUTED`.
Both columns had produced the predicted values (test `corroborada` 714,
control `activa` 716); the oracle was wrong — it counted every experiment in
the compass, including the one in the seeded demo scenario. Fixed to count
experiments on the test/control hypotheses only. Kept here because a REFUTED
printed by a broken oracle is exactly the kind of result a reviewer should be
able to audit.

---

## Threat model

- **Actors enumerated** (`authorization-surface-mapping` Part 1): anonymous
  internet client with no header; holder of compass id X (the person, or
  anyone given X); holder of a different id Y; LLM roles (extractor, abductor,
  narrator, resource finder); a visitor of the ADK agent service; the
  Autopilot job; *the deployment topology itself* (instances, warm copies).
- **Attacker CAN:** send arbitrary HTTP to the API (`--allow-unauthenticated`,
  CORS `*`); pick or omit `X-Compass-User`; act as the person on their own
  compass (the self-deception adversary the product names); chat with the
  public ADK service.
- **Attacker CANNOT:** modify code; guess another person's id (12 chars ×
  62 symbols from `crypto.getRandomValues`, ≈71 bits); write the bucket
  directly.

## Invariant table (`invariant-hunting` Part 1)

| Invariant the system declares | Established at | Transported by | Reconstituted at | Sink | Result |
|---|---|---|---|---|---|
| Corroboration requires a discriminating experiment (README:404) | `experiment_complete` creates `experiment_result` | `evidence.evidence_type` label | `compute_hypothesis` reads the label (engine.py:268) | status `corroborada` | **broken** — R2-1, R2-2 |
| Only validated evidence counts | person's validate act | `evidence.validated` | engine SQL filter | sealed index | holds — AUTHZ-2 |
| Every ledger entry persists ("never a silent gap") | `append` in a transaction | local SQLite file | `ensure_local` / GCS restore | `/api/chain`, verifiers | **broken** — R2-3 |
| Single writer per compass (README:479) | session affinity | browser → instance | — | GCS object | **broken by the Autopilot** — R2-3b |
| One compass per person | `X-Compass-User` | header | `storage.local_path` | per-user DB | holds on the API (AUTHZ-1); **broken on the agent service** — R2-8 |
| Narration never states the index as a probability (README:421) | `validate_prose` | prose string | — | human reader | **partially broken** — R2-5 |
| The failure criterion is written *before* running | preregister | `experiment.preregistered_at` | `experiment_complete` | `experiment_result` | not enforced — R2-7 |

---

## Executive summary

| ID | Impact (one sentence) | Demonstrated severity | Status | Novelty |
|---|---|---|---|---|
| R2-1 | Anyone who controls a compass can make a hypothesis **"corroborated" with zero experiments** by labelling their own entries `outcome_external`. | High | CONFIRMED → **FIXED** | new; contradicts README:404 |
| R2-3 | The Autopilot's sealed chain row (and any write from another instance) is **silently erased** by the next web write, and every verifier still reports OK. | High | CONFIRMED (local); deploy reach = inference from CODE FACT | two-instance race is a **declared** blind spot; the Autopilot breaking the single-writer premise is new |
| R2-2 | One completed experiment can corroborate **any number of unrelated hypotheses**. | Medium | CONFIRMED | new |
| R2-8 | On the public ADK agent service, **every visitor shares one compass**: visitor A's actions change visitor B's state and next step. | Medium | CONFIRMED (local); cross-session prompt injection via state REFUTED | new; DEPLOY.md covers cross-*instance*, not cross-*session* |
| R2-4 | An anonymous client can enrol unbounded compasses, each costing ≈3 billed LLM calls **every day** via the Autopilot. | Medium | CONFIRMED (local, counted calls) | partly declared (DEPLOY.md:194, per-request only) |
| R2-6 | A request without a header can rewrite the shared showcase presented as **"Anna (user zero)"**. | Low–Medium | CONFIRMED → **FIXED** | new |
| R2-5 | `97 per cent`, `97％`, `noventa y siete por ciento`, `0.97 probability`, `950/1000` pass the guard that README says rejects "any percentage". | Low–Medium | CONFIRMED | variant of declared R1-A; contradicts README:421 |
| R2-7 | An experiment can be preregistered and closed 6 ms later, so a post-hoc experiment looks preregistered. | Low | CONFIRMED | new (declared limitation class, R1-C) |

**Refuted this round** (first-class results): cross-id IDOR (AUTHZ-1),
unvalidated evidence moving an index (AUTHZ-2), cross-session prompt injection
through `get_compass_state` (R2-8b), uid path traversal, Autopilot moving a
sealed value.

---

## Findings

### R2-1 — The corroboration gate reads a label the caller writes

**Impact:** anyone who controls a compass — the person, or anyone at all on
`demo` (R2-6) — can seal `corroborada` without any experiment.
**Severity:** demonstrated **High** (the product's headline guarantee against
the flattering mirror, README:404, is bypassed by its own adversary).
**Status:** CONFIRMED — proposition: *"self-typed `outcome_external` opens the
corroboration gate with 0 experiments, and the type label is the factor."*
Scope: code at `85d8d2e`, local.

**Reproduce** (`tools/redteam_round2.py`, block R2-1). One factor differs:

| Column | Evidence | Net | Index | Status |
|---|---|---|---|---|
| test | 3 × `outcome_external`, self-entered, linked `supports` | 750 | 714 | **corroborada** |
| control | 19 × `self_report`, same endpoint, same direction | 760 | 716 | activa |

Experiments on either hypothesis: 0. The control rules out "the index alone
corroborates": with a *higher* index, the control stays `activa`.

**Why this is a boundary crossing.** Invariant:
`status == corroborada ⇒ ∃ experiment E preregistered for H, completed exito`.
The engine checks `evidence_type ∈ corroboration_requires`
(`engine.py:268-269`); `POST /api/evidence` takes `evidence_type` from the body
(`api.py:225`) and defaults `validated` to `True` (`api.py:228`). Family:
*validated once, never re-validated* — the property "came from an experiment /
from outside" is established nowhere; it is asserted by the writer.

**The class.** Pattern: a gate keyed on a self-declared provenance label.
Also applies, CODE FACT, to `experiment_result` typed by hand (same field,
same check) — not run separately. **Complete fix =** the invariant above holds
on every path that creates evidence, not "`outcome_external` is rejected".

**Remediation (ranked).** 1. Structural: provenance by construction — only
`experiment_complete` may create `experiment_result`; `outcome_external`
requires a recorded provenance (who/where) and stays out of
`corroboration_requires` until it has one. 2. Scoped: reject both types on
`POST /api/evidence`. 3. Stopgap: drop `validated: bool = True` default.
**Regression assertion:** POST of `experiment_result` / `outcome_external`
via `/api/evidence` → 400; the test column above must end `activa`.
**Detection requirement:** chain entries `evidence_added` with
`evidence_type ∈ {experiment_result, outcome_external}` and
`source` not of the form `experiment:<id>` — near-zero false positives after
the fix.

### R2-3 — Silent, verifier-invisible loss of ledger entries

**Impact:** with the deployed topology, the Autopilot's sealed chain row is
erased by the person's next write on a warm web instance, and nothing reports
it. **Severity:** demonstrated **High** locally. Plausible-if-chained on the
deploy: the edges are CODE FACT (`--min-instances 1` in DEPLOY.md:53 keeps a
warm instance; the Autopilot is a second writer; `ensure_local` never
re-reads GCS while a local copy exists, `storage.py:96`; upload has no
precondition, `storage.py:130`); I did **not** run this against the deploy.
**Status:** CONFIRMED — two propositions, scope local:
- R2-3a *"a write from a second warm instance replaces another instance's
  write, the survivor verifies clean, and multi-writer is the factor."*
- R2-3b *"a web write from an instance warm across the sweep erases the
  Autopilot's sealed chain row; a cold instance does not."*

**Novelty.** R2-3a is the README's declared blind spot (README:479-485:
"single-writer … two instances racing on one id is last-writer-wins"). It is
included only as the control-bearing base case. **R2-3b is the finding:** the
declared mitigation is session affinity, which pins a *browser*; the
Autopilot is not a browser and writes every user's compass by design, so the
"single-writer" premise of the declared limitation no longer holds in the
shipped system.

**Reproduce.**

| Case | Column | Observed |
|---|---|---|
| R2-3a | test: instance A writes `CANARY-R23-A`, warm instance B writes `CANARY-R23-B` | A=0, B=1, linkage/integrity/content all OK |
| R2-3a | control: same two writes through one instance | A=1, B=1, all OK |
| R2-3b | test: sweep, then warm web instance writes | `autopilot_briefing` rows in GCS 1 → **0** |
| R2-3b | control: sweep, then cold web instance writes | 1 → 1 |

**Why this is a boundary crossing.** Invariant: *every committed `append`
remains in the persisted chain.* A hash chain proves internal consistency of
one branch; the overwritten branch is simply absent, so `verify_chain` and
`verify_content` are correct and silent (falsifying the rival "the verifier
would catch it"). Classes per `distributed-write-atomicity`: two systems (local
SQLite, GCS object) with no shared transactional authority; per
`concurrency-reasoning`: shared mutable state = the GCS object, concurrency
sources = replicas + overlapping cron, check-then-act = download → mutate →
blind upload, no fencing token.

**Remediation (ranked).** 1. Structural: conditional write — keep the object
generation read at restore, upload with `if_generation_match`, and on
mismatch re-restore and replay the logical operation (or fail loudly); revalidate
the local copy against the blob generation at the start of each request.
2. Scoped: the Autopilot writes its trace to a *separate* object (it already
keeps the briefing outside the DB) instead of appending to the user's chain.
3. Stopgap: `--max-instances 1` and run the sweep only when the web service is
scaled to zero — fragile, document it as such. Independently: publish each
compass's chain head (seq + hash) to an append-only location so a dropped tail
becomes detectable (closes the R1 "anchor" open decision too).
**Regression assertion:** R2-3b test column must keep the row (1 → 1), forced
deterministically as in the script (`concurrency-reasoning` Part 7: force the
interleaving you fear). **Detection requirement:** per compass, the chain head
seq observed by the Autopilot must never be greater than the seq of the next
snapshot.

### R2-2 — Discriminating evidence is portable across hypotheses

**Impact:** one experiment can corroborate unrelated hypotheses.
**Severity:** demonstrated **Medium**. **Status:** CONFIRMED — *"an
`experiment_result` preregistered for A opens the corroboration gate of an
unrelated hypothesis B, and the borrowed link is the factor."* Scope: local.

| Column | Links on the hypothesis | Index | Status |
|---|---|---|---|
| test (B) | A's `experiment_result` + 23 `self_report` | 785 | **corroborada** |
| control (C) | 28 `self_report`, no borrowed link | 788 | activa |

**Invariant / class:** the gate binds to the *type* of the evidence, not to
the relation experiment ↔ hypothesis. `evidence_link` (`domain.py:138`)
accepts any pair. Linking A's result to A's **rival** as `contradicts` is
legitimate; the defect is narrowly the gate opening on a hypothesis the
experiment was not preregistered for. **Fix:** an `experiment_result` counts
toward `corroboration_requires` only on `experiment.hypothesis_id` (read from
`source = experiment:<id>`); elsewhere it still weighs, but does not open the
gate. **Regression assertion:** test column ends `activa`.

### R2-8 — The public ADK agent service shares one compass across all visitors

**Impact:** visitor A's actions change visitor B's sealed state and "one next
step"; A's narrative quotes are stored in a compass other visitors act on.
**Severity:** demonstrated **Medium** (integrity across users; content
exposure not demonstrated, see R2-8b).
**Status:** R2-8a CONFIRMED — *"visitor A's acts change visitor B's sealed
state and next step on a shared agent instance; the shared DB is the
factor."* R2-8b REFUTED — *"visitor A can plant text that reaches visitor B's
agent through `get_compass_state`."* Scope: local, tool functions called
directly (ADK never passes a session id to them).

| Column | B's pending evidence | B's next step | A's canaries visible to B |
|---|---|---|---|
| test: same `COMPASS_DB` after A extracted, added a hypothesis and preregistered | 0 → 2 | `ejecutar_experimento` **#2 = A's experiment** | no |
| control: fresh `COMPASS_DB` | 0 | `diseñar_experimento` | no |

**Why.** `_conn()` opens `COMPASS_DB` (`agent.py:49-50`), set to
`/tmp/compass.db` for the whole process (`deploy/agent/Dockerfile:13`).
Family: *namespace collapse* — ADK keys sessions, the tools key nothing.
**Why R2-8b failed (assurance data):** `compass_state` exposes only
`activa/corroborada/debilitada` hypotheses and counts; the agent has no tool
that validates, links or activates, so an A-authored statement stays latent and
invisible. That refutation is scoped to the *current* tool set: adding any tool
that reads statements of latent hypotheses or evidence content would reopen it.
**Fix:** key the agent DB by ADK `user_id`/session (ADK passes `tool_context`
to tools that declare it) through `storage.local_path`, or point the agent at
the API with the visitor's compass id. **Regression assertion:** the R2-8a
test column must equal the control column.

### R2-4 — Unbounded anonymous enrolment amplifies into daily LLM spend

**Impact:** one anonymous POST per fresh id enrols it in every future sweep.
**Severity:** demonstrated **Medium** (resource / denial-of-wallet). Cost on
the deploy is NOT TESTED; scaling the counted calls to money would be
extrapolation. **Status:** CONFIRMED — *"one anonymous POST per fresh id puts
that id into every Autopilot sweep at ≥1 LLM call each; a GET alone does
not."* Scope: local, counted backend calls.

| Column | Enrolled in sweep | Backend calls |
|---|---|---|
| test: 25 fresh ids × 1 `POST /api/recompute` | 25/25 | 75 (≈3 per compass) |
| control: 25 fresh ids × 1 `GET /api/state` | 0/25 | — (but 3.3 MiB left on instance disk; `/tmp` is memory on Cloud Run) |

**Novelty:** DEPLOY.md:194 already warns that request-path Vertex calls need
auth or rate limiting. New here: the Autopilot turns a single request into a
**recurring, unattended** cost per id, with no expiry. **Fix (ranked):** sweep
only compasses with a non-seed, person-authored write and recent activity; cap
compasses per sweep; persist a compass only after its first non-seed write;
rate-limit id creation. **Detection:** count of distinct new ids per source
per hour; sweep size growth day over day.

### R2-6 — Anonymous writes on a showcase presented under a real person's name

**Status:** CONFIRMED — *"an anonymous request without the header mutates the
shared showcase; the header is the only factor."* Test (no header): demo
evidence #1 tombstoned, HTTP 200. Control (header `u-r26ctrl00001`, identical
path and body): demo evidence #2 untouched. Showcase person: "Anna (user
zero)". `get_uid` defaults to `demo` (`api.py:82`). Combined with R2-1, an
anonymous visitor can seal corroborated — or damaging — claims on the profile
every judge lands on. **Severity:** demonstrated Low–Medium. **Fix:** `demo`
read-only at the API (or copy-on-write to a fresh id on first write); require
the header on every write route. **Regression assertion:** test column → 403,
demo unchanged.

### R2-5 — The percentage guard accepts six figure-claims (variant of R1-A)

**Status:** CONFIRMED — *"the R1 guard rejects only digit + `%` / `percent` /
`por ciento`; six other figure-claims pass."* Controls (`97%`, `97 percent`)
rejected; variants accepted: `97 per cent`, `97 pct`, `noventa y siete por
ciento`, `97％` (fullwidth), `0.97 probability`, `950/1000`.
`_PERCENT_RE` at `llm.py:239`. README:421 says it "rejects any percentage" —
that claim needs narrowing now. **Severity:** Low–Medium (declared class).
**Fix (ranked):** 1. any integer 0–1000 or `N/1000` in the prose must equal a
value in the summary handed to the narrator (deterministic, closes the
"number contradicting the seal" class, not just the `%` spelling);
2. NFKC-normalize, add `per cent`, `pct`, word numbers, `probabilit*`.

### R2-7 — Preregistration has no temporal separation

**Status:** CONFIRMED — *"an experiment can be preregistered and closed within
one second"* (6.3 ms, HTTP 200). No control: no code path could reject it
(CODE FACT, `domain.py:291`). **Severity:** Low — same class as R1-C (the
system cannot observe the real world). **Mitigation:** minimum interval, or
surface `completed_at − preregistered_at` next to every corroboration.

---

## Authorization matrix (`authorization-surface-mapping`)

| Actor | Resource | Action | Expected | Observed | Control |
|---|---|---|---|---|---|
| no header | `demo` compass | any write | denied | allowed | **FAIL** (R2-6) |
| id X | own compass | all | allowed | allowed | PASS |
| id Y | X's evidence id | forget / list | no effect on X | hits Y's own row; canary not visible | **PASS** (AUTHZ-1 REFUTED) |
| any holder | evidence type label | create `outcome_external` / `experiment_result` | restricted | allowed | **FAIL** (R2-1) |
| any holder | another hypothesis | link a foreign `experiment_result` (gate) | no gate effect | opens gate | **FAIL** (R2-2) |
| LLM extractor | validated evidence | create | denied | `validated=0` only; ×10 linked → index 0 | PASS (AUTHZ-2) |
| agent visitor A | visitor B's compass | write | denied | allowed (shared DB) | **FAIL** (R2-8a) |
| agent visitor A | visitor B's agent context | inject text | denied | not reachable with current tools | PASS (R2-8b) |
| Autopilot | sealed indices | write | denied | guard never tripped | PASS |
| Autopilot | user's chain | append row | allowed (by design) | allowed — and lost later | WARN (R2-3b) |
| traversal ids | filesystem | open | denied | 400 for `../etc`, `a/b`, 65 chars, `%2F` | PASS |

**Cells not tested, and why:** ADK `adk web` endpoints themselves (session
listing, artifact service) — not part of this repo and would require the live
service; the frontend; GCS IAM; Vertex quota behavior; the `demo\n` uid (the
regex at `storage.py` uses `re.match` + `$` and accepts a trailing newline
in-process, but h11 strips it before the app — REFUTED over HTTP, keep as
hygiene: use `fullmatch`).

## Discarded / refuted vectors

| Vector | Status | Evidence |
|---|---|---|
| IDOR across compass ids | REFUTED | AUTHZ-1: per-user DB; Y's request resolves in Y's DB. |
| Unvalidated evidence moves an index | REFUTED | AUTHZ-2: index 0. |
| Stored cross-session prompt injection via agent state | REFUTED (current tool set) | R2-8b. |
| Path traversal via id | REFUTED | 400 on four forms. |
| Autopilot moves a sealed value | REFUTED | guard never tripped across all runs. |
| Brute-forcing a compass id | not feasible | ≈71 bits. |
| Duplicate link inflates | REFUTED | PK rejects it — as an unhandled `IntegrityError` → HTTP 500 (hygiene: map to 400). |

## Hygiene (not findings)

No unlink endpoint (a wrong link is permanent short of tombstoning); no body
size caps; CORS `*` (no credentials, low impact). Test environment: with only
fastapi installed, 177 tests pass; 2 in `test_hackathon_layer.py` and the ADK
modules need `google-genai` / `google-adk`.

## Custody (`finding-custody`)

- **This repository is public** and the deployment is live and
  unauthenticated. Pushing this report discloses the *mechanism* layer of
  R2-1, R2-4 and R2-6 against the live service before any fix ships. The
  owner of the system and of the decision is the repository owner; the
  options are recorded, not taken: keep the report on a branch until the
  fixes land, move it to a private location, or accept publication (the demo
  data is synthetic). **Revisit trigger:** the first fix commit — patches
  disclose the class on their own (`finding-custody` Part 2).
- PoC inventory: `tools/redteam_round2.py` (this repo); the session transcript
  of the assistant that ran it. No live-system data was touched; all state is
  in a temp dir the script prints and that is safe to delete.

## Remediation status

Applied after the audit, on the same branch. Each fix: a regression test that
**failed first** on the unfixed source (verified by running
`tests/test_redteam_round2_fixes.py` with `src/` stashed: 6 failed — exactly
the attack tests — and 5 passed — the controls), then green with the fix.

| ID | Status | What changed | Control that must still pass |
|---|---|---|---|
| R2-1 | **FIXED** | New `domain.evidence_add_by_person`: rejects every type in the *active* engine config's `corroboration_requires` (today `experiment_result`, `outcome_external`) with `DomainError` → HTTP 400. Used by `POST /api/evidence` and the CLI. `experiment_complete` and the seed keep the internal `evidence_add`. | A real preregistered experiment completed `exito` still reaches `corroborada`; same index from volume alone stays `activa`; other types still accepted. |
| R2-6 | **FIXED** | `api._db`: a write route on `demo` → 403 before opening anything; the `demo` read connection is opened `PRAGMA query_only = ON`, so an undeclared write path also fails closed. | Own compass still writable with the identical request; showcase still readable (`/api/state`, `/api/chain`, `/health`). |

Reproducer on the fixed code: `R2-1 REFUTED` (test column `index=0 latente`,
the gate-type writes are refused) and `R2-6 REFUTED` (`http=403`, demo
untouched); every other row unchanged.

**Not closed by these fixes — verified against the class, not the payload**
(`remediation-driven-reporting` Part 5): **R2-2 is still CONFIRMED** on the
fixed code. It is the sibling of R2-1 (the gate binds to the evidence *type*,
not to the experiment ↔ hypothesis relation) through a different path —
linking a legitimately created `experiment_result` — so closing R2-1 did not
close the class. `outcome_external` now has no client path at all; giving it
one with recorded provenance is an open decision.

Side effect on existing tests: eight API tests wrote to `demo` without a
header. They now use their own compass id (`t-own-compass`), which is seeded
with the identical scenario, so they assert the same behavior.

## Recommendations (record only — remaining findings)

R2-1 and R2-6 are fixed (see Remediation status). Remaining, by demonstrated
severity × cost: **R2-3** (conditional upload / move the Autopilot trace out
of the user chain) first; then R2-8, R2-2 (same class as R2-1), R2-4, R2-5,
R2-7. Each fix should land with the regression assertion listed under its
finding, red first on `85d8d2e`, and be verified against the class, not only
against the script's inputs (`remediation-driven-reporting` Part 5).
