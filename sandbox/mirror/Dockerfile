# The mirror: a fresh container per check that runs the candidate's build, tests and app.
# Gets no keys and no platform secrets; tests run with no network (see app/services/mirror.py).
# Build once:  docker build -t forgeit-mirror:latest sandbox/mirror
FROM python:3.12-slim
RUN pip install --no-cache-dir pytest fastapi httpx uvicorn python-multipart ruff \
 && useradd --create-home --uid 1000 mirror
USER mirror
WORKDIR /work
