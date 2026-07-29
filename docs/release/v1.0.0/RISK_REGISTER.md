# Risk Register — v1.0.0

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|----|------|------------|--------|------------|-------|
| R1 | Public CORS misconfiguration | Med | High | Env lint / deploy checklist blocks `*` | Platform eng |
| R2 | Secrets leak via logs/env | Low | High | Vault; no secrets in git; rotate JWT | Security |
| R3 | Redis outage → limiter/jobs fail | Med | High | Redis HA; health alerts; degrade gracefully | SRE |
| R4 | Migration failure on upgrade | Low | High | Backup before deploy; `alembic upgrade` in CI against staging | Backend |
| R5 | SSL issuance failure | Med | Med | Keep simulate for staging; certbot + monitoring alerts | SRE |
| R6 | Billing webhook spoofing | Low | High | Verify Stripe/Razorpay signatures | Payments |
| R7 | Quota bypass under race | Med | Med | Keep UsageService checks; add unique constraints where missing | Backend |
| R8 | Copilot destructive action without confirm | Low | High | Confirmation gate in CopilotService | Backend |
| R9 | Backup restore untested | Med | High | Quarterly restore drill | SRE |
| R10 | Notification stubs → missed alerts | High | Med | Wire email/push or page via external Alertmanager | Ops |
