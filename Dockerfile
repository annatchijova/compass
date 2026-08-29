# COMPASS API for Google Cloud Run.
# The forensic/deterministic core is stdlib-only; this image adds the
# FastAPI layer and the Gemini/ADK agent on top of it.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    COMPASS_DB=/tmp/compass.db \
    COMPASS_BACKEND=demo

WORKDIR /app

# Dependencies first, for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code, then install the package itself (src layout) without
# re-resolving deps — requirements.txt already pinned them.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

# Default backend is 'demo' (role-aware, no credential) so the hosted URL
# shows the full cycle offline. Set COMPASS_BACKEND=gemini + Vertex env
# vars at deploy time for the mandatory Gemini model. Cloud Run routes to $PORT.
CMD exec uvicorn compass.api:app --host 0.0.0.0 --port ${PORT}
