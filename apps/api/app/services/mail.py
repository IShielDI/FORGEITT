"""Outgoing mail (Gmail SMTP). Used for invite links; never sends keys or tokens other than the invite."""

import smtplib
from email.message import EmailMessage

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
    msg["From"], msg["To"], msg["Subject"] = config.SMTP_USER, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=SMTP_TIMEOUT_S) as smtp:
            smtp.starttls()
            smtp.login(config.SMTP_USER, config.SMTP_APP_PASSWORD)
            smtp.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as e:
        print("mail failed:", type(e).__name__)  # no addresses or credentials in logs
        return False


def send_invite(to: str, room_name: str, link: str, ttl_days: int) -> bool:
    body = (
        f"You have been invited to the ForgeIt workspace '{room_name}'.\n\n"
        f"Open this link to join (it works once and expires in {ttl_days} days):\n{link}\n\n"
        "If you were not expecting this, ignore this message."
    )
    return send(to, f"Join '{room_name}' on ForgeIt", body)
