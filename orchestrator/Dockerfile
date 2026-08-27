# THTWAAT Deploy — build orchestrator. The only container in the stack that
# is allowed to reach the Docker API (via docker-socket-proxy — see
# docker-compose.prod.yml and orchestrator/README.md). Deliberately minimal:
# no database driver, no application code from the main image, nothing
# beyond FastAPI + the `docker` CLI binary itself.
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# docker-ce-cli only — the CLI binary this service shells out to, never the
# daemon (containerd/dockerd stay on the host, or in docker-socket-proxy's
# scope). See deploy/bootstrap/04-docker.sh for the same upstream repo used
# for the real host install.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd -r orchestrator && useradd -r -g orchestrator orchestrator

COPY orchestrator_app ./orchestrator_app

# Actual host-daemon access is granted (or not) at compose level via
# DOCKER_HOST / docker-socket-proxy — this user needs no docker group
# membership when talking to the socket-proxy over TCP (the recommended,
# default path; see docker-compose.prod.yml). Only the direct-socket
# fallback documented in orchestrator/README.md requires additional compose-
# level group_add wiring, which this Dockerfile does not assume.
USER orchestrator

EXPOSE 8080
CMD ["uvicorn", "orchestrator_app.main:app", "--host", "0.0.0.0", "--port", "8080"]
