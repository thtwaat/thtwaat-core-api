#!/bin/sh
# THTWAAT Deploy — controlled Vite build entrypoint.
#
# Runs ONLY inside the isolated, non-root, network-restricted, resource-
# capped build container (see app/static_sites/vite_build.py). Never
# accepts an arbitrary command: INSTALL_CMD is restricted to exactly "ci" or
# "install", and the build command is hardcoded to `npm run build` — the
# only thing left to the uploaded project is what its own package.json
# "build" script does, which is precisely the isolation boundary this
# container exists to contain.
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

if [ ! -d dist ]; then
  echo "dist/ was not produced by the build" >&2
  exit 1
fi

cp -r dist/. "$OUTPUT_DIR"/
echo "Build complete."
