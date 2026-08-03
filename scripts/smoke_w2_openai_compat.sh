#!/usr/bin/env bash
# Week 2 smoke — OpenAI-compatible /v1 surface (Sem02 W2 gate).
# Usage:
#   export API_BASE=http://127.0.0.1:8000
#   export API_KEY=tht_live_...   # or tht_key_...
#   bash scripts/smoke_w2_openai_compat.sh
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
API_KEY="${API_KEY:?Set API_KEY to a valid tht_live_* or tht_key_*}"

hdr=(-H "Authorization: Bearer ${API_KEY}" -H "Content-Type: application/json")
idem="smoke-w2-$(date +%s)"

echo "== liveness =="
curl -fsS "${API_BASE}/live" | head -c 200
echo

echo "== models (401 without key) =="
code=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/v1/models")
test "$code" = "401"

echo "== models list =="
curl -fsS "${hdr[@]}" "${API_BASE}/v1/models?limit=5&offset=0" | head -c 400
echo

echo "== chat completions =="
curl -fsS "${hdr[@]}" \
  -H "Idempotency-Key: ${idem}" \
  -d '{"model":"thtwaat-stub-mini","messages":[{"role":"user","content":"ping"}],"temperature":0,"stream":false}' \
  "${API_BASE}/v1/chat/completions" | head -c 500
echo

echo "== idempotent replay =="
curl -fsS -D - "${hdr[@]}" \
  -H "Idempotency-Key: ${idem}" \
  -d '{"model":"thtwaat-stub-mini","messages":[{"role":"user","content":"ping"}],"temperature":0,"stream":false}' \
  "${API_BASE}/v1/chat/completions" 2>/dev/null | tr -d '\r' | grep -i "Idempotent-Replayed" || true

echo "== usage =="
curl -fsS "${hdr[@]}" "${API_BASE}/v1/usage" | head -c 400
echo

echo "OK smoke_w2_openai_compat"
