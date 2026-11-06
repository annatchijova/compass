# Security Audit — COMPASS

## Red Team Round 2

**Date:** 2026-11-06 **Method:** Abductive Engineering (A–D–I) + Red-Team Auditing
**Scope:** everything that landed *after* Round 1 (base `675fe3c`): the
multi-user API (`X-Compass-User` → per-user SQLite), GCS snapshot persistence
(`storage.py`), the autonomous Autopilot (`agent/autopilot.py`, Cloud Run Job +
Scheduler), and a re-attack of the engine's **corroboration gate** and the
Round-1 prose guard (variant analysis). Out of scope: modifying source code;
touching the live deployment (every induction ran offline).
**Base:** `main` @ `85d8d2e` **Runtime:** Python 3.13.18, fastapi (latest from pip)
**Reproducible evidence:** `python3 -I tools/redteam_round2.py` (offline; fake
GCS bucket shared between simulated instances; `google.adk` stubbed). Every
experiment prints PREDICTION before OBSERVED.

## Threat model

- **Attacker CAN:** send arbitrary HTTP requests to the API (the deploy is
  `--allow-unauthenticated`, CORS `*`); choose any `X-Compass-User` value or
  omit it; act as the person on their own compass (the self-deception vector —
  the product's stated adversary is the flattering mirror). For the persistence
  findings no attacker is needed at all: the "adversary" is the deployed
  topology itself (`--min-instances 1 --max-instances 4`, daily Autopilot job).
- **Attacker CANNOT:** modify code; read another user's compass id (ids are
  12 chars from a 62-symbol alphabet via `crypto.getRandomValues`, ≈71 bits —
  brute force is not a realistic vector); write to the GCS bucket directly.
- **Trust boundaries crossed:** caller-declared label → corroboration gate
  (R2-1, R2-2); instance-local disk ↔ GCS (R2-3); anonymous internet → paid
  LLM calls (R2-4); model prose → human reader (R2-5); anonymous internet →
  shared showcase under a real person's name (R2-6).

## Epistemic legend

CODE FACT · PLAUSIBLE HYPOTHESIS · CONFIRMED BY INDUCTION · FALSIFIED

## What holds

The Round-1 boundaries were re-tested and **still hold**: unvalidated evidence
linked ×10 contributes `index=0` (extractor boundary); uid path traversal
(`../etc`, `a/b`, 65 chars, `%2F`) is rejected with 400; the Autopilot's
fail-closed guard did not trip in any run, and it indeed has no domain write
lever. The findings below are not breaks of the seal — the seal is computed
faithfully every time. They are cases where **a wrong state gets sealed**, or
where **a sealed entry silently disappears**.

## Executive summary

| ID | Severity | Level | Module | Finding |
|----|----------|-------|--------|---------|
| R2-1 | High | CONFIRMED BY INDUCTION | `api.py`, `engine.py` | "Corroborating requires a discriminating experiment" is bypassed by **labelling** self-entered evidence `outcome_external`: `corroborada` (714) with zero experiments. |
| R2-2 | Medium | CONFIRMED BY INDUCTION | `domain.py`, `engine.py` | One `experiment_result` can be **linked to other hypotheses** and act as their discriminating evidence: `corroborada` (785) with no experiment of its own. |
| R2-3 | High | CONFIRMED BY INDUCTION (offline); deploy precondition = CODE FACT | `storage.py`, `autopilot.py` | GCS snapshot is last-write-wins over a stale local copy: writes from another instance — and the Autopilot's own chain row — are **silently lost**, and the surviving chain **verifies clean**. |
| R2-4 | Medium | CONFIRMED BY INDUCTION (offline) | `api.py`, `autopilot.py` | Anonymous, unbounded compass creation: 1 POST per fresh id ⇒ a GCS blob ⇒ ≈3 LLM calls per id per Autopilot run (denial-of-wallet); GET-only requests fill `/tmp` (RAM on Cloud Run). |
| R2-5 | Low–Med | CONFIRMED BY INDUCTION | `llm.py` | The Round-1 percentage guard is a narrow regex: `97 per cent`, `97 pct`, `97％`, `noventa y siete por ciento`, `0.97 probability`, `950/1000` all pass. |
| R2-6 | Low–Med | CONFIRMED BY INDUCTION | `api.py`, `seed_demo.py` | A request with no header writes to the shared `demo` showcase, which is presented under a real person's name ("Anna (user zero)"); combined with R2-1, anyone can seal flattering — or damaging — claims there. |
| R2-7 | Low | CONFIRMED (code fact + trivial run) | `domain.py` | "Preregistration" has no temporal separation: preregister + complete 5 ms apart is accepted, so a post-hoc experiment looks preregistered. |

---

## Findings

### R2-1 — The corroboration gate trusts a caller-declared label

**Severity:** High **Level:** CONFIRMED BY INDUCTION
**Bucket:** software / design vulnerability
**Precondition:** controls the compass (the person themselves, or anyone with
the id — including anyone at all on `demo`, see R2-6).

- **Expectation violated:** README / CLAUDE_LEEME: *"Corroborar exige un
  experimento discriminante. Ningún volumen de auto-reporte corrobora."*
- **Code fact:** `engine.compute_hypothesis` grants `corroborada` when
  `index >= 600` **and** some supporting evidence has
  `evidence_type ∈ corroboration_requires = [experiment_result, outcome_external]`.
  `POST /api/evidence` accepts any `evidence_type` from the body, with
  `validated: bool = True` by default. Nothing ties `outcome_external` to an
  external source, nor `experiment_result` to an experiment.
- **Abduction (ranked by cost):** (1) the gate checks a *label*, and the label
  is input-controlled; (2) the API restricts which types a person may enter
  directly. (2) is falsified by reading `EvidenceIn` — no restriction. Test (1).
- **Deduction:** three self-typed `outcome_external` entries (3×250 = 750 net)
  linked as `supports` ⇒ index ≥ 600 and status `corroborada`, with 0
  experiments on the hypothesis.
- **Induction:**
  ```
  PREDICTION: status=corroborada, index>=600, 0 experimentos sobre la hipótesis
  OBSERVED:   status=corroborada index=714 experimentos=0 seal=c6e97104c04d5b77…
  ```
  The same works with `evidence_type: "experiment_result"` typed by hand.
- **Causal chain:**
  ```
  caller sets evidence_type="outcome_external" (body field)
      ↓ born validated=1 by default
  caller links it as supports (human act — allowed)
      ↓
  engine: weight 250 each AND discriminante_a_favor = True  (label check only)
      ↓
  corroborada — sealed
  ```
- **Precise language:** not "the seal is broken" — **"a `corroborada` status
  with no discriminating experiment behind it can be sealed, because the gate
  reads a self-declared type."** This is the relabel shape, not injection.
- **Recommendation:** make the discriminating types *unforgeable by
  construction*: reject `experiment_result` on `POST /api/evidence` (only
  `experiment_complete` may create it), and give `outcome_external` a required,
  recorded provenance (who/where), or drop it from `corroboration_requires`
  until it has one. Weight is a separate question from gate eligibility.

### R2-2 — Discriminating evidence is portable across hypotheses

**Severity:** Medium **Level:** CONFIRMED BY INDUCTION **Bucket:** design vulnerability
**Precondition:** controls the compass; at least one completed experiment.

- **Code fact:** `experiment_complete` links its `experiment_result` to the
  experiment's hypothesis; `POST /api/link` then lets the same evidence be
  linked to *any* hypothesis. The gate does not check that the experiment was
  about that hypothesis.
- **Induction:** experiment on h3 closed `exito`; its evidence linked to h4
  and h5, plus `self_report` only:
  ```
  PREDICTION: B y C cuentan el experiment_result del experimento de A (peso 180 c/u)
  OBSERVED:   h3 support=180 index=375 status=activa
  OBSERVED:   h4 support=300 index=500 status=activa
  OBSERVED:   h5 support=300 index=500 status=activa
  PREDICTION: B llega a 'corroborada' con 0 experimentos propios
  OBSERVED:   h4 index=785 status=corroborada
  ```
- **Nuance:** linking one experiment to its *rival* as `contradicts` is
  legitimate and desirable (that is what "discriminating" means). The defect is
  only the `supports` direction to an unrelated hypothesis counting toward the
  gate. Not every reuse is wrong — so the fix is narrow.
- **Recommendation:** `experiment_result` counts toward `corroboration_requires`
  only on the hypothesis it was preregistered for (`experiment.hypothesis_id`),
  checked from `source = experiment:<id>`; any other link still weighs, but
  does not open the gate.

### R2-3 — Silent, verifier-invisible loss of ledger entries (GCS last-write-wins)

**Severity:** High **Level:** CONFIRMED BY INDUCTION (offline simulation);
the deployment precondition is a CODE FACT; **not** reproduced against prod.
**Bucket:** software vulnerability — composition break (no attacker required)

- **Expectation violated:** "append-only, hash-chained, tamper-evident ledger";
  "a write that cannot be persisted is logged, never silently dropped"
  (`storage.py` docstring).
- **Code facts:**
  - `storage.ensure_local` returns the local file if it exists — it **never
    re-checks GCS** while the instance lives.
  - `storage.snapshot` uploads the whole file unconditionally (no generation
    precondition), so the last uploader wins.
  - `DEPLOY.md`: `--min-instances 1 --max-instances 4 --session-affinity`
    (affinity is best-effort). The Autopilot job downloads every DB, appends
    an `autopilot_briefing` row, and uploads.
- **Rival hypotheses:** (1) last-write-wins loses writes; (2) session affinity
  + a single instance make it unreachable; (3) the verifier would flag the
  divergence. (2) is weakened by `min-instances 1` alone: a warm instance
  always exists and the Autopilot is a *second writer by design*.
- **Induction:**
  ```
  [two web instances, same user]
  PREDICTION: la escritura de A se pierde en silencio; la cadena sobreviviente verifica OK
  OBSERVED:   evidencia_de_A=0 hipotesis_de_B=1 linkage=True integrity=True content=True issues=0

  [warm web instance vs Autopilot sweep]
    tras sweep, en GCS: autopilot_briefing=1
  PREDICTION: tras la escritura web, GCS ya no contiene la fila autopilot_briefing
  OBSERVED:   autopilot_briefing en GCS=0
  ```
  (3) **FALSIFIED**: the surviving chain is a valid chain — just a different
  branch. A hash chain proves internal consistency, not that no sibling branch
  existed; detecting a dropped tail needs an external anchor (the Round-1
  declared limit), and here the drop happens in normal operation.
- **Causal chain:**
  ```
  instance W holds local copy at seq N (never refreshed)
  Autopilot: download seq N → append seq N+1 (autopilot_briefing) → upload
  person writes on W: local seq N → append N+1' → snapshot uploads
      ↓ whole-file overwrite, no precondition
  GCS = W's branch; the Autopilot's sealed row is gone
      ↓
  verify_chain / verify_content on the survivor: all OK
  ```
  Bonus effect: W also *reads* stale state, so a person on W never sees the
  Autopilot's work it was supposed to leave "waiting".
- **Recommendation:** conditional upload with GCS object generations
  (`if_generation_match`): remember the generation you downloaded, refuse to
  overwrite a newer one, and re-download + retry the logical op (or fail loud).
  Re-validate the local copy against the blob generation at the start of each
  request. Separately, publish the chain head per user (e.g. a tiny
  `head` object or the Autopilot's log) so a lost tail becomes detectable.

### R2-4 — Unbounded anonymous compasses amplify into paid LLM calls

**Severity:** Medium **Level:** CONFIRMED BY INDUCTION (offline, counted calls)
**Bucket:** software vulnerability (resource / denial-of-wallet)
**Precondition:** anonymous HTTP access (the deploy).

- **Code facts:** any syntactically valid id creates and seeds a DB; any write
  (even an empty `POST /api/recompute`) snapshots it to GCS; `sweep` iterates
  **every** blob and calls Abductor + ResourceFinder (Google Search grounding) +
  Narrator for each. No rate limit, quota, or cap exists anywhere.
- **Induction:**
  ```
  PREDICTION: cada uid creado con UN POST anónimo entra al barrido y cuesta >=1 llamada LLM
  OBSERVED:   blobs en bucket=29 uids_flood_barridos=25/25 llamadas_backend_totales=87 (≈3.0 por brújula)
    GET-only: 25 bases locales creadas, 3300 KiB en DATA_DIR (/tmp = RAM en Cloud Run)
  ```
  ≈132 KiB of seeded SQLite per GET-created id lands in instance memory.
  Scaling these numbers to real costs is extrapolation, not measured.
- **Recommendation:** only sweep compasses with a real person-authored write
  (not the seed) and recent activity; cap the sweep per run; rate-limit id
  creation per client IP; consider not persisting a compass until its first
  non-seed write.

### R2-5 — Prose guard variants (Round-1 finding A, variant analysis)

**Severity:** Low–Med **Level:** CONFIRMED BY INDUCTION **Bucket:** limitation (declared v2 gap), now with its exact edges
- `_PERCENT_RE = r"\d\s*(%|percent|por\s+ciento)"`:
  ```
  rechazada | ...97% certain.          rechazada | ...97 percent certain.
  ACEPTADA  | ...97 per cent certain.  ACEPTADA  | ...97 pct.
  ACEPTADA  | ...al noventa y siete por ciento.
  ACEPTADA  | ...97％ certain.          (fullwidth percent sign)
  ACEPTADA  | There is a 0.97 probability ...
  ACEPTADA  | Your design index is 950/1000 — essentially certain.  (sealed value differs)
  ```
- **Recommendation:** NFKC-normalize before matching; extend to `per cent`,
  `pct`, word-number + `por ciento`; reject `probabilit*`; and the decisive one:
  any `N/1000` or bare integer in 0–1000 in the prose must equal a value in the
  summary handed to the narrator (that check is deterministic and cheap).

### R2-6 — Anonymous writes land on a showcase named after a real person

**Severity:** Low–Med **Level:** CONFIRMED BY INDUCTION **Bucket:** design / hygiene
- **Code fact:** `get_uid` defaults a missing header to `demo`; every write
  endpoint accepts it; `/health` reports the demo chain.
- **Induction:**
  ```
  PREDICTION: un request sin X-Compass-User borra evidencia de la vitrina
  OBSERVED:   http=200 evidencia#1 deleted=1
  ```
- **Why it matters beyond vandalism:** the seed person is "Anna (user zero)".
  With R2-1, an anonymous visitor can seal `corroborada` claims (or tombstone
  everything) on the profile every judge lands on, and it persists to GCS.
- **Recommendation:** make `demo` read-only at the API (or copy-on-write into a
  fresh id on first write); require the header on writes.

### R2-7 — Preregistration has no time separation

**Severity:** Low **Level:** CODE FACT + trivial induction **Bucket:** limitation
- `prereg=…39.861287`, `completed=…39.866944` — accepted. The schema enforces
  that a failure criterion *exists*, not that it was written *before* running.
  A person can write the criteria after the fact and close the experiment
  instantly. No fully deterministic fix (the system cannot observe the real
  world), but a minimum interval between `preregistered_at` and
  `completed_at`, or surfacing that interval in the UI, makes it visible —
  same honest mitigation as Round-1 C.

---

## Discarded / falsified vectors

| Vector | Result | Why |
|--------|--------|-----|
| Path traversal via `X-Compass-User` | **FALSIFIED** | `../etc`, `a/b`, 65 chars, `ok%2F..` → 400. |
| Trailing-newline uid (`demo\n`) | **FALSIFIED over HTTP**; CODE FACT remains | `re.match` with `$` accepts `"demo\n"` and creates a separate `compass_demo\n.db` when called in-process, but h11 strips it before the app sees it. Use `fullmatch`/`\Z` as hygiene. |
| Brute-forcing another person's compass id | **Not feasible** | ≈71 bits from `crypto.getRandomValues`. |
| Unvalidated evidence moves an index | **FALSIFIED** | 10 linked `validated=false` → `index=0 latente`. |
| Autopilot moves a sealed value | **FALSIFIED** | No domain write lever; guard never tripped across all runs. |
| Linking the same evidence twice to inflate | **FALSIFIED** | PK `(hypothesis_id, evidence_id)` rejects it — but as an unhandled `IntegrityError` → HTTP 500 (hygiene: map to 400). |

## Hygiene noted (not exploited)

- No unlink endpoint: a mistaken link (including the wrong direction) is
  permanent short of tombstoning the evidence.
- Request bodies (`content`, `narrative`, `statement`) have no size cap.
- CORS `*` (no credentials, so low impact; ids travel in a header).
- Environment note: 2 tests in `test_hackathon_layer.py` and the ADK test
  modules need `google-genai` / `google-adk`; with only fastapi installed the
  rest of the suite is green (177 passed).

## Recommendations (out of scope of this change — record only)

Priority by severity × cost: R2-3 (generation-conditional upload) and R2-1
(unforgeable discriminating types) first; R2-6 (read-only demo) is a few
lines; then R2-2, R2-4, R2-5, R2-7. Each fix should land with a regression
test that fails first on `85d8d2e`, as in Round 1.
