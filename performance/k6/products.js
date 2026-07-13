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

export function setup() {
  const uid = Math.random().toString(36).substring(7);
  
  const companyRes = http.post(`${BASE_URL}/api/v1/companies/`, JSON.stringify({
    name: `k6 Prod ${uid}`,
    slug: `k6-prod-${uid}`,
    domain: `k6prod${uid}.com`
  }), { headers: { 'Content-Type': 'application/json' } });
  const companyId = companyRes.json('id');
  
  const email = `k6prod${uid}@test.com`;
  const password = "securepassword";
  
  http.post(`${BASE_URL}/api/v1/users/`, JSON.stringify({
    email: email,
    password: password,
    company_id: companyId,
    first_name: "k6",
    last_name: "Prod",
    role: "admin"
  }), { headers: { 'Content-Type': 'application/json' } });
  
  const loginRes = http.post(`${BASE_URL}/api/v1/auth/login`, JSON.stringify({
    email: email,
    password: password
  }), { headers: { 'Content-Type': 'application/json' } });
  
  return { token: loginRes.json('access_token') };
}

export default function (data) {
  const uid = Math.random().toString(36).substring(7);
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${data.token}`
  };
  
  const createRes = http.post(`${BASE_URL}/api/v1/products/`, JSON.stringify({
    name: `k6 Product ${uid}`,
    category: "Website",
    description: "k6 Load Test",
    ai_enabled: false
  }), { headers: headers });
  
  check(createRes, { 'create status is 201': (r) => r.status === 201 });
  
  if (createRes.status === 201) {
    const prodId = createRes.json('id');
    
    const getRes = http.get(`${BASE_URL}/api/v1/products/${prodId}`, { headers: headers });
    check(getRes, { 'get status is 200': (r) => r.status === 200 });
    
    const listRes = http.get(`${BASE_URL}/api/v1/products/`, { headers: headers });
    check(listRes, { 'list status is 200': (r) => r.status === 200 });
    
    const deleteRes = http.del(`${BASE_URL}/api/v1/products/${prodId}`, null, { headers: headers });
    check(deleteRes, { 'delete status is 200': (r) => r.status === 200 });
  }
  
  sleep(1);
}
