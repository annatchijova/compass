<!--
Paste-ready EXTRA text for the Devpost submission. Written to carry the
autonomous-agent story in prose, since the demo video is final. Copy the
section below (from "The autonomous layer" down) straight into the Devpost
"Text description" / "Features and functionality" field.
-->

# Devpost — EXTRA text (paste this)

## The autonomous layer: an agent that acts, not one that waits

Most AI waits for you to ask. COMPASS ships an **Autopilot** that doesn't.

The *same* multi-agent team you can chat with (a Companion orchestrating an
Analyst, an Activity Scout, and a Reflector, built on **Google ADK**) also runs
**unattended in the background** as a **Cloud Run Job triggered by Cloud
Scheduler**. On a schedule, with no human in the room, it sweeps *every* user's
compass and, for each one:

1. reads the person's already-sealed state (read-only);
2. names the deterministic capability gap worth testing next;
3. **drafts the next discriminating experiment** (a preregistered design with a
   failure criterion written before it runs);
4. **searches the live web with Gemini + Google Search** for concrete, grounded
   ways to actually run that experiment — a course, a community, an open project;
5. puts the whole thing into words; and
6. acts as a **Sentinel**, verifying the tamper-evident audit ledger
   (linkage · integrity · content) of every compass — so tampering is not merely
   *detectable*, it is actively *watched*, across the whole fleet, asynchronously.

The person wakes up to a ready-to-act briefing. The heavy lifting — gap
analysis, web research, drafting, and fleet-wide ledger verification — already
happened while they slept. This is the hackathon's thesis delivered literally:
**runs in the background, handles the heavy lifting, async.**

## The discipline that makes it trustworthy

Here is the part we are proudest of. It would have been easy to make the agent
"autonomous" by letting it decide — validate your evidence, close your
experiments, move your numbers. We refused. COMPASS's core invariant is that
**no number describing a person ever comes out of a language model**; a
deterministic engine computes and *seals* every index before any model speaks.

So the Autopilot's autonomy is over the **heavy lifting, never over the
decision**. It *proposes* and it *watches*; it never validates evidence, links
it, closes an experiment, or moves a single sealed number. Three mechanisms
enforce that boundary:

- **By construction** it holds no domain-write lever — it imports only sealed
  reads, the no-authority LLM roles, and the verifier.
- **By a fail-closed runtime guard**: the seal and every index are snapshotted
  before and after each run; if anything moved, it raises `AutopilotBoundaryError`
  and refuses to persist — the architecture would be broken.
- **By storing its briefing *beside* the seal, never inside it**: only a hash of
  the briefing enters the append-only chain, so the schema never changes and the
  already-deployed services keep serving unchanged.

A test locks this in: swap the model backend (Gemini ↔ offline) and only the
*wording* of the briefing changes — never a verdict, a seal, or the chain of
custody. That test *is* the thesis, now proven for the autonomous actor too.

## Proof it runs on Google Cloud

- **Cloud Run Job:** `compass-autopilot` (region `us-central1`, project
  `vigia-497422`) — batch, runs to completion, no public URL by design.
- **Cloud Scheduler:** `compass-autopilot-cron`, ENABLED, daily.
- **Vertex AI:** serves `gemini-3.5-flash` through the job's service identity
  (no API key stored).
- **Cloud Storage:** each user's sealed SQLite base is restored, swept, and
  snapshotted back — the same bucket the live backend uses.
- Reproduce it in one command: `bash deploy/autopilot/deploy.sh`; trigger a run
  with `gcloud run jobs execute compass-autopilot`. Full walkthrough in
  `DEPLOY.md`; code in `src/compass/agent/autopilot.py`.

---

### One-liner (for the tagline / social post)

> COMPASS's Autopilot is the same agent team, running unattended on Cloud Run +
> Cloud Scheduler: while you sleep it drafts your next experiment, finds where to
> run it, and stands guard over a tamper-evident ledger — autonomous over the
> heavy lifting, never over your decision, and provably unable to move a single
> sealed number. #AllThingsAgenticHackathon
