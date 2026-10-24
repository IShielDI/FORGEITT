"""Submission handoff (stage 14): a summary of a change generated from its diff.

The summary comes from the diff, not from the agent's claims. If no model reply is usable, the
agent's own note is stored instead and labelled as such.
"""

import json
from typing import Any

from pydantic import BaseModel, Field

from app.core.db import ex, q1
from app.llm import prompts
from app.llm.client import LLMClient, LLMError, StructuredOutputError, get_client
from app.services import credits, gitops, knowledge

MAX_DIFF_CHARS = 12000


class Handoff(BaseModel):
    what_changed: list[str] = Field(default_factory=list, max_length=30)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    contract_deviations: list[str] = Field(default_factory=list, max_length=20)
    how_to_test: list[str] = Field(default_factory=list, max_length=20)


def generate(
    change_id: int, agent_note: str = "", client: LLMClient | None = None
) -> dict[str, Any]:
    ch = q1("SELECT * FROM changes WHERE id=?", (change_id,))
    if not ch:
        raise LookupError("no such change")
    diff = gitops.diff_stat(ch["room_id"], ch["branch"])
    contracts = (gitops.original(ch["room_id"]) / "protected/contracts/contracts.json").read_text()
    prompt = prompts.load("handoff")
    payload = {
        "agent_note": agent_note[:2000],
        "contracts": contracts[:4000],
        "diff_stat": diff["stat"],
        "diff": diff["diff"][:MAX_DIFF_CHARS],
    }
    try:
        client = client or get_client(ch["room_id"], ch["member_id"], label="handoff")
        reply = client.complete(
            [{"role": "user", "content": json.dumps(payload)}],
            schema=Handoff,
            system=prompt.text,
            prompt_version=prompt.tag,
        )
        if not isinstance(reply.data, Handoff):
            raise StructuredOutputError("handoff reply did not match the schema")
        summary: dict[str, Any] = {
            **reply.data.model_dump(),
            "source": "diff",
            "prompt": prompt.tag,
        }
    except (LLMError, credits.BudgetExceededError) as e:
        summary = {
            "what_changed": [agent_note or "(no note)"],
            "assumptions": [],
            "contract_deviations": [],
            "how_to_test": [],
            "source": "agent_note",
            "note": f"generated summary unavailable: {str(e)[:200]}",
        }
    ex("UPDATE changes SET handoff=? WHERE id=?", (json.dumps(summary), change_id))
    if ch["commit_sha"]:
        knowledge.link(ch["room_id"], "change", change_id, "commit", ch["commit_sha"], "produced")
    if ch["task_id"]:
        knowledge.link(ch["room_id"], "task", ch["task_id"], "change", change_id, "submitted_as")
    return summary
