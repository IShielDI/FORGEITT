import re
import shutil
import subprocess
import threading
import time

from app.core import config


class Tunnel:
    def __init__(self, url, proc=None, kind="none"):
        self.url, self.proc, self.kind = url, proc, kind

    def close(self):
        if self.proc:
            self.proc.terminate()


def open_tunnel(port: int) -> Tunnel:
    """Public address for the mirror: Cloudflare quick tunnel; or a fixed preview URL from MIRROR_PUBLIC_URL."""
    if config.MIRROR_PUBLIC_URL:
        return Tunnel(config.MIRROR_PUBLIC_URL, None, "preset")
    if not shutil.which("cloudflared"):
        return Tunnel(None, None, "unavailable")
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    found = {}

    def reader():
        for line in proc.stdout:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m:
                found["url"] = m.group(0)
                return

    threading.Thread(target=reader, daemon=True).start()
    for _ in range(60):
        if "url" in found:
            time.sleep(2)
            return Tunnel(found["url"], proc, "cloudflared")
        time.sleep(0.5)
    proc.terminate()
    return Tunnel(None, None, "failed")
