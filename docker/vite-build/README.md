# THTWAAT Deploy — Vite build sandbox image

Builds untrusted, user-uploaded Vite projects. This image is launched by
`app/static_sites/vite_build.py::run_vite_build()` via a single `docker run`
invocation per deployment — it is never started as a long-lived service and
never appears in `docker-compose.prod.yml` as a service (only its network is
declared there, for documentation/creation purposes).

## What's in the image

- `node:20-alpine` (Node major version pinned deliberately — bump this file
  when THTWAAT decides to support a newer Node major, never track `:latest`)
- The base image's built-in non-root `node` user (uid:gid `1000:1000`,
  matching the `--user 1000:1000` flag `run_vite_build()` always passes)
- `build.sh`, the only entrypoint — installs dependencies (`npm ci` or
  `npm install`, decided by the caller from lockfile presence) and runs
  `npm run build`, nothing else. It never accepts an arbitrary command.

Nothing else is installed: no yarn/pnpm/bun, no ssh client, no docker CLI,
no build-time secrets baked into the image.

## Building the image

```bash
cd docker/vite-build
docker build -t thtwaat-vite-build:20 .
```

The tag must match `settings.VITE_BUILD_IMAGE` (`app/config/settings.py`).
Rebuild and re-tag whenever `build.sh` or the base Node version changes.

## One-time host setup (manual — not automated by this repo)

```bash
# Isolated network for build containers only — deliberately NOT thtwaat_net,
# so a build container can never resolve or route to Postgres/Redis/the
# internal API/nginx by container DNS name or private network address.
docker network create thtwaat_vite_build_net
```

`VITE_BUILD_ENABLED` defaults to `false`. An operator must explicitly:
1. Build and tag this image (above).
2. Create `thtwaat_vite_build_net` (above).
3. Decide which process may run `run_vite_build()` — it needs the `docker`
   CLI and access to `/var/run/docker.sock`, which is a real privilege
   decision this repo does not make for you (see the Vite build feature's
   production report for the trade-offs between granting it to the existing
   `worker`/`api` container vs. a dedicated orchestrator process).
4. Set `VITE_BUILD_ENABLED=true` once 1–3 are done.

## Isolation summary (enforced by `run_vite_build()`, not by this image alone)

| Property | Mechanism |
|---|---|
| No Docker socket / host filesystem | Only `/workspace/source` (ro) and `/workspace/output` (rw) are bind-mounted; nothing else |
| No secrets | Fixed `-e` allowlist only (`INSTALL_CMD`, `NODE_ENV`, `CI`, npm flags) — no DB/JWT/SSL/webhook values ever passed |
| Non-root | `--user 1000:1000`, no privilege escalation (`--security-opt=no-new-privileges`) |
| No capabilities | `--cap-drop=ALL` |
| Resource limits | `--memory`, `--memory-swap` (swap disabled), `--cpus`, `--pids-limit` |
| Time limit | Python-side `subprocess.run(..., timeout=...)`; the container is `docker kill`ed + `docker rm -f`d on timeout |
| Network segmentation | Attached only to `thtwaat_vite_build_net`, never `thtwaat_net` |
| Ephemeral | `--rm` — nothing persists after the build exits |

**Known limitation:** outbound internet access from the build container to
the public npm registry (and, absent a registry-only egress proxy, to any
other public host) remains open in this phase — see the Vite build
feature's production report for why a full domain-allowlisting proxy was
out of scope here, and what network segmentation is already in place
instead.
