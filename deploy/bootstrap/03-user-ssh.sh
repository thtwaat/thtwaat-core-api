#!/usr/bin/env bash
# Create deploy user + harden SSH (safe defaults — never lock out without a key).
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${DEPLOY_DIR}/lib/common.sh"

USER_NAME="${THTWAAT_APP_USER:-thtwaat}"
ROOT="${THTWAAT_ROOT:-/opt/thtwaat}"
SSH_PORT="${SSH_PORT:-22}"
HARDEN_SSH="${HARDEN_SSH:-1}"

if ! id "${USER_NAME}" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash --groups sudo "${USER_NAME}"
  ok "Created deploy user ${USER_NAME}"
else
  ok "Deploy user ${USER_NAME} exists"
fi

# Passwordless sudo for deploy automation (scoped)
SUDOERS="/etc/sudoers.d/thtwaat-${USER_NAME}"
cat > "${SUDOERS}" <<EOF
# THTWAAT deploy user — limited NOPASSWD for ops
${USER_NAME} ALL=(ALL) NOPASSWD: /usr/bin/systemctl, /usr/sbin/ufw, /usr/bin/docker, /usr/bin/docker-compose, /usr/libexec/docker/cli-plugins/docker-compose, /bin/journalctl
EOF
chmod 0440 "${SUDOERS}"
visudo -cf "${SUDOERS}" >/dev/null

install -d -m 0700 -o "${USER_NAME}" -g "${USER_NAME}" "/home/${USER_NAME}/.ssh"
AUTH_KEYS="/home/${USER_NAME}/.ssh/authorized_keys"
touch "${AUTH_KEYS}"
chmod 0600 "${AUTH_KEYS}"
chown "${USER_NAME}:${USER_NAME}" "${AUTH_KEYS}"

KEY_INSTALLED=0
if [[ -n "${THTWAAT_SSH_PUBKEY:-}" ]]; then
  if ! grep -qxF "${THTWAAT_SSH_PUBKEY}" "${AUTH_KEYS}" 2>/dev/null; then
    echo "${THTWAAT_SSH_PUBKEY}" >> "${AUTH_KEYS}"
  fi
  KEY_INSTALLED=1
  ok "Installed THTWAAT_SSH_PUBKEY for ${USER_NAME}"
elif [[ -n "${THTWAAT_SSH_PUBKEY_FILE:-}" ]] && [[ -f "${THTWAAT_SSH_PUBKEY_FILE}" ]]; then
  cat "${THTWAAT_SSH_PUBKEY_FILE}" >> "${AUTH_KEYS}"
  sort -u -o "${AUTH_KEYS}" "${AUTH_KEYS}"
  KEY_INSTALLED=1
  ok "Installed keys from ${THTWAAT_SSH_PUBKEY_FILE}"
else
  warn "No THTWAAT_SSH_PUBKEY provided — SSH hardening will NOT disable passwords"
fi

chown -R "${USER_NAME}:${USER_NAME}" "${ROOT}" 2>/dev/null || true
usermod -aG docker "${USER_NAME}" 2>/dev/null || true

# SSH daemon hardening
SSHD_DROPIN="/etc/ssh/sshd_config.d/99-thtwaat.conf"
mkdir -p /etc/ssh/sshd_config.d
if [[ "${HARDEN_SSH}" == "1" ]] && [[ "${KEY_INSTALLED}" == "1" ]]; then
  cat > "${SSHD_DROPIN}" <<EOF
# THTWAAT SSH hardening
Port ${SSH_PORT}
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
AllowUsers ${USER_NAME}
X11Forwarding no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
EOF
  sshd -t
  systemctl reload ssh || systemctl reload sshd
  ok "SSH hardened (root login off, password auth off, AllowUsers=${USER_NAME})"
elif [[ "${HARDEN_SSH}" == "1" ]]; then
  cat > "${SSHD_DROPIN}" <<EOF
# THTWAAT SSH partial hardening (awaiting pubkey before disabling passwords)
Port ${SSH_PORT}
PermitRootLogin prohibit-password
PubkeyAuthentication yes
PasswordAuthentication yes
AllowUsers ${USER_NAME} root
EOF
  sshd -t
  systemctl reload ssh || systemctl reload sshd
  warn "PasswordAuthentication still enabled — set THTWAAT_SSH_PUBKEY and re-run 03-user-ssh.sh"
else
  ok "SSH hardening skipped (HARDEN_SSH=0)"
fi
