"use client";
import { useEffect, useState } from "react";
import { api, forget, recent } from "../lib/api";
import People from "./People";
import HiddenTests from "./HiddenTests";

const PROFILES = [["fast", "Fast", "Build, locked and hidden tests."], ["standard", "Standard", "Adds lint, contracts, security scans and a quick referee journey."], ["strict", "Strict", "Adds full referee journeys. Any non-pass verdict blocks approval."]];

// Owner-only setup: people, how much checking runs, the customer journey, hidden tests and the agent list.
export default function Setup({ rid, me, room, catalog, models, members, reload }) {
  const [j, setJ] = useState({ goal: "", success_text: "", db_check: "" }); const [msg, setMsg] = useState("");
  const [c, setC] = useState({ key: "", label: "", description: "", role_prompt: "", model: models[0] || "", part: "" });
  const [openCard, setOpenCard] = useState("people"); const [confirmName, setConfirmName] = useState(""); const [delErr, setDelErr] = useState("");
  const owner = me?.is_owner;
  const load = async () => { setJ({ goal: "", success_text: "", db_check: "", ...(await api(`/api/rooms/${rid}/journey`, { rid })) }); };
  useEffect(() => { load().catch(() => {}); }, [rid]);
  const removeWorkspace = async () => {
    setDelErr("");
    try {
      await api(`/api/rooms/${rid}`, { rid, method: "DELETE", body: { confirm_name: confirmName } });
      forget(rid);
      const next = recent()[0];
      window.location.href = next ? `/w/${next.id}` : "/";
    } catch (e) { setDelErr(e.message); }
  };
  const run = async (fn, ok) => { setMsg(""); try { await fn(); setMsg(ok); await load(); reload?.(); } catch (e) { setMsg(e.message); } };
  if (!owner) return <p className="muted">Only the workspace owner can change the setup. Ask them if the journey, hidden tests or agents need to change.</p>;
  const cardState = { openCard, setOpenCard };
  return (
    <div>
      <p role="status" className={/saved|Saved|set to/.test(msg) ? "ok" : "err"}>{msg}</p>
      <SetupCard {...cardState} id="people" title="People" hint="Who has joined, and invite more teammates."><People rid={rid} room={room} /></SetupCard>
      <SetupCard {...cardState} id="profile" title="How much checking" hint="What runs before a person is asked to approve.">
        <p className="muted small">A person approves every merge in every level.</p>
        {PROFILES.map(([k, l, d]) => <button key={k} className="pick-card opt" aria-pressed={room.room.profile === k} onClick={() => run(() => api(`/api/rooms/${rid}/profile`, { rid, method: "PUT", body: { profile: k } }), `Profile set to ${k}. Saved.`)}><b>{l}</b><span>{d}</span></button>)}
        <h3 style={{ marginTop: "1.2rem" }}>Limit edits to a task's files</h3>
        <p className="muted small">Off: an agent may change any file. Task: a change may only touch files connected to its task in the project graph, and anything else is rejected on submit.</p>
        <div className="row">{[["off", "Off"], ["task", "Limit edits to the task's files"]].map(([k, l]) =>
          <button key={k} className="quiet" onClick={() => run(() => api(`/api/rooms/${rid}/edit-scope`, { rid, method: "PUT", body: { scope: k } }), `Edit scope set to ${k}. Saved.`)}>{l}</button>)}</div>
      </SetupCard>
      <SetupCard {...cardState} id="journey" title="What a customer does" hint="The steps the referee replays in a real browser after each change.">
        <p className="muted">Write it in plain words. Use {"{email}"} where a fresh email address is needed.</p>
        <label htmlFor="g">Steps</label><textarea id="g" value={j.goal} onChange={(e) => setJ({ ...j, goal: e.target.value })} placeholder="Open the home page, create an account with {email}, add an item to the cart and check out." />
        <label htmlFor="s">Text the last page must show</label><input id="s" value={j.success_text} onChange={(e) => setJ({ ...j, success_text: e.target.value })} placeholder="Order placed" />
        <label htmlFor="d">Record the app must have afterwards (one SELECT, optional)</label><input id="d" value={j.db_check} onChange={(e) => setJ({ ...j, db_check: e.target.value })} placeholder="SELECT 1 FROM orders WHERE email = :email" />
        <div className="actions">
          <button onClick={() => run(() => api(`/api/rooms/${rid}/journey`, { rid, method: "PUT", body: j }), "Journey saved.")}>Save</button>
          <button className="quiet" onClick={() => run(async () => { const d = await api(`/api/rooms/${rid}/journey/draft`, { rid, method: "POST" }); setJ({ goal: d.goal, success_text: d.success_text, db_check: d.db_check }); }, "Draft ready: review it above, then approve it.")}>Draft from approved requirements</button>
          <button className="quiet" onClick={() => run(() => api(`/api/rooms/${rid}/journey/draft/approve`, { rid, body: j }), "Journey approved and saved.")}>Approve the draft</button>
        </div>
      </SetupCard>
      <SetupCard {...cardState} id="hidden" title="Hidden tests" hint="Checks agents never see. A teammate writes them, a different person approves.">
        <HiddenTests rid={rid} me={me} members={members} />
      </SetupCard>
      <SetupCard {...cardState} id="agents" title="Agents" hint="The list your team picks from.">
        <table><tbody>{catalog.map((a) => <tr key={a.key}><td><b>{a.label}</b><br /><span className="muted small">{a.description}</span></td><td className="small">{a.model}</td>
          <td><button className="quiet" onClick={() => setC({ ...a, part: a.part || "" })}>Edit</button> <button className="quiet" onClick={() => run(() => api(`/api/rooms/${rid}/catalog/${a.key}`, { rid, method: "DELETE" }), "Agent removed. Saved.")}>Remove</button></td></tr>)}</tbody></table>
        <label htmlFor="ck">Short name (letters, digits, - or _)</label><input id="ck" value={c.key} onChange={(e) => setC({ ...c, key: e.target.value })} />
        <label htmlFor="cl">Name shown to the team</label><input id="cl" value={c.label} onChange={(e) => setC({ ...c, label: e.target.value })} />
        <label htmlFor="cd">What it is for</label><input id="cd" value={c.description} onChange={(e) => setC({ ...c, description: e.target.value })} />
        <label htmlFor="cp">Instructions that shape how it works</label><textarea id="cp" value={c.role_prompt} onChange={(e) => setC({ ...c, role_prompt: e.target.value })} />
        <label htmlFor="cm">Model</label><select id="cm" value={c.model} onChange={(e) => setC({ ...c, model: e.target.value })}>{models.map((m) => <option key={m}>{m}</option>)}</select>
        <div className="actions"><button onClick={() => run(() => api(`/api/rooms/${rid}/catalog`, { rid, method: "PUT", body: { ...c, part: c.part || null } }), "Agent saved.")}>Save agent</button></div>
      </SetupCard>
      <SetupCard {...cardState} id="delete" title="Delete workspace" hint="Permanently remove this workspace for everyone.">
        <p className="muted">This removes the chat, spec, plan, changes, agents, credits records, members' keys and the project files for everyone, and every teammate's login stops working. It cannot be undone. Stop any running agent first.</p>
        <label htmlFor="dn">Type the workspace name, <b>{room.room.name}</b>, to confirm</label>
        <input id="dn" autoComplete="off" value={confirmName} onChange={(e) => setConfirmName(e.target.value)} />
        <p className="err" role="alert">{delErr}</p>
        <div className="actions"><button className="danger" disabled={confirmName.trim() !== room.room.name} onClick={removeWorkspace}>Delete this workspace</button></div>
      </SetupCard>
    </div>
  );
}

// Defined outside Setup so React keeps the same component between renders (inputs keep focus while typing).
function SetupCard({ id, title, hint, children, openCard, setOpenCard }) {
  return (
    <section className="card acc" data-open={openCard === id}>
      <button className="acc-head" aria-expanded={openCard === id} onClick={() => setOpenCard(openCard === id ? "" : id)}>
        <span><b>{title}</b><span>{hint}</span></span>
        <svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 7l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      {openCard === id && <div className="acc-body">{children}</div>}
    </section>);
}
