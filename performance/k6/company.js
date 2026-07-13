import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 10,
  duration: '10s',
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  const uid = Math.random().toString(36).substring(7);
  
  // Create
  const createRes = http.post(`${BASE_URL}/api/v1/companies/`, JSON.stringify({
    name: `k6 Company ${uid}`,
    slug: `k6-company-${uid}`,
    domain: `k6-${uid}.com`
  }), { headers: { 'Content-Type': 'application/json' } });
  
  check(createRes, { 'create status is 201': (r) => r.status === 201 });
  
  if (createRes.status === 201) {
    const companyId = createRes.json('id');
    
    // Get
    const getRes = http.get(`${BASE_URL}/api/v1/companies/${companyId}`);
    check(getRes, { 'get status is 200': (r) => r.status === 200 });
  }
  
  sleep(1);
}
