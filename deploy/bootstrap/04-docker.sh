#!/usr/bin/env bash
# Install Docker Engine + Compose plugin.
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEPLOY_DIR}/lib/common.sh"

USER_NAME="${THTWAAT_APP_USER:-thtwaat}"
export DEBIAN_FRONTEND=noninteractive

if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  ok "Docker already present: $(docker --version)"
fi

systemctl enable --now docker
usermod -aG docker "${USER_NAME}" || true

# THTWAAT Deploy — Vite build sandbox networks (idempotent). See
# docker/vite-build/README.md and orchestrator/README.md for what each one
# isolates; the metadata-SSRF firewall rule these networks need lives in
# deploy/security/configure-ufw.sh, not here.
docker network create thtwaat_vite_build_net 2>/dev/null || true
docker network create --internal thtwaat_orchestrator_net 2>/dev/null || true
docker network create --internal thtwaat_socket_proxy_net 2>/dev/null || true

# Daemon logging defaults
mkdir -p /etc/docker
if [[ ! -f /etc/docker/daemon.json ]]; then
  cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "5" },
  "live-restore": true
}
EOF
  systemctl restart docker
fi

ok "Docker $(docker --version) / $(docker compose version)"
