#!/usr/bin/env bash
# Run unit → integration → e2e (optional via RUN_E2E=1).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

./scripts/test-unit.sh "$@"
./scripts/test-integration.sh "$@"

if [[ "${RUN_E2E:-0}" == "1" ]]; then
  ./scripts/test-e2e.sh "$@"
else
  echo "==> Skipping e2e (set RUN_E2E=1 to enable)."
fi

echo "==> All requested suites finished. Reports in ./reports/"
