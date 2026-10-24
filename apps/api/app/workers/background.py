"""In-process background worker: loan/request housekeeping, memory sweeps, and the referee pile."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from app.core.db import ex, q
from app.services import ledger, memory, orchestrator

TICK_SECONDS = 30


async def _loop() -> None:
    while True:
        await asyncio.sleep(TICK_SECONDS)
        for r in q("SELECT id FROM rooms"):
            try:
                ledger.housekeeping(r["id"])
                memory.sweep(r["id"])
                if orchestrator.pile_due(r["id"]):
                    await asyncio.to_thread(orchestrator.run_referee, r["id"])
            except Exception as e:  # keep the worker alive; one room must not stop the others
                print("background error", e)


@asynccontextmanager
async def lifespan(_app: Any) -> AsyncIterator[None]:
    ex("UPDATE agents SET status='idle' WHERE status='running'")  # a restart ends in-flight runs
    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        task.cancel()
