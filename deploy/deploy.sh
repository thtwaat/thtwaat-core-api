#!/usr/bin/env bash
# One-command production deploy for THTWAAT on VPS.
#
#   ./deploy/deploy.sh
#   ENV_FILE=.env.prod SKIP_GIT_PULL=1 ./deploy/deploy.sh
#   IMAGE_TAG=sha-abc123 ./deploy/deploy.sh   # when using pre-built registry images
#
# Steps: validate → rollback point → (optional backup) → pull → build → up →
#         migrate → health → monitoring check → rollback on failure
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

LOG_FILE="${LOG_DIR}/deploy-$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee -a "${LOG_FILE}") 2>&1

require_cmd docker
require_cmd curl
require_cmd git

cd "${ROOT_DIR}"

DEPLOY_FAILED=0
ROLLBACK_POINT=""

on_err() {
  DEPLOY_FAILED=1
  warn "Deploy failed — initiating rollback"
  if [[ -n "${ROLLBACK_POINT}" ]]; then
    ROLLBACK_POINT="${ROLLBACK_POINT}" "${SCRIPT_DIR}/rollback.sh" || warn "Rollback script also failed — manual recovery required"
  fi
  exit 1
}
trap on_err ERR

log "=== THTWAAT production deploy ==="
log "ROOT=${ROOT_DIR} ENV_FILE=${ENV_FILE}"

# 1) Validate env / secrets
bash "${SCRIPT_DIR}/validate-env.sh"
load_env

# 2) Rollback snapshot
ROLLBACK_POINT="$(save_rollback_point)"
ok "Rollback point: ${ROLLBACK_POINT}"

# 3) Pre-deploy backup (recommended; soft-fail on first bring-up)
if [[ "${BACKUP_BEFORE_DEPLOY:-1}" == "1" ]]; then
  log "Pre-deploy backup..."
  export ALLOW_BACKUP_FAILURE="${ALLOW_BACKUP_FAILURE:-1}"
  bash "${SCRIPT_DIR}/backup.sh" || warn "Pre-deploy backup skipped/failed"
fi

# 4) Pull latest release (git) unless skipped / image-only mode
if [[ "${SKIP_GIT_PULL:-0}" != "1" ]] && [[ -d "${ROOT_DIR}/.git" ]]; then
  BRANCH="${DEPLOY_BRANCH:-main}"
  log "Fetching ${BRANCH}..."
  git fetch --tags --prune origin
  if [[ -n "${DEPLOY_REF:-}" ]]; then
    git checkout -q "${DEPLOY_REF}"
    git pull --ff-only origin "${DEPLOY_REF}" || true
  else
    git checkout -q "${BRANCH}"
    git pull --ff-only "origin" "${BRANCH}"
  fi
  ok "Git at $(git rev-parse --short HEAD)"
else
  log "Skipping git pull (SKIP_GIT_PULL=1 or no .git)"
fi

# 5) Build / pull images
if [[ -n "${IMAGE_TAG:-}" ]] && [[ -n "${IMAGE_REGISTRY:-}" ]]; then
  log "Pulling images ${IMAGE_REGISTRY}/thtwaat-core-api:${IMAGE_TAG}"
  export THTWAAT_API_IMAGE="${IMAGE_REGISTRY}/thtwaat-core-api:${IMAGE_TAG}"
  docker pull "${THTWAAT_API_IMAGE}"
  # Override build with image if compose supports it — fall through to build otherwise
fi

log "Building containers..."
compose build

# 6) Start services
log "Starting services..."
compose up -d --remove-orphans

# 7) Explicit migrations (also run on api start — double-safe)
log "Running migrations..."
compose exec -T api alembic upgrade head

# 8) Health verification
bash "${SCRIPT_DIR}/verify-health.sh"

# 9) Monitoring (optional)
if [[ "${VERIFY_MONITORING:-1}" == "1" ]]; then
  bash "${SCRIPT_DIR}/verify-monitoring.sh" || warn "Monitoring verification soft-failed"
fi

trap - ERR
ok "Deploy succeeded. Log: ${LOG_FILE}"
compose ps
echo ""
echo "Health:  http://127.0.0.1:8000/live  |  https://<host>/live"
echo "Ready:   http://127.0.0.1:8000/ready"
echo "Rollback point kept at: ${ROLLBACK_POINT}"
