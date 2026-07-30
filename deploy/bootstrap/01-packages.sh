#!/usr/bin/env bash
# Install base packages for THTWAAT VPS.
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEPLOY_DIR}/lib/common.sh"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  ca-certificates curl gnupg lsb-release apt-transport-https \
  software-properties-common unzip wget vim-tiny \
  git jq htop \
  ufw fail2ban \
  nginx certbot python3-certbot-nginx \
  unattended-upgrades apt-listchanges \
  prometheus-node-exporter

ok "Base packages installed (git jq htop curl nginx certbot ufw fail2ban node-exporter)"
