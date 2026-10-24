"""Single-use invites (TRD R14). Links expire after INVITE_TTL_DAYS and are stored only as hashes.

Accepting an invite creates the member and issues their own login token (shown once). A room name or
slug is never accepted as a credential.
"""

from app.core import auth, config
from app.core.db import ex, now, q, q1
from app.services import mail

ROLES = ("owner", "member", "viewer")
INVITABLE_ROLES = ("member", "viewer")
DAY_S = 86400


class InviteError(Exception):
    """Raised with a stable `code`: unknown, used or expired."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def create(
    room_id: int,
    created_by: int | None,
    role: str = "member",
    email: str = "",
    member_id: int | None = None,
) -> dict:
    """Make an invite. Returns the raw link once (only its hash is stored) and whether it was mailed.
    With member_id, the invite is for a member slot made at workspace creation: accepting it signs
    the person in as that member instead of adding a new one."""
    if role not in INVITABLE_ROLES:
        raise ValueError(f"role must be one of {', '.join(INVITABLE_ROLES)}")
    room = q1("SELECT name FROM rooms WHERE id=?", (room_id,))
    if not room:
        raise ValueError("no such room")
    token = auth.new_token()
    expires = now() + config.INVITE_TTL_DAYS * DAY_S
    iid = ex(
        "INSERT INTO invites(room_id,token_hash,role,email,created_by,created,expires,member_id) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (
            room_id,
            auth.hash_token(token),
            role,
            email.strip(),
            created_by,
            now(),
            expires,
            member_id,
        ),
    )
    link = f"{config.PUBLIC_WEB_URL}/invite/{token}"
    mailed = mail.send_invite(
        email.strip(),
        room["name"],
        room_id,
        link,
        token,
        config.INVITE_TTL_DAYS,
        config.PUBLIC_WEB_URL,
    )
    return {
        "id": iid,
        "role": role,
        "link": link,
        "token": token,
        "expires": expires,
        "mailed": mailed,
    }


def _find(token: str) -> dict:
    inv = (
        q1("SELECT * FROM invites WHERE token_hash=?", (auth.hash_token(token),)) if token else None
    )
    if not inv:
        raise InviteError("unknown", "this invite link is not valid")
    if inv["used_at"] is not None:
        raise InviteError("used", "this invite link has already been used")
    if inv["expires"] <= now():
        raise InviteError("expired", "this invite link has expired: ask the owner for a new one")
    return inv


def peek(token: str) -> dict:
    """What an invite is for, without using it (room name, role, and the invited email to pre-fill)."""
    inv = _find(token)
    room = q1("SELECT name FROM rooms WHERE id=?", (inv["room_id"],))
    return {
        "room_id": inv["room_id"],
        "room_name": room["name"] if room else "",
        "role": inv["role"],
        "email": inv["email"] or "",
        "name": _slot_name(inv),  # set when the owner already named this teammate
    }


def _slot_name(inv: dict) -> str:
    if not inv.get("member_id"):
        return ""
    m = q1("SELECT name FROM members WHERE id=?", (inv["member_id"],))
    return m["name"] if m else ""


def _claim_slot(inv: dict, email: str) -> dict:
    """Accept an invite bound to a member made at creation: give that member a fresh login token."""
    m = q1("SELECT * FROM members WHERE id=? AND room_id=?", (inv["member_id"], inv["room_id"]))
    if not m:
        raise InviteError("unknown", "this invite link is not valid")
    ex(
        "UPDATE invites SET used_at=?, used_by=? WHERE id=? AND used_at IS NULL",
        (now(), m["id"], inv["id"]),
    )
    if q1("SELECT used_by FROM invites WHERE id=?", (inv["id"],))["used_by"] != m["id"]:
        raise InviteError("used", "this invite link has already been used")
    member_token = auth.new_token()  # replaces any earlier token: only the invitee holds this login
    address = email.strip() or inv["email"] or m["email"] or ""
    ex(
        "UPDATE members SET token_hash=?, email=? WHERE id=?",
        (auth.hash_token(member_token), address, m["id"]),
    )
    room = q1("SELECT name FROM rooms WHERE id=?", (inv["room_id"],))
    mailed = bool(address) and mail.send_credentials(
        address,
        room["name"] if room else "",
        inv["room_id"],
        m["name"],
        member_token,
        config.PUBLIC_WEB_URL,
    )
    return {
        "room_id": inv["room_id"],
        "member_id": m["id"],
        "name": m["name"],
        "role": auth.role_of(m),
        "token": member_token,
        "mailed": mailed,
    }


def accept(token: str, name: str, email: str = "") -> dict:
    """Use the invite: create the member, mark the invite used, return the member's login token once."""
    inv = _find(token)
    if inv.get("member_id"):
        return _claim_slot(inv, email)
    name = name.strip()
    if not name:
        raise ValueError("say your name")
    rid = inv["room_id"]
    if q1("SELECT 1 x FROM members WHERE room_id=? AND name=?", (rid, name)):
        raise ValueError("someone in this workspace already uses that name: pick another")
    member_token = auth.new_token()
    address = email.strip() or inv["email"] or ""
    mid = ex(
        "INSERT INTO members(room_id,name,email,token_hash,is_owner,role) VALUES(?,?,?,?,0,?)",
        (
            rid,
            name,
            address,
            auth.hash_token(member_token),
            inv["role"],
        ),
    )
    # single use: only succeeds if nobody used it in the meantime
    ex(
        "UPDATE invites SET used_at=?, used_by=? WHERE id=? AND used_at IS NULL",
        (now(), mid, inv["id"]),
    )
    if q1("SELECT used_by FROM invites WHERE id=?", (inv["id"],))["used_by"] != mid:
        ex("DELETE FROM members WHERE id=?", (mid,))
        raise InviteError("used", "this invite link has already been used")
    room = q1("SELECT name FROM rooms WHERE id=?", (rid,))
    mailed = bool(address) and mail.send_credentials(  # their login for other devices
        address, room["name"] if room else "", rid, name, member_token, config.PUBLIC_WEB_URL
    )
    return {
        "room_id": rid,
        "member_id": mid,
        "name": name,
        "role": inv["role"],
        "token": member_token,
        "mailed": mailed,
    }


def listing(room_id: int) -> list[dict]:
    """Invites for the owner's view: never the token or its hash."""
    return q(
        "SELECT id,role,email,created,expires,used_at,used_by FROM invites WHERE room_id=? ORDER BY id DESC",
        (room_id,),
    )
