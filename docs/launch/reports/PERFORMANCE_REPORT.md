# Performance Report

Generated: 2026-08-05T13:50:00.000Z

## Production GET latencies

| Endpoint | Duration (ms) | Status |
|----------|--------------:|--------|
| GET /live | 1330 | 200 |
| GET /api/v1/status | 205 | 200 |
| GET /api/v1/payments/plans/?country=IN | 228 | 200 |
| GET /widget.js | 436 | 200 |
| GET app.thtwaat.com/login | 1245 | 200 |

## Targets

- API smoke steps: prefer **&lt; 15s** (met)
- Public status/plans: prefer **&lt; 1s** (met)
- Login page TTFB-ish: prefer **&lt; 2s** (met at 1245ms)
- `/live` at 1330ms is acceptable but watch cold-start / proxy overhead

## Notes

- Playwright UI steps should stay under **60s** once run against a live stack.
- Archive `apps/templates/saas/e2e-reports/PERFORMANCE_REPORT.md` after each staging run for trend history.
