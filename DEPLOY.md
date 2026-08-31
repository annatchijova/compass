# COMPASS — Google Cloud deployment

Spin-up for the COMPASS backend on Google Cloud Run, with Gemini served by
Vertex AI through the service identity (no API key stored in the service).

Three mandatory hackathon boxes, all checked: **Gemini** (Vertex AI), a
**Google agent framework** (ADK), and a **Google Cloud service** (Cloud Run).
The index is sealed by the deterministic core, never by Gemini — swapping the
model changes only the narration.

## What runs where

- **Cloud Run** (`compass`, region `us-central1`) hosts the FastAPI backend
  (`compass.api:app`): the deterministic core + the LLM roles behind an HTTP
  API. This is what the Next.js frontend calls.
- **Vertex AI** serves Gemini to the `GeminiBackend` through the Cloud Run
  service identity.
- The **ADK agent** (`compass.agent.root_agent`) is deployable separately with
  `adk deploy cloud_run` (below), or run locally with `adk web`.

## Prerequisites

```bash
PROJECT=vigia-497422    # reuse the existing billing-enabled project
gcloud services enable run.googleapis.com aiplatform.googleapis.com \
    cloudbuild.googleapis.com artifactregistry.googleapis.com \
    storage.googleapis.com --project $PROJECT
```

### Per-user persistence bucket

Each user's isolated SQLite base is snapshotted to Cloud Storage (survives
cold starts). Create the bucket and let the Cloud Run runtime service account
read/write it:

```bash
BUCKET=gs://compass-user-data-$PROJECT
SA=1028999311218-compute@developer.gserviceaccount.com   # Cloud Run runtime SA
gcloud storage buckets create $BUCKET --project $PROJECT \
    --location us-central1 --uniform-bucket-level-access
gcloud storage buckets add-iam-policy-binding $BUCKET --project $PROJECT \
    --member="serviceAccount:$SA" --role="roles/storage.objectAdmin"
```

## Deploy the backend API

```bash
gcloud run deploy compass \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi --cpu 1 --timeout 300 \
  --session-affinity --min-instances 1 --max-instances 4 \
  --set-env-vars COMPASS_BACKEND=gemini,GOOGLE_GENAI_USE_VERTEXAI=TRUE,\
GOOGLE_CLOUD_PROJECT=vigia-497422,GOOGLE_CLOUD_LOCATION=global,\
COMPASS_MODEL=gemini-3.5-flash,COMPASS_GCS_BUCKET=compass-user-data-vigia-497422 \
  --project vigia-497422
```

`--session-affinity` keeps a browser on one instance (so its per-user SQLite
writes and GCS snapshots do not race across instances). To run the hosted demo
**without** a model (still shows the full deterministic cycle), drop the Gemini
env vars — the container defaults to `COMPASS_BACKEND=demo`. Drop
`COMPASS_GCS_BUCKET` to run without persistence (local-only, reported on
`/health`).

### Gotcha 1 — Vertex location for Gemini 3.x is `global`, not a region

Gemini 3.x publisher models are served on Vertex AI's **`global`** endpoint.
A regional `GOOGLE_CLOUD_LOCATION=us-central1` yields a 404
(`Publisher model ... was not found`). Set `GOOGLE_CLOUD_LOCATION=global`; the
Cloud Run service itself still lives in `us-central1`. (Verified the hard way
on the sibling VIGIA deployment.)

### Gotcha 2 — `GOOGLE_CLOUD_PROJECT` is not injected for you

Cloud Run injects `PORT` and `K_SERVICE`, but **not** `GOOGLE_CLOUD_PROJECT`.
Vertex needs it. Set it explicitly, as above, and confirm on `/health` that
`gemini_transport` reads `vertex-ai` before recording the demo.

### Verify

```bash
URL=$(gcloud run services describe compass --region us-central1 \
      --format 'value(status.url)' --project vigia-497422)
curl -s "$URL/health" | python3 -m json.tool
curl -s "$URL/api/state" | python3 -m json.tool     # seeded compass
```

## Deploy the frontend

The Next.js app in `frontend/` has its own `Dockerfile` (standalone output).
Build its `NEXT_PUBLIC_API_URL` to point at the backend URL, then:

```bash
cd frontend
gcloud run deploy compass-web \
  --source . --region us-central1 --allow-unauthenticated \
  --set-env-vars NEXT_PUBLIC_API_URL=$URL \
  --project vigia-497422
```

## Resource search (Google Search grounding)

The resource finder asks Gemini with the SDK's built-in Google Search tool,
so resources come back with the sources they were found at. It needs no
extra API beyond `aiplatform.googleapis.com`, which the prerequisites above
already enable, and no extra env var: any deployment where
`COMPASS_BACKEND=gemini` works will ground.

Two things to know before turning it loose:

- It sends the capability's wording to Google. That is why it is an explicit
  click in the UI and never automatic (design doc §6).
- A backend that cannot search answers `grounded: false`, and the web app
  says so rather than passing the model's memory off as a search. The
  offline `demo` backend returns sample resources with no URLs at all.

**Untested live.** This path is written against `google-genai` 2.x and
covered by a stub in the suite; no real search call has been made yet.

## Deploy the ADK agent (separate service)

The multi-agent team (`compass.agent.root_agent`: a Companion orchestrating
analyst / activity_scout / reflector) runs as its own Cloud Run service and is
**live** at
<https://compass-agent-1028999311218.us-central1.run.app> (ADK Web UI —
pick `compass_companion` and chat).

`adk deploy cloud_run src/compass/agent` does **not** work here: ADK copies the
agent folder and loads it as a top-level package, but the agent uses relative
imports into the stdlib-only core (`from .. import domain, engine, ...`), so it
must be loaded as `compass.agent` with the whole package installed. Instead we
build a container that installs the `compass` package and serves `adk web` over
a thin wrapper that re-exports `root_agent` with an absolute import. All of it
lives under `deploy/agent/` (Dockerfile, entrypoint that seeds the demo state
on boot, and `agents/compass_companion/__init__.py`). Same Vertex config as the
backend (`GOOGLE_CLOUD_LOCATION=global` for the gemini-3.5-flash family).

```bash
# Build the image (context = repo root) and deploy.
gcloud builds submit --config deploy/agent/cloudbuild.yaml --project vigia-497422 .
gcloud run deploy compass-agent \
  --image gcr.io/vigia-497422/compass-agent \
  --project vigia-497422 --region us-central1 \
  --allow-unauthenticated --memory 1Gi --timeout 300 \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=vigia-497422,GOOGLE_CLOUD_LOCATION=global,COMPASS_BACKEND=gemini,COMPASS_MODEL=gemini-3.5-flash,COMPASS_DB=/tmp/compass.db
```

The ADK Web UI is a development surface: fine for the demo, but it is not the
branded COMPASS frontend, and each instance seeds its own ephemeral SQLite on
boot (no cross-instance shared state). The architecture invariant still holds —
every agent reads or reseals through the deterministic core; none can fabricate
an index.

## Known considerations

- Deployed `--allow-unauthenticated` for the demo. Agent-mode / narrate /
  extract requests trigger billed Vertex calls; add authentication or rate
  limiting before sharing the URL widely.
- Cloud Run local disk is ephemeral: the SQLite DB is seeded on boot and
  resets on cold start. `/health` reports `db_durability` honestly. For
  durable state, mount a volume or back the store with a managed database.
