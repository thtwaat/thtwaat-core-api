#!/bin/sh
# nginx's own container is the only one with both the nginx binary and direct
# filesystem access to the SSL Manager's generated vhosts/certs. api/worker
# containers have neither Docker socket access nor a local nginx binary, so
# their reload_nginx() attempts (app/ssl/nginx_gen.py) always fail silently —
# newly issued domains sat on the shared volume unreloaded, stuck on nginx's
# self-signed default_server cert. This watches the two paths the SSL Manager
# writes to and reloads nginx itself whenever they change.
set -e

nginx -g "daemon off;" &
NGINX_PID=$!

trap 'kill -QUIT "$NGINX_PID" 2>/dev/null' TERM INT QUIT

(
  while true; do
    inotifywait -r -e create,modify,delete,move,close_write \
      /etc/nginx/conf.d/domains /etc/nginx/ssl 2>/dev/null
    sleep 1
    nginx -t 2>/dev/null && nginx -s reload
  done
) &

wait "$NGINX_PID"
