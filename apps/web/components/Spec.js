"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

/**
 * The living spec: proposed items from the observer, and what the team has confirmed.
 * A suggestion becomes a decision only when a person confirms it.
 * @typedef {{id:number, kind:string, text:string, status:string, version:number, source_message_ids:number[], supersedes_id:number|null}} SpecItem
 */
export default function Spec({ rid, me }) {
  const [data, setData] = useState(null); const [msgs, setMsgs] = useState({}); const [err, setErr] = useState(""); const [editing, setEditing] = useState(null); const [draft, setDraft] = useState("");
  const viewer = me?.role === "viewer";
  const load = useCallback(async () => {
    try {
      setData(await api(`/api/rooms/${rid}/spec`, { rid }));
      const page = await api(`/api/rooms/${rid}/messages?limit=200`, { rid });
      setMsgs(Object.fromEntries(page.map((m) => [m.id, m])));
    } catch (e) { setErr(e.message); }
  }, [rid]);
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, [load]);
  const act = async (fn) => { setErr(""); try { await fn(); setEditing(null); await load(); } catch (e) { setErr(e.message); } };
  if (!data) return <p className="muted">{err || "Loading…"}</p>;

  const proposed = data.items.filter((i) => i.status === "proposed");
  const confirmed = data.items.filter((i) => i.status === "confirmed");
  const row = (i) => (
    <li key={i.id} className="spec-item">
      <span className={`badge ${i.kind}`}>{i.kind}</span> {editing === i.id
        ? <span className="row"><input className="grow" value={draft} onChange={(e) => setDraft(e.target.value)} aria-label="Edit text" />
            <button onClick={() => act(() => api(`/api/spec/items/${i.id}/edit`, { rid, body: { text: draft } }))}>Save</button>
            <button className="quiet" onClick={() => setEditing(null)}>Cancel</button></span>
        : <span>{i.text}{i.version > 1 && <span className="muted small"> · v{i.version}</span>}</span>}
      <div className="small muted">From: {i.source_message_ids.length ? i.source_message_ids.map((id) => <span key={id} title={msgs[id]?.body || ""} className="src">“{(msgs[id]?.body || `message ${id}`).slice(0, 60)}”{msgs[id] ? ` (${msgs[id].author})` : ""} </span>) : "edited by a person"}</div>
      {!viewer && editing !== i.id && <div className="row">
        {i.status === "proposed" && <><button className="go" onClick={() => act(() => api(`/api/spec/items/${i.id}/confirm`, { rid, method: "POST" }))}>Confirm{i.kind === "suggestion" ? " as decision" : ""}</button>
          <button className="quiet" onClick={() => act(() => api(`/api/spec/items/${i.id}/reject`, { rid, method: "POST" }))}>Reject</button></>}
        <button className="quiet" onClick={() => { setEditing(i.id); setDraft(i.text); }}>Edit</button>
      </div>}
    </li>);

  return (
    <div>
      <p className="err" role="alert">{err}</p>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <p className="muted">The observer reads the chat and proposes items. Nothing counts until a person confirms it. Editing a confirmed item creates a new version to confirm.</p>
        {!viewer && <button className="quiet" onClick={() => act(() => api(`/api/rooms/${rid}/observe`, { rid, method: "POST" }))}>Check the chat now</button>}
      </div>
      <section className="panel"><h2>Proposed ({proposed.length})</h2>{proposed.length ? <ul className="plain">{proposed.map(row)}</ul> : <p className="muted">Nothing waiting.</p>}</section>
      <section className="panel"><h2>Confirmed {data.approved ? `· spec v${data.approved.version}` : ""}</h2>{confirmed.length ? <ul className="plain">{confirmed.map(row)}</ul> : <p className="muted">Nothing confirmed yet.</p>}</section>
    </div>
  );
}
