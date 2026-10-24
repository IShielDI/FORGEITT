"""Check the Gmail SMTP settings in .env.

    cd apps/api && python ../../scripts/test_mail.py --login-only     # log in, send nothing
    cd apps/api && python ../../scripts/test_mail.py you@example.com  # send one test message
"""

import smtplib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.core import config
from app.services import mail


def main(argv: list[str]) -> int:
    if not mail.configured():
        print("SMTP_USER / SMTP_APP_PASSWORD are not set in .env")
        return 1
    if argv[:1] == ["--login-only"]:
        try:
            timeout = mail.SMTP_TIMEOUT_S
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=timeout) as smtp:
                smtp.starttls()
                smtp.login(config.SMTP_USER, config.SMTP_APP_PASSWORD)
        except (OSError, smtplib.SMTPException) as e:
            print("login failed:", type(e).__name__, getattr(e, "smtp_code", ""))
            return 1
        print(f"login ok as {config.SMTP_USER}")
        return 0
    if len(argv) != 1 or "@" not in argv[0]:
        print(__doc__)
        return 2
    body = "This is a test message from ForgeIt. Mail is working."
    ok = mail.send(argv[0], "ForgeIt mail test", body)
    print("sent" if ok else "send failed (see the line above)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
