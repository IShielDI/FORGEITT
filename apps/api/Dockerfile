# ForgeIt API for an always-on server (docs/adr/ADR-007-always-on-server.md).
# Build from the repo root: docker build -f apps/api/Dockerfile .
# It starts agent sandboxes and mirror containers through the host's Docker socket, so it ships the
# Docker CLI, plus git (managed repos) and cloudflared (the referee's temporary tunnel).
FROM python:3.11-slim

ARG CLOUDFLARED_VERSION=2026.10.3
ARG APP_UID=1000

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && curl -fsSL -o /usr/local/bin/cloudflared \
       "https://github.com/cloudflare/cloudflared/releases/download/${CLOUDFLARED_VERSION}/cloudflared-linux-$(dpkg --print-architecture)" \
    && chmod +x /usr/local/bin/cloudflared \
    && rm -rf /var/lib/apt/lists/*

# A regular user: agent sandboxes run as this same uid (agent_runner._container_user), never root.
RUN useradd --uid "${APP_UID}" --create-home forgeit

# Same layout as the repo, so config.REPO_ROOT (/app) finds samples/ for the workspace templates.
WORKDIR /app
COPY apps/api /app/apps/api
COPY samples /app/samples
RUN pip install --no-cache-dir -e /app/apps/api

USER forgeit
WORKDIR /app/apps/api
ENV PYTHONUNBUFFERED=1
# Host networking (docker-compose.yml): only Caddy faces the internet; the API listens on loopback.
CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--proxy-headers"]
