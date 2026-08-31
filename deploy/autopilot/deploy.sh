#!/usr/bin/env bash
# COMPASS Autopilot — deploy the background job + its cron trigger.
#
# What this creates:
#   1. a Cloud Run JOB (compass-autopilot) that sweeps every sealed compass
#      once and exits (no server, no public URL: it is batch work);
#   2. a Cloud Scheduler cron that runs the job (default: daily 07:00 ART),
#      so the person wakes up to a fresh next-step briefing.
#
# The job reuses the SAME billing project, Vertex config and GCS bucket as
# the live backend, so it restores/snapshots the very same user bases. It
# stays on schema v3 (append-only chain row, no migration), so the already
# deployed services keep opening those bases unchanged.
#
# Idempotent-ish: uses `create || update`. Run from the repo root.
set -euo pipefail

PROJECT=vigia-497422
REGION=us-central1
JOB=compass-autopilot
IMAGE=gcr.io/${PROJECT}/${JOB}
BUCKET=compass-user-data-${PROJECT}
SCHEDULE=${SCHEDULE:-"0 7 * * *"}        # daily 07:00; override with SCHEDULE=...
TZ_NAME=${TZ_NAME:-"America/Argentina/Buenos_Aires"}

# The runtime service account of the job (must be able to read/write the
# bucket and call Vertex — the same grants the backend already has).
SA=${SA:-"$(gcloud iam service-accounts list --project "$PROJECT" \
  --filter 'displayName:Compute Engine default service account' \
  --format 'value(email)' | head -1)"}

echo "== 1/3 build the job image =="
gcloud builds submit --config deploy/autopilot/cloudbuild.yaml --project "$PROJECT" .

echo "== 2/3 create/update the Cloud Run Job =="
COMMON_ENV="COMPASS_BACKEND=gemini,COMPASS_MODEL=gemini-3.5-flash,\
GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=${PROJECT},\
GOOGLE_CLOUD_LOCATION=global,COMPASS_GCS_BUCKET=${BUCKET},\
COMPASS_DATA_DIR=/tmp/compass-data,COMPASS_LANGUAGE=English"

if gcloud run jobs describe "$JOB" --region "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud run jobs update "$JOB" --image "$IMAGE" --region "$REGION" \
    --project "$PROJECT" --service-account "$SA" \
    --set-env-vars "$COMMON_ENV" --max-retries 1 --task-timeout 900
else
  gcloud run jobs create "$JOB" --image "$IMAGE" --region "$REGION" \
    --project "$PROJECT" --service-account "$SA" \
    --set-env-vars "$COMMON_ENV" --max-retries 1 --task-timeout 900
fi

echo "== 3/3 create/update the Cloud Scheduler cron =="
# Scheduler calls the Cloud Run Admin API :run endpoint with an OAuth token.
RUN_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB}:run"
if gcloud scheduler jobs describe "${JOB}-cron" --location "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "${JOB}-cron" --location "$REGION" --project "$PROJECT" \
    --schedule "$SCHEDULE" --time-zone "$TZ_NAME" --uri "$RUN_URI" \
    --http-method POST --oauth-service-account-email "$SA"
else
  gcloud scheduler jobs create http "${JOB}-cron" --location "$REGION" --project "$PROJECT" \
    --schedule "$SCHEDULE" --time-zone "$TZ_NAME" --uri "$RUN_URI" \
    --http-method POST --oauth-service-account-email "$SA"
fi

echo
echo "Done. Trigger one run now with:"
echo "  gcloud run jobs execute ${JOB} --region ${REGION} --project ${PROJECT}"
echo "Watch logs with:"
echo "  gcloud run jobs executions list --job ${JOB} --region ${REGION} --project ${PROJECT}"
