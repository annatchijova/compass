# Security Audit — COMPASS

## Red Team Round 1

**Date:** 2026-08-29 **Method:** Abductive Engineering (A–D–I) + Red-Team Auditing
**Scope:** the load-bearing invariant — *no number describing the person comes
from an LLM; the deterministic engine seals every index before any model is
called; swapping the model changes only prose, never a sealed value* — plus the
anti-flattery factor, experiment preregistration, the audit chain, and the ADK
agent's tool-bounded authority. Out of scope: modifying the source code.
**Base:** `main` @ 675fe3c **Runtime:** Python 3.12.3
**Reproducible evidence:** inductions below run against the seeded demo scenario;
each states its PREDICTION before the OBSERVED result.

## Threat model

- **Attacker CAN:** act as the LLM in any of its roles (extractor, abductor,
  narrator) and drive the ADK agent through its authorized tools — this is the
  thing under audit. For the audit-chain findings, additionally: write rows in
  the SQLite database (this is the very capability a tamper-evident ledger
  exists to detect; a ledger whose threat model excludes DB writes has no
  reason to hash-chain).
- **Attacker CANNOT:** modify the source code; hold no capability the design
  already declares game-over (the README already concedes that a writer who
  rewrites the whole chain from genesis is only *detectable* against an external
  tail-hash anchor).
- **Trust boundaries crossed:** LLM/agent → sealed index (B′, A); DB → sealed
  content reference (D1, D2); user/agent intent → anti-flattery guarantee (C).

## Epistemic legend

CODE FACT · PLAUSIBLE HYPOTHESIS · CONFIRMED BY INDUCTION · FALSIFIED

## What holds — the headline invariant is intact

**CONFIRMED (live, 2026-08-29):** swapping the narrator backend (offline `demo`
↔ Gemini 2.5 Flash on Vertex AI) returns the **same state seal** (`8fc1128…`) on
`POST /api/narrate`. The engine seals before the model is called; the arithmetic
never leaves the deterministic core. This invariant did **not** break. The
findings below are cracks *around* the seal — in authority, in content
verification, and in the human-facing channel — not in the sealing itself. They
matter precisely because they are only visible if you look for them.

## Inspected surface

Read in full against the live tree at 675fe3c: `src/compass/llm.py`,
`engine.py`, `views.py`, `domain.py`, `db.py`, `audit_chain.py`,
`canonicalize.py`, `api.py`, `agent/agent.py`, `seed_demo.py`, `storage.py`, and
the independent verifier `tools/verify_chain.py`. The determinism suite and the
negative-control mutations in `tests/` were noted but not re-audited this round.

## Executive summary

| ID | Severity | Level | Module | Finding |
|----|----------|-------|--------|---------|
| B′ | High | CONFIRMED BY INDUCTION | `agent/agent.py`, `domain.py`, `engine.py` | **FIXED.** The ADK agent set an arbitrary *sealed* index by choosing the evidence→hypothesis graph and its supports/contradicts direction, then calling recompute — no human step. `link_evidence` removed from the agent. |
| D1 | High | CONFIRMED BY INDUCTION | `tools/verify_chain.py` | **FIXED.** Referenced-content tamper-evidence was evaded by editing `evidence.content` and `evidence.content_hash` together, because verifiers compared live content to the **mutable table column**, not to the `content_hashes` **sealed in the chain**. Verifier now binds to the sealed value. |
| C | Medium | CONFIRMED (code fact) | `engine.py`, `domain.py` | The anti-flattery factor is defeated by omission: unlinked contradicting evidence simply does not count; nothing enforces graph completeness. |
| A | Low–Med | CONFIRMED BY INDUCTION (declared gap) | `llm.py`, `views.py` | Narrator prose can state a number/verdict contradicting the seal; `validate_prose` checks only length. Acknowledged as a v2 gap in the design. |
| D2 | Low | CODE FACT | `audit_chain.py`, `api.py` | The in-package `verify_chain` used by `/health` and `/api/chain` never checks content, so the dashboard "integrity ✓" badge does not cover content tampering. |

---

## Findings

### B′ — The ADK agent fixes a sealed index by choosing the graph

**Severity:** High **Epistemic level:** CONFIRMED BY INDUCTION
**Bucket:** software / design vulnerability (authority boundary)

- **Surprise / expectation violated:** the design's authority table states the
  LLM may *"propose, abduce, narrate — never decide or score."* Yet the agent's
  tools include `link_evidence` (with a caller-chosen `supports`/`contradicts`
  direction) and `recompute_indices`. Choosing the graph the engine scores *is*
  scoring.
- **Abduction (ranked by economy):** (1) the tool set grants the model authority
  the design reserves away from it; (2) benign — the agent can only *propose*, a
  human still gates everything. Test (1) first: it is a one-shot induction.
- **Deduction:** if (1) holds, then with the **same** human-validated evidence,
  the agent can produce two different sealed indices purely by choosing the link
  direction, with no human action.
- **Induction (run against 675fe3c, seeded scenario):** using only the agent's
  own tools — `add_hypothesis` → `link_evidence` → `recompute_indices` — on the
  same validated evidence #3 (`outcome_external`, weight 250):

  ```
  PREDICTION: same evidence → HIGH index via 'supports', ZERO via 'contradicts'.
  OBSERVED supports:    index=454/1000 [activa]      seal=5bdd7da43085c409…
  OBSERVED contradicts: index=0/1000  [debilitada]  seal=d16e35f4f150482a…
  → same evidence, agent-chosen sign; sealed index and seal differ (454 vs 0).
  ```

- **Causal chain:**
  ```
  agent picks hypothesis + evidence + direction (link_evidence)
      ↓
  recompute_indices() runs the deterministic engine over that graph
      ↓
  engine sums weights by the agent-chosen sign → index
      ↓
  index is SEALED and returned
  → the number is engine-computed, but it is a deterministic function of a
    model-chosen input. The model controls the sealed value.
  ```
- **Precise language:** not "the LLM emits a number" (it does not) — but
  **"an arbitrary sealed index can be induced before sealing, because the agent
  chooses the graph and direction the engine then scores."** The seal works; the
  input was model-authored.
- **Mitigating context (does not remove the finding):** the agent acts for the
  person; it cannot fabricate evidence (evidence still requires human
  validation); the link is recorded in the audit chain. But nothing *prevents*
  it or marks the index as resting on model-authored links.
- **Recommendation:** remove `link_evidence` / `recompute_indices` from the
  agent's tools (make linking a human act, mirroring evidence validation); or
  tag agent-created links `origin=llm` and exclude them from the sealed index
  until the person confirms them.
- **Status: FIXED (this round).** `link_evidence` was removed from the ADK
  agent's tool set (and from the module). Linking is now a human-only act, like
  validation. The agent keeps its propose/read/narrate tools plus
  `recompute_indices` (a pure deterministic run over the human-authored graph,
  which involves no model choice). Regression:
  `tests/test_redteam_round1_fixes.py::test_bprime_agent_has_no_scoring_authority`.

### D1 — Content tamper-evidence evaded by a dual-column edit

**Severity:** High **Epistemic level:** CONFIRMED BY INDUCTION
**Bucket:** software vulnerability

- **Surprise / expectation violated:** the README claims *"editing the
  referenced row is detected even though the chain recomputes fine"*, and the
  design distinguishes this from a full-history rewrite (which it concedes needs
  an external anchor). So content tampering should be caught by a *fresh*
  verifier with no prior anchor.
- **Abduction:** (1) the guarantee holds; (2) the verifier compares live content
  against the wrong value. The initial hypothesis "content edits go undetected"
  is the cheapest to test first.
- **Deduction → self-falsification:** predicted that editing `evidence.content`
  would go undetected. It did **not** — a single-column edit is caught
  (`QUIEBRE DETECTADO`, exit 1). The first framing is **FALSIFIED**; corrected
  vector: the verifier checks `sha256(content)` against `evidence.content_hash`
  (a mutable table column), not against the `content_hashes` sealed in the
  chain — so editing **both** columns consistently should evade it.
- **Induction (run against 675fe3c):**

  ```
  [single-column edit of evidence.content]
  PREDICTION: DETECTED (exit=1, contenido_ok False)
  OBSERVED:   exit=1  contenido_ok: False  →  QUIEBRE DETECTADO

  [dual-column edit — content AND content_hash together]
  PREDICTION: NOT DETECTED (exit=0, VERIFICA) — the finding
  OBSERVED:   exit=0  contenido_ok: True   →  VERIFICA
  chain's SEALED content_hashes (old) = 842e0f498e277a5c…
  live evidence.content_hash (forged)  = 806dd8d94b9348d5…
  → the sealed value exists but is never compared against the live content.
  ```

  Reproduction: seed a DB, then
  `UPDATE evidence SET content='{"text":"FORGED"}',
   content_hash='<sha256 of that string>' WHERE id=1;`
  then `python3 tools/verify_chain.py <db>` → prints `VERIFICA`.
- **Causal chain:**
  ```
  content_hash is stored in TWO places:
    (1) evidence.content_hash   — a mutable table column
    (2) audit_chain.content_hashes — sealed into audit_hash (tamper-evident)
  verifier checks:  sha256(live content) == (1)      ← mutable
  verifier never:   sha256(live content) == (2)      ← the sealed value
  → editing (content, (1)) together satisfies the check; (2) sits unused.
  ```
- **Precise language:** not "the seal is broken" — chain linkage and integrity
  are intact — but **"referenced-content tamper-evidence is bypassable by
  updating `evidence.content` and `evidence.content_hash` together, because the
  verifiers bind live content to a mutable column instead of to the sealed chain
  value."** No genesis rewrite required; a fresh verifier does not catch it.
- **Recommendation:** the verifier must compare `sha256(live content)` against
  the chain's **sealed** `content_hashes` (matching by `evidence_id` in the
  payload), not against `evidence.content_hash`. That binds the live content to
  the tamper-evident value and closes the bypass. Apply the same fix to any
  API-surfaced content check (see D2).
- **Status: FIXED (this round).** `tools/verify_chain.py` now builds a map
  `evidence_id -> {content hashes sealed in the chain}` by reading the
  tamper-evident `content_hashes` and the `evidence_id` straight from each
  sealed payload (stdlib-only, still no package import), and checks
  `sha256(live content)` against *that* set — not the mutable column. This
  closes both the demonstrated dual-column forge and the narrower
  content-swap-between-evidences residual (the hash must match the sealed value
  *for that specific evidence_id*). Regressions:
  `test_d1_dual_column_content_forgery_is_detected`,
  `test_d1_single_column_edit_still_detected`, `test_d1_clean_db_still_verifies`.

### C — Anti-flattery is defeated by omission

**Severity:** Medium **Epistemic level:** CONFIRMED (code fact)
**Bucket:** limitation (self-deception vector, not an external attack)

- **Code fact:** `compute_hypothesis` applies the ×3/2 factor only to evidence
  **linked** as `contradicts`. Nothing requires the evidence→hypothesis graph to
  be complete.
- **Consequence:** anyone seeking a flattering result (or a biased agent) simply
  does not link the disconfirming evidence; the engine faithfully sums an
  incomplete graph and seals an inflated index. The guarantee "cannot become a
  flattering mirror" is conditional on graph completeness — and omission is the
  most natural failure mode of someone who wants the mirror. This is precisely
  the failure the tool advertises it prevents.
- **Recommendation:** surface coverage ("N validated evidences not linked to
  this hypothesis"), and/or have the abductor actively propose the refuting
  evidence. No fully deterministic fix exists — document it as an honest limit.

### A — Narrator prose can contradict the seal (declared gap, confirmed)

**Severity:** Low–Medium **Epistemic level:** CONFIRMED BY INDUCTION
**Bucket:** limitation — already disclosed (design §3.3 "v2"; README blind spot)

- **Induction (run against 675fe3c):** a narrator backend returning
  *"Your design capability is measured at 97 percent — essentially certain."*
  was accepted and stored verbatim by `narrate_compass`, alongside the sealed
  662/1000 index (which is not a percentage). `validate_prose` checks only
  length and non-emptiness; no prose-vs-seal consistency check exists.
- **The nuance that matters:** the invariant "swapping the backend never changes
  a number" holds for the **sealed** number; but the human reads the **prose**,
  and the prose can smuggle an unsealed number presented as authoritative. The
  documented mitigation ("a verifier can confirm the result without trusting the
  prose") is true, but an ordinary user does not run a verifier — so the
  *practical* guarantee to a human is weaker than the architectural one.
- **Recommendation:** implement the v2 narrative auditor (a deterministic check
  that the prose asserts no numbers inconsistent with the summary), or forbid the
  narrator from emitting figures (template the numbers in after generation).

### D2 — The dashboard "integrity ✓" badge does not cover content

**Severity:** Low **Epistemic level:** CODE FACT **Bucket:** claim precision

- **Code fact:** the in-package `verify_chain` (used by `/health` and
  `/api/chain`, and shown as the dashboard's "linkage ✓ integrity ✓" badge)
  verifies only chain linkage and hash integrity; it never reads the `evidence`
  table. The content check lives only in the standalone `tools/verify_chain.py`
  (and even there is bypassable per D1).
- **Induction (run against 675fe3c):** with forged content in place,
  `verify_chain` reported `linkage_ok=True integrity_ok=True issues=0`.
- **Recommendation:** wire the (fixed, per D1) content check into the API path,
  or relabel the badge precisely as "chain linkage / integrity" rather than the
  broader "integrity".

---

## Discarded / falsified vectors (part of the deliverable)

| Vector | Result | Why |
|--------|--------|-----|
| "Swapping the backend changes a sealed number" | **FALSIFIED** | Same seal `8fc1128…` under `demo` and Gemini/Vertex, verified live. The headline invariant holds. |
| "The extractor injects validated evidence and moves the index" | **FALSIFIED** | `compute_hypothesis` filters `validated=1 AND deleted=0`; extractor candidates are born `validated=0` and are excluded. The extraction boundary holds. |
| "Editing content (single column) goes undetected" | **FALSIFIED** | It is detected (`QUIEBRE DETECTADO`). The real bypass needs both columns (D1). |
| "A float or non-determinism leaks into the seal" | **Not attacked this round** | `canonicalize` raises on floats (`CanonicalizeError`) and checks `bool` before `int`; a determinism suite exists. No claim made. |

## Remediation

**Applied this round** (each: audit-before-patch on the live file, surgical
anchored patch, a regression test that failed first on the vulnerable state,
full suite green at 105 tests):

1. **B′ — FIXED.** `link_evidence` removed from the ADK agent's tools; linking
   is now human-only. Test: `test_bprime_agent_has_no_scoring_authority`.
2. **D1 — FIXED.** The independent verifier binds live content to the
   chain-sealed `content_hashes` per `evidence_id`, not to the mutable column.
   Tests: the three `test_d1_*`.

**Backlog (recorded, not applied):**

3. **D2** — surface the (now fixed) content check on the API, or relabel the
   dashboard badge as "chain linkage / integrity".
4. **A** — implement the v2 narrative auditor, or template numbers into prose.
5. **C** — surface unlinked-evidence coverage; document the omission limit
   (no fully deterministic fix — an honest limitation).
