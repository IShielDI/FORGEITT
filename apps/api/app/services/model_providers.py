"""Which model providers a member can use right now: Claude on their own key, or a free tier on their own
key or the shared demo key. Keys are encrypted at rest and only their last 4 characters are ever shown."""

import time
from typing import Any

from app.core import config
from app.core.db import ex, q, q1
from app.llm import catalog
from app.services import ledger

LIVE_MODELS_TIMEOUT_S = 15
MAX_LIVE_MODELS = 60
OLLAMA_PROBE_TIMEOUT_S = 0.5
OLLAMA_PROBE_TTL_S = 30
_ollama_seen: dict[str, float | bool] = {"at": 0.0, "up": False}


class ProviderKeyError(ValueError):
    pass


def _own_key(member_id: int, provider: str) -> dict[str, Any] | None:
    return q1(
        "SELECT last4 FROM keys WHERE member_id=? AND provider=? AND status='active' ORDER BY id DESC",
        (member_id, provider),
    )


def ollama_up() -> bool:
    """Is Ollama answering on this machine? Checked at most every 30 s so listing stays fast."""
    import httpx

    if time.monotonic() - float(_ollama_seen["at"]) < OLLAMA_PROBE_TTL_S:
        return bool(_ollama_seen["up"])
    try:
        up = httpx.get(
            f"{config.OLLAMA_BASE_URL}/api/tags", timeout=OLLAMA_PROBE_TIMEOUT_S
        ).is_success
    except httpx.HTTPError:
        up = False
    _ollama_seen.update(at=time.monotonic(), up=up)
    return up


def overview(member_id: int) -> list[dict[str, Any]]:
    """Every provider with whether it is ready for this member and where the key comes from."""
    claude = _own_key(member_id, catalog.ANTHROPIC)
    rows: list[dict[str, Any]] = [
        {
            "id": catalog.ANTHROPIC,
            "label": "Claude (Anthropic)",
            "free": False,
            "needs_key": True,
            "signup_url": "https://console.anthropic.com/settings/keys",
            "note": "Paid. Runs on your own key and your credits in this workspace.",
            "models": [
                r["model"]
                for r in q("SELECT model FROM prices ORDER BY input")
                if not catalog.is_free(r["model"]) and r["model"] not in ("mock", "scripted")
            ],
            "ready": bool(claude),
            "source": "yours" if claude else None,
            "key_last4": claude["last4"] if claude else None,
        }
    ]
    for p in catalog.CATALOG:
        own = _own_key(member_id, p.id) if p.needs_key else None
        demo = bool(catalog.demo_key(p.id))
        if not p.needs_key:
            source = "local" if ollama_up() else None
        else:
            source = "yours" if own else "demo" if demo else None
        rows.append(
            {
                "id": p.id,
                "label": p.label,
                "free": True,
                "needs_key": p.needs_key,
                "signup_url": p.signup_url,
                "note": p.note,
                "models": [f"{p.id}:{m}" for m in p.models],
                "ready": source is not None,
                "source": source,
                "key_last4": own["last4"] if own else None,
            }
        )
    return rows


def save_key(member_id: int, provider: str, key: str) -> str:
    """Store a member's key for a free provider (replacing the old one). Returns its last 4 characters."""
    key = key.strip()
    problem = catalog.key_problem(provider, key)
    if problem:
        raise ProviderKeyError(problem)
    ex(
        "UPDATE keys SET status='replaced' WHERE member_id=? AND provider=? AND status='active'",
        (member_id, provider),
    )
    ledger.add_key(member_id, provider, "plain", key)
    return key[-4:]


def remove_key(member_id: int, provider: str) -> None:
    ex(
        "UPDATE keys SET status='removed' WHERE member_id=? AND provider=? AND status='active'",
        (member_id, provider),
    )


def live_models(member_id: int, provider: str, http: Any = None) -> list[str]:
    """Ask the provider which models exist now (free lists change often). OpenRouter: only ':free' ones."""
    import httpx

    info = catalog.get(provider)
    if info is None:
        raise ProviderKeyError(f"unknown provider '{provider}'")
    key = ledger.free_key(member_id, provider)
    if info.needs_key and not key:
        raise ProviderKeyError(f"no {info.label} key yet")
    client = http or httpx.Client(timeout=LIVE_MODELS_TIMEOUT_S)
    try:
        r = client.get(
            f"{catalog.base_url(info)}/models",
            headers={"Authorization": f"Bearer {key}"} if key else {},
        )
    except httpx.HTTPError as e:
        raise ProviderKeyError(f"{info.label} did not answer ({type(e).__name__})") from e
    if r.status_code >= 400:
        raise ProviderKeyError(f"{info.label} refused the request (HTTP {r.status_code})")
    data = r.json()
    items = data.get("data", data) if isinstance(data, dict) else data
    ids = []
    for m in items if isinstance(items, list) else []:
        mid = str(m.get("id", "")) if isinstance(m, dict) else str(m)
        mid = mid.removeprefix("models/")  # Gemini names its models "models/<id>"
        if not mid or (provider == "openrouter" and not mid.endswith(":free")):
            continue
        ids.append(f"{provider}:{mid}")
    return sorted(set(ids))[:MAX_LIVE_MODELS]
