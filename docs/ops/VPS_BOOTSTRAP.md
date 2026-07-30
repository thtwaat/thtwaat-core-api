# VPS Bootstrap Guide — Ubuntu 24.04 LTS

One-command host preparation for THTWAAT production.

## Quick start

```bash
# On a fresh Ubuntu 24.04 VPS (as root)
git clone <repo> /tmp/thtwaat-bootstrap && cd /tmp/thtwaat-bootstrap

sudo THTWAAT_SSH_PUBKEY="$(cat /path/to/your.pub)" \
     THTWAAT_GIT_URL="git@github.com:org/thtwaat-core-api.git" \
     HARDEN_SSH=1 \
     INSTALL_MONITORING=1 \
     AUTO_DEPLOY=0 \
     ./bootstrap.sh
```

Or after copying the repo to the server:

```bash
sudo THTWAAT_SSH_PUBKEY="$(cat ~/.ssh/id_ed25519.pub)" ./bootstrap.sh
```

## What it installs

| Component | Notes |
|-----------|--------|
| Docker + Compose plugin | Engine with log rotation |
| Git, curl, jq, htop | Ops utilities |
| Nginx + Certbot | Host nginx disabled by default (compose binds 80/443) |
| UFW | SSH + 80/443 only |
| Fail2Ban | sshd + nginx rate-limit jail |
| unattended-upgrades | Security patches |
| prometheus-node-exporter | `127.0.0.1:9100` |
| Prometheus + Grafana + cAdvisor | Optional (`INSTALL_MONITORING=1`) |

## Security

- Deploy user: `thtwaat` (override `THTWAAT_APP_USER`)
- When `THTWAAT_SSH_PUBKEY` is set and `HARDEN_SSH=1`:
  - `PermitRootLogin no`
  - `PasswordAuthentication no`
  - `AllowUsers thtwaat`
- UFW default deny inbound
- Automatic security updates via `unattended-upgrades`

**Warning:** Never enable full SSH hardening without installing your pubkey first.

## Directory layout

```text
/opt/thtwaat/
  releases/<timestamp>/     # immutable release checkouts
  current -> releases/...   # active release symlink
  shared/
    .env.prod
    data/uploads
    data/knowledge
    nginx/...
    monitoring/
  backups/
    postgres/               # nightly dumps
    storage/                # weekly tarballs
  logs/
    health/
    deploy/
```

## Systemd

| Unit | Role |
|------|------|
| `thtwaat-worker.service` | `docker compose up -d worker` |
| `thtwaat-scheduler.service` | `docker compose up -d scheduler` |
| `thtwaat-health-monitor.timer` | `/live` `/ready` `/health` every 2m |
| `thtwaat-backup-nightly.timer` | PostgreSQL dump + gzip integrity check |
| `thtwaat-backup-weekly.timer` | Storage archive + tar verify |

```bash
sudo systemctl start thtwaat-worker thtwaat-scheduler
systemctl list-timers | grep thtwaat
```

## Deploy after bootstrap

```bash
sudo -u thtwaat -H bash
cd /opt/thtwaat/current
nano /opt/thtwaat/shared/.env.prod   # real secrets
export ENV_FILE=/opt/thtwaat/shared/.env.prod
./deploy/validate-env.sh
./deploy.sh
./deploy/verify-health.sh
```

Rollback remains `./deploy/rollback.sh`.

## Backups & restore verify

```bash
# Manual
/opt/thtwaat/current/deploy/scripts/backup-nightly.sh
/opt/thtwaat/current/deploy/scripts/backup-weekly-storage.sh

# Deep restore probe (creates temp DB)
VERIFY_RESTORE_DEEP=1 /opt/thtwaat/current/deploy/scripts/backup-nightly.sh
# or
./deploy/scripts/verify-restore.sh --archive /opt/thtwaat/backups/postgres/db_....sql.gz
```

Retention: `POSTGRES_BACKUP_RETENTION_DAYS` (default 14), `STORAGE_BACKUP_RETENTION_DAYS` (default 56).

## Monitoring

- Node exporter: `http://127.0.0.1:9100/metrics`
- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3000` (change `GRAFANA_ADMIN_PASSWORD`)

Use SSH tunnels — ports are not opened in UFW by default.

```bash
ssh -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 thtwaat@vps
```

Dashboard: **THTWAAT VPS Overview** (auto-provisioned).

## Related

- [DEPLOYMENT.md](./DEPLOYMENT.md)
- [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md)
- [RECOVERY_GUIDE.md](./RECOVERY_GUIDE.md)
