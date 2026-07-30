# Deploy toolkit

| Script | Role |
|--------|------|
| [`../bootstrap.sh`](../bootstrap.sh) | **One-command VPS bootstrap** (Ubuntu 24.04) |
| [`bootstrap.sh`](./bootstrap.sh) | Alias → root bootstrap |
| [`../deploy.sh`](../deploy.sh) | One-command production deploy |
| `validate-env.sh` | Secrets / env gate |
| `deploy.sh` | Full deploy + health + rollback trap |
| `rollback.sh` | Restore last rollback point |
| `backup.sh` / `restore.sh` | DB + storage |
| `scripts/backup-nightly.sh` | Nightly PostgreSQL + verify |
| `scripts/backup-weekly-storage.sh` | Weekly storage + verify |
| `scripts/health-monitor.sh` | Systemd health probe |
| `verify-health.sh` / `verify-monitoring.sh` | Post-deploy checks |
| `monitoring/` | Prometheus + Grafana + dashboards |

Docs: [VPS_BOOTSTRAP.md](../docs/ops/VPS_BOOTSTRAP.md) · [DEPLOYMENT.md](../docs/ops/DEPLOYMENT.md)
