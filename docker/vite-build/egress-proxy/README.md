# THTWAAT Deploy — Vite build sandbox egress allowlist (optional)

Answers the Phase 2 staging validation report §4/§13 finding: the build
sandbox has ordinary, unrestricted outbound internet access today (confirmed
live — see the report's §4), not just npm registry access. This is a plain
Squid forward proxy that allowlists CONNECT targets to `.npmjs.org` /
`.npmjs.com` only, by hostname — no TLS interception, no logging of package
contents (`cache deny all`).

Live-tested (this local Docker Desktop): a request to `registry.npmjs.org`
through the proxy returns `200`; a request to an arbitrary host (`example.com`)
through the same proxy returns a refused `CONNECT` (curl reports `000`).

## The part this does NOT solve by itself

Wiring `VITE_BUILD_EGRESS_PROXY_URL` sets `HTTP_PROXY`/`HTTPS_PROXY` inside
the build container (see `app/build.py` / `orchestrator/README.md`) —
**cooperative only**. `npm` and most well-behaved tools respect those env
vars, but nothing stops a malicious `postinstall` script in an untrusted
uploaded project from ignoring them and opening a direct TCP connection to
any host it likes, exactly as it can today. The proxy only becomes a real
control once direct outbound from `thtwaat_vite_build_net` is blocked at
the host firewall, forcing every connection through it.

**Required host firewall rule** (same category as
`deploy/security/block-metadata-docker.sh` — a `DOCKER-USER` iptables rule,
not a UFW rule, for the same reason documented there): pin
`thtwaat_vite_build_net`'s subnet at creation time
(`docker network create --subnet=172.30.0.0/24 thtwaat_vite_build_net`, or
whatever range doesn't collide with your other Docker networks) so it has a
fixed CIDR to reference, then:

```bash
EGRESS_PROXY_IP="$(docker inspect -f '{{.NetworkSettings.Networks.thtwaat_vite_build_net.IPAddress}}' thtwaat-vite-egress-proxy)"
iptables -I DOCKER-USER -s 172.30.0.0/24 -d "${EGRESS_PROXY_IP}" -j ACCEPT
iptables -I DOCKER-USER -s 172.30.0.0/24 -p udp --dport 53 -j ACCEPT   # DNS
iptables -I DOCKER-USER -s 172.30.0.0/24 -j DROP                       # everything else
```

This has **not** been live-tested (unlike the metadata-SSRF DOCKER-USER
rule in `deploy/security/block-metadata-docker.sh`, which was) — the
egress-proxy container's IP isn't stable across restarts the way a fixed
subnet is, so this rule needs re-applying (or scripting against the
container name via `docker inspect` at rule-application time, as above)
whenever the proxy container is recreated. Treat this as a documented
starting point for a real host, not a finished, validated mitigation.

## Residual risk if you don't apply the firewall rule

Exactly today's status quo: the build sandbox can reach any host on the
public internet, same as before this proxy existed. The proxy container
running is not, by itself, a security boundary — only the firewall rule
that forces traffic through it is. Say so explicitly in any deployment
sign-off rather than implying the proxy alone closes this gap.

## Enabling

```bash
docker build -t thtwaat-vite-egress-proxy ./docker/vite-build/egress-proxy
docker run -d --name thtwaat-vite-egress-proxy --network thtwaat_vite_build_net thtwaat-vite-egress-proxy
```

Then set `VITE_BUILD_EGRESS_PROXY_URL=http://thtwaat-vite-egress-proxy:3128`
on build-orchestrator (or on api/worker directly in direct mode) — see
`app/config/settings.py` / `orchestrator/app/settings.py`.
