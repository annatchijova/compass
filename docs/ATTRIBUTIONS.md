# COMPASS — third-party knowledge, instruments, and licensing

The vocational direction of COMPASS draws on established, validated
instruments and datasets. This file records exactly what may be used, under
what terms, and what must be avoided — so the project stays honest (no
pseudoscience) **and** clean (no license debt). Terms below were verified
against the sources' own license pages on 2026-08-29; links are provided so
they can be re-checked. This is documentation, not legal advice — confirm
current terms at the source before any change of use.

COMPASS is currently used **non-commercially**. Several notes below flag
where commercial use would differ, for future reference.

---

## The core distinction: theory vs. instrument

Scientific **models and theories are not copyrightable** — only specific
expressions are (the exact wording of a questionnaire's items, published
descriptions, logos, names). So COMPASS is free to use the *models* (Big
Five, Holland's RIASEC) and must only be careful about the *specific
instruments* that express them: use public-domain / openly-licensed ones, or
write original items informed by the free model.

COMPASS's own discipline keeps all of this honest: any questionnaire result
is `self_report` evidence — the **lowest-weight** type — and seeds
*hypotheses to test*, never a verdict. We use the same inputs as the
personality tests, but treat them as hypotheses, not truths.

---

## Usable (free / openly licensed)

### Big Five (OCEAN) — via IPIP
- **Model:** the Five-Factor model is a scientific framework — free to use.
- **Instrument:** **International Personality Item Pool (IPIP)** —
  **public domain**. Verified statement:
  > "the IPIP has been placed in the public domain, permission has already
  > been automatically granted for any person to use IPIP items, scales, and
  > inventories for any purpose, commercial or non-commercial."
  No permission, no contact, no fee; may be modified and embedded in
  software. Source: https://ipip.ori.org/newPermission.htm
- **How COMPASS uses it:** an optional intake that produces `self_report`
  evidence and candidate hypotheses (trait descriptions), never a typed
  verdict.

### Holland's RIASEC interests
- **Model:** RIASEC (Realistic, Investigative, Artistic, Social,
  Enterprising, Conventional) — a scientific taxonomy, free to use.
- **Instrument options:**
  - **O*NET Interest Profiler** — **CC BY-ND 4.0** (verbatim copies only,
    with attribution; *no modifications* under this option). A separate
    *O\*NET Tools Developer License* covers modified/derived tools (attribution
    + a "not approved/endorsed/tested" disclaimer; developer registration
    requested). Source: https://www.onetcenter.org/license_tools.html
  - **Preferred for a custom, modifiable intake:** write **original items**
    measuring the six RIASEC dimensions, informed by the free model. Original
    expression sidesteps the ND restriction entirely and keeps the intake
    fully ours (Apache-2.0).

### Occupation data (what paths require) — O*NET Database
- **License:** **CC BY 4.0** — free to use, adapt, and redistribute
  (commercial included) with attribution. Verified required statement:
  > "This page includes information from the O*NET 31.0 Database by the U.S.
  > Department of Labor, Employment and Training Administration (USDOL/ETA).
  > Used under the CC BY 4.0 license."
  For modified data add: "[COMPASS] has modified all or some of this
  information." Three conditions: credit O*NET + USDOL/ETA, link the CC BY 4.0
  license, indicate changes. Optional developer registration.
  Source: https://www.onetcenter.org/license_db.html
- **Trademark:** "O\*NET" is a registered trademark — use it as an adjective
  with a generic noun ("O\*NET data", "O\*NET database"), display the ®, never
  as a bare/possessive/plural noun, and never imply USDOL/ETA endorsement.
- **How COMPASS uses it:** occupation → required interests/skills, feeding the
  **Trajectory / trajectory_requirement** layer (design doc §5, §7) as
  `outcome_external`-grade reference data for capability-requirement fit.

---

## Avoid (proprietary — do not copy items, descriptions, or marks)

| Source | Why avoid |
|---|---|
| **MBTI®** / **16personalities** / NERIS Type Explorer | Trademarked; the 16-type items and descriptions are copyrighted. We take the Big Five *idea* (via IPIP), nothing of theirs. Also: the 16-type output is the pseudoscience COMPASS rejects (categorical claims about continuous traits). |
| **Self-Directed Search (SDS)** | Proprietary RIASEC instrument (PAR); licensed/paid. Use O*NET or original items instead. |
| **Strong Interest Inventory®** | Proprietary interest inventory; licensed/paid. |
| **NEO-PI-R** | Proprietary Big Five instrument (PAR); paid. Use IPIP instead. |

---

## Attribution COMPASS must carry when it ships O*NET data

Include in a user-visible place (e.g. the intake/trajectory screen and this
repo) whichever applies:

- Verbatim: *"This product includes information from the O\*NET® Database by
  the U.S. Department of Labor, Employment and Training Administration
  (USDOL/ETA), used under the CC BY 4.0 license
  (https://creativecommons.org/licenses/by/4.0/). O\*NET® is a trademark of
  USDOL/ETA."*
- Modified: append *"COMPASS has modified some of this information. USDOL/ETA
  has not approved, endorsed, or tested these modifications."*

IPIP requires no attribution (public domain), but crediting it is courteous:
*"Personality items adapted from the International Personality Item Pool
(https://ipip.ori.org), public domain."*

---

## Bottom line

The non-pseudoscience path is also the open path: **IPIP (public domain) +
O\*NET Database (CC BY 4.0) + original RIASEC-informed items** give COMPASS a
validated, free, Apache-2.0-compatible vocational foundation with zero
proprietary dependencies — no MBTI, no SDS, no Strong, no NEO.
