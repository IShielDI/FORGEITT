"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

/**
 * Plan board: proposed tasks (owner, component, dependencies) and the contracts they rely on.
 * The owner approves the plan, which pins the contract versions. Tasks start only after that.
 * @typedef {{id:number, key:string, title:string, description:string, component:string, depends_on:string[], owner_member_id:number|null, status:string, contract_ids:number[]}} Task
 */
export default function Plan({ rid, me, members, blankFirst = false }) {
  const [data, setData] = useState(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const viewer = me?.role === "viewer", owner = me?.is_owner;
  const load = useCallback(async () => { try { setData(await api(`/api/rooms/${rid}/plan`, { rid })); } catch (e) { setErr(e.message); } }, [rid]);
  useEffect(() => { load(); const t = setInterval(load, 6000); return () => clearInterval(t); }, [load]);
  const act = async (fn) => { setErr(""); setBusy(true); try { await fn(); await load(); } catch (e) { setErr(e.message); } finally { setBusy(false); } };
  if (!data) return <p className="muted">{err || "Loading…"}</p>;

  const proposed = data.tasks.some((t) => t.status === "proposed");
  const contractsById = Object.fromEntries(data.contracts.map((c) => [c.id, c]));
  const people = members.filter((m) => (m.role || "member") !== "viewer");
  return (
    <div>
      <p className="err" role="alert">{err}</p>
      <div className="row">
        {!viewer && !data.tasks.some((t) => !["proposed", "dropped"].includes(t.status)) && <button disabled={busy} onClick={() => act(() => api(`/api/rooms/${rid}/plan/generate`, { rid, method: "POST" }))}>{data.tasks.length ? "Propose a new plan" : "Propose a plan from the spec"}</button>}
        {owner && proposed && <button className="go" disabled={busy} onClick={() => act(() => api(`/api/rooms/${rid}/plan/approve`, { rid, method: "POST" }))}>Approve plan and pin contracts</button>}
        {!owner && proposed && <span className="muted small">The workspace owner approves the plan.</span>}
      </div>
      {(data.stale || []).length > 0 && <p className="warn-note">The team changed its mind in the spec: {data.stale.join(", ")} {data.stale.length === 1 ? "is" : "are"} built on an option that was replaced. {owner ? "Drop the task below" : "The owner can drop it"}{proposed ? ", or propose a new plan" : ""}.</p>}
      <section className="panel"><h2>Tasks</h2>
        {blankFirst && <p className="muted small">This project is empty, so the first task you start builds its first version. Review and approve that build on the Work tab; it becomes the locked baseline, and then the other tasks can start.</p>}
        {data.tasks.length ? <table><thead><tr><th>Task</th><th>Component</th><th>Depends on</th><th>Owner</th><th>Contracts</th><th>Status</th></tr></thead><tbody>
          {data.tasks.map((t) => <tr key={t.id}>
            <td><b>{t.title}</b><br /><span className="muted small">{t.key} · {t.description}</span></td>
            <td>{t.component}</td><td>{t.depends_on.join(", ") || "none"}</td>
            <td>{t.status === "proposed" && !viewer
              ? <select aria-label={`Owner of ${t.key}`} style={{ width: "auto" }} value={t.owner_member_id || ""} onChange={(e) => act(() => api(`/api/tasks/${t.id}`, { rid, method: "PATCH", body: { owner_member_id: e.target.value ? +e.target.value : null } }))}>
                  <option value="">unassigned</option>{people.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select>
              : members.find((m) => m.id === t.owner_member_id)?.name || "unassigned"}</td>
            <td className="small">{t.contract_ids.map((id) => contractsById[id] ? `${contractsById[id].name} v${contractsById[id].version}` : id).join(", ")}</td>
            <td className={t.status === "dropped" ? "muted" : ""}>{t.status}
              {owner && (data.stale || []).includes(t.key) && <><br /><button className="quiet" disabled={busy} onClick={() => act(() => api(`/api/tasks/${t.id}/drop`, { rid, method: "POST" }))}>Drop task</button></>}
              {!viewer && t.status === "approved" && (t.owner_member_id === me.id || owner || !t.owner_member_id) && <><br /><button className="go" disabled={busy} onClick={() => act(() => api(`/api/tasks/${t.id}/start`, { rid, body: { member_id: me.id } }))}>Start</button></>}</td></tr>)}
        </tbody></table> : <p className="muted">No plan yet. Confirm some spec items first, then propose a plan.</p>}
      </section>
      <section className="panel"><h2>Contracts</h2>
        {data.contracts.length ? <ul className="plain">{data.contracts.map((c) => <li key={c.id} className="spec-item">
          <span className="badge">{c.kind}</span> <b>{c.name}</b> v{c.version} · <span className="muted">{c.status}</span>
          {owner && c.status === "proposed" && !proposed && <button className="quiet" onClick={() => act(() => api(`/api/contracts/${c.id}/approve`, { rid, method: "POST" }))}>Approve this version</button>}
          <pre>{c.content}</pre></li>)}</ul> : <p className="muted">Contracts (API shapes, schemas, shared types) are proposed with the plan.</p>}
      </section>
    </div>
  );
}
