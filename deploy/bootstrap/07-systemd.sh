#!/usr/bin/env bash
# Install systemd units for worker, scheduler, health monitor, backups.
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEPLOY_DIR}/lib/common.sh"

ROOT="${THTWAAT_ROOT:-/opt/thtwaat}"
UNIT_SRC="${DEPLOY_DIR}/systemd"

install -m 0644 \
  "${UNIT_SRC}/thtwaat-worker.service" \
  "${UNIT_SRC}/thtwaat-scheduler.service" \
  "${UNIT_SRC}/thtwaat-health-monitor.service" \
  "${UNIT_SRC}/thtwaat-health-monitor.timer" \
  "${UNIT_SRC}/thtwaat-backup-nightly.service" \
  "${UNIT_SRC}/thtwaat-backup-nightly.timer" \
  "${UNIT_SRC}/thtwaat-backup-weekly.service" \
  "${UNIT_SRC}/thtwaat-backup-weekly.timer" \
  "${UNIT_SRC}/thtwaat-backup.service" \
  "${UNIT_SRC}/thtwaat-backup.timer" \
  /etc/systemd/system/

# Rewrite paths if THTWAAT_ROOT != /opt/thtwaat
if [[ "${ROOT}" != "/opt/thtwaat" ]]; then
  sed -i "s|/opt/thtwaat|${ROOT}|g" /etc/systemd/system/thtwaat-*.service
  sed -i "s|/opt/thtwaat|${ROOT}|g" /etc/systemd/system/thtwaat-*.timer
fi

systemctl daemon-reload

# Timers can enable immediately; services that need current/ wait until clone
systemctl enable thtwaat-health-monitor.timer thtwaat-backup-nightly.timer thtwaat-backup-weekly.timer
systemctl enable thtwaat-worker.service thtwaat-scheduler.service || true

# Start timers (harmless if current missing — oneshot will fail until deploy)
systemctl start thtwaat-health-monitor.timer thtwaat-backup-nightly.timer thtwaat-backup-weekly.timer || true

ok "Systemd units installed"
systemctl list-timers --all | grep thtwaat || true
