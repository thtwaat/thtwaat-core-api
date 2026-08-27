# THTWAAT Deploy — Next.js build sandbox

Mirrors `docker/vite-build/` exactly in spirit — see that README for the
shared threat model (untrusted source, no Docker socket, no host filesystem,
no secrets, `--cap-drop=ALL`, non-root, hard resource caps, dedicated
network). This image differs only in what it produces:

- Runs `npm ci|install` then the project's own `npm run build` (expected to
  invoke `next build`), exactly like the Vite image.
- Requires `.next/standalone` and `.next/static` to exist after the build —
  if either is missing, the build fails with the fixed message
  `"Next.js standalone output is required for this deployment."` rather than
  silently falling back to a different output mode (see
  `app/static_sites/vite_detect.py` for the pre-build detection step, and
  `next.config.js` `output: "standalone"` requirement).
- Assembles the **runtime artifact** by hand: `.next/standalone/*` +
  `.next/static` (copied under `.next/`) + `public/` (if present) — Next.js
  intentionally omits both of the latter from `.next/standalone`, per its own
  docs, so this build.sh copies them in.
- Never includes `node_modules` from the *source* tree, `.git`, `.env*`, or
  `src/` — the artifact only ever contains what `.next/standalone` actually
  ships (its own pruned, traced `node_modules`) plus the two additions above.

Built with `docker build -t thtwaat-nextjs-build:20 docker/next-build`.

Consumed by `app/static_sites/nextjs_build.py` (direct/dev mode) and
`orchestrator/orchestrator_app/nextjs_build.py` (production/orchestrator
mode) — see those modules' docstrings for the exact `docker run` invocation
and resource limits (`NEXTJS_MAX_BUILD_*` in `app/config/settings.py`).
