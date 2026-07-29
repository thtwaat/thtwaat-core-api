# cURL equivalents

## Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","password":"secret"}'
```

## Publish agent
```bash
curl -X POST http://localhost:8000/api/v1/agents/$AGENT_ID/publish \
  -H "Authorization: Bearer $JWT"
```

## Public chat
```bash
curl -X POST http://localhost:8000/public/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"api_key":"tht_live_xxx","message":"Hello"}'
```

## Knowledge upload
```bash
curl -X POST http://localhost:8000/v2/knowledge/upload \
  -H "Authorization: Bearer $JWT" \
  -F "file=@faq.pdf" \
  -F "kb_id=$KB_ID"
```
