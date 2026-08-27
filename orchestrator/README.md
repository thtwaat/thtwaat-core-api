# THTWAAT Deploy — build orchestrator

Answers the Docker-socket question raised in the Phase 2 staging validation
report (§1/§13): **api/worker never get `/var/run/docker.sock`.** This
service does, and does nothing else.

## What it is

A tiny, standalone FastAPI service with exactly one real endpoint:

```
POST /v1/vite-builds
Authorization: Bearer <ORCHESTRATOR_SHARED_SECRET>
{"workspace_id": "...", "site_id": "...", "deployment_id": "...", "install_cmd": "ci" | "install"}
```

It does not import anything from `app/` (the main THTWAAT package) — no
SQLAlchemy, no DB models, no JWT code, no billing/AI-gateway/anything. It
has no database credentials, no SSL private keys, no THTWAAT application
secrets, and no public port. Its entire attack surface is the request
schema above: three UUIDs and a two-value enum. Every filesystem path used
to launch the Vite build container is computed **server-side**, from those
UUIDs, against this service's own `STATIC_SITES_DIR` — a caller can never
supply a path, an image name, a docker flag, or a command (see
`orchestrator_app/build.py`'s module docstring for why that's the actual security
boundary here, not just the network isolation below).

## Why a separate service instead of api/worker calling Docker directly

Docker socket access is root-equivalent on the host. `api` already runs as
root inside its own container (see the main `Dockerfile` — no `USER`
directive) and serves all of THTWAAT's normal traffic (auth, billing, AI
Gateway, everything) — it is not a narrow, low-value target. Putting
docker.sock there means *any* unrelated bug in that large surface is a full
host compromise. This service is small, does one fixed thing, and never
touches application data — a much smaller thing to have to trust with root.

## Network topology (see docker-compose.prod.yml)

```
api/worker  ──(HTTP, shared-secret bearer)──►  build-orchestrator  ──(Docker API, allowlisted)──►  docker-socket-proxy  ──►  /var/run/docker.sock
   │                                                  │
   └── thtwaat_net, thtwaat_orchestrator_net          └── thtwaat_orchestrator_net, thtwaat_socket_proxy_net
```

`api`/`worker` are **not** on `thtwaat_socket_proxy_net` — they cannot reach
docker-socket-proxy even if compromised, only this service's narrow HTTP
API. That's the actual defense-in-depth property: compromising api gets you
"can ask for a Vite build of an already-staged deployment_id", not "can run
arbitrary Docker commands".

The Vite build container itself is launched onto `thtwaat_vite_build_net`
(a third, separate network) — this service is not a member of that network
either; it only asks the host daemon to attach the *build* container to it.

## Docker API access: two options

**Recommended (default in docker-compose.prod.yml): `docker-socket-proxy`.**
[tecnativa/docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy)
sits between this service and the real socket, exposing only the
`CONTAINERS`/`IMAGES`/`POST` operations needed for
create/start/wait/kill/remove — explicitly **not** `BUILD`, `EXEC`,
`NETWORKS`, `VOLUMES`, `SERVICES`, `SWARM`, or anything else. See the env
block on the `docker-socket-proxy` service in `docker-compose.prod.yml` for
the exact allowlist.

Live-tested (this local Docker Desktop, not a VPS — see the staging
validation report §10/§11 for what still needs verifying on a real host)
with exactly the env allowlist committed in `docker-compose.prod.yml`:

| Operation | Result |
|---|---|
| `docker version` (negotiation) | allowed |
| `docker run --rm hello-world` (create+start+wait+logs — what build-orchestrator actually does) | **allowed, ran end to end** |
| `docker exec` into a running container | **blocked** — clean `403`, "unable to upgrade to tcp" |
| `docker network create` | **blocked** — clean `403 Forbidden` |
| `docker build` from a Dockerfile piped over stdin | **blocked** — no image was ever created; the client hung rather than a fast 403 (verified via `docker images` showing nothing was built, then killed the hung client) — the practical effect is the same (build never happens), the failure mode just isn't as clean as EXEC/NETWORKS. If your ops tooling depends on a fast, clean rejection rather than a hang, treat this as worth a closer look before relying on it. |

**Fallback: direct socket mount.** If socket-proxy turns out to be
impractical, mount `/var/run/docker.sock` directly into `build-orchestrator`
instead of into `docker-socket-proxy`, and unset `DOCKER_HOST`. This is
strictly worse in defense-in-depth terms (this service then has the *entire*
Docker API, not an allowlisted subset) but is still a large improvement over
the alternative of granting it to api/worker. If you do this, the container
also needs group membership matching the host's `docker` group GID — add
`group_add: ["${DOCKER_GID}"]` to the `build-orchestrator` service, where
`DOCKER_GID` is `getent group docker | cut -d: -f3` on the host. Running the
socket-owning process as root defeats the purpose of the non-root `USER
orchestrator` in the Dockerfile, so prefer the GID approach over `USER root`.

## Host-path translation (Docker-out-of-Docker)

This service asks the *host* Docker daemon to launch a container — the
daemon resolves `-v` bind-mount sources against the **host** filesystem, not
against this container's own filesystem namespace. `STATIC_SITES_HOST_DIR`
(required, no default — see `orchestrator_app/settings.py`) tells it what the literal
host path of its own `./data/static-sites` mount is, exactly mirroring the
existing `STATIC_SITES_CONTAINER_PREFIX` remap `app/ssl/nginx_gen.py` uses
to solve the identical problem for nginx. Get this wrong and the build
container gets the wrong host directory bind-mounted — verify it on first
deploy against a real staging host, don't assume the default.

## Enabling this in production

Nothing above starts by default — both services are gated behind Compose's
`vite-build` profile:

```bash
docker network create --internal thtwaat_orchestrator_net
docker network create --internal thtwaat_socket_proxy_net
# ORCHESTRATOR_SHARED_SECRET and STATIC_SITES_HOST_DIR must be set in .env.prod first
docker compose -f docker-compose.prod.yml --profile vite-build up -d --build
```

Then, and only then, set `VITE_BUILD_ENABLED=true` and
`VITE_BUILD_ORCHESTRATOR_URL=http://build-orchestrator:8080` for api/worker
(already wired as the default in docker-compose.prod.yml once the shared
secret is set).
