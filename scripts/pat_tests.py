import httpx
import uuid
import sys
import time

API_URL = 'http://localhost:8000/api/v1'

# We reuse the user created in previous run if possible, but let's just make a new one
uid = uuid.uuid4().hex[:6]
email = f'pat_{uid}@test.com'
password = 'SecurePassword123!'

resp = httpx.post(f'{API_URL}/companies/', json={'name': f'PAT {uid}', 'slug': f'pat-{uid}', 'domain': f'pat{uid}.com'})
if resp.status_code != 201:
    print(f"Failed to create company: {resp.text}")
    sys.exit(1)
company_id = resp.json()['id']

resp = httpx.post(f'{API_URL}/users/', json={'email': email, 'password': password, 'company_id': company_id, 'first_name': 'PAT', 'last_name': 'Tester', 'role': 'admin'})
if resp.status_code != 201:
    print(f"Failed to create user: {resp.text}")
    sys.exit(1)

resp = httpx.post(f'{API_URL}/auth/login', json={'email': email, 'password': password})
if resp.status_code != 200:
    print(f"Failed to login: {resp.text}")
    sys.exit(1)
token = resp.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

print('\n=== 2. PAYMENTS ===')
# The payload schema for POST /payments/ is:
# amount, currency, payment_method (CREDIT_CARD), gateway (STRIPE)
payload = {
    "amount": 49.99,
    "currency": "USD",
    "payment_method": "CREDIT_CARD",
    "gateway": "STRIPE"
}
r = httpx.post(f'{API_URL}/payments/', json=payload, headers=headers)
print('Create Payment:', r.status_code, r.text)
if r.status_code == 201:
    payment_id = r.json()['id']
    
    # Update status to COMPLETED
    r_patch = httpx.patch(f'{API_URL}/payments/{payment_id}/status', json={"status": "COMPLETED"}, headers=headers)
    print('Update Status:', r_patch.status_code, r_patch.text)
    
    # Refund
    r_ref = httpx.post(f'{API_URL}/payments/{payment_id}/refund', headers=headers)
    print('Refund:', r_ref.status_code, r_ref.text)


print('\n=== 3. AI GATEWAY ===')
r = httpx.post(f'{API_URL}/ai/generate', json={'prompt': 'Say hello', 'model': 'gpt-4o-mini'}, headers=headers)
print('AI Generate:', r.status_code, r.text)


print('\n=== 4. MONITORING ===')
r = httpx.get('http://localhost:8000/metrics')
if r.status_code == 200:
    lines = r.text.split('\n')
    print(f'Prometheus Metrics endpoint is UP. Received {len(lines)} lines of metrics.')
    for line in lines[:5]:
        print(line)
else:
    print('Metrics failed:', r.status_code)
