"""The referee controller: runs a journey in a real browser (TinyFish Agent API), enforces our own step limit,
and decides the verdict from the app's own records, never from the agent's say-so."""

import json
import re
from pathlib import Path

import httpx

from app.core import config, db

RESULT_SCHEMA = '{"signup_ok": true|false, "confirmation_number": string|null, "order_total_shown": string|null, "stuck_reason": string|null}'


def journey_goal(email, password="Passw0rd!"):
    return (
        f"You are a new customer on a small web shop. 1) Open the sign up page and create an account with email {email} "
        f"and password {password}. 2) On the products page add 2 of 'Notebook' to the cart (set Quantity to 2, then click the "
        "add button for Notebook). 3) On the cart page click 'Check out'. 4) Read the order confirmation page. "
        "Do not try workarounds; if any step fails or is unclear, stop and report why in stuck_reason. "
        f"Reply with ONLY this JSON: {RESULT_SCHEMA}. confirmation_number is the text after 'Confirmation number:'; "
        "order_total_shown is the amount after 'Order total'."
    )


def expected_total_cents():
    return 2 * 1200


# ---- journeys defined by humans for any project (stored outside the repo: agents never see them) ----
GENERIC_SCHEMA = (
    '{"completed": true|false, "final_page_text": string|null, "stuck_reason": string|null}'
)


def journey_path(room_id):
    return config.DATA / "rooms" / str(room_id) / "journey.json"


def load_journey(room_id):
    p = journey_path(room_id)
    return json.loads(p.read_text()) if p.exists() else None


def save_journey(room_id, goal, success_text="", db_check=""):
    if not goal.strip():
        raise ValueError("a journey needs a goal in plain words")
    if db_check and not re.fullmatch(r"\s*select\b[^;]*;?\s*", db_check, re.I):
        raise ValueError("db_check must be a single SELECT")
    j = {"goal": goal.strip(), "success_text": success_text.strip(), "db_check": db_check.strip()}
    p = journey_path(room_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(j, indent=1))
    return j


def goal_for(journey, email):
    if not journey:
        return journey_goal(email)
    return (
        journey["goal"].replace("{email}", email)
        + " Do not try workarounds; if any step fails or is unclear, stop and "
        f"report why in stuck_reason. Reply with ONLY this JSON: {GENERIC_SCHEMA}. final_page_text is the visible text of the last page."
    )


def _envelope(raw):
    """TinyFish HTTP errors look like {"error": {"code", "message"}, "request_id"}. Returns (code, category-or-None)."""
    try:
        e = (json.loads(raw) or {}).get("error") or {}
    except Exception:
        return None, None
    if not isinstance(e, dict):
        return None, None
    code = e.get("code")
    cat = e.get("category") or ("BILLING_FAILURE" if code in ("INSUFFICIENT_CREDITS",) else None)
    return code, cat


class RunResult:
    def __init__(self, runner):
        self.runner, self.status, self.result, self.error = runner, None, None, None
        self.steps, self.run_id, self.streaming_url, self.cancelled = [], None, None, False
        self.error_code, self.error_category = (
            None,
            None,
        )  # TinyFish's own words: SYSTEM_FAILURE / AGENT_FAILURE / BILLING_FAILURE / UNKNOWN

    def asdict(self):
        return self.__dict__


class TinyFishRunner:
    name = "tinyfish"

    def __init__(self, key=None):
        self.key = key or config.TINYFISH_KEY

    @property
    def headers(self):
        return {"X-API-Key": self.key, "Content-Type": "application/json"}

    def run(self, url, goal, step_limit):
        # max_steps and capture_config are documented request fields; our own PROGRESS count below
        # stays as a second guard, so the step cap can be dropped where the account lacks it.
        body = {
            "url": url,
            "goal": goal,
            "agent_config": {"max_steps": step_limit},
            "capture_config": {"screenshots": True, "recording": True},
        }
        rr = self._run(body, step_limit)
        if rr.error and "403" in rr.error and "max steps" in rr.error.lower():
            # some accounts are not enabled for a custom step cap (a TinyFish beta): run without it
            body.pop("agent_config")
            rr = self._run(body, step_limit)
        return rr

    def _run(self, body, step_limit):
        rr = RunResult(self.name)
        try:
            with httpx.stream(
                "POST",
                f"{config.TINYFISH_BASE}/v1/automation/run-sse",
                headers=self.headers,
                json=body,
                timeout=httpx.Timeout(300, connect=20),
            ) as resp:
                if resp.status_code >= 400:
                    raw = resp.read().decode()
                    rr.status, rr.error = "FAILED", f"HTTP {resp.status_code}: {raw[:300]}"
                    rr.error_code, rr.error_category = _envelope(raw)
                    if resp.status_code == 402 and not rr.error_category:
                        rr.error_category = "BILLING_FAILURE"
                    return rr
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        ev = json.loads(line[5:].strip())
                    except Exception:
                        continue
                    t = ev.get("type")
                    if ev.get("run_id"):
                        rr.run_id = ev["run_id"]
                    if t == "STREAMING_URL":
                        rr.streaming_url = ev.get("streaming_url")
                    elif t == "PROGRESS":
                        rr.steps.append({"action": ev.get("purpose", "")})
                        if len(rr.steps) >= step_limit:  # our own limit; TinyFish's default is 150
                            self.cancel(rr.run_id)
                            rr.cancelled = True
                            rr.status = "CANCELLED"
                            return rr
                    elif t == "COMPLETE":
                        rr.status = ev.get("status", "COMPLETED")
                        rr.result = ev.get("result")
                        e = ev.get("error")
                        if isinstance(e, dict):
                            rr.error, rr.error_code, rr.error_category = (
                                e.get("message"),
                                e.get("code"),
                                e.get("category"),
                            )
                        elif e:
                            rr.error = str(e)
                        return rr
        except Exception as e:
            rr.status, rr.error = "FAILED", f"{type(e).__name__}: {e}"
        return rr

    def cancel(self, run_id):
        if run_id:
            try:
                httpx.post(
                    f"{config.TINYFISH_BASE}/v1/runs/{run_id}/cancel",
                    headers=self.headers,
                    timeout=15,
                )
            except Exception:
                pass

    def collect_evidence(self, rr, out: Path):
        """Download per-step screenshots and the video promptly (video links expire after 15 minutes)."""
        out.mkdir(parents=True, exist_ok=True)
        if not rr.run_id:
            return
        try:
            run = httpx.get(
                f"{config.TINYFISH_BASE}/v1/runs/{rr.run_id}", headers=self.headers, timeout=30
            ).json()
        except Exception:
            return
        steps = run.get("steps") or []
        rr.steps = [
            {
                "action": s.get("action") or s.get("purpose") or "",
                "status": s.get("status"),
                "duration": s.get("duration"),
            }
            for s in steps
        ] or rr.steps
        for i, s in enumerate(steps):
            u = s.get("screenshot")
            data = self._media(u, "image/", 30) if isinstance(u, str) else None
            if data:
                (out / f"step{i:02d}.png").write_bytes(data)
                rr.steps[i]["screenshot"] = f"step{i:02d}.png"
        v = run.get("video_url")
        data = self._media(v, "video/", 60) if isinstance(v, str) else None
        if data:
            (out / "run.mp4").write_bytes(data)

    def _media(self, url: str, kind: str, timeout: int) -> bytes | None:
        """Fetch an evidence file. Signed links work as they are; links on TinyFish's own host may
        need the API key, which is never sent anywhere else. Error bodies are never saved as media."""
        if not url.startswith("http"):
            return None
        same_host = httpx.URL(url).host == httpx.URL(config.TINYFISH_BASE).host
        try:
            r = httpx.get(url, timeout=timeout, follow_redirects=True)
            if r.status_code in (401, 403) and same_host:
                r = httpx.get(url, headers=self.headers, timeout=timeout, follow_redirects=True)
        except httpx.HTTPError:
            return None
        ctype = r.headers.get("content-type", "")
        if r.status_code != 200 or not (
            ctype.startswith(kind) or ctype == "application/octet-stream"
        ):
            return None
        return r.content


class LocalRunner:
    """Stand-in used when there is no TinyFish key or no public address. It drives the same journey with plain HTTP
    so the pipeline can be rehearsed offline. Its results are labelled 'local-standin' and are NOT a TinyFish verdict."""

    name = "local-standin"

    def run(self, url, goal, step_limit):
        rr = RunResult(self.name)
        rr.status = "COMPLETED"
        email = re.search(r"email (\S+) and", goal).group(1)
        try:
            with httpx.Client(base_url=url, follow_redirects=True, timeout=15) as c:

                def step(a):
                    rr.steps.append({"action": a})

                step("open /signup")
                c.get("/signup")
                step("submit sign up form")
                r = c.post("/signup", data={"email": email, "password": "Passw0rd!"})
                ok = "Products" in r.text
                step("add 2 x Notebook")
                c.post("/cart/add", data={"product_id": 1, "qty": 2})
                step("open cart")
                cart = c.get("/cart")
                # act like a user: submit the checkout form exactly as the page defines it
                fm = re.search(
                    r"<form method='(\w+)' action='([^']+)'><button type='submit'>Check out",
                    cart.text,
                )
                step("click Check out")
                page = c.request(fm.group(1).upper(), fm.group(2)) if fm else c.post("/checkout")
                conf = re.search(r"Confirmation number:\s*(ORD-\d+)", page.text)
                tot = re.search(r"Order total:\s*(\$[\d.,]+)", page.text)
                rr.result = {
                    "signup_ok": ok,
                    "confirmation_number": conf.group(1) if conf else None,
                    "order_total_shown": tot.group(1) if tot else None,
                    "stuck_reason": None if conf else "No confirmation page after checkout",
                }
        except Exception as e:
            rr.status, rr.error = "FAILED", f"{type(e).__name__}: {e}"
        return rr

    def collect_evidence(self, rr, out):
        pass


def parse_result(res):
    if isinstance(res, dict) and (
        "confirmation_number" in res or "stuck_reason" in res or "completed" in res
    ):
        return res
    if isinstance(res, str):
        m = re.search(r"\{.*\}", res, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    if isinstance(res, dict):  # sometimes wrapped, e.g. {"result": ...}
        for v in res.values():
            p = parse_result(v)
            if p:
                return p
    return None


def judge_for(journey, rr, mirror, email):
    return judge_generic(journey, rr, mirror, email) if journey else judge(rr, mirror, email)


def _service_verdict(rr):
    """Verdicts that do not depend on what the journey was: our cap, TinyFish failures. None if the run actually finished."""
    if rr.cancelled:
        return (
            "browser_failure",
            f"Hit our step limit ({config.STEP_LIMIT}) and was cancelled",
            False,
        )
    if rr.status == "FAILED" or rr.status is None:
        why = f"{rr.error_category or 'FAILED'}: {rr.error or 'run failed'}"
        if rr.error_category == "BILLING_FAILURE":
            return (
                "service_error",
                f"TinyFish credits ran out ({why}). Not an app problem; top up or wait.",
                False,
            )
        if rr.error_category == "AGENT_FAILURE":
            return (
                "inconclusive",
                f"The browser agent could not complete the run ({why}). A human should look.",
                False,
            )
        return "service_error", why, False
    return None


def judge_generic(journey, rr, mirror, email):
    """Same rule as the shop journey: the app's own records decide, not the agent's say-so."""
    v = _service_verdict(rr)
    if v:
        return v
    res = parse_result(rr.result)
    if res is None or "completed" not in res:
        return "inconclusive", "Agent returned no usable structured answer", False
    if not res.get("completed"):
        stuck = (res.get("stuck_reason") or "").lower()
        if not stuck:
            return "inconclusive", "Journey not completed and no stated reason", False
        if any(
            k in stuck
            for k in (
                "load",
                "block",
                "captcha",
                "timeout",
                "navigate",
                "unreachable",
                "warning page",
            )
        ):
            return (
                "browser_failure",
                f"Browser could not complete the journey: {res['stuck_reason']}",
                False,
            )
        return "app_failure", f"The journey stopped: {res['stuck_reason']}", False
    want = journey.get("success_text") or ""
    if want and want.lower() not in (res.get("final_page_text") or "").lower():
        return "app_failure", f"The last page did not show the expected text {want!r}", False
    if journey.get("db_check"):
        try:
            rows = mirror.query(journey["db_check"], email=email)
        except Exception as e:
            return "inconclusive", f"Could not run the record check in the app database: {e}", False
        if not rows:
            return (
                "app_failure",
                "Agent reported success but the app has NO matching record (db_check returned nothing)",
                True,
            )
    return "pass", "Journey completed and the app's records agree", False


def judge(rr: RunResult, mirror, email):
    """Verdict from the app's own records. Returns (verdict, reason, suspicious)."""
    v = _service_verdict(rr)
    if v:
        return v
    res = parse_result(rr.result)
    if res is None:
        return "inconclusive", "Agent returned no usable structured answer", False
    conf = res.get("confirmation_number")
    orders = mirror.orders(email)
    if not conf:
        stuck = (res.get("stuck_reason") or "").lower()
        if not stuck:
            return "inconclusive", "No confirmation and no stated reason", False
        # Stuck after reaching checkout points at the app; stuck earlier or on loading/blocking points at the browser.
        if res.get("signup_ok") is not False and any(
            k in stuck for k in ("confirmation", "checkout", "check out", "error", "500")
        ):
            return "app_failure", f"Checkout produced no confirmation: {res['stuck_reason']}", False
        if (
            any(
                k in stuck
                for k in (
                    "load",
                    "block",
                    "captcha",
                    "timeout",
                    "navigate",
                    "unreachable",
                    "warning page",
                )
            )
            or res.get("signup_ok") is False
        ):
            return (
                "browser_failure",
                f"Browser could not complete the journey: {res['stuck_reason']}",
                False,
            )
        return "inconclusive", f"Unclear stop reason: {res['stuck_reason']}", False
    if not orders:
        return (
            "app_failure",
            "Agent saw a confirmation but the app has NO order record for the test user",
            True,
        )
    shown = res.get("order_total_shown") or ""
    got = orders[-1]["total_cents"]
    want = expected_total_cents()
    if got != want:
        return (
            "app_failure",
            f"Order saved with total {got / 100:.2f}, expected {want / 100:.2f} (page showed {shown})",
            False,
        )
    return "pass", f"Order {conf} recorded with the correct total {want / 100:.2f}", False


def runs_last_hour(room_id):
    return db.q1(
        "SELECT COUNT(*) n FROM referee_runs WHERE room_id=? AND runner='tinyfish' AND ts>?",
        (room_id, db.now() - 3600),
    )["n"]
