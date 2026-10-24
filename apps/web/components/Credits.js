"use client";
import { useEffect, useState } from "react";
import { api, money } from "../lib/api";

export default function Credits({ rid, me, members }) {
  const [b, setB] = useState(null); const [amt, setAmt] = useState(""); const [req, setReq] = useState({ amount: "", target: "" }); const [fund, setFund] = useState({}); const [msg, setMsg] = useState("");
  const load = async () => { try { setB(await api(`/api/rooms/${rid}/budget`, { rid })); } catch (e) { setMsg(e.message); } };
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [rid]);
  const run = async (fn) => { setMsg(""); try { await fn(); await load(); } catch (e) { setMsg(e.message); } };
  if (!b) return <p className="muted">{msg || "Loading…"}</p>;
  const mine = b.view.me, byId = Object.fromEntries(members.map((m) => [m.id, m.name]));
  return (
    <div>
      <p className="err" role="alert">{msg}</p>
      <h2>Your credits</h2>
      <p>{money(mine.remaining)} left of {money(mine.budget)} · spent {money(mine.spent)}</p>
      <div className="bar" role="img" aria-label={`${Math.round(mine.usage_pct)} percent used`}><i style={{ width: Math.min(100, mine.usage_pct) + "%" }} />{[70, 80, 90].map((p) => <b key={p} style={{ left: p + "%" }} />)}</div>
      <p className="muted small">The team has put in {money(b.view.pool_total)} and used {money(b.view.pool_spent)}. You only ever see your own balance. Agents pause at 90% and ask you what to do.</p>
      <div className="row"><input className="grow" inputMode="decimal" placeholder="Add to your budget (dollars of your own key)" value={amt} onChange={(e) => setAmt(e.target.value)} aria-label="Amount to add" />
        <button onClick={() => run(async () => { await api(`/api/rooms/${rid}/contribute`, { rid, body: { amount: parseFloat(amt) } }); setAmt(""); })}>Add</button></div>
      <section className="panel"><h2>Ask a teammate for credits</h2>
        <div className="row"><input style={{ width: "7rem" }} inputMode="decimal" placeholder="Amount" value={req.amount} onChange={(e) => setReq({ ...req, amount: e.target.value })} aria-label="Amount to ask for" />
          <select style={{ width: "auto" }} value={req.target} onChange={(e) => setReq({ ...req, target: e.target.value })} aria-label="Who to ask"><option value="">Everyone with spare credits</option>{members.filter((m) => m.id !== me.id).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select>
          <button onClick={() => run(() => api(`/api/rooms/${rid}/requests`, { rid, body: { amount: parseFloat(req.amount), target: req.target ? +req.target : null } }))}>Send request</button></div>
        <p className="muted small">A loan bills the lender's own key for what you use, up to the amount they approve. Whether Anthropic's terms allow sharing a key this way is unconfirmed: check before relying on it.</p>
      </section>
      <section className="panel"><h2>Requests</h2>
        {b.requests.length ? b.requests.map((r) => (
          <div key={r.id} className="row" style={{ marginBottom: ".6rem" }}>
            <span className="grow">{r.requester === me.id ? "You asked for" : byId[r.requester] + " asks for"} {money(r.asked)} · funded {money(r.funded)}{r.progress ? ` · their agent is at ${r.progress.threshold}%` : ""}</span>
            {r.requester !== me.id && <><input style={{ width: "6rem" }} inputMode="decimal" placeholder="Amount" aria-label="Amount to lend" value={fund[r.id] || ""} onChange={(e) => setFund({ ...fund, [r.id]: e.target.value })} />
              <button onClick={() => run(() => api(`/api/requests/${r.id}/fund`, { rid, body: { amount: parseFloat(fund[r.id]) } }))}>Lend</button>
              <button className="quiet" onClick={() => run(() => api(`/api/requests/${r.id}/reject`, { rid, method: "POST" }))}>Decline</button></>}
          </div>)) : <p className="muted">No open requests.</p>}
      </section>
      <section className="panel"><h2>Loans</h2>
        {b.loans.length ? <table><tbody>{b.loans.map((l) => <tr key={l.id}><td>{byId[l.lender]} → {byId[l.borrower]}</td><td>{money(l.used)} of {money(l.cap)}</td><td>{l.status}</td>
          <td>{l.status === "active" && <button className="quiet" onClick={() => run(() => api(`/api/loans/${l.id}/close`, { rid, method: "POST" }))}>Close</button>}</td></tr>)}</tbody></table> : <p className="muted">No loans.</p>}
      </section>
    </div>
  );
}
