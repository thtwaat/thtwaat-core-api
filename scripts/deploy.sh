#!/usr/bin/env bash
# Compatibility wrapper — production entrypoint is deploy/deploy.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "${ROOT}/deploy/deploy.sh" "$@"
