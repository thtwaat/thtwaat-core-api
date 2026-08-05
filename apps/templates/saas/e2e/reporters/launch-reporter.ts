import type {
  FullConfig,
  FullResult,
  Reporter,
  Suite,
  TestCase,
  TestResult
} from "@playwright/test/reporter";
import fs from "fs";
import path from "path";

type Row = {
  title: string;
  status: string;
  durationMs: number;
  error?: string;
  workflow?: string;
};

/**
 * Writes launch readiness artifacts under apps/templates/saas/e2e-reports/
 */
class LaunchReporter implements Reporter {
  private rows: Row[] = [];
  private started = Date.now();
  private outDir = path.resolve(__dirname, "../../e2e-reports");

  onBegin(_config: FullConfig, _suite: Suite) {
    fs.mkdirSync(this.outDir, { recursive: true });
  }

  onTestEnd(test: TestCase, result: TestResult) {
    const workflow = test.annotations.find((a) => a.type === "workflow")?.description;
    this.rows.push({
      title: test.titlePath().slice(1).join(" › "),
      status: result.status,
      durationMs: result.duration,
      error: result.error?.message,
      workflow
    });
  }

  onEnd(result: FullResult) {
    const failed = this.rows.filter((r) => r.status === "failed" || r.status === "timedOut");
    const passed = this.rows.filter((r) => r.status === "passed");
    const skipped = this.rows.filter((r) => r.status === "skipped");
    const elapsed = Date.now() - this.started;

    const launch = `# Launch Report

Generated: ${new Date().toISOString()}
Overall: **${result.status.toUpperCase()}**
Duration: ${(elapsed / 1000).toFixed(1)}s

| Metric | Count |
|--------|------:|
| Passed | ${passed.length} |
| Failed | ${failed.length} |
| Skipped | ${skipped.length} |
| Total | ${this.rows.length} |

## Workflow coverage

${this.rows
  .map((r) => `- [${r.status}] ${r.workflow || r.title} (${r.durationMs}ms)`)
  .join("\n")}
`;

    const failedMd = `# Failed Tests

${
  failed.length
    ? failed.map((f) => `## ${f.title}\n\n\`\`\`\n${f.error || "unknown"}\n\`\`\`\n`).join("\n")
    : "_No failed tests._\n"
}
`;

    const perf = `# Performance Report

| Test | Duration (ms) | Status |
|------|--------------:|--------|
${this.rows
  .slice()
  .sort((a, b) => b.durationMs - a.durationMs)
  .map((r) => `| ${r.title.replace(/\|/g, "/")} | ${r.durationMs} | ${r.status} |`)
  .join("\n")}

## Notes
- Targets under 15s for API smoke steps and under 60s for UI flows are preferred.
- Slowest steps above should be investigated before public launch.
`;

    fs.writeFileSync(path.join(this.outDir, "LAUNCH_REPORT.md"), launch);
    fs.writeFileSync(path.join(this.outDir, "FAILED_TESTS.md"), failedMd);
    fs.writeFileSync(path.join(this.outDir, "PERFORMANCE_REPORT.md"), perf);
    fs.writeFileSync(
      path.join(this.outDir, "summary.json"),
      JSON.stringify({ status: result.status, rows: this.rows, elapsedMs: elapsed }, null, 2)
    );
  }
}

export default LaunchReporter;
