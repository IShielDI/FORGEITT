# The agents' sandbox: the tools they need to run the visible tests, and nothing else.
# At run time it gets no network, no keys, only its own per-task clone (see app/services/agent_runner.py).
# Build once:  docker build -t forgeit-agent:latest sandbox/agent
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir pytest fastapi httpx uvicorn python-multipart \
 && useradd --create-home --uid 1000 agent
USER agent
WORKDIR /work
