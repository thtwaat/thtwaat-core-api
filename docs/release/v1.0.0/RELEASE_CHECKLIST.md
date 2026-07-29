# v1.0.0 Release Checklist

## Pre-release

- [x] Feature freeze for v1.0.0 (no new product features in this packaging)
- [x] Alembic single head (`a7b8c9d0e1f2`)
- [x] CHANGELOG + Release Notes authored
- [x] Security review documented
- [x] E2E checklist authored
- [ ] Staging E2E checklist executed end-to-end (human/QA)
- [ ] Load/performance smoke on staging
- [ ] Backup + restore drill on staging
- [ ] Secrets provisioned in prod vault
- [ ] `CORS_ORIGINS` explicit
- [ ] `SSL_MODE=certbot` (or approved terminate-TLS at edge)
- [ ] `/metrics` scrape ACL
- [ ] Notification channel decision (stub vs live)

## Build & migrate

- [ ] Tag `v1.0.0` on git
- [ ] Build prod images
- [ ] `alembic upgrade head` on staging ✓ then prod
- [ ] Worker + scheduler healthy

## Go-live

- [ ] DNS cutover / TLS verified
- [ ] Smoke: login, agent publish, health
- [ ] Monitoring alerts evaluated
- [ ] On-call roster confirmed

## Post-release

- [ ] Watch error rate 24h
- [ ] Confirm backups written
- [ ] Publish known issues to status page if needed
