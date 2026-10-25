# ADR-007: One always-on Linux server for a permanent deployment

**Status:** accepted

**Context.** ForgeIt began local first (TRD §9): the laptop runs the backend, the web app and Docker, and a temporary Cloudflare quick tunnel gives it a public address. That address changes on every restart and disappears when the laptop sleeps. A permanent deployment still needs Docker on the same machine: every agent command runs in a fresh `forgeit-agent` container (ADR-003) and the mirror starts candidate apps in containers. Serverless hosts cannot start containers, so they cannot run ForgeIt.

**Decision.** Run the same three pieces on one small Linux VM with `docker compose` (`docker-compose.yml`): the API, the web app and Caddy. `scripts/deploy/setup-server.sh` installs Docker, builds the sandbox images and starts everything.
- **Host networking** for all three, matching the laptop: the mirror publishes the candidate app on the host's 127.0.0.1 and the referee's tunnel must reach it there. Only Caddy listens publicly (80/443); the API and the web app listen on loopback.
- **Caddy** obtains HTTPS certificates automatically, sends `/api/*` (including the chat WebSocket) to the API and everything else to the web app. Without a domain, the free `<ip>.sslip.io` name is used.
- **The API reaches the host's Docker through its socket** to start sandboxes. Data lives at `/srv/forgeit/data` on the host and is mounted at the same path in the API container, so the paths it hands to Docker are valid for the sibling containers.
- **The API runs as a regular user (uid 1000)**, so agent sandboxes also run as uid 1000, never root.

**Consequences.**
- The site stays up without the laptop, at a fixed address, with HTTPS.
- Access to the Docker socket is root-equivalent on that host. Only platform code holds it, never agent or candidate code, which still runs in the locked-down containers of ADR-003. Use a dedicated VM, not a shared machine.
- One VM means one SQLite database and one in-process background worker, which matches the current design (no horizontal scaling).
- Keys stay in the server's `.env` (mode 600) and the encrypted key store under `/srv/forgeit/data/state`; back that folder up.
