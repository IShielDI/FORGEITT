"""Test-only stand-in for a model: replays a fixed plan, costs nothing. Never imported by the product code."""

import uuid

from app.llm.providers import Reply, Usage


class ScriptedProvider:
    """Each turn is a list of ('text', str) or ('tool', name, input) items."""

    name = "scripted"

    def __init__(self, turns):
        self.turns, self.i = turns, 0

    def complete(self, system, messages, max_tokens):
        if self.i >= len(self.turns):
            return Reply(
                [{"type": "text", "text": "done"}], call_id=f"s{self.i}", stop_reason="end_turn"
            )
        turn = self.turns[self.i]
        self.i += 1
        blocks = []
        for it in turn:
            if it[0] == "text":
                blocks.append({"type": "text", "text": it[1]})
            else:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": "tu_" + uuid.uuid4().hex[:8],
                        "name": it[1],
                        "input": it[2],
                    }
                )
        return Reply(
            blocks,
            Usage(),
            f"s{self.i}",
            "tool_use" if any(b["type"] == "tool_use" for b in blocks) else "end_turn",
        )
