# SETUP.md

How to prepare a machine and the repo so you can build this project stage by stage.

## 1. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Git | 2.40+ | |
| Python | 3.11+ | |
| Node.js | 20 LTS+ | |
| Docker | Docker Desktop or Docker Engine | Windows: enable WSL2 backend |
| A code editor | VS Code or similar | |
| A coding agent (optional) | Aider / Claude Code / Cursor / Copilot | To run the stage prompts |
| An LLM API key | Gemini or Groq free tier, or Ollama locally | For the platform's own agents |

Check:
```
git --version && python --version && node --version && docker --version
```

## 2. Create the GitHub Repo
```
cd FORGEITT                        # docs/ and root files are already in place (see AGENTS.md "File Placement")
git init -b main
git add . && git commit -m "docs: add PRD, TRD, architecture, agents and build plan (stage 0)"
git remote add origin https://github.com/<you>/ai-collab-workspace.git
git push -u origin main
```

## 3. Protect `main` on GitHub
Settings, Branches, Add rule for `main`:
- Require a pull request before merging
- Require status checks to pass (add CI once stage 1 lands)
- Block force pushes

Workflow per stage: `git switch -c stage/NN-name`, build, commit, push, PR, merge. This keeps history as one clean commit (or few) per stage.

## 4. Environment Variables
Create `.env` from `.env.example` (created in stage 1). Never commit `.env`.
```
DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/collab
LLM_PROVIDER=gemini            # gemini | groq | openrouter | ollama | mock
LLM_MODEL=<model name>
GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
SECRET_KEY=change-me
GIT_STORAGE_PATH=./data/git
ARTIFACT_PATH=./data/artifacts
SANDBOX_IMAGE=collab-agent:latest
VERIFICATION_PROFILE=light
```
Use `LLM_PROVIDER=mock` for development without keys.

## 5. First Run (after stage 1)
```
docker compose up -d db
cd apps/api && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload            # http://localhost:8000/docs

# new terminal
cd apps/web && npm install && npm run dev   # http://localhost:3000
```

## 6. Free Tier Options
- **LLM:** Gemini API free tier, Groq free tier, OpenRouter free models, or Ollama locally. Limits change; check each provider.
- **DB hosting (optional):** Neon or Supabase free Postgres.
- **Web hosting (optional):** Vercel. **API hosting (optional):** Render or Fly.io.
- **CI:** GitHub Actions free minutes.
- Sandboxes need Docker, so run them locally or on a VM for demos.

## 7. Building the Sandbox Images (stage 12)
```
docker build -t collab-agent:latest sandbox/agent
docker build -t collab-mirror:latest sandbox/mirror
```

## 8. Running Tests
```
cd apps/api && pytest -q
cd apps/web && npm test
```

## 9. Using a Coding Agent on the Stages
1. Open the repo in your agent.
2. Tell it: "Read AGENTS.md and docs/. Implement only Stage N from BUILD_PROMPTS.md."
3. Paste the stage prompt.
4. Run tests, review the diff, commit with the suggested message, open a PR.

## 10. Troubleshooting
- **Docker permission denied (Linux):** add your user to the `docker` group and re-login.
- **Windows path issues:** work inside WSL2 and keep the repo in the Linux filesystem.
- **Port in use:** change ports in `docker-compose.yml` and `.env`.
- **LLM rate limit:** switch provider or set `LLM_PROVIDER=mock`.
