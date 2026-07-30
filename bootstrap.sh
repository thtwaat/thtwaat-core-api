#!/usr/bin/env bash
# THTWAAT VPS bootstrap — Ubuntu 24.04 LTS
# One command to prepare a production-ready host (no application code changes).
#
#   curl -fsSL ... | sudo bash   # or:
#   sudo THTWAAT_SSH_PUBKEY="$(cat ~/.ssh/id_ed25519.pub)" ./bootstrap.sh
#
# Optional env:
#   THTWAAT_ROOT=/opt/thtwaat
#   THTWAAT_APP_USER=thtwaat
#   THTWAAT_GIT_URL=git@github.com:org/thtwaat-core-api.git
#   THTWAAT_SSH_PUBKEY="ssh-ed25519 AAAA..."
#   HARDEN_SSH=1                 # disable root + password SSH (requires pubkey)
#   AUTO_DEPLOY=0                # set 1 to clone + validate + deploy after bootstrap
#   INSTALL_MONITORING=1         # Prometheus + Grafana + node-exporter
#   FORCE_HOST_NGINX=0
#   SSH_PORT=22
set -euo pipefail

ROOT_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Allow invocation as ./bootstrap.sh from repo root OR ./deploy/bootstrap.sh
if [[ -d "${ROOT_SCRIPT}/deploy/bootstrap" ]]; then
  REPO_HINT="${ROOT_SCRIPT}"
  BOOT_DIR="${ROOT_SCRIPT}/deploy/bootstrap"
  DEPLOY_DIR="${ROOT_SCRIPT}/deploy"
elif [[ -d "${ROOT_SCRIPT}/bootstrap" ]]; then
  DEPLOY_DIR="${ROOT_SCRIPT}"
  BOOT_DIR="${ROOT_SCRIPT}/bootstrap"
  REPO_HINT="$(cd "${DEPLOY_DIR}/.." && pwd)"
else
  echo "Cannot locate deploy/bootstrap/" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "${DEPLOY_DIR}/lib/common.sh"

export THTWAAT_ROOT="${THTWAAT_ROOT:-/opt/thtwaat}"
export THTWAAT_APP_USER="${THTWAAT_APP_USER:-thtwaat}"
export HARDEN_SSH="${HARDEN_SSH:-1}"
export AUTO_DEPLOY="${AUTO_DEPLOY:-0}"
export INSTALL_MONITORING="${INSTALL_MONITORING:-1}"
export SSH_PORT="${SSH_PORT:-22}"
export DEBIAN_FRONTEND=noninteractive

if [[ "$(id -u)" -ne 0 ]]; then
  die "Run as root: sudo $0"
fi

. /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || warn "Expected Ubuntu; got ID=${ID:-unknown}"
[[ "${VERSION_ID:-}" == "24.04" ]] || warn "Validated for 24.04; got VERSION_ID=${VERSION_ID:-unknown}"

mkdir -p /var/log/thtwaat
LOG_FILE="/var/log/thtwaat/bootstrap-$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee -a "${LOG_FILE}") 2>&1

log "=== THTWAAT VPS bootstrap starting ==="
log "THTWAAT_ROOT=${THTWAAT_ROOT} USER=${THTWAAT_APP_USER}"

run_step() {
  local name="$1"
  local script="$2"
  log "── Step: ${name}"
  # shellcheck disable=SC1090
  bash "${script}"
  ok "${name}"
}

run_step "packages"              "${BOOT_DIR}/01-packages.sh"
run_step "directories"           "${BOOT_DIR}/02-directories.sh"
run_step "deploy-user-and-ssh"   "${BOOT_DIR}/03-user-ssh.sh"
run_step "docker"                "${BOOT_DIR}/04-docker.sh"
run_step "firewall-fail2ban"     "${BOOT_DIR}/05-firewall-fail2ban.sh"
run_step "unattended-upgrades"   "${BOOT_DIR}/06-unattended-upgrades.sh"
run_step "systemd-units"         "${BOOT_DIR}/07-systemd.sh"
run_step "monitoring"            "${BOOT_DIR}/08-monitoring.sh"
run_step "clone-and-deploy"      "${BOOT_DIR}/09-clone-deploy.sh"

ok "Bootstrap finished. Log: ${LOG_FILE}"
cat <<EOF

========================================================================
 THTWAAT VPS is ready for production deployment
========================================================================
 Root:     ${THTWAAT_ROOT}
 User:     ${THTWAAT_APP_USER}
 Current:  ${THTWAAT_ROOT}/current  (symlink after first release)

 Next (if AUTO_DEPLOY=0):
   1. sudo -u ${THTWAAT_APP_USER} -H bash
   2. cp ${THTWAAT_ROOT}/shared/.env.prod.example ${THTWAAT_ROOT}/shared/.env.prod
      # or edit existing shared/.env.prod
   3. ${THTWAAT_ROOT}/current/deploy/validate-env.sh
   4. ${THTWAAT_ROOT}/current/deploy/deploy.sh

 Docs: docs/ops/VPS_BOOTSTRAP.md
========================================================================
EOF
