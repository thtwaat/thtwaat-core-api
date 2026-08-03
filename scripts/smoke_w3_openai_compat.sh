#!/usr/bin/env bash
# Week 3 smoke — async edge (stream + idempotency + usage) Sem02 W3.
# Usage:
#   export API_BASE=http://127.0.0.1:8000
#   export API_KEY=tht_live_...   # or tht_key_...
#   bash scripts/smoke_w3_openai_compat.sh
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
API_KEY="${API_KEY:?Set API_KEY to a valid tht_live_* or tht_key_*}"

hdr=(-H "Authorization: Bearer ${API_KEY}" -H "Content-Type: application/json")
ts="$(date +%s)"
idem_json="smoke-w3-json-${ts}"
idem_sse="smoke-w3-sse-${ts}"

echo "== liveness =="
curl -fsS "${API_BASE}/live" | head -c 200
echo

echo "== JSON completion + idempotency =="
curl -fsS "${hdr[@]}" \
  -H "Idempotency-Key: ${idem_json}" \
  -d '{"model":"thtwaat-stub-mini","messages":[{"role":"user","content":"w3-json"}],"temperature":0,"stream":false}' \
  "${API_BASE}/v1/chat/completions" | head -c 400
echo

echo "== JSON replay header =="
curl -fsS -D - "${hdr[@]}" \
  -H "Idempotency-Key: ${idem_json}" \
  -d '{"model":"thtwaat-stub-mini","messages":[{"role":"user","content":"w3-json"}],"temperature":0,"stream":false}' \
  "${API_BASE}/v1/chat/completions" 2>/dev/null | tr -d '\r' | grep -i "Idempotent-Replayed" || true

echo "== SSE stream =="
# -N disables buffering; stop after [DONE] appears
curl -fsS -N "${hdr[@]}" \
  -H "Idempotency-Key: ${idem_sse}" \
  -d '{"model":"thtwaat-stub-mini","messages":[{"role":"user","content":"w3-stream"}],"stream":true}' \
  "${API_BASE}/v1/chat/completions" | tr -d '\r' | tee /tmp/tht_w3_sse.txt | head -c 800
echo
grep -q "chat.completion.chunk" /tmp/tht_w3_sse.txt
grep -q "\[DONE\]" /tmp/tht_w3_sse.txt

echo "== SSE replay (Idempotent-Replayed) =="
curl -fsS -N -D /tmp/tht_w3_sse_hdrs.txt "${hdr[@]}" \
  -H "Idempotency-Key: ${idem_sse}" \
  -d '{"model":"thtwaat-stub-mini","messages":[{"role":"user","content":"w3-stream"}],"stream":true}' \
  "${API_BASE}/v1/chat/completions" >/tmp/tht_w3_sse_replay.txt
tr -d '\r' </tmp/tht_w3_sse_hdrs.txt | grep -i "Idempotent-Replayed: true"
grep -q "\[DONE\]" /tmp/tht_w3_sse_replay.txt

echo "== usage =="
curl -fsS "${hdr[@]}" "${API_BASE}/v1/usage" | head -c 400
echo

echo "OK smoke_w3_openai_compat"
