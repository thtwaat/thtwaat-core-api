#!/usr/bin/env bash
# Compatibility wrapper → root bootstrap.sh / modular bootstrap.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
exec bash "${ROOT}/bootstrap.sh" "$@"
