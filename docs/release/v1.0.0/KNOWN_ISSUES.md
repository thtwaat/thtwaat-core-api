# Known Issues — v1.0.0

| ID | Severity | Issue | Workaround / Status |
|----|----------|-------|---------------------|
| K1 | High | CORS `*` unsafe if misconfigured in non-hardened env | Hardened envs refuse `*`; wildcard path now uses `allow_credentials=False`. Still set explicit origins in prod. |
| K2 | Medium | Email/SMS/Push providers may be stubbed | Wire SMTP/SendGrid before public signup OTP |
| K3 | Medium | Grafana dashboards not shipped as JSON panels | Build panels against Prometheus manually |
| K4 | Medium | Full pytest suite errors without Redis | Redis is a hard dependency for API boot |
| K5 | Medium | `SSL_MODE=simulate` default in examples | Set `certbot` or edge TLS for public hosts |
| K6 | Low | No OpenTelemetry tracing | Use Prometheus + structured logs |
| K7 | Low | Gemini provider migration TODO | Functional via current provider |
| K8 | Low | DB restore is operational (scripts), not a one-click API | Follow `docs/ops/RECOVERY_GUIDE.md` |
| K9 | Low | iOS starter builds require macOS/Xcode | CI on macOS runners |
| K10 | Info | Legacy `/api/v1/ai-platform/*` still mounted | Deprecated in OpenAPI; use `/v2/agents` |

## Fixed in Launch Freeze

| Was | Fix |
|-----|-----|
| Billing webhook failures marked processed + HTTP 200 (no retry) | Failures stay unprocessed + HTTP 500 |
| Agent create fail-open on quota errors | Fail closed with 503 |
| Orphan agent analytics router | Mounted + SQL aggregate optimized |
| AI gateway rate limit stub | Redis RPM limiter |
| Monitoring alerts never scheduled | Scheduler tick calls `evaluate_and_raise` |

## Launch readiness snapshot

See `docs/launch/reports/` — Conditional PASS (prod GET smoke green; full Playwright write-path pending staging credentials).
