"""Credit ledger: portions, per-call metering from usage reports, checkpoints, requests and loans.
The platform cannot read anyone's real Anthropic balance; this ledger is the fine meter."""

from app.core import secrets_store
from app.core.db import ex, now, q, q1

BUFFER = 0.05  # dollars that must remain before a call is allowed
THRESHOLDS = (70, 80, 90)


def add_key(member_id, provider, key_type, secret):
    return ex(
        "INSERT INTO keys(member_id,provider,key_type,secret_enc,last4) VALUES(?,?,?,?,?)",
        (member_id, provider, key_type, secrets_store.encrypt(secret), secret[-4:]),
    )


def get_secret(member_id, provider="anthropic"):
    k = q1(
        "SELECT * FROM keys WHERE member_id=? AND provider=? AND status='active' ORDER BY id DESC",
        (member_id, provider),
    )
    return secrets_store.decrypt(k["secret_enc"]) if k else None


def contribute(room_id, member_id, amount):
    return ex(
        "INSERT INTO contributions(room_id,member_id,amount) VALUES(?,?,?)",
        (room_id, member_id, amount),
    )


def cost_of(model, tin, tout, tcr=0, tcw=0):
    p = q1("SELECT * FROM prices WHERE model=?", (model,))
    if not p:
        raise ValueError(f"no price for model {model}")
    return (
        tin * p["input"] + tcr * p["cache_read"] + tcw * p["cache_write"] + tout * p["output"]
    ) / 1e6


def _contrib(room, m):
    return q1(
        "SELECT COALESCE(SUM(amount),0) s FROM contributions WHERE room_id=? AND member_id=?",
        (room, m),
    )["s"]


def _own_spent(room, m):
    return q1(
        "SELECT COALESCE(SUM(cost),0) s FROM ledger WHERE room_id=? AND member_id=? AND loan_id IS NULL",
        (room, m),
    )["s"]


def _lent_committed(room, m):
    r = 0.0
    for l in q("SELECT * FROM loans WHERE room_id=? AND lender=?", (room, m)):
        r += l["cap"] - l["returned"] if l["status"] == "active" else l["used"]
    return r


def balance(room, m):
    """Spendable = own contribution - credits lent out + credits borrowed."""
    contrib, own = _contrib(room, m), _own_spent(room, m)
    lent = _lent_committed(room, m)
    loans = q("SELECT * FROM loans WHERE room_id=? AND borrower=? AND status='active'", (room, m))
    borrowed_cap = sum(l["cap"] for l in loans)
    borrowed_used = sum(l["used"] for l in loans)
    budget = contrib - lent + borrowed_cap
    spent = own + borrowed_used
    return {
        "contribution": contrib,
        "lent_out": lent,
        "borrowed": borrowed_cap,
        "budget": budget,
        "spent": spent,
        "remaining": budget - spent,
        "own_remaining": contrib - lent - own,
        "usage_pct": (spent / budget * 100) if budget > 0 else 100.0,
    }


def room_view(room, m):
    """What the screen may show: pool total and the person's own balance, never anyone else's."""
    pool = q1("SELECT COALESCE(SUM(amount),0) s FROM contributions WHERE room_id=?", (room,))["s"]
    spent = q1("SELECT COALESCE(SUM(cost),0) s FROM ledger WHERE room_id=?", (room,))["s"]
    return {"pool_total": pool, "pool_spent": spent, "me": balance(room, m)}


def pick_key(room, m):
    """Own portion first, then an active loan's key. Returns (member_id_whose_key, loan_id|None) or None if nothing covers the buffer."""
    b = balance(room, m)
    if b["own_remaining"] > BUFFER and get_secret(m):
        return (m, None)
    for l in q(
        "SELECT * FROM loans WHERE room_id=? AND borrower=? AND status='active' ORDER BY id",
        (room, m),
    ):
        if l["cap"] - l["used"] > BUFFER:
            return (l["lender"], l["id"])
    return None


def record_call(room, m, agent, model, call_id, tin, tout, tcr, tcw, loan_id):
    cost = cost_of(model, tin, tout, tcr, tcw)
    ex(
        "INSERT INTO ledger(room_id,member_id,agent,model,call_id,tin,tout,tcr,tcw,cost,loan_id,ts) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (room, m, agent, model, call_id, tin, tout, tcr, tcw, cost, loan_id, now()),
    )
    cap_reached = False
    if loan_id:
        ex("UPDATE loans SET used=used+? WHERE id=?", (cost, loan_id))
        l = q1("SELECT * FROM loans WHERE id=?", (loan_id,))
        cap_reached = l["used"] >= l["cap"]
    pct = balance(room, m)["usage_pct"]
    crossed = None
    for t in THRESHOLDS:
        if pct >= t and not q1(
            "SELECT 1 x FROM checkpoints WHERE room_id=? AND member_id=? AND threshold=?",
            (room, m, t),
        ):
            crossed = t
            ex(
                "INSERT INTO checkpoints(room_id,member_id,agent,threshold,state,ts) VALUES(?,?,?,?,?,?)",
                (room, m, agent, t, "{}", now()),
            )  # state is filled by the runner from its own records (no tokens spent)
    return {"cost": cost, "pct": pct, "checkpoint": crossed, "cap_reached": cap_reached}


# ---- requests and loans (all approvals are manual; agents never send or approve) ----
def eligible_lenders(room, requester):
    return [
        m
        for m in q("SELECT id,name FROM members WHERE room_id=? AND id!=?", (room, requester))
        if balance(room, m["id"])["own_remaining"] > BUFFER
    ]


def create_request(room, requester, asked, target=None, ttl_hours=24, checkpoint_id=None):
    if q1(
        "SELECT 1 x FROM requests WHERE room_id=? AND requester=? AND status='open'",
        (room, requester),
    ):
        raise ValueError("You already have an open request")
    return ex(
        "INSERT INTO requests(room_id,requester,target,asked,expires,checkpoint_id) VALUES(?,?,?,?,?,?)",
        (room, requester, target, asked, now() + ttl_hours * 3600, checkpoint_id),
    )


def visible_requests(room, viewer):
    out = []
    for r in q("SELECT * FROM requests WHERE room_id=? AND status='open'", (room,)):
        if r["requester"] == viewer or r["target"] in (None, viewer):
            if r["requester"] != viewer and balance(room, viewer)["own_remaining"] <= BUFFER:
                continue  # no spare budget: no pop-up
            cp = (
                q1("SELECT * FROM checkpoints WHERE id=?", (r["checkpoint_id"],))
                if r["checkpoint_id"]
                else None
            )
            out.append({**r, "progress": cp})
    return out


def fund_request(request_id, lender, amount, cap_hours=48):
    """Approve (or counter with a smaller amount). Creates a loan the borrower can use straight away."""
    r = q1("SELECT * FROM requests WHERE id=?", (request_id,))
    if not r or r["status"] != "open":
        raise ValueError("Request is not open")
    if r["target"] not in (None, lender):
        raise ValueError("Request was not sent to you")
    if amount <= 0 or amount > balance(r["room_id"], lender)["own_remaining"]:
        raise ValueError("Amount exceeds your spare budget")
    amount = min(amount, r["asked"] - r["funded"])
    lid = ex(
        "INSERT INTO loans(room_id,lender,borrower,cap,expires,request_id) VALUES(?,?,?,?,?,?)",
        (r["room_id"], lender, r["requester"], amount, now() + cap_hours * 3600, request_id),
    )
    funded = r["funded"] + amount
    ex(
        "UPDATE requests SET funded=?, status=? WHERE id=?",
        (funded, "funded" if funded >= r["asked"] - 1e-9 else "open", request_id),
    )
    return lid


def reject_request(request_id, lender):
    r = q1("SELECT * FROM requests WHERE id=?", (request_id,))
    if r and r["target"] == lender:
        ex("UPDATE requests SET status='rejected' WHERE id=?", (request_id,))


def close_loan(loan_id, who, reason="closed"):
    l = q1("SELECT * FROM loans WHERE id=?", (loan_id,))
    if not l or l["status"] != "active":
        return None
    if who not in (l["borrower"], l["lender"], 0):
        raise ValueError("Not your loan")
    unspent = l["cap"] - l["used"]
    ex("UPDATE loans SET status=?, returned=? WHERE id=?", (reason, unspent, loan_id))
    return unspent


def housekeeping(room: int) -> list[dict]:
    """Expire loans (unspent credits return to the lender) and unfunded requests; list reminders due within 1 hour."""
    t = now()
    reminders = []
    for l in q("SELECT * FROM loans WHERE room_id=? AND status='active'", (room,)):
        if l["expires"] <= t:
            close_loan(l["id"], 0, "expired")
        elif l["expires"] - t < 3600:
            reminders.append(l)
    ex(
        "UPDATE requests SET status='expired' WHERE room_id=? AND status='open' AND expires<=?",
        (room, t),
    )
    return reminders


def funding_bar(request_id):
    r = q1("SELECT * FROM requests WHERE id=?", (request_id,))
    return {
        "asked": r["asked"],
        "funded": r["funded"],
        "pct": min(100, r["funded"] / r["asked"] * 100),
        "status": r["status"],
    }
