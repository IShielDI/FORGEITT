"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

// Owner-only setup: the customer journey, hidden tests, and the agent catalog.
export default function Setup({ rid, me, room, catalog, models, reload }) {
  const [j, setJ] = useState({ goal: "", success_text: "", db_check: "" }); const [hid, setHid] = useState([]); const [msg, setMsg] = useState("");
  const [h, setH] = useState({ filename: "", content: "" });
  const [c, setC] = useState({ key: "", label: "", description: "", role_prompt: "", model: models[0] || "", part: "" });
  const owner = me?.is_owner;
  const load = async () => { setJ({ goal: "", success_text: "", db_check: "", ...(await api(`/api/rooms/${rid}/journey`, { rid })) }); setHid(await api(`/api/rooms/${rid}/holdout`, { rid })); };
  useEffect(() => { load().catch(() => {}); }, [rid]);
  const run = async (fn, ok) => { setMsg(""); try { await fn(); setMsg(ok); await load(); reload?.(); } catch (e) { setMsg(e.message); } };
  if (!owner) return <p className="muted">Only the workspace owner can change the setup. Ask them if the journey, hidden tests or agents need to change.</p>;
  return (
    <div>
      <p role="status" className={msg.includes("saved") || msg.includes("Saved") ? "ok" : "err"}>{msg}</p>
      <section className="panel">
        <h2>Customer journey</h2>
        <p className="muted">What a new customer does, in plain words. The referee replays it in a real browser after each change. Use {"{email}"} where a fresh email address is needed.</p>
        <label htmlFor="g">Steps</label><textarea id="g" value={j.goal} onChange={(e) => setJ({ ...j, goal: e.target.value })} placeholder="Open the home page, create an account with {email}, add an item to the cart and check out." />
        <label htmlFor="s">Text the last page must show</label><input id="s" value={j.success_text} onChange={(e) => setJ({ ...j, success_text: e.target.value })} placeholder="Order placed" />
        <label htmlFor="d">Record the app must have afterwards (one SELECT, optional)</label><input id="d" value={j.db_check} onChange={(e) => setJ({ ...j, db_check: e.target.value })} placeholder="SELECT 1 FROM orders WHERE email = :email" />
        <p />
        <button onClick={() => run(() => api(`/api/rooms/${rid}/journey`, { rid, method: "PUT", body: j }), "Journey saved.")}>Save journey</button>
      </section>
      <section className="panel">
        <h2>Hidden tests</h2>
        <p className="muted">Tests only you can see. They run on every change, and agents never read them. Write at least a few after the first build, so a change cannot pass by hard-coding the visible answers.</p>
        {hid.length ? <p className="small">Saved: {hid.join(", ")}</p> : <p className="small muted">None yet.</p>}
        <label htmlFor="hf">File name</label><input id="hf" value={h.filename} onChange={(e) => setH({ ...h, filename: e.target.value })} placeholder="test_hidden_totals.py" />
        <label htmlFor="hc">Test code (uses the project's own fixtures, such as <code>client</code>)</label><textarea id="hc" value={h.content} onChange={(e) => setH({ ...h, content: e.target.value })} />
        <p /><button onClick={() => run(() => api(`/api/rooms/${rid}/holdout`, { rid, body: h }), "Hidden test saved.")}>Save hidden test</button>
      </section>
      <section className="panel">
        <h2>Agents in this workspace</h2>
        <table><tbody>{catalog.map((a) => <tr key={a.key}><td><b>{a.label}</b><br /><span className="muted small">{a.description}</span></td><td className="small">{a.model}</td>
          <td><button className="quiet" onClick={() => setC({ ...a, part: a.part || "" })}>Edit</button> <button className="quiet" onClick={() => run(() => api(`/api/rooms/${rid}/catalog/${a.key}`, { rid, method: "DELETE" }), "Agent removed. Saved.")}>Remove</button></td></tr>)}</tbody></table>
        <label htmlFor="ck">Short name (letters, digits, - or _)</label><input id="ck" value={c.key} onChange={(e) => setC({ ...c, key: e.target.value })} />
        <label htmlFor="cl">Name shown to the team</label><input id="cl" value={c.label} onChange={(e) => setC({ ...c, label: e.target.value })} />
        <label htmlFor="cd">What it is for</label><input id="cd" value={c.description} onChange={(e) => setC({ ...c, description: e.target.value })} />
        <label htmlFor="cp">Instructions that shape how it works</label><textarea id="cp" value={c.role_prompt} onChange={(e) => setC({ ...c, role_prompt: e.target.value })} />
        <label htmlFor="cm">Model</label><select id="cm" value={c.model} onChange={(e) => setC({ ...c, model: e.target.value })}>{models.map((m) => <option key={m}>{m}</option>)}</select>
        <p /><button onClick={() => run(() => api(`/api/rooms/${rid}/catalog`, { rid, method: "PUT", body: { ...c, part: c.part || null } }), "Agent saved.")}>Save agent</button>
      </section>
    </div>
  );
}
