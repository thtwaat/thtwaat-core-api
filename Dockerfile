FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# JSON-form CMD (hadolint DL3025); shell via sh -c keeps ${PORT} expansion
# Seed marketplace catalog after migrations. Seed must not block API boot if it fails.
CMD ["sh", "-c", "alembic upgrade head && (python -m scripts.seed_marketplace --no-refresh || echo 'marketplace seed failed (non-fatal)') && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
