#!/usr/bin/env bash
# Rollback to last saved deploy state (images / git SHA).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

require_cmd docker
cd "${ROOT_DIR}"

POINT="${ROLLBACK_POINT:-${STATE_DIR}/rollback-latest.env}"
[[ -f "${POINT}" ]] || die "No rollback point at ${POINT}"

# shellcheck disable=SC1090
source "${POINT}"
log "Rolling back using ${POINT} (git=${GIT_SHA:-unknown})"

if [[ "${ROLLBACK_GIT:-1}" == "1" ]] && [[ -d "${ROOT_DIR}/.git" ]] && [[ "${GIT_SHA:-unknown}" != "unknown" ]]; then
  git checkout -q "${GIT_SHA}" || warn "git checkout ${GIT_SHA} failed"
fi

# Prefer re-up with previously built images if IDs known
if [[ -n "${API_IMAGE:-}" ]]; then
  log "Re-tagging previous API image ${API_IMAGE}"
  docker tag "${API_IMAGE}" thtwaat-api-rollback:local 2>/dev/null || true
fi

log "Recreating stack from rollback checkout..."
compose up -d --build --remove-orphans || compose up -d --remove-orphans

log "Migrations (downgrade not automatic — apply alembic carefully if needed)..."
compose exec -T api alembic upgrade head || warn "alembic upgrade failed during rollback"

if bash "${SCRIPT_DIR}/verify-health.sh"; then
  ok "Rollback healthy"
else
  die "Rollback completed but health checks failed — escalate to recovery guide"
fi
