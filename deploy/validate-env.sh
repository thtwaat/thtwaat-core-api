#!/usr/bin/env bash
# Validate production environment before deploy. Exits non-zero on failure.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

load_env

ERRORS=0
fail() { echo "  ✗ $*"; ERRORS=$((ERRORS + 1)); }
pass() { echo "  ✓ $*"; }
note() { echo "  · $*"; }

log "Validating ${ENV_FILE}"

# ── Required secrets ──────────────────────────────────────────────────────────
for key in JWT_SECRET_KEY JWT_REFRESH_SECRET_KEY DB_PASSWORD DB_USER DB_NAME; do
  val="$(env_get "$key")"
  if is_placeholder "$val"; then
    fail "$key is missing or still a placeholder"
  else
    pass "$key set"
  fi
done

jwt="$(env_get JWT_SECRET_KEY)"
rjwt="$(env_get JWT_REFRESH_SECRET_KEY)"
if [[ "$jwt" == "$rjwt" ]]; then
  fail "JWT_SECRET_KEY and JWT_REFRESH_SECRET_KEY must differ"
else
  pass "JWT secrets differ"
fi
if [[ ${#jwt} -lt 32 ]]; then
  fail "JWT_SECRET_KEY too short (<32)"
else
  pass "JWT_SECRET_KEY length ok"
fi
if [[ ${#rjwt} -lt 32 ]]; then
  fail "JWT_REFRESH_SECRET_KEY too short (<32)"
else
  pass "JWT_REFRESH_SECRET_KEY length ok"
fi

# Mirrors WEAK_SECRET_MARKERS in app/config/settings.py — the API refuses to
# boot in production when either secret matches one of these.
weak_markers="devsecret|changeme|change-me|change_me|placeholder|example|insecure|notsecret|supersecret|your-secret|your_secret|yoursecret|secret123|password|testsecret|dummy|sample|todo|xxxx"
for key in JWT_SECRET_KEY JWT_REFRESH_SECRET_KEY; do
  val="$(env_get "$key")"
  if echo "$val" | tr '[:upper:]' '[:lower:]' | grep -Eq "$weak_markers"; then
    fail "$key looks like a development placeholder"
  else
    pass "$key not a known placeholder"
  fi
done

# ── App env ───────────────────────────────────────────────────────────────────
app_env="$(env_get APP_ENV production)"
if [[ "$app_env" != "production" ]]; then
  fail "APP_ENV must be production (got: ${app_env})"
else
  pass "APP_ENV=production"
fi

cors="$(env_get CORS_ORIGINS)"
if [[ -z "$cors" ]] || echo "$cors" | grep -Fq '*'; then
  fail "CORS_ORIGINS must be an explicit list (no *)"
else
  pass "CORS_ORIGINS restricted"
fi

# ── Metrics exposure ──────────────────────────────────────────────────────────
metrics_token="$(env_get METRICS_TOKEN)"
if is_placeholder "$metrics_token"; then
  note "METRICS_TOKEN unset — /metrics limited to internal networks only"
else
  pass "METRICS_TOKEN set"
fi

pub="$(env_get PUBLIC_API_BASE_URL)"
if is_placeholder "$pub" || [[ ! "$pub" =~ ^https:// ]]; then
  fail "PUBLIC_API_BASE_URL must be https://..."
else
  pass "PUBLIC_API_BASE_URL ok"
fi

# ── Database / Redis ──────────────────────────────────────────────────────────
db_host="$(env_get DB_HOST db)"
redis_host="$(env_get REDIS_HOST redis)"
pass "DB_HOST=${db_host}"
pass "REDIS_HOST=${redis_host}"

# ── Storage ───────────────────────────────────────────────────────────────────
storage="$(env_get STORAGE_PROVIDER local)"
pass "STORAGE_PROVIDER=${storage}"
if [[ ! -d "${ROOT_DIR}/data/uploads" ]]; then
  mkdir -p "${ROOT_DIR}/data/uploads"
fi
pass "upload dir present"

# ── SMTP (optional unless REQUIRE_SMTP=1) ─────────────────────────────────────
smtp_host="$(env_get SMTP_HOST)"
if [[ -z "$smtp_host" ]]; then
  if [[ "${REQUIRE_SMTP:-0}" == "1" ]]; then
    fail "SMTP_HOST required (REQUIRE_SMTP=1)"
  else
    note "SMTP not configured (set REQUIRE_SMTP=1 to enforce)"
  fi
else
  for key in SMTP_PORT SMTP_USER SMTP_PASSWORD SMTP_FROM; do
    val="$(env_get "$key")"
    if is_placeholder "$val"; then
      fail "$key missing for SMTP"
    else
      pass "$key set"
    fi
  done
fi

# ── TLS mode ──────────────────────────────────────────────────────────────────
ssl_mode="$(env_get SSL_MODE simulate)"
if [[ "$ssl_mode" == "simulate" ]]; then
  warn "SSL_MODE=simulate — use certbot for public production TLS"
  note "SSL_MODE=simulate (acceptable for private VPS bring-up)"
else
  pass "SSL_MODE=${ssl_mode}"
  email="$(env_get SSL_ACME_EMAIL)"
  if is_placeholder "$email"; then
    fail "SSL_ACME_EMAIL required when SSL_MODE!=simulate"
  else
    pass "SSL_ACME_EMAIL set"
  fi
fi

# ── Live dependency probes (when stack already running) ───────────────────────
if docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps --status running 2>/dev/null | grep -q "db"; then
  if compose exec -T db pg_isready -U "$(env_get DB_USER)" -d "$(env_get DB_NAME)" >/dev/null 2>&1; then
    pass "PostgreSQL reachable"
  else
    fail "PostgreSQL not ready"
  fi
fi
if docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps --status running 2>/dev/null | grep -q "redis"; then
  if compose exec -T redis redis-cli ping 2>/dev/null | grep -qi pong; then
    pass "Redis reachable"
  else
    fail "Redis not ready"
  fi
fi

if [[ "$ERRORS" -gt 0 ]]; then
  die "Environment validation failed (${ERRORS} error(s))"
fi

ok "Environment validation passed"
