"""Credits for platform model calls, on top of the existing ledger (TRD R13).

Every call writes a ledger row (which also records the 70/80/90% checkpoints). A member whose
portion is used up is stopped before the call: the hard stop at 100%.
"""

from app.core.db import ex, q1
from app.llm import catalog
from app.services import events, ledger

FREE_PROVIDERS = ("mock", *catalog.IDS)  # the free tiers and local Ollama cost no credits


class BudgetExceededError(Exception):
    pass


def price_key(provider: str, model: str) -> str:
    if provider == "mock":
        return "mock"
    return f"{provider}:{model}" if provider in catalog.IDS else model


def _ensure_free_price(provider: str, model: str) -> None:
    if provider in FREE_PROVIDERS:
        ex("INSERT OR IGNORE INTO prices VALUES(?,0,0,0,0)", (price_key(provider, model),))


def ensure_budget(room_id: int, member_id: int | None, provider: str) -> None:
    """Refuse the call when the member has nothing left (free providers are never blocked)."""
    if member_id is None or provider in FREE_PROVIDERS:
        return
    if ledger.balance(room_id, member_id)[
        "remaining"
    ] <= ledger.BUFFER and not ledger.house_available(room_id, member_id):
        raise BudgetExceededError(
            "your credits for this workspace are used up: add more or ask a teammate"
        )


def charge(
    room_id: int,
    member_id: int | None,
    label: str,
    provider: str,
    model: str,
    tin: int,
    tout: int,
    call_id: str,
) -> dict:
    """Record one platform call in the ledger and announce any checkpoint crossed."""
    if member_id is None:  # bill the owner when no member triggered it (e.g. a background job)
        owner = q1("SELECT id FROM members WHERE room_id=? AND is_owner=1 ORDER BY id", (room_id,))
        member_id = owner["id"] if owner else 0
    _ensure_free_price(provider, model)
    paid_by_house = (
        provider not in FREE_PROVIDERS
        and ledger.balance(room_id, member_id)["own_remaining"] <= ledger.BUFFER
        and ledger.house_available(room_id, member_id)
    )
    res = ledger.record_call(
        room_id,
        member_id,
        label,
        price_key(provider, model),
        call_id,
        tin,
        tout,
        0,
        0,
        None,
        source="house" if paid_by_house else None,
    )
    if res["checkpoint"]:
        events.emit(
            room_id, label, "budget", {"checkpoint": res["checkpoint"], "member_id": member_id}
        )
    return res
