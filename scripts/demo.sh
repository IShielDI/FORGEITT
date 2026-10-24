#!/usr/bin/env bash
# ForgeIt demo (stage 23): the scripted end-to-end test, then the finale loop. Offline: mock models,
# scripted agents and the labelled referee stand-in. Nothing here needs keys.
set -euo pipefail
cd "$(dirname "$0")/../apps/api"
PY="${PYTHON:-python}"
[ -x .venv/Scripts/python ] && PY=.venv/Scripts/python
[ -x .venv/bin/python ] && PY=.venv/bin/python
echo "== end-to-end test: todo app (chat -> spec -> plan -> agents -> routed failure -> fix -> merge)"
"$PY" -m pytest -q -p no:cacheprovider tests/e2e
echo "== finale loop: task -> agent -> mirror -> referee -> human approval -> merge -> undo"
"$PY" ../../scripts/finale_demo.py
