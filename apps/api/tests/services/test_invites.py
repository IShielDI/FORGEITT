import pytest

from app.core import auth, config
from app.core.db import ex, q1
from app.services import invites, mail


@pytest.fixture()
def sent(monkeypatch):
    """Stub mail: record what would be sent instead of talking to Gmail."""
    box: list[dict] = []

    def fake_send_invite(to, room_name, link, ttl_days):
        box.append({"to": to, "room": room_name, "link": link, "ttl": ttl_days})
        return bool(to)

    monkeypatch.setattr(mail, "send_invite", fake_send_invite)
    return box


def test_create_returns_link_once_and_stores_only_a_hash(room, sent):
    inv = invites.create(room, None, "member", "new@example.test")

    row = q1("SELECT * FROM invites WHERE id=?", (inv["id"],))
    assert inv["link"].endswith("/invite/" + inv["token"])
    assert row["token_hash"] == auth.hash_token(inv["token"])
    assert inv["token"] not in str(row)
    assert inv["mailed"] is True
    assert sent[0]["to"] == "new@example.test" and sent[0]["ttl"] == config.INVITE_TTL_DAYS


def test_without_an_email_the_link_is_only_shown(room, sent):
    inv = invites.create(room, None)

    assert inv["mailed"] is False


def test_accept_creates_member_with_own_token_and_role(room, sent):
    inv = invites.create(room, None, "viewer")

    joined = invites.accept(inv["token"], "Zed", "zed@example.test")

    m = q1("SELECT * FROM members WHERE id=?", (joined["member_id"],))
    assert m["room_id"] == room and m["role"] == "viewer" and m["is_owner"] == 0
    assert m["token_hash"] == auth.hash_token(joined["token"])


def test_invite_is_single_use(room, sent):
    inv = invites.create(room, None)
    invites.accept(inv["token"], "Zed")

    with pytest.raises(invites.InviteError) as e:
        invites.accept(inv["token"], "Yan")
    assert e.value.code == "used"


def test_expired_invite_is_refused(room, sent):
    inv = invites.create(room, None)
    ex("UPDATE invites SET expires=1 WHERE id=?", (inv["id"],))

    with pytest.raises(invites.InviteError) as e:
        invites.accept(inv["token"], "Zed")
    assert e.value.code == "expired"


def test_unknown_invite_is_refused(room):
    with pytest.raises(invites.InviteError) as e:
        invites.accept("not-a-token", "Zed")
    assert e.value.code == "unknown"


def test_invites_expire_after_seven_days(room, sent):
    inv = invites.create(room, None)

    assert inv["expires"] - q1("SELECT created FROM invites WHERE id=?", (inv["id"],))[
        "created"
    ] == pytest.approx(7 * 86400)


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_only_member_or_viewer_can_be_invited(room, role):
    with pytest.raises(ValueError):
        invites.create(room, None, role)


def test_duplicate_name_is_refused_and_invite_stays_usable(room, sent):
    inv = invites.create(room, None)

    with pytest.raises(ValueError):
        invites.accept(inv["token"], "riya")  # already in the room
    assert invites.accept(inv["token"], "Zed")["name"] == "Zed"


def test_listing_never_exposes_tokens(room, sent):
    inv = invites.create(room, None)

    text = str(invites.listing(room))
    assert inv["token"] not in text and "token_hash" not in text


def test_mail_uses_starttls_and_login(monkeypatch):
    calls: list[str] = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(f"connect {host}:{port}")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            calls.append("starttls")

        def login(self, user, password):
            calls.append(f"login {user}")

        def send_message(self, msg):
            calls.append(f"send {msg['To']}")

    monkeypatch.setattr(config, "SMTP_USER", "team@gmail.example")
    monkeypatch.setattr(config, "SMTP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)

    assert mail.send_invite("a@example.test", "Demo", "http://x/invite/t", 7) is True
    assert calls == [
        "connect smtp.gmail.com:587",
        "starttls",
        "login team@gmail.example",
        "send a@example.test",
    ]


def test_mail_is_skipped_when_not_configured(monkeypatch):
    monkeypatch.setattr(config, "SMTP_USER", "")

    assert mail.send_invite("a@example.test", "Demo", "http://x", 7) is False
