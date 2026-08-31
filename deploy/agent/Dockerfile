# COMPASS multi-agent team (Google ADK) for Cloud Run.
#
# Build context is the REPO ROOT (the agent uses relative imports into the
# stdlib-only deterministic core, so the whole `compass` package must be
# installed, not just the agent folder). Mirrors the proven backend image:
# same requirements pins, same Vertex config (LOCATION=global for the
# gemini-2.5-flash family), COMPASS_BACKEND=gemini for the extractor role.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    COMPASS_DB=/tmp/compass.db \
    COMPASS_BACKEND=gemini \
    COMPASS_MODEL=gemini-2.5-flash \
    GOOGLE_GENAI_USE_VERTEXAI=TRUE \
    GOOGLE_CLOUD_PROJECT=vigia-497422 \
    GOOGLE_CLOUD_LOCATION=global

WORKDIR /app

# Deps first (google-adk, google-genai, ...), for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The compass package (src layout), installed so `compass.agent` and its
# relative imports resolve. Deps already pinned above.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

# ADK agents directory + entrypoint.
COPY deploy/agent/agents ./agents
COPY deploy/agent/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

CMD ["./entrypoint.sh"]
