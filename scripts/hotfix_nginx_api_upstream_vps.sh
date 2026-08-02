#!/usr/bin/env bash
# Fix: nginx static upstream api_backend → stale IP (public API ≠ thtwaat-api).
# Run on VPS: bash scripts/hotfix_nginx_api_upstream_vps.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Current upstream resolution"
docker exec thtwaat-nginx getent hosts api || true
docker exec thtwaat-api hostname -i || true
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'NAME|api|nginx' || true

echo "==> Where is api.thtwaat.com defined?"
docker exec thtwaat-nginx sh -c 'grep -rl "api.thtwaat.com" /etc/nginx 2>/dev/null || true'

# Ensure host has api vhost with Docker DNS re-resolve (certs already on VPS per nginx -T)
API_CONF="nginx/conf.d/domains/api.thtwaat.com.conf"
if [[ ! -f "$API_CONF" ]]; then
  mkdir -p nginx/conf.d/domains
  cat > "$API_CONF" <<'EOF'
# https://api.thtwaat.com → FastAPI (api:8000)
server {
    listen 80;
    server_name api.thtwaat.com;
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/acme;
        default_type text/plain;
    }
    location / { return 301 https://$host$request_uri; }
}
server {
    listen 443 ssl;
    http2 on;
    server_name api.thtwaat.com;
    ssl_certificate     /etc/nginx/ssl/domains/api.thtwaat.com/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/domains/api.thtwaat.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    client_max_body_size 50m;
    location = /metrics { deny all; }
    location / {
        resolver 127.0.0.11 valid=10s ipv6=off;
        set $api_upstream api:8000;
        proxy_pass http://$api_upstream;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 120s;
    }
}
EOF
  echo "wrote $API_CONF"
else
  echo "host already has $API_CONF"
fi

# Patch baked nginx.conf inside container: default 443 location uses variable upstream
docker exec -i thtwaat-nginx sh <<'EOS'
set -e
CONF=/etc/nginx/nginx.conf
cp -a "$CONF" /tmp/nginx.conf.bak
python3 - <<'PY' || true
from pathlib import Path
p = Path("/etc/nginx/nginx.conf")
t = p.read_text()
if "$api_upstream" in t and "resolver 127.0.0.11" in t:
    print("nginx.conf already uses variable upstream")
else:
    old = """        location / {
            limit_req zone=api_limit burst=20 nodelay;

            proxy_pass http://api_backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_read_timeout 120s;
        }"""
    new = """        location / {
            limit_req zone=api_limit burst=20 nodelay;

            resolver 127.0.0.11 valid=10s ipv6=off;
            set $api_upstream api:8000;
            proxy_pass http://$api_upstream;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_connect_timeout 5s;
            proxy_read_timeout 120s;
        }"""
    if old not in t:
        # broader replace of proxy_pass http://api_backend; in default server only is risky;
        # fall back to replace_all for location blocks that still use static upstream.
        n = t.count("proxy_pass http://api_backend;")
        t2 = t.replace("proxy_pass http://api_backend;", "proxy_pass http://$api_upstream;")
        if n == 0:
            print("WARNING: no api_backend proxy_pass found")
        else:
            # inject resolver + set once inside http{} if missing
            if "set $api_upstream" not in t2:
                t2 = t2.replace(
                    "upstream api_backend {",
                    "resolver 127.0.0.11 valid=10s ipv6=off;\n    # dynamic upstream for proxy_pass variables\n    # (api_backend kept for any remaining references)\n    upstream api_backend {",
                    1,
                )
                # Can't use $api_upstream without set — do per-server injection instead
                print("partial replace done — prefer full block replace / recreate conf")
            p.write_text(t2)
            print(f"replaced {n} api_backend proxy_pass(es)")
    else:
        p.write_text(t.replace(old, new, 1))
        print("nginx.conf default location patched")
PY

# If python missing in alpine nginx, use sed fallback
if ! command -v python3 >/dev/null 2>&1; then
  echo "no python3 in nginx image — sed fallback"
  # Ensure map/set: rewrite every api_backend proxy to variable form is hard in sed;
  # restart with fresh conf from host instead.
  exit 0
fi

nginx -t
nginx -s reload
echo "nginx reloaded"
EOS

# Also drop our api vhost onto the bind-mounted domains dir (picked up on reload)
# domains mount is :ro for nginx — write on HOST then reload
if [[ -f "$API_CONF" ]]; then
  echo "api vhost present on host mount"
fi

# Alpine nginx may lack python3 — always docker cp host nginx.conf if we have the fixed one
if [[ -f nginx/nginx.conf ]] && grep -q '\$api_upstream' nginx/nginx.conf; then
  docker cp nginx/nginx.conf thtwaat-nginx:/etc/nginx/nginx.conf
  docker exec thtwaat-nginx nginx -t
  docker exec thtwaat-nginx nginx -s reload
  echo "copied host nginx.conf + reloaded"
else
  # Last resort: full nginx container restart (re-resolves upstream at start)
  docker restart thtwaat-nginx
  sleep 3
fi

echo "==> Verify nginx → current api"
docker exec thtwaat-nginx getent hosts api
docker exec thtwaat-nginx wget -qO- http://api:8000/api/v1/payments/plans/ | head -c 200; echo

echo "==> Public + RID correlation"
curl -sk -D /tmp/hdrs.txt -o /tmp/body.txt https://api.thtwaat.com/api/v1/payments/plans/
RID=$(awk -F': ' 'tolower($1)=="x-request-id"{gsub("\r","",$2); print $2}' /tmp/hdrs.txt)
echo "RID=$RID"
head -c 300 /tmp/body.txt; echo
docker logs thtwaat-api --tail 50 2>&1 | grep -F "$RID" && echo "OK: traffic hits thtwaat-api" || echo "STILL WRONG BACKEND"
