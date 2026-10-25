"""Exercises TinyFishRunner against a local fake that speaks the documented protocol
(POST /v1/automation/run-sse with X-API-Key; STARTED/STREAMING_URL/PROGRESS/COMPLETE events; POST /v1/runs/{id}/cancel)."""

import json
import socket
import threading
import time

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from app.core import config
from app.services import referee

fake = FastAPI()
STATE = {"cancelled": [], "mode": "ok", "keys": [], "bodies": []}


@fake.post("/v1/automation/run-sse")
async def run_sse(req: Request):
    STATE["keys"].append(req.headers.get("x-api-key"))
    body = await req.json()
    STATE["bodies"].append(body)
    if STATE["mode"] == "401":
        from fastapi.responses import JSONResponse

        return JSONResponse({"error": "bad key"}, status_code=401)
    if STATE["mode"] == "beta" and "agent_config" in body:
        from fastapi.responses import JSONResponse

        msg = "Your account is not enabled for custom max steps yet. Join the beta program."
        return JSONResponse({"error": {"code": "FORBIDDEN", "message": msg}}, status_code=403)
    if STATE["mode"] == "402":
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {
                "error": {"code": "INSUFFICIENT_CREDITS", "message": "wallet balance too low"},
                "request_id": "q",
            },
            status_code=402,
        )

    def gen():
        if STATE["mode"] in ("agentfail", "sysfail"):
            yield f"data: {json.dumps({'type': 'STARTED', 'run_id': 'r1'})}\n\n"
            cat = "AGENT_FAILURE" if STATE["mode"] == "agentfail" else "SYSTEM_FAILURE"
            yield f"data: {json.dumps({'type': 'COMPLETE', 'run_id': 'r1', 'status': 'FAILED', 'result': None, 'error': {'code': 'X', 'message': 'boom', 'category': cat}})}\n\n"
            return
        ev = lambda d: f"data: {json.dumps(d)}\n\n"
        yield ev({"type": "STARTED", "run_id": "r1"})
        yield ev({"type": "STREAMING_URL", "run_id": "r1", "streaming_url": "https://x/live"})
        n = 100 if STATE["mode"] == "loop" else 3
        for i in range(n):
            yield ev({"type": "PROGRESS", "run_id": "r1", "purpose": f"step {i}"})
        res = STATE.get(
            "result",
            {
                "signup_ok": True,
                "confirmation_number": "ORD-1",
                "order_total_shown": "$24.00",
                "stuck_reason": None,
            },
        )
        yield ev({"type": "COMPLETE", "run_id": "r1", "status": "COMPLETED", "result": res})

    return StreamingResponse(gen(), media_type="text/event-stream")


@fake.post("/v1/runs/{rid}/cancel")
def cancel(rid: str, req: Request):
    STATE["cancelled"].append((rid, req.headers.get("x-api-key")))
    return {"status": "CANCELLED"}


PNG = b"PNG-fake-image-bytes"


@fake.get("/v1/runs/{rid}")
def run_detail(rid: str, req: Request):
    base = str(req.base_url).rstrip("/")
    return {
        "steps": [
            {"action": "open the shop", "screenshot": f"{base}/shots/0.png"},
            {"action": "broken link", "screenshot": f"{base}/shots/missing.png"},
        ],
        "video_url": f"{base}/video.webm",
    }


@fake.get("/shots/{name}")
def shot(name: str, req: Request):
    from fastapi.responses import JSONResponse, Response

    if req.headers.get("x-api-key") != "key-123":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if name != "0.png":
        return JSONResponse({"error": "not found"}, status_code=404)
    return Response(PNG, media_type="image/png")


@fake.get("/video.webm")
def video():
    from fastapi.responses import Response

    return Response(b"WEBM-fake-video-bytes", media_type="video/webm")


@pytest.fixture(scope="module", autouse=True)
def server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(fake, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=srv.run, daemon=True).start()
    time.sleep(1)
    old = config.TINYFISH_BASE
    config.TINYFISH_BASE = f"http://127.0.0.1:{port}"
    yield
    config.TINYFISH_BASE = old
    srv.should_exit = True


class FakeMirror:
    def __init__(self, orders):
        self._o = orders

    def orders(self, email):
        return self._o


def run(mode="ok", result=None, limit=20):
    STATE.update(mode=mode, cancelled=[], keys=[])
    STATE.pop("result", None)
    if result is not None:
        STATE["result"] = result
    return referee.TinyFishRunner("key-123").run(
        "https://m.example", referee.journey_goal("t@x.com"), limit
    )


def test_parses_events_and_sends_key():
    rr = run()
    assert (
        rr.status == "COMPLETED" and rr.run_id == "r1" and len(rr.steps) == 3 and rr.streaming_url
    )
    assert STATE["keys"] == ["key-123"]


def test_step_limit_cancels_run():
    rr = run("loop", limit=10)
    assert rr.cancelled and rr.status == "CANCELLED" and STATE["cancelled"] == [("r1", "key-123")]
    assert referee.judge(rr, FakeMirror([]), "t@x.com")[0] == "browser_failure"


def test_http_error_is_service_error():
    rr = run("401")
    assert referee.judge(rr, FakeMirror([]), "t@x.com")[0] == "service_error"


def test_pass_requires_matching_record():
    rr = run()
    assert referee.judge(rr, FakeMirror([{"total_cents": 2400}]), "t@x.com")[0] == "pass"


def test_agent_says_pass_but_no_record_is_suspicious():
    rr = run()
    v, reason, susp = referee.judge(rr, FakeMirror([]), "t@x.com")
    assert v == "app_failure" and susp


def test_wrong_total_in_records_fails_even_if_page_looks_right():
    rr = run()
    v, reason, _ = referee.judge(rr, FakeMirror([{"total_cents": 1200}]), "t@x.com")
    assert v == "app_failure" and "12.00" in reason


def test_unstructured_answer_is_inconclusive():
    rr = run(result="I think it worked!")
    assert referee.judge(rr, FakeMirror([]), "t@x.com")[0] == "inconclusive"


def test_json_wrapped_in_text_is_parsed():
    rr = run(
        result='Here you go: {"signup_ok": true, "confirmation_number": "ORD-1", "order_total_shown": "$24.00", "stuck_reason": null}'
    )
    assert referee.judge(rr, FakeMirror([{"total_cents": 2400}]), "t@x.com")[0] == "pass"


def test_browser_stuck_early_vs_app_stuck_late():
    r1 = run(
        result={
            "signup_ok": False,
            "confirmation_number": None,
            "order_total_shown": None,
            "stuck_reason": "page would not load",
        }
    )
    assert referee.judge(r1, FakeMirror([]), "t@x.com")[0] == "browser_failure"
    r2 = run(
        result={
            "signup_ok": True,
            "confirmation_number": None,
            "order_total_shown": None,
            "stuck_reason": "Check out button gave an error",
        }
    )
    assert referee.judge(r2, FakeMirror([]), "t@x.com")[0] == "app_failure"


def test_request_asks_for_step_cap_and_evidence():
    run(limit=12)
    b = STATE["bodies"][-1]
    assert (
        b["agent_config"]["max_steps"] == 12
        and b["capture_config"]["recording"]
        and b["capture_config"]["screenshots"]
    )


def test_out_of_credits_is_a_billing_message_not_an_app_failure():
    rr = run("402")
    v, why, _ = referee.judge(rr, FakeMirror([]), "t@x.com")
    assert rr.error_category == "BILLING_FAILURE" and v == "service_error" and "credits" in why


def test_agent_failure_needs_a_human_not_blame_on_the_app():
    rr = run("agentfail")
    assert rr.error_category == "AGENT_FAILURE"
    assert referee.judge(rr, FakeMirror([]), "t@x.com")[0] == "inconclusive"


def test_system_failure_is_a_service_error():
    rr = run("sysfail")
    assert referee.judge(rr, FakeMirror([]), "t@x.com")[0] == "service_error"


def test_accounts_without_the_step_cap_beta_retry_without_it():
    rr = run("beta", limit=12)
    first, second = STATE["bodies"][-2], STATE["bodies"][-1]
    assert "agent_config" in first and "agent_config" not in second
    assert second["capture_config"]["recording"]  # evidence is still requested
    assert rr.status == "COMPLETED" and rr.error is None


def test_evidence_downloads_real_images_and_video_never_error_bodies(tmp_path):
    rr = referee.RunResult("tinyfish")
    rr.run_id = "r1"
    referee.TinyFishRunner("key-123").collect_evidence(rr, tmp_path)

    assert (tmp_path / "step00.png").read_bytes() == PNG  # needed the key: sent to TinyFish only
    assert not (tmp_path / "step01.png").exists()  # a 404 body is never saved as an image
    assert (tmp_path / "run.mp4").read_bytes() == b"WEBM-fake-video-bytes"
    assert rr.steps[0]["screenshot"] == "step00.png" and "screenshot" not in rr.steps[1]


def test_the_key_is_never_sent_to_another_host(monkeypatch):
    seen = []

    def fake_get(url, headers=None, **kw):
        seen.append((url, headers))
        return httpx.Response(
            401, json={"error": "Unauthorized"}, request=httpx.Request("GET", url)
        )

    import httpx

    monkeypatch.setattr(referee.httpx, "get", fake_get)
    assert (
        referee.TinyFishRunner("key-123")._media("https://cdn.elsewhere.test/a.png", "image/", 5)
        is None
    )
    assert seen == [("https://cdn.elsewhere.test/a.png", None)]
