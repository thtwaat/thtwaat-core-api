#!/usr/bin/env bash
# UFW + Fail2Ban + host nginx posture.
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEPLOY_DIR}/lib/common.sh"

bash "${DEPLOY_DIR}/security/configure-ufw.sh"

install -d /etc/fail2ban/jail.d /etc/fail2ban/filter.d
install -m 0644 "${DEPLOY_DIR}/security/fail2ban/jail.local" /etc/fail2ban/jail.d/thtwaat.local
install -m 0644 "${DEPLOY_DIR}/security/fail2ban/filter-nginx-limit.conf" \
  /etc/fail2ban/filter.d/thtwaat-nginx-limit.conf
systemctl enable --now fail2ban
fail2ban-client reload || systemctl restart fail2ban
ok "Fail2Ban configured"

systemctl enable nginx
if [[ "${FORCE_HOST_NGINX:-0}" != "1" ]]; then
  systemctl disable --now nginx || true
  ok "Host nginx installed (disabled — compose binds 80/443)"
else
  # Drop security headers snippet
  install -m 0644 "${DEPLOY_DIR}/security/nginx-security-headers.conf" \
    /etc/nginx/conf.d/thtwaat-security-headers.conf
  systemctl restart nginx
  ok "Host nginx enabled"
fi

ok "Certbot: $(certbot --version 2>&1 | head -n1)"
