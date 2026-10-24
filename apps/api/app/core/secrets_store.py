import os

from cryptography.fernet import Fernet

from app.core.config import STATE


def _fernet():
    k = os.environ.get("PLATFORM_SECRET")
    if not k:
        f = STATE / "secret.key"
        if not f.exists():
            f.write_bytes(Fernet.generate_key())
            f.chmod(0o600)
        k = f.read_bytes().decode()
    return Fernet(k.encode() if isinstance(k, str) else k)


def encrypt(s: str) -> str:
    return _fernet().encrypt(s.encode()).decode()


def decrypt(s: str) -> str:
    return _fernet().decrypt(s.encode()).decode()
