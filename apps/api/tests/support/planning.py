"""Helpers that set up an approved spec and a mock plan for planner/knowledge/context tests."""

import json

from app.core.db import ex, now
from app.llm.client import LLMClient
from app.llm.providers import MockChat
from app.services import planner, spec


def approved_spec(room: int) -> dict[str, int]:
    """Confirm three spec items and return their ids by name."""
    ids = {}
    for name, kind, text in (
        ("login", "requirement", "Users can sign up and log in"),
        ("cart", "requirement", "Users can add items to a cart"),
        ("sqlite", "suggestion", "Use SQLite"),
    ):
        iid = ex(
            "INSERT INTO spec_items(room_id,kind,text,status,created) VALUES(?,?,?,'proposed',?)",
            (room, kind, text, now()),
        )
        spec.confirm(iid, None)
        ids[name] = iid
    return ids


def plan_reply(ids: dict[str, int], cycle: bool = False) -> str:
    return json.dumps(
        {
            "contracts": [
                {
                    "kind": "schema",
                    "name": "db",
                    "content": "users(email), cart(email, product)",
                    "spec_item_ids": [ids["sqlite"]],
                },
                {
                    "kind": "api",
                    "name": "shop-api",
                    "content": '{"paths": {"/signup": {"post": {}}}}',
                    "spec_item_ids": [ids["login"]],
                },
            ],
            "tasks": [
                {
                    "key": "db",
                    "title": "Database",
                    "component": "database",
                    "depends_on": ["api"] if cycle else [],
                    "suggested_owner": "kriti",
                    "spec_item_ids": [ids["sqlite"]],
                    "contracts": ["db"],
                },
                {
                    "key": "api",
                    "title": "Signup API",
                    "component": "backend",
                    "depends_on": ["db"],
                    "suggested_owner": "aman",
                    "spec_item_ids": [ids["login"]],
                    "contracts": ["db", "shop-api"],
                },
                {
                    "key": "ui",
                    "title": "Cart page",
                    "component": "frontend",
                    "depends_on": ["api"],
                    "suggested_owner": "riya",
                    "spec_item_ids": [ids["cart"]],
                    "contracts": ["shop-api"],
                },
            ],
        }
    )


def proposed_plan(room: int) -> dict[str, int]:
    ids = approved_spec(room)
    planner.generate(room, LLMClient(MockChat([plan_reply(ids)]), room))
    return ids
