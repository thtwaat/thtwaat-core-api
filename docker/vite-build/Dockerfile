# THTWAAT Deploy — isolated Vite build image.
#
# This image ever only runs UNTRUSTED, user-uploaded source (see
# app/static_sites/vite_build.py). It contains the absolute minimum needed
# to run `npm ci|install` + `npm run build`:
#   - Node.js (major version pinned below — bump deliberately, never :latest)
#   - npm (bundled with Node)
# No yarn/pnpm/bun, no ssh client, no docker CLI, no build-time secrets, no
# extra services. The container this image runs as is additionally started
# with --cap-drop=ALL --security-opt=no-new-privileges --user 1000:1000 and
# no Docker socket / host filesystem mount — see run_vite_build().
FROM node:20-alpine

# node:20-alpine already ships a non-root `node` user at uid:gid 1000:1000
# (see /etc/passwd in the base image) — reuse it rather than creating a
# second uid:gid 1000 account, which fails to build (`addgroup: gid '1000'
# in use`). This still matches the --user 1000:1000 flag run_vite_build()
# always passes at `docker run` time.
WORKDIR /workspace
COPY build.sh /usr/local/bin/build.sh
RUN chmod +x /usr/local/bin/build.sh \
    && mkdir -p /workspace/build /workspace/output \
    && chown -R node:node /workspace

USER node
ENTRYPOINT ["/usr/local/bin/build.sh"]
