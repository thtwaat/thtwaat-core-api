# Failed Tests

_No failed Playwright tests in the latest local run._

## Skipped (expected without live API / credentials)

Most of the 20 workflow tests skip when:

1. Local API is not running (`E2E_API_URL` unreachable), or
2. `E2E_EMAIL` / `E2E_PASSWORD` are unset (UI login), or
3. `E2E_SUPER_ADMIN_EMAIL` / `E2E_SUPER_ADMIN_PASSWORD` are unset (admin analytics).

Re-run against staging with credentials to convert skips into pass/fail signal.
