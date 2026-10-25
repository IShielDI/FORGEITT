# ForgeIt web app for an always-on server. Build from apps/web: docker build apps/web
FROM node:20-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /web
ENV NODE_ENV=production
COPY --from=build /web/package.json /web/package-lock.json /web/next.config.js ./
COPY --from=build /web/node_modules ./node_modules
COPY --from=build /web/.next ./.next
USER node
# Host networking: Caddy reaches this on loopback; /api/* goes straight to the API (BACKEND_URL).
CMD ["node_modules/.bin/next", "start", "-p", "3000", "-H", "127.0.0.1"]
