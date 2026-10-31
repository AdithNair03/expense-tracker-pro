# Spendwise - production container image.
#
# Built from python:3.12-slim (small, official, well-maintained). Runs the app with
# Gunicorn instead of Flask's dev server - Gunicorn is a production-grade WSGI server
# that handles multiple worker processes and concurrent requests properly.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_APP=wsgi.py \
    FLASK_CONFIG=production

WORKDIR /app

# curl is only here so the HEALTHCHECK below can call the app's own health endpoint.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first, separately from app code, so Docker can cache this layer
# and skip reinstalling everything just because a template or route changed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user - a container should never run its app as root.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Docker/Kubernetes can use this to know when the app is actually ready to serve traffic,
# not just "the process started".
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# 3 workers is a reasonable default for a small app; Kubernetes will run multiple pods
# for real scaling rather than relying on worker count alone.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "wsgi:app"]
