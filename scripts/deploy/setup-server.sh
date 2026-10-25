#!/usr/bin/env bash
# Set up ForgeIt on a fresh Ubuntu 22.04/24.04 server and start it (docs/adr/ADR-007-always-on-server.md).
#
#   git clone <your repo> forgeit && cd forgeit
#   bash scripts/deploy/setup-server.sh                 # free address: <server-ip>.sslip.io
#   bash scripts/deploy/setup-server.sh forgeit.example.com   # your own domain (point its A record here first)
#
# Safe to run again: it keeps an existing .env and only fills in what is missing.
set -euo pipefail
cd "$(dirname "$0")/../.."

DOMAIN="${1:-}"
DATA=/srv/forgeit/data
APP_UID=1000

say() { printf '\n== %s\n' "$*"; }

if ! command -v docker >/dev/null 2>&1; then
  say "Installing Docker (official convenience script from get.docker.com)"
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo systemctl enable --now docker >/dev/null 2>&1 || true

if [ -z "$DOMAIN" ]; then
  IP="$(curl -fsS https://api.ipify.org)"
  DOMAIN="${IP//./-}.sslip.io"
  say "No domain given: using the free address $DOMAIN (sslip.io maps it to $IP)"
fi

say "Data folder $DATA (managed repos, database, encryption key, evidence)"
sudo mkdir -p "$DATA"
sudo chown -R "$APP_UID:$APP_UID" "$DATA"

say "Settings in .env"
[ -f .env ] || cp .env.example .env
set_env() {  # set KEY=VALUE, replacing an existing line
  if grep -q "^$1=" .env; then sed -i "s#^$1=.*#$1=$2#" .env; else printf '%s=%s\n' "$1" "$2" >> .env; fi
}
set_env FORGEIT_DOMAIN "$DOMAIN"
set_env DOCKER_GID "$(getent group docker | cut -d: -f3)"
grep -q '^SECRET_KEY=change-me' .env && set_env SECRET_KEY "$(openssl rand -hex 32)"
grep -q '^LLM_PROVIDER=mock' .env && set_env LLM_PROVIDER auto
grep -q '^VERIFICATION_PROFILE=fast' .env && set_env VERIFICATION_PROFILE standard
chmod 600 .env

say "Opening ports 80 and 443 (if a ufw firewall is active)"
if command -v ufw >/dev/null 2>&1 && sudo ufw status | grep -q active; then
  sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
fi

say "Building the sandbox images (agent commands and checks run in these)"
sudo docker build -t forgeit-agent:latest sandbox/agent
sudo docker build -t forgeit-mirror:latest sandbox/mirror

say "Building and starting ForgeIt"
sudo docker compose up -d --build

say "Done. ForgeIt will be at https://$DOMAIN"
echo "   The HTTPS certificate is issued on the first visit (allow a minute)."
echo "   Add your keys to .env (GEMINI_API_KEY, TINYFISH_API_KEY, SMTP_*), then: sudo docker compose up -d"
echo "   Logs: sudo docker compose logs -f api"
