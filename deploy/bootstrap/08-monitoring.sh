#!/usr/bin/env bash
# Enable node-exporter + optional Prometheus/Grafana stack.
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEPLOY_DIR}/lib/common.sh"

ROOT="${THTWAAT_ROOT:-/opt/thtwaat}"
USER_NAME="${THTWAAT_APP_USER:-thtwaat}"

# Distro node-exporter (from 01-packages) — bind localhost only via override
mkdir -p /etc/systemd/system/prometheus-node-exporter.service.d
cat > /etc/systemd/system/prometheus-node-exporter.service.d/override.conf <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/prometheus-node-exporter \
  --web.listen-address=127.0.0.1:9100 \
  --collector.filesystem.mount-points-exclude=^/(dev|proc|sys|run|var/lib/docker/.+)($|/)
EOF
systemctl daemon-reload
systemctl enable --now prometheus-node-exporter
ok "node-exporter listening on 127.0.0.1:9100"

# Copy monitoring bundle into shared
mkdir -p "${ROOT}/shared/monitoring"
cp -a "${DEPLOY_DIR}/monitoring/." "${ROOT}/shared/monitoring/"
chown -R "${USER_NAME}:${USER_NAME}" "${ROOT}/shared/monitoring"

if [[ "${INSTALL_MONITORING:-1}" == "1" ]]; then
  # Prefer current release path once available; otherwise shared copy
  MON_DIR="${ROOT}/shared/monitoring"
  if [[ -d "${ROOT}/current/deploy/monitoring" ]]; then
    MON_DIR="${ROOT}/current/deploy/monitoring"
  fi
  log "Starting Prometheus/Grafana/cAdvisor from ${MON_DIR}"
  ( cd "${MON_DIR}" && docker compose up -d ) || warn "Monitoring compose start deferred until docker/network ready"
  ok "Monitoring stack requested (Grafana :3000, Prometheus :9090 — localhost; use SSH tunnel)"
else
  ok "INSTALL_MONITORING=0 — skipped Prometheus/Grafana containers"
fi
