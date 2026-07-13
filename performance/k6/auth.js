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
    name: `k6 Auth ${uid}`,
    slug: `k6-auth-${uid}`,
    domain: `k6auth${uid}.com`
  }), { headers: { 'Content-Type': 'application/json' } });
  
  const companyId = companyRes.json('id');
  
  const email = `k6auth${uid}@test.com`;
  const password = "securepassword";
  
  http.post(`${BASE_URL}/api/v1/users/`, JSON.stringify({
    email: email,
    password: password,
    company_id: companyId,
    first_name: "k6",
    last_name: "Auth",
    role: "admin"
  }), { headers: { 'Content-Type': 'application/json' } });
  
  return { email: email, password: password };
}

export default function (data) {
  const loginRes = http.post(`${BASE_URL}/api/v1/auth/login`, JSON.stringify({
    email: data.email,
    password: data.password
  }), { headers: { 'Content-Type': 'application/json' } });
  
  check(loginRes, {
    'login status is 200': (r) => r.status === 200,
    'has access token': (r) => r.json('access_token') !== undefined,
  });
  
  sleep(1);
}
