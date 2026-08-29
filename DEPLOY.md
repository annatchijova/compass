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
    --project $PROJECT
```

## Deploy the backend API

```bash
gcloud run deploy compass \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi --cpu 1 --timeout 300 \
  --set-env-vars COMPASS_BACKEND=gemini,GOOGLE_GENAI_USE_VERTEXAI=TRUE,\
GOOGLE_CLOUD_PROJECT=vigia-497422,GOOGLE_CLOUD_LOCATION=global,\
COMPASS_MODEL=gemini-2.5-flash \
  --project vigia-497422
```

To run the hosted demo **without** a model (still shows the full deterministic
cycle), drop the env vars — the container defaults to `COMPASS_BACKEND=demo`.

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

## Deploy the ADK agent (optional, separate service)

```bash
adk deploy cloud_run src/compass/agent \
  --project vigia-497422 --region us-central1
```

## Known considerations

- Deployed `--allow-unauthenticated` for the demo. Agent-mode / narrate /
  extract requests trigger billed Vertex calls; add authentication or rate
  limiting before sharing the URL widely.
- Cloud Run local disk is ephemeral: the SQLite DB is seeded on boot and
  resets on cold start. `/health` reports `db_durability` honestly. For
  durable state, mount a volume or back the store with a managed database.
