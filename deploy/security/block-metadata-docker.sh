#!/usr/bin/env bash
# THTWAAT Deploy — block cloud instance metadata from Docker containers.
#
# UFW does not see container-originated traffic (see the comment in
# configure-ufw.sh) — Docker inserts its own rules into the FORWARD chain,
# consulting the DOCKER-USER chain first, which is the documented,
# Docker-guaranteed insertion point for host-operator rules that must apply
# to every container regardless of which network it's on. This must run
# after dockerd is up (DOCKER-USER only exists once Docker has created it)
# and be re-applied on every docker.service restart, since dockerd
# recreates its chains — see the systemd unit that calls this script.
#
# On real cloud infrastructure this is the mitigation that actually matters
# for the Vite build sandbox's unrestricted outbound access (Phase 2
# staging validation report §5) — verify it took effect with:
#   docker run --rm --network thtwaat_vite_build_net alpine \
#     wget -T 4 -O- http://169.254.169.254/ 2>&1
# which must fail to connect, not merely time out for unrelated reasons.
set -euo pipefail

# Idempotent: DOCKER-USER always exists once Docker has started, but only
# ever has Docker's own default RETURN rule until an operator adds to it —
# check before inserting so re-running this script doesn't duplicate rules.
if ! iptables -C DOCKER-USER -d 169.254.169.254 -j DROP 2>/dev/null; then
  iptables -I DOCKER-USER -d 169.254.169.254 -j DROP
fi
if command -v ip6tables >/dev/null 2>&1; then
  if ! ip6tables -C DOCKER-USER -d fe80::a9fe:a9fe -j DROP 2>/dev/null; then
    ip6tables -I DOCKER-USER -d fe80::a9fe:a9fe -j DROP 2>/dev/null || true
  fi
fi

echo "Cloud metadata endpoint blocked for all Docker containers (DOCKER-USER chain)."
