#!/bin/sh
# THTWAAT Deploy — controlled Next.js build entrypoint.
#
# Runs ONLY inside the isolated, non-root, network-restricted, resource-
# capped build container (see app/static_sites/nextjs_build.py). Never
# accepts an arbitrary command: INSTALL_CMD is restricted to exactly "ci" or
# "install", and the build command is hardcoded to `npm run build` — the
# only thing left to the uploaded project is what its own package.json
# "build" script does (expected to be `next build`), which is precisely the
# isolation boundary this container exists to contain.
#
# THTWAAT Phase 3 requires "next.config.*: output: 'standalone'" and
# explicitly forbids silently falling back to a different output mode — this
# script enforces that by hard-failing with the exact required message when
# .next/standalone is missing, rather than publishing whatever else exists.
set -eu

SOURCE_DIR="/workspace/source"
BUILD_DIR="/workspace/build"
OUTPUT_DIR="/workspace/output"

case "${INSTALL_CMD:-}" in
  ci|install) ;;
  *)
    echo "Refusing to run: unsupported INSTALL_CMD" >&2
    exit 1
    ;;
esac

mkdir -p "$BUILD_DIR"
cp -r "$SOURCE_DIR"/. "$BUILD_DIR"/
cd "$BUILD_DIR"

if [ ! -f package.json ]; then
  echo "package.json not found" >&2
  exit 1
fi

echo "Installing dependencies (npm $INSTALL_CMD)..."
if [ "$INSTALL_CMD" = "ci" ]; then
  npm ci --no-audit --no-fund
else
  npm install --no-audit --no-fund
fi

if [ -n "${MAX_NODE_MODULES_BYTES:-}" ] && [ -d node_modules ]; then
  SIZE=$(du -sb node_modules 2>/dev/null | cut -f1 || echo 0)
  if [ "$SIZE" -gt "$MAX_NODE_MODULES_BYTES" ]; then
    echo "node_modules exceeds the allowed size limit" >&2
    exit 1
  fi
fi

echo "Running build (npm run build)..."
npm run build

if [ ! -d .next/standalone ]; then
  echo "Next.js standalone output is required for this deployment." >&2
  exit 1
fi
if [ ! -d .next/static ]; then
  echo "Next.js standalone output is required for this deployment." >&2
  exit 1
fi

# Assemble the immutable runtime artifact. .next/standalone contains
# server.js + a pruned node_modules + a partial .next/ (server chunks only —
# Next.js deliberately excludes static assets and public/ from standalone
# output; both must be copied in by hand, per Next.js's own docs).
cp -r .next/standalone/. "$OUTPUT_DIR"/
mkdir -p "$OUTPUT_DIR/.next"
cp -r .next/static "$OUTPUT_DIR/.next/static"
if [ -d public ]; then
  cp -r public "$OUTPUT_DIR/public"
fi

if [ ! -f "$OUTPUT_DIR/server.js" ]; then
  echo "Next.js standalone output is required for this deployment. (server.js not found at project root — monorepo/custom outputFileTracingRoot layouts are not supported yet)" >&2
  exit 1
fi

echo "Build complete."
