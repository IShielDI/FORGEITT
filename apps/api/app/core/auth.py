"""Member logins and roles. A token is shown once (at room creation or when an invite is accepted);
only its hash is stored. Roles: owner, member, viewer (read-only)."""

import hashlib
import secrets

from fastapi import HTTPException, Request

from app.core import config
from app.core.db import q1


def new_token() -> str:
    return secrets.token_urlsafe(24)


def hash_token(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def actor(request: Request, rid: int, claimed: int | None = None):
    """The member who is acting. Reads 'Authorization: Bearer <token>' (or ?token= for the live stream, which cannot set headers).
    With REQUIRE_AUTH off (tests, offline rehearsal) it trusts the claimed member id instead."""
    if not config.REQUIRE_AUTH:
        if claimed is None:
            return None
        m = q1("SELECT * FROM members WHERE id=? AND room_id=?", (claimed, rid))
        if not m:
            raise HTTPException(404, "no such member in this room")
        return m
    h = request.headers.get("authorization", "")
    tok = h[7:] if h.lower().startswith("bearer ") else request.query_params.get("token", "")
    m = (
        q1("SELECT * FROM members WHERE room_id=? AND token_hash=?", (rid, hash_token(tok)))
        if tok
        else None
    )
    if not m:
        raise HTTPException(401, "sign in: send your room token as 'Authorization: Bearer <token>'")
    if claimed is not None and claimed != m["id"]:
        raise HTTPException(403, "you can only act as yourself")
    return m


def owner(request: Request, rid: int):
    m = actor(request, rid)
    if config.REQUIRE_AUTH and not m["is_owner"]:
        raise HTTPException(403, "only the workspace owner can do this")
    return m


def role_of(m) -> str:
    """owner | member | viewer. Older rows without a role fall back to the owner flag."""
    if not m:
        return ""
    return m.get("role") or ("owner" if m.get("is_owner") else "member")


def writer(request: Request, rid: int, claimed: int | None = None):
    """Like actor(), but viewers are read-only: they may look, never change anything."""
    m = actor(request, rid, claimed)
    if m and role_of(m) == "viewer":
        raise HTTPException(403, "viewers are read-only in this workspace")
    return m
