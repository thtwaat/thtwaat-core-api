#!/usr/bin/env bash
# Clone repository into releases/, link current, optional first deploy.
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEPLOY_DIR}/lib/common.sh"

ROOT="${THTWAAT_ROOT:-/opt/thtwaat}"
USER_NAME="${THTWAAT_APP_USER:-thtwaat}"
GIT_URL="${THTWAAT_GIT_URL:-}"
GIT_REF="${THTWAAT_GIT_REF:-main}"
AUTO_DEPLOY="${AUTO_DEPLOY:-0}"

# If bootstrap is running from an existing checkout, seed first release from it
SEED_REPO="$(cd "${DEPLOY_DIR}/.." && pwd)"

release_id="$(date -u +%Y%m%dT%H%M%SZ)"
release_dir="${ROOT}/releases/${release_id}"

mkdir -p "${ROOT}/releases"
if [[ -n "${GIT_URL}" ]]; then
  log "Cloning ${GIT_URL} @ ${GIT_REF} → ${release_dir}"
  sudo -u "${USER_NAME}" git clone --depth 1 --branch "${GIT_REF}" "${GIT_URL}" "${release_dir}" \
    || { rm -rf "${release_dir}"; sudo -u "${USER_NAME}" git clone "${GIT_URL}" "${release_dir}"; sudo -u "${USER_NAME}" bash -lc "cd '${release_dir}' && git checkout '${GIT_REF}'"; }
elif [[ -f "${SEED_REPO}/docker-compose.prod.yml" ]]; then
  log "Seeding release from local checkout ${SEED_REPO}"
  mkdir -p "${release_dir}"
  # Prefer rsync if available; else cp
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude '.venv' --exclude '.git' --exclude 'data/uploads' --exclude 'data/backups' \
      "${SEED_REPO}/" "${release_dir}/"
    # keep .git if present for pull-based deploys
    [[ -d "${SEED_REPO}/.git" ]] && rsync -a "${SEED_REPO}/.git" "${release_dir}/"
  else
    cp -a "${SEED_REPO}/." "${release_dir}/"
  fi
  chown -R "${USER_NAME}:${USER_NAME}" "${release_dir}"
else
  die "Set THTWAAT_GIT_URL or run bootstrap from a repo checkout"
fi

# Link shared assets into release
ln -sfn "${ROOT}/shared/.env.prod" "${release_dir}/.env.prod" 2>/dev/null || true
mkdir -p "${release_dir}/data"
ln -sfn "${ROOT}/shared/data/uploads" "${release_dir}/data/uploads"
ln -sfn "${ROOT}/shared/data/knowledge" "${release_dir}/data/knowledge"
ln -sfn "${ROOT}/backups" "${release_dir}/data/backups"
# nginx ssl/config from shared
if [[ -d "${release_dir}/nginx" ]]; then
  rm -rf "${release_dir}/nginx/ssl" "${release_dir}/nginx/conf.d" "${release_dir}/nginx/acme-webroot" 2>/dev/null || true
  ln -sfn "${ROOT}/shared/nginx/ssl" "${release_dir}/nginx/ssl"
  ln -sfn "${ROOT}/shared/nginx/conf.d" "${release_dir}/nginx/conf.d"
  ln -sfn "${ROOT}/shared/nginx/acme-webroot" "${release_dir}/nginx/acme-webroot"
fi

ln -sfn "${release_dir}" "${ROOT}/current"
chown -h "${USER_NAME}:${USER_NAME}" "${ROOT}/current"

# Ensure env file exists
if [[ ! -f "${ROOT}/shared/.env.prod" ]]; then
  if [[ -f "${release_dir}/.env.prod.example" ]]; then
    cp "${release_dir}/.env.prod.example" "${ROOT}/shared/.env.prod"
    warn "Created ${ROOT}/shared/.env.prod from example — EDIT SECRETS before deploy"
  fi
fi
ln -sfn "${ROOT}/shared/.env.prod" "${release_dir}/.env"
chown -R "${USER_NAME}:${USER_NAME}" "${ROOT}/shared" "${ROOT}/current" "${release_dir}"

ok "Release ${release_id} linked as current"

if [[ "${AUTO_DEPLOY}" == "1" ]]; then
  log "AUTO_DEPLOY=1 — validating and deploying"
  sudo -u "${USER_NAME}" -H bash -lc "
    set -euo pipefail
    cd '${ROOT}/current'
    export ENV_FILE='${ROOT}/shared/.env.prod'
    export THTWAAT_ROOT='${ROOT}'
    export SKIP_GIT_PULL=1
    export ALLOW_BACKUP_FAILURE=1
    ./deploy/validate-env.sh
    ./deploy/deploy.sh
    ./deploy/verify-health.sh
  "
  systemctl start thtwaat-worker.service thtwaat-scheduler.service || warn "Start worker/scheduler after env is valid"
  ok "Auto-deploy finished"
else
  log "Skipping auto-deploy (AUTO_DEPLOY=0). Next: edit shared/.env.prod then ./deploy/deploy.sh"
fi

# Keep last N releases
KEEP="${RELEASE_KEEP:-5}"
count=0
for d in $(ls -1dt "${ROOT}/releases"/* 2>/dev/null || true); do
  count=$((count + 1))
  [[ "${count}" -le "${KEEP}" ]] && continue
  cur="$(readlink -f "${ROOT}/current" 2>/dev/null || true)"
  [[ "${d}" == "${cur}" ]] && continue
  rm -rf "${d}"
  log "Pruned old release ${d}"
done
