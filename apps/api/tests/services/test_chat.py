import pytest

from app.services import chat
from tests.integration.test_platform import ids


def test_post_and_history_in_order(api, room):
    riya = ids(api, room)["riya"]
    for text in ("one", "two", "three"):
        chat.post(room, riya, text)

    page = chat.history(room)
    assert [m["body"] for m in page] == ["one", "two", "three"]
    assert page[0]["author"] == "riya"


def test_pagination_before_id(api, room):
    riya = ids(api, room)["riya"]
    msgs = [chat.post(room, riya, f"m{i}") for i in range(5)]

    older = chat.history(room, before=msgs[3]["id"], limit=2)
    assert [m["body"] for m in older] == ["m1", "m2"]


@pytest.mark.parametrize("body", ["", "   ", "x" * (chat.MAX_BODY + 1)])
def test_rejects_empty_or_oversized(api, room, body):
    with pytest.raises(ValueError):
        chat.post(room, ids(api, room)["riya"], body)


def test_since_returns_only_newer(api, room):
    riya = ids(api, room)["riya"]
    first = chat.post(room, riya, "a")
    chat.post(room, riya, "b")

    assert [m["body"] for m in chat.since(room, first["id"])] == ["b"]
