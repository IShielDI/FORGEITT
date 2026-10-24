"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

const Tick = () => <svg className="tick" viewBox="0 0 18 18" aria-hidden="true"><path d="M3.5 9.5l3.5 3.5 7.5-8" /></svg>;

// Who is in the workspace, and the single-use invite links for more. A link is shown once, and mailed when mail is set up.
export default function People({ rid, room }) {
  const [list, setList] = useState([]); const [inv, setInv] = useState({ role: "member", email: "" }); const [link, setLink] = useState(null); const [msg, setMsg] = useState(""); const [busy, setBusy] = useState(false);
  const load = async () => { try { setList(await api(`/api/rooms/${rid}/invites`, { rid })); } catch (e) { setMsg(e.message); } };
  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, [rid]);
  const create = async () => {
    setMsg(""); setBusy(true);
    try { setLink(await api(`/api/rooms/${rid}/invites`, { rid, body: inv })); setInv({ ...inv, email: "" }); await load(); }
    catch (e) { setMsg(e.message); } finally { setBusy(false); }
  };
  const when = (t) => new Date(t * 1000).toLocaleDateString();
  const pending = list.filter((i) => !i.used_at);
  return (
    <div>
      <h3>In this workspace</h3>
      {room.members.map((m) => <div className="invite-row" key={m.id}><Tick /><span><b>{m.name}</b> <span className="muted small">{m.is_owner ? "owner" : m.role || "member"}</span></span></div>)}
      <h3 style={{ marginTop: "1.2rem" }}>Invite a teammate</h3>
      <p className="muted small">Each link works once and expires in 7 days. Nobody can join without one.</p>
      <div className="row">
        <select style={{ width: "auto" }} value={inv.role} onChange={(e) => setInv({ ...inv, role: e.target.value })} aria-label="Role"><option value="member">Member: can run agents</option><option value="viewer">Viewer: read-only</option></select>
        <input className="grow" type="email" placeholder="Email (optional: the link is mailed if mail is set up)" value={inv.email} onChange={(e) => setInv({ ...inv, email: e.target.value })} aria-label="Email" />
        <button className="go" onClick={create} disabled={busy}>Create invite</button>
      </div>
      <p className="err" role="alert">{msg}</p>
      {link && <div className="card" style={{ marginTop: ".8rem" }}>
        <p className="small" style={{ marginTop: 0 }}>{link.mailed ? "Mailed. " : "Not mailed: send this link yourself. "}It is shown once.</p>
        <p><code className="token">{link.link}</code> <button className="quiet" onClick={() => navigator.clipboard?.writeText(link.link)}>Copy</button></p>
      </div>}
      {!!pending.length && <><h3 style={{ marginTop: "1.2rem" }}>Waiting to be used</h3>
        {pending.map((i) => <div className="invite-row" key={i.id}><span>{i.role}{i.email ? ` · ${i.email}` : ""} <span className="muted small">expires {when(i.expires)}</span></span></div>)}</>}
    </div>
  );
}
