/**
 * Week 4 Day 3 — OpenAI-compatible gateway load (JSON + SSE).
 *
 * Usage:
 *   export BASE_URL=http://127.0.0.1:8000
 *   export API_KEY=tht_live_...
 *   k6 run performance/k6/openai_compat.js
 *
 * Optional:
 *   k6 run -e VUS=20 -e DURATION=30s performance/k6/openai_compat.js
 */
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const failRate = new Rate('openai_compat_failures');

export const options = {
  vus: Number(__ENV.VUS || 10),
  duration: __ENV.DURATION || '20s',
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    openai_compat_failures: ['rate<0.05'],
  },
};

const BASE_URL = (__ENV.BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const API_KEY = __ENV.API_KEY || '';

function headers(extra) {
  return Object.assign(
    {
      Authorization: `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    extra || {}
  );
}

export function setup() {
  if (!API_KEY) {
    throw new Error('Set API_KEY to a valid tht_live_* / tht_key_* bearer token');
  }
  const live = http.get(`${BASE_URL}/live`);
  check(live, { 'live 200': (r) => r.status === 200 });
  return { ts: Date.now() };
}

export default function (data) {
  const uid = `${data.ts}-${__VU}-${__ITER}`;

  // JSON completion
  const jsonRes = http.post(
    `${BASE_URL}/v1/chat/completions`,
    JSON.stringify({
      model: 'thtwaat-stub-mini',
      messages: [{ role: 'user', content: `k6-json-${uid}` }],
      temperature: 0,
      stream: false,
    }),
    {
      headers: headers({ 'Idempotency-Key': `k6-json-${uid}` }),
      tags: { name: 'chat_completions_json' },
    }
  );
  const jsonOk =
    check(jsonRes, {
      'json status 200': (r) => r.status === 200,
      'json has id': (r) => {
        try {
          return !!(r.json('id'));
        } catch (e) {
          return false;
        }
      },
    }) || false;
  failRate.add(!jsonOk);

  // SSE stream (buffer full body — stub is short)
  const sseRes = http.post(
    `${BASE_URL}/v1/chat/completions`,
    JSON.stringify({
      model: 'thtwaat-stub-mini',
      messages: [{ role: 'user', content: `k6-sse-${uid}` }],
      stream: true,
    }),
    {
      headers: headers({ 'Idempotency-Key': `k6-sse-${uid}` }),
      tags: { name: 'chat_completions_sse' },
    }
  );
  const body = sseRes.body || '';
  const sseOk =
    check(sseRes, {
      'sse status 200': (r) => r.status === 200,
      'sse has chunk': () => body.indexOf('chat.completion.chunk') !== -1,
      'sse has DONE': () => body.indexOf('[DONE]') !== -1,
    }) || false;
  failRate.add(!sseOk);

  // Models list
  const modelsRes = http.get(`${BASE_URL}/v1/models`, {
    headers: headers(),
    tags: { name: 'models_list' },
  });
  const modelsOk =
    check(modelsRes, {
      'models 200': (r) => r.status === 200,
    }) || false;
  failRate.add(!modelsOk);

  sleep(0.3);
}
