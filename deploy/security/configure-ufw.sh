#!/usr/bin/env bash
# UFW baseline for THTWAAT VPS (Ubuntu).
set -euo pipefail

ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# THTWAAT Deploy — cloud metadata SSRF, host-process leg only (Phase 2
# staging validation report §5/§13). This blocks 169.254.169.254 for
# traffic UFW actually sees — processes running directly on the host. It
# does NOT block traffic from Docker containers (the Vite build sandbox):
# Docker manages its own DOCKER-USER/FORWARD iptables chains for
# container-originated traffic, which UFW's OUTPUT-chain rules do not
# intercept — this is a well-documented Docker+UFW gotcha, not a
# theoretical one. The rule that actually matters for the build sandbox is
# in deploy/security/block-metadata-docker.sh (installed as a systemd unit
# by deploy/bootstrap/05-firewall-fail2ban.sh below) — keep this one too as
# harmless defense in depth, but do not mistake it for covering containers.
ufw deny out to 169.254.169.254 comment "block cloud metadata SSRF (host processes)"

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
