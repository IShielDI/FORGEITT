"""Outgoing mail (Gmail SMTP). Used for invite links and for the login a teammate is given when a workspace is created; never sends API keys."""

import smtplib
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from app.core import config

SMTP_TIMEOUT_S = 20


def configured() -> bool:
    return bool(config.SMTP_USER and config.SMTP_APP_PASSWORD)


def send(to: str, subject: str, body: str) -> bool:
    """Send one plain-text message. Returns False (never raises) when mail is not configured or fails,
    so callers can fall back to showing the link to the owner."""
    if not configured() or not to:
        return False
    msg = EmailMessage()
    msg["From"] = formataddr(("ForgeIt", config.SMTP_USER))
    msg["To"], msg["Subject"] = to, subject
    msg["Date"] = formatdate(localtime=True)  # missing Date/Message-ID headers look like spam
    msg["Message-ID"] = make_msgid(domain=config.SMTP_USER.partition("@")[2] or None)
    msg.set_content(body)
    domain = to.rpartition("@")[2]  # logs name the recipient's domain only, never the address
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=SMTP_TIMEOUT_S) as smtp:
            smtp.starttls()
            smtp.login(config.SMTP_USER, config.SMTP_APP_PASSWORD)
            refused = smtp.send_message(msg)
        if refused:
            print("mail refused for", domain)
            return False
        print("mail accepted by the SMTP server for", domain)
        return True
    except (OSError, smtplib.SMTPException) as e:
        print("mail failed for", domain, type(e).__name__)  # no credentials in logs
        return False


def send_invite(
    to: str, room_name: str, rid: int, link: str, code: str, ttl_days: int, web_url: str
) -> bool:
    """The join link plus the workspace number and invite code, for anyone who cannot click links."""
    body = (
        f"You have been invited to the ForgeIt workspace '{room_name}'.\n\n"
        f"Workspace: {room_name}\nWorkspace number: {rid}\n\n"
        f"Join with one click (the link works once and expires in {ttl_days} days):\n{link}\n\n"
        f"Or open {web_url}, choose 'Join a workspace' and paste this invite code:\n{code}\n\n"
        "Joining signs you in and gives you your own login token for other devices; "
        "we email it to you as well.\n\n"
        "If you were not expecting this, ignore this message."
    )
    return send(to, f"Join '{room_name}' on ForgeIt", body)


def send_credentials(
    to: str, room_name: str, rid: int, name: str, token: str, web_url: str
) -> bool:
    """The workspace number and login token for a new member (added at creation or by invite)."""
    body = (
        f"Hi {name}, you are a member of the ForgeIt workspace '{room_name}'.\n\n"
        f"Workspace number: {rid}\nYour token: {token}\n\n"
        f"Open {web_url}, choose 'Join a workspace', then 'Already joined? Sign in with a workspace number and token'.\n"
        "Keep the token private: it is your login, and it is not shown again.\n\n"
        "If you were not expecting this, ignore this message."
    )
    return send(to, f"Your login for '{room_name}' on ForgeIt", body)
