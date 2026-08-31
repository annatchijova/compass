#!/usr/bin/env bash
# COMPASS ADK agent — Cloud Run entrypoint.
#
# Seed the demo state first so the Companion has real, SEALED hypotheses to
# talk about (get_compass_state reads this DB), then serve the ADK Web UI.
# Sessions and artifacts stay in memory: Cloud Run's disk is ephemeral and the
# agents dir is read-only, and the sealed state lives in the SQLite DB anyway.
set -euo pipefail

python -c "from compass.db import open_db; from compass import seed_demo; c = open_db('${COMPASS_DB}'); print('seed:', seed_demo.seed(c).get('seeded')); c.close()" \
  || echo "seed skipped (non-fatal)"

exec adk web \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --session_service_uri="memory://" \
  --artifact_service_uri="memory://" \
  /app/agents
