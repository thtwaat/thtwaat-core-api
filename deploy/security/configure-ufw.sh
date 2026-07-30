#!/usr/bin/env bash
# UFW baseline for THTWAAT VPS (Ubuntu).
set -euo pipefail

ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# SSH — allow before enabling firewall
SSH_PORT="${SSH_PORT:-22}"
ufw allow "${SSH_PORT}/tcp" comment "SSH"

# HTTP/HTTPS for nginx (compose or host)
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"

# Optional monitoring (bind to localhost in compose when possible; open only if needed)
if [[ "${ALLOW_MONITORING_PORTS:-0}" == "1" ]]; then
  ufw allow 9090/tcp comment "Prometheus"
  ufw allow 3000/tcp comment "Grafana"
fi

ufw --force enable
ufw status verbose
echo "UFW configured."
