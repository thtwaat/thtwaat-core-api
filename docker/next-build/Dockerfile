# THTWAAT Deploy — isolated Next.js build image.
#
# This image ever only runs UNTRUSTED, user-uploaded source (see
# app/static_sites/nextjs_build.py). It contains the absolute minimum needed
# to run `npm ci|install` + `npm run build` and assemble the standalone
# runtime artifact:
#   - Node.js (major version pinned below — bump deliberately, never :latest)
#   - npm (bundled with Node)
# No yarn/pnpm/bun, no ssh client, no docker CLI, no build-time secrets, no
# extra services. The container this image runs as is additionally started
# with --cap-drop=ALL --security-opt=no-new-privileges --user 1000:1000 and
# no Docker socket / host filesystem mount — see run_nextjs_build().
#
# Deliberately the SAME Node major version as docker/vite-build/Dockerfile
# (node:20-alpine) — nothing here needs a different Node line, and keeping
# them identical means one fewer image to reason about when bumping majors.
FROM node:20-alpine

# node:20-alpine already ships a non-root `node` user at uid:gid 1000:1000
# (see /etc/passwd in the base image) — reuse it rather than creating a
# second uid:gid 1000 account, which fails to build (`addgroup: gid '1000'
# in use`). This still matches the --user 1000:1000 flag run_nextjs_build()
# always passes at `docker run` time.
WORKDIR /workspace
COPY build.sh /usr/local/bin/build.sh
RUN chmod +x /usr/local/bin/build.sh \
    && mkdir -p /workspace/build /workspace/output \
    && chown -R node:node /workspace

USER node
ENTRYPOINT ["/usr/local/bin/build.sh"]
