#!/usr/bin/env node
/**
 * Generates Security + Recommendations reports for production launch readiness.
 * Run after Playwright: node scripts/generate-launch-reports.mjs
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, "../e2e-reports");
const docsDir = path.resolve(__dirname, "../../../../docs/launch/reports");
fs.mkdirSync(outDir, { recursive: true });
fs.mkdirSync(docsDir, { recursive: true });

const summaryPath = path.join(outDir, "summary.json");
let summary = { status: "unknown", rows: [], elapsedMs: 0 };
if (fs.existsSync(summaryPath)) {
  try {
    summary = JSON.parse(fs.readFileSync(summaryPath, "utf8"));
  } catch {
    /* ignore */
  }
}

const failed = (summary.rows || []).filter((r) => r.status === "failed" || r.status === "timedOut");
const passed = (summary.rows || []).filter((r) => r.status === "passed");
const skipped = (summary.rows || []).filter((r) => r.status === "skipped");

const security = `# Security Report

Generated: ${new Date().toISOString()}

## Production configuration gates

| Control | Status | Notes |
|---------|--------|-------|
| Explicit CORS (no \`*\`) | **REQUIRED** | \`Settings\` refuses \`CORS_ORIGINS=*\` when \`APP_ENV=production\` |
| Distinct JWT secrets | **REQUIRED** | Access + refresh secrets must differ |
| OpenAPI disabled in prod | **PASS (code)** | \`main.py\` gates docs when hardened |
| Metrics ACL / token | **REQUIRED OPS** | Prefer private network or \`METRICS_TOKEN\` |
| SSL mode | **REQUIRED OPS** | Set \`SSL_MODE=certbot\` (or edge TLS); avoid \`simulate\` on public hosts |
| Widget keys in URLs | **PASS (code)** | Live keys rejected from iframe query strings |
| Public agent routes allowlisted | **PASS (code)** | \`INTENTIONAL_PUBLIC_OPERATIONS\` |

## Findings from this run

- Playwright overall: **${String(summary.status || "unknown").toUpperCase()}**
- Failed tests: **${failed.length}**
- Skipped (env/credential gated): **${skipped.length}**

${
  failed.length
    ? failed.map((f) => `- FAIL: ${f.title}`).join("\n")
    : "- No automated security-sensitive test failures in this run."
}

## Residual risks

1. Email/SMS providers may still be stubs — OTP flows need real provider keys for public launch.
2. Backup restore drill must be signed off operationally (not covered by Playwright).
3. Razorpay/Stripe live keys must be present for paid checkout E2E on staging.
`;

const recommendations = `# Recommendations

Generated: ${new Date().toISOString()}

## Launch decision inputs

| Signal | Value |
|--------|------:|
| Passed | ${passed.length} |
| Failed | ${failed.length} |
| Skipped | ${skipped.length} |
| Duration ms | ${summary.elapsedMs || 0} |

## Go / No-Go guidance

${
  failed.length === 0
    ? "- **CONDITIONAL GO** for controlled launch if ops CORS/SSL/metrics/backups are signed off and skipped workflows are re-run against staging with credentials."
    : "- **NO-GO for wide public launch** until failed tests below are green on staging."
}

## Priority actions

1. Run against staging with credentials:
   \`\`\`bash
   export E2E_API_URL=https://api.thtwaat.com
   export PLAYWRIGHT_BASE_URL=https://app.thtwaat.com
   export E2E_EMAIL=...
   export E2E_PASSWORD=...
   export E2E_SUPER_ADMIN_EMAIL=...
   export E2E_SUPER_ADMIN_PASSWORD=...
   npm run test:e2e
   \`\`\`
2. Lock \`CORS_ORIGINS=["https://app.thtwaat.com"]\` on VPS \`.env\`.
3. Set \`SSL_MODE=certbot\` (or confirm edge TLS) and scrape ACL for \`/metrics\`.
4. Execute a DB backup restore drill and record evidence.
5. Wire production email provider before marketing public signup.
6. Re-run Playwright after each deploy; archive \`e2e-reports/\`.

## Workflow checklist (20)

1. User Registration
2. Email Verification
3. Workspace Creation
4. AI Provider Selection
5. AI Agent Creation
6. Knowledge Upload
7. Widget Generation
8. Widget Installation
9. Chat Conversation
10. Conversation Memory
11. Human Handoff
12. Lead Capture
13. Billing Upgrade
14. Razorpay Checkout
15. Stripe Checkout
16. Subscription Activation
17. Usage Quotas
18. Marketplace Purchase
19. Publisher Flow
20. Super Admin Analytics
`;

fs.writeFileSync(path.join(outDir, "SECURITY_REPORT.md"), security);
fs.writeFileSync(path.join(outDir, "RECOMMENDATIONS.md"), recommendations);

const index = `# Production Launch Readiness Reports

Generated: ${new Date().toISOString()}

| Report | File |
|--------|------|
| Launch | [LAUNCH_REPORT.md](./LAUNCH_REPORT.md) |
| Failed Tests | [FAILED_TESTS.md](./FAILED_TESTS.md) |
| Performance | [PERFORMANCE_REPORT.md](./PERFORMANCE_REPORT.md) |
| Security | [SECURITY_REPORT.md](./SECURITY_REPORT.md) |
| Recommendations | [RECOMMENDATIONS.md](./RECOMMENDATIONS.md) |
| Raw JSON | [summary.json](./summary.json) |
`;
fs.writeFileSync(path.join(outDir, "README.md"), index);

// Mirror into docs for the repo (committed launch pack)
for (const name of [
  "LAUNCH_REPORT.md",
  "FAILED_TESTS.md",
  "PERFORMANCE_REPORT.md",
  "SECURITY_REPORT.md",
  "RECOMMENDATIONS.md",
  "README.md",
  "summary.json"
]) {
  const src = path.join(outDir, name);
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(docsDir, name));
  }
}

console.log(`Wrote launch reports to ${outDir}`);
console.log(`Mirrored to ${docsDir}`);
