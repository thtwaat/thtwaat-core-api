#!/usr/bin/env bash
# Week 4 smoke — gateway ship gate (Sem02 W4).
# Reuses W3 async-edge smoke, then prints W4 ops reminders.
#
#   export API_BASE=http://127.0.0.1:8000
#   export API_KEY=tht_live_...
#   bash scripts/smoke_w4_openai_compat.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=smoke_w3_openai_compat.sh
bash "${ROOT}/scripts/smoke_w3_openai_compat.sh"

echo
echo "== W4 reminders (manual / ops) =="
echo "- alembic current should include g1a2b3c4d5e6 (webhook_deliveries)"
echo "- worker logs: no SQLAlchemy Mapper / Company / User errors"
echo "- SSRF: creating webhook https://127.0.0.1/ must 400"
echo "- optional: k6 run performance/k6/openai_compat.js"
echo "OK smoke_w4_openai_compat"
