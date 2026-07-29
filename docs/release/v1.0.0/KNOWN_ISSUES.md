# Known Issues — v1.0.0

| ID | Severity | Issue | Workaround |
|----|----------|-------|------------|
| K1 | High | CORS `*` + credentials unsafe if misconfigured | Set explicit `CORS_ORIGINS` in prod |
| K2 | Medium | Email/SMS/Push providers stubbed | Use in-app notifications; wire providers before customer email alerts |
| K3 | Medium | Grafana dashboards not shipped as JSON panels | Build panels against Prometheus datasource manually |
| K4 | Medium | Full pytest suite errors without Redis | Run Redis locally or use `not integration` + module unit tests |
| K5 | Medium | `SSL_MODE=simulate` default in compose | Set `certbot` for real TLS |
| K6 | Low | No OpenTelemetry tracing | Use Prometheus + structured logs |
| K7 | Low | Gemini provider migration TODO | Functional via current provider; plan google-genai migration |
| K8 | Low | DB restore is operational (pg_restore/psql), not a one-click API | Follow Operations Guide restore |
| K9 | Low | iOS starter builds require macOS/Xcode | CI on macOS runners |
| K10 | Info | README root still mentions older RBAC wording | Prefer `docs/release/v1.0.0` guides |

## Test run snapshot (packaging host)

Recorded 2026-07-30 during release packaging:

```
# Broad suite (needs Redis for TestClient lifespan)
pytest tests app/agent_platform/tests -m "not integration"
→ 75 passed, 14 failed, 145 errors (predominantly redis.exceptions.ConnectionError)

# Focused modules
pytest tests/copilot tests/enterprise tests/onboarding tests/monitoring \
  tests/branding tests/marketplace tests/domains tests/usage tests/deploy tests/agent_platform \
  -m "not integration"
→ 63 passed, 1 failed, 18 errors (Redis-backed TestClient cases)
```

Pure unit modules (copilot/enterprise/onboarding/monitoring NLU/service units) are green when Redis is not required.
