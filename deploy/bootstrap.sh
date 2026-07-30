#!/usr/bin/env bash
# Alias under deploy/ for documentation parity with Goal "bootstrap.sh".
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${HERE}/../bootstrap.sh" "$@"
