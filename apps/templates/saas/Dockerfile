FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* .npmrc ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_API_URL=https://api.thtwaat.com
ARG NEXT_PUBLIC_SITE_URL=https://app.thtwaat.com
ARG NEXT_PUBLIC_SITE_NAME=THTWAAT
ARG NEXT_PUBLIC_BRAND_COLOR=#0f766e
ARG NEXT_PUBLIC_RAZORPAY_KEY_ID=

ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_SITE_NAME=$NEXT_PUBLIC_SITE_NAME \
    NEXT_PUBLIC_BRAND_COLOR=$NEXT_PUBLIC_BRAND_COLOR \
    NEXT_PUBLIC_RAZORPAY_KEY_ID=$NEXT_PUBLIC_RAZORPAY_KEY_ID

# Refuse accidental IP / localhost bake-ins for production images.
RUN echo "$NEXT_PUBLIC_API_URL" | grep -Eq '^https://api\.thtwaat\.com/?$' \
    || (echo "NEXT_PUBLIC_API_URL must be https://api.thtwaat.com (got: $NEXT_PUBLIC_API_URL)" >&2 && exit 1)

RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3300

RUN addgroup -S nodejs && adduser -S nextjs -G nodejs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3300
# Docker overwrites HOSTNAME with the container id; force 0.0.0.0 so nginx can reach the app.
CMD ["sh", "-c", "export HOSTNAME=0.0.0.0; export PORT=${PORT:-3300}; exec node server.js"]
