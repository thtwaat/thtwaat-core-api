#!/usr/bin/env bash
# Root one-command deploy entrypoint.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "${ROOT}/deploy/deploy.sh" "$@"
