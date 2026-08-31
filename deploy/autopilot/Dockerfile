# COMPASS Autopilot — Cloud Run JOB (not a service): background, async, batch.
#
# The same deterministic core + the same no-authority LLM roles as the ADK
# team, run UNATTENDED: it sweeps every user's sealed compass, watches the
# seal (Sentinel) and assembles the next-step briefing BESIDE the base. It
# never validates, links, closes or seals anything.
#
# Build context is the REPO ROOT (relative imports into the stdlib-only core).
# Mirrors the proven backend/agent images: same pins, same Vertex config
# (LOCATION=global for the gemini-3.5-flash family), COMPASS_BACKEND=gemini.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COMPASS_BACKEND=gemini \
    COMPASS_MODEL=gemini-3.5-flash \
    COMPASS_LANGUAGE=English \
    COMPASS_DATA_DIR=/tmp/compass-data \
    GOOGLE_GENAI_USE_VERTEXAI=TRUE \
    GOOGLE_CLOUD_PROJECT=vigia-497422 \
    GOOGLE_CLOUD_LOCATION=global

WORKDIR /app

# Deps first (google-genai, google-cloud-storage, ...), for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The compass package (src layout), installed so relative imports resolve.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

COPY deploy/autopilot/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# A Job runs to completion and exits (no PORT, no server). Cloud Scheduler
# triggers it on a cron; the sweep restores each base from GCS, runs once,
# and snapshots it back.
CMD ["./entrypoint.sh"]
