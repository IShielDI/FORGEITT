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

  const open = (data.conflicts || []).filter((c) => c.status === "open");
  const settled = (data.conflicts || []).filter((c) => c.status === "resolved").slice(0, 5);
  const inConflict = new Set(open.flatMap((c) => [c.earlier.id, c.latest.id]));
  const proposed = data.items.filter((i) => i.status === "proposed" && !inConflict.has(i.id));
  const confirmed = data.items.filter((i) => i.status === "confirmed");
  const owner = me?.is_owner;
  const side = (c, s, label) => {
    const mine = s.picked_by.includes(me?.name);
    return (
      <div className={"conflict-side" + (label === "Latest" ? " latest" : "")}>
        <span className="eyebrow">{label}{s.status === "confirmed" ? " · confirmed earlier" : ""}</span>
        <p><span className={`badge ${s.kind}`}>{s.kind}</span> {s.text}</p>
        <p className="muted small">Said by {s.by.join(", ") || "a person"} · picked by {s.picked_by.join(", ") || "nobody yet"}</p>
        {!viewer && <div className="row">
          <button className={mine ? "" : "quiet"} aria-pressed={mine} onClick={() => act(() => api(`/api/spec/conflicts/${c.id}/vote`, { rid, body: { choice: s.id } }))}>{mine ? "Your pick" : "Pick this"}</button>
          {owner && <button className="go" onClick={() => act(() => api(`/api/spec/conflicts/${c.id}/decide`, { rid, body: { choice: s.id } }))}>Decide: keep this</button>}
        </div>}
      </div>);
  };
  const waiting = (c) => c.involved.filter((n) => !c.earlier.picked_by.includes(n) && !c.latest.picked_by.includes(n));
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
      {open.length > 0 && <section className="panel conflicts"><h2>Conflicting decisions ({open.length})</h2>
        <p className="muted small">The chat changed its mind. Pick the option you want: if everyone who argued picks the same one, it is applied. If they disagree, the workspace owner makes the final call. Only the chosen option goes into the spec and the plan.</p>
        {open.map((c) => <div key={c.id} className="conflict">
          <div className="conflict-pair">{side(c, c.earlier, "Earlier")}{side(c, c.latest, "Latest")}</div>
          <div className="row small">
            <span className="muted grow">{waiting(c).length ? `Waiting for: ${waiting(c).join(", ")}` : "Everyone who argued has picked, but they disagree: the owner decides."}</span>
            {owner && <button className="quiet" onClick={() => act(() => api(`/api/spec/conflicts/${c.id}/decide`, { rid, body: { choice: 0 } }))}>Not a conflict: both can stand</button>}
          </div>
        </div>)}
      </section>}
      {(data.plan_stale || []).length > 0 && <p className="warn-note">The spec changed after the plan was made: task {data.plan_stale.join(", ")} is built on an option that was replaced. Propose a new plan on the Plan tab.</p>}
      <section className="panel"><h2>Proposed ({proposed.length})</h2>{proposed.length ? <ul className="plain">{proposed.map(row)}</ul> : <p className="muted">Nothing waiting.</p>}</section>
      <section className="panel"><h2>Confirmed {data.approved ? `· spec v${data.approved.version}` : ""}</h2>{confirmed.length ? <ul className="plain">{confirmed.map(row)}</ul> : <p className="muted">Nothing confirmed yet.</p>}</section>
      {settled.length > 0 && <section className="panel"><h2>Settled conflicts</h2><ul className="plain">{settled.map((c) => {
        if (c.decided_how === "both") return <li key={c.id} className="small">Kept both “{c.earlier.text}” and “{c.latest.text}” · the owner said they do not conflict</li>;
        const win = c.winner_id === c.latest.id ? c.latest : c.earlier, lose = win === c.latest ? c.earlier : c.latest;
        return <li key={c.id} className="small">Kept “{win.text}” over “{lose.text}” · {c.decided_how === "agreement" ? "everyone who argued agreed" : "decided by the owner"}</li>; })}</ul></section>}
    </div>
  );
}
