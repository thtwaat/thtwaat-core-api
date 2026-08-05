# v1.0.0 Release Checklist (Launch Freeze)

## Pre-release

- [x] Feature freeze / launch freeze packaging
- [x] Critical bugs fixed (webhooks, quota fail-closed, CORS credentials)
- [x] Dead/orphan router mounted or deprecated
- [x] Security headers + rate limiting verified in code/tests
- [x] Release notes + final launch checklist authored
- [ ] Staging E2E checklist executed end-to-end (human/QA)
- [ ] Backup + restore drill on staging (evidence)
- [ ] Secrets provisioned in prod vault
- [ ] `CORS_ORIGINS` explicit on VPS
- [ ] `SSL_MODE=certbot` (or approved edge TLS)
- [ ] `/metrics` scrape ACL or `METRICS_TOKEN`
- [ ] Notification channel decision (stub vs live)

## Build & migrate

- [x] Tag `v1.0.0` on launch-freeze commit
- [ ] Build prod images
- [ ] `alembic upgrade head` on staging ✓ then prod
- [ ] Worker + scheduler healthy (alerts tick visible in logs)

## Go-live

- [ ] DNS / TLS verified
- [ ] Smoke: login, agent publish, `/live`, billing plans
- [ ] Monitoring alerts evaluated
- [ ] On-call roster confirmed

## Post-release

- [ ] Watch error rate 24h
- [ ] Confirm backups written
- [ ] Publish known issues to status page if needed
