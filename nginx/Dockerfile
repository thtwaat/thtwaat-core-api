FROM nginx:alpine
RUN apk add --no-cache openssl \
    && mkdir -p /etc/nginx/ssl /etc/nginx/conf.d/domains /var/www/acme/.well-known/acme-challenge \
    && openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/server.key \
    -out /etc/nginx/ssl/server.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
COPY nginx.conf /etc/nginx/nginx.conf
# Empty conf.d include target (avoids nginx fail if no domains yet)
RUN touch /etc/nginx/conf.d/domains/.keep
