"""Model providers API: list, paste a free key, remove it, and run with a free model."""

from app.core import config


def _riya(api, room):
    return next(m for m in api.get(f"/api/rooms/{room}").json()["members"] if m["name"] == "riya")[
        "id"
    ]


def test_list_save_and_remove_a_free_key(api, room, monkeypatch):
    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {})
    mid = _riya(api, room)

    rows = api.get(f"/api/rooms/{room}/me/providers?member={mid}").json()
    assert rows[0]["id"] == "anthropic" and {r["id"] for r in rows} >= {
        "groq",
        "gemini",
        "openrouter",
    }

    bad = api.put(f"/api/rooms/{room}/me/keys/groq?member={mid}", json={"key": "nope nope"})
    assert bad.status_code == 400

    r = api.put(f"/api/rooms/{room}/me/keys/groq?member={mid}", json={"key": "gsk_live_key_9876"})
    assert r.json() == {"provider": "groq", "key_last4": "9876"}
    me = api.get(f"/api/rooms/{room}/me?member={mid}").json()
    assert "groq" in me["ready_providers"] and "gsk_live" not in str(me)

    assert api.delete(f"/api/rooms/{room}/me/keys/groq?member={mid}").status_code == 200
    assert "groq" not in api.get(f"/api/rooms/{room}/me?member={mid}").json()["ready_providers"]


def test_free_models_are_listed_and_accepted_without_a_price(api, room):
    from app.routers.rooms import _known_model

    assert "groq:llama-3.3-70b-versatile" in api.get("/api/models").json()
    _known_model("groq:anything-new")  # free tiers need no price row

    agent = api.get(f"/api/rooms/{room}/catalog").json()[0]["key"]
    r = api.post(
        f"/api/rooms/{room}/run",
        json={"agent": agent, "task": "x", "model": "gpt-unpriced", "member_id": _riya(api, room)},
    )
    assert r.status_code == 400 and "no price" in r.json()["detail"]
