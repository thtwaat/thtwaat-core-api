# THTWAAT Deploy — Next.js standalone runtime image

One long-lived container per LIVE Next.js deployment version, started from
this generic image with the immutable per-deployment artifact directory
(produced by `docker/next-build/`) bind-mounted read-only at `/app`.

Security posture (THTWAAT Phase 3, Phases 5/6/14/15):

- `--cap-drop=ALL --security-opt no-new-privileges --user 1000:1000`
- `--read-only` root filesystem, with a small `tmpfs /tmp` scratch mount
- `--memory` / `--cpus` / `--pids-limit` hard caps
  (`NEXTJS_RUNTIME_MEMORY_MB` / `NEXTJS_RUNTIME_CPU` / `NEXTJS_RUNTIME_PIDS`)
- No Docker socket, no SSH keys, no database credentials, no host filesystem
  access beyond the one read-only artifact bind mount
- Attached ONLY to `thtwaat_nextjs_runtime_net` — never `thtwaat_net`
  (Postgres/Redis/API), never the build or socket-proxy networks
- No published host port — nginx reaches the container by its fixed name
  (`thtwaat-nextjs-runtime-<deployment_id.hex>`) over Docker's embedded DNS
  on `thtwaat_nextjs_runtime_net` (see `app/ssl/nginx_gen.py`
  `RUNTIME_PROXY_LOCATION_BLOCK`) — there is no host-port allocator to run,
  and therefore no host-port collision to prevent
- Always starts `node server.js` — no arbitrary user-defined startup command

Built with `docker build -t thtwaat-nextjs-runtime:20 docker/next-runtime`.

Started/stopped by `app/static_sites/nextjs_runtime.py` (direct/dev mode) and
`orchestrator/orchestrator_app/nextjs_runtime.py` (production/orchestrator
mode) — see those modules for the exact `docker run` invocation and the
post-start health-check loop.

Known limitation: the root filesystem is read-only and the artifact mount is
read-only, so Next.js features that write to disk at runtime (on-disk ISR
cache beyond what fits in the in-memory LRU, `revalidate`-triggered file
writes) are not supported in this phase — see the Phase 3 final report,
"Known limitations".
