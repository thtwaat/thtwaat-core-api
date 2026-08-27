"""Build-orchestrator settings — deliberately tiny.

This process exists to do exactly one thing: launch the locked-down Vite
build container on behalf of api/worker, which no longer need Docker socket
access themselves (see app/static_sites/vite_build.py and
docker-compose.prod.yml). It must never gain database credentials, JWT
secrets, SSL private keys, or any THTWAAT application config — importing
app.config.settings here would pull all of that in by association, so this
settings module is intentionally standalone and only knows about the Docker
build it is allowed to run.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestratorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Shared-secret bearer auth on every request — defense in depth on top of
    # network isolation (this service has no public port and sits on its own
    # network, reachable only from api/worker; see docker-compose.prod.yml).
    ORCHESTRATOR_SHARED_SECRET: str

    # Empty (default) = talk to the local Docker socket directly (requires
    # this container to be granted /var/run/docker.sock — see docker-compose
    # comments). Set to e.g. tcp://docker-socket-proxy:2375 to instead talk
    # through a docker-socket-proxy sidecar that only allows the exact API
    # operations this service needs (create/start/wait/kill/remove) — see
    # orchestrator/README.md. Preferred whenever available.
    DOCKER_HOST: str = ""

    VITE_BUILD_IMAGE: str = "thtwaat-vite-build:20"
    VITE_BUILD_NETWORK: str = "thtwaat_vite_build_net"
    VITE_MAX_BUILD_TIME_SECONDS: int = 300
    VITE_MAX_BUILD_MEMORY_MB: int = 1536
    VITE_MAX_BUILD_CPU: float = 1.0
    VITE_BUILD_TMPFS_MB: int = 512
    VITE_MAX_NODE_MODULES_BYTES: int = 1024 * 1024 * 1024
    VITE_MAX_OUTPUT_BYTES: int = 100 * 1024 * 1024
    VITE_MAX_OUTPUT_FILE_COUNT: int = 20000
    VITE_MAX_LOG_BYTES: int = 200_000

    # THTWAAT Phase 3 — Next.js standalone build + isolated Node runtime.
    # Same shared secret / narrow-schema philosophy as the Vite fields above;
    # this is one control-plane process with two more endpoint families.
    NEXTJS_BUILD_IMAGE: str = "thtwaat-nextjs-build:20"
    NEXTJS_BUILD_NETWORK: str = "thtwaat_vite_build_net"
    NEXTJS_MAX_BUILD_TIME_SECONDS: int = 600
    NEXTJS_MAX_BUILD_MEMORY_MB: int = 2048
    NEXTJS_MAX_BUILD_CPU: float = 1.5
    NEXTJS_BUILD_TMPFS_MB: int = 512
    NEXTJS_MAX_NODE_MODULES_BYTES: int = 1536 * 1024 * 1024
    NEXTJS_MAX_OUTPUT_BYTES: int = 300 * 1024 * 1024
    NEXTJS_MAX_OUTPUT_FILE_COUNT: int = 40000
    NEXTJS_MAX_LOG_BYTES: int = 200_000

    NEXTJS_RUNTIME_IMAGE: str = "thtwaat-nextjs-runtime:20"
    NEXTJS_RUNTIME_NETWORK: str = "thtwaat_nextjs_runtime_net"
    NEXTJS_RUNTIME_PORT: int = 3000
    NEXTJS_RUNTIME_MEMORY_MB: int = 512
    NEXTJS_RUNTIME_CPU: float = 0.5
    NEXTJS_RUNTIME_PIDS: int = 128
    NEXTJS_RUNTIME_TMPFS_MB: int = 64
    NEXTJS_HEALTH_STARTUP_TIMEOUT_SECONDS: int = 60
    NEXTJS_HEALTH_RETRY_COUNT: int = 10
    NEXTJS_HEALTH_RETRY_INTERVAL_SECONDS: float = 2.0
    NEXTJS_HEALTH_REQUEST_TIMEOUT_SECONDS: float = 3.0

    # Optional forward proxy that allowlists only the npm registry (see
    # docker/vite-build/egress-proxy/) — empty means the build container
    # gets ordinary, unrestricted-by-this-service outbound access (still
    # confined to thtwaat_vite_build_net, which cannot reach internal
    # services; see docker-compose.prod.yml network comments). Setting this
    # does not by itself force traffic through the proxy — see
    # docker/vite-build/egress-proxy/README.md for the required host
    # firewall rule that actually closes that gap.
    VITE_BUILD_EGRESS_PROXY_URL: str = ""

    # This container's own view of the shared staging tree (bind-mounted
    # identically to api/worker's STATIC_SITES_DIR — see
    # docker-compose.prod.yml) and the literal host filesystem path of that
    # SAME directory. The two differ because this process asks the HOST
    # Docker daemon (via socket or socket-proxy) to bind-mount paths for the
    # build container it launches — the daemon resolves -v arguments against
    # the host filesystem, not against this container's own view of it. This
    # mirrors the existing STATIC_SITES_CONTAINER_PREFIX remap in
    # app/ssl/nginx_gen.py, which solves the identical problem for nginx.
    STATIC_SITES_DIR: str = "/data/static-sites"
    STATIC_SITES_HOST_DIR: str


settings = OrchestratorSettings()
