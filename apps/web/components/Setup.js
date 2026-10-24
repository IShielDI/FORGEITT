"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

// Owner-only setup: the customer journey, hidden tests, and the agent catalog.
export default function Setup({ rid, me, room, catalog, models, reload }) {
  const [j, setJ] = useState({ goal: "", success_text: "", db_check: "" }); const [msg, setMsg] = useState("");
  const [inv, setInv] = useState({ role: "member", email: "" }); const [link, setLink] = useState(null);
  const [c, setC] = useState({ key: "", label: "", description: "", role_prompt: "", model: models[0] || "", part: "" });
  const owner = me?.is_owner;
  const load = async () => { setJ({ goal: "", success_text: "", db_check: "", ...(await api(`/api/rooms/${rid}/journey`, { rid })) }); };
  useEffect(() => { load().catch(() => {}); }, [rid]);
  const run = async (fn, ok) => { setMsg(""); try { await fn(); setMsg(ok); await load(); reload?.(); } catch (e) { setMsg(e.message); } };
  if (!owner) return <p className="muted">Only the workspace owner can change the setup. Ask them if the journey, hidden tests or agents need to change.</p>;
  return (
    <div>
      <p role="status" className={msg.includes("saved") || msg.includes("Saved") ? "ok" : "err"}>{msg}</p>
      <section className="panel">
        <h2>Verification profile</h2>
        <p className="muted">How much checking runs before a person is asked to approve. A human approves every merge in every profile.</p>
        <div className="row">{[["fast", "Fast: build, locked and hidden tests"], ["standard", "Standard: + lint, contracts, security scans, referee smoke journey"], ["strict", "Strict: + full referee journeys; any non-pass verdict blocks approval"]].map(([k, l]) =>
          <button key={k} className="quiet" onClick={() => run(() => api(`/api/rooms/${rid}/profile`, { rid, method: "PUT", body: { profile: k } }), `Profile set to ${k}. Saved.`)}>{l}</button>)}</div>
      </section>
      <section className="panel">
        <h2>Edit scope</h2>
        <p className="muted">Off: an agent may change any file (it is still guided to the relevant ones). Task: a task's change may only touch the files connected to that task in the project graph; anything else is rejected when it is submitted.</p>
        <div className="row">{[["off", "Off"], ["task", "Limit edits to the task's files"]].map(([k, l]) =>
          <button key={k} className="quiet" onClick={() => run(() => api(`/api/rooms/${rid}/edit-scope`, { rid, method: "PUT", body: { scope: k } }), `Edit scope set to ${k}. Saved.`)}>{l}</button>)}</div>
      </section>
      <section className="panel">
        <h2>Invite a teammate</h2>
        <p className="muted">Each invite link works once and expires in 7 days. The workspace name is not a password: nobody can join without a link.</p>
        <div className="row"><select style={{ width: "auto" }} value={inv.role} onChange={(e) => setInv({ ...inv, role: e.target.value })} aria-label="Role">
          <option value="member">Member: can run agents</option><option value="viewer">Viewer: read-only</option></select>
          <input className="grow" type="email" placeholder="Email (optional, the link is mailed if mail is set up)" value={inv.email} onChange={(e) => setInv({ ...inv, email: e.target.value })} aria-label="Email" />
          <button onClick={() => run(async () => { setLink(await api(`/api/rooms/${rid}/invites`, { rid, body: inv })); setInv({ ...inv, email: "" }); }, "Invite created. Saved.")}>Create invite</button></div>
        {link && <p className="small">{link.mailed ? "Mailed. " : "Not mailed: send this link yourself. "}It is shown once: <code>{link.link}</code> <button className="quiet" onClick={() => navigator.clipboard?.writeText(link.link)}>Copy</button></p>}
      </section>
      <section className="panel">
        <h2>Customer journey</h2>
        <p className="muted">What a new customer does, in plain words. The referee replays it in a real browser after each change. Use {"{email}"} where a fresh email address is needed.</p>
        <label htmlFor="g">Steps</label><textarea id="g" value={j.goal} onChange={(e) => setJ({ ...j, goal: e.target.value })} placeholder="Open the home page, create an account with {email}, add an item to the cart and check out." />
        <label htmlFor="s">Text the last page must show</label><input id="s" value={j.success_text} onChange={(e) => setJ({ ...j, success_text: e.target.value })} placeholder="Order placed" />
        <label htmlFor="d">Record the app must have afterwards (one SELECT, optional)</label><input id="d" value={j.db_check} onChange={(e) => setJ({ ...j, db_check: e.target.value })} placeholder="SELECT 1 FROM orders WHERE email = :email" />
        <p />
        <button onClick={() => run(() => api(`/api/rooms/${rid}/journey`, { rid, method: "PUT", body: j }), "Journey saved.")}>Save journey</button> <button className="quiet" onClick={() => run(async () => { const d = await api(`/api/rooms/${rid}/journey/draft`, { rid, method: "POST" }); setJ({ goal: d.goal, success_text: d.success_text, db_check: d.db_check }); }, "Draft ready: review it above, then approve it.")}>Draft from approved requirements</button>
        <button className="quiet" onClick={() => run(() => api(`/api/rooms/${rid}/journey/draft/approve`, { rid, body: j }), "Journey approved and saved.")}>Approve the draft</button>
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
