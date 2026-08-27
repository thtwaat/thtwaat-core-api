# THTWAAT Deploy — Next.js standalone runtime image.
#
# Generic, reusable across every Next.js deployment: it contains ONLY the
# Node.js runtime, nothing project-specific. The actual application code
# (server.js + .next/static + public/ + a pruned node_modules — see
# docker/next-build/build.sh) is bind-mounted READ-ONLY at /app when a
# container is started FROM this image (see app/static_sites/nextjs_runtime.py)
# — this Dockerfile never COPYs any tenant code and is never rebuilt per
# deployment, exactly like nginx reading static_root_path off a bind mount.
#
# The container started from this image is additionally run with
# --cap-drop=ALL --security-opt=no-new-privileges --user 1000:1000
# --read-only --pids-limit --memory --cpus and NO Docker socket, NO SSH
# keys, NO database credentials, NO host filesystem access beyond the one
# read-only artifact mount, and NO published host port (nginx reaches it by
# container name over the dedicated NEXTJS_RUNTIME_NETWORK only). See
# run_runtime()/start_runtime() for the full flag list.
FROM node:20-alpine

WORKDIR /app

# node:20-alpine's built-in non-root `node` user (uid:gid 1000:1000) — same
# convention as docker/vite-build and docker/next-build, so a build
# container's output (owned 1000:1000) is directly readable by this runtime
# container without any chmod/chown step.
USER node

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000

EXPOSE 3000

# No arbitrary user-defined startup command in MVP (THTWAAT Phase 3 Phase 5) —
# always the standalone server entrypoint Next.js itself produces.
CMD ["node", "server.js"]
