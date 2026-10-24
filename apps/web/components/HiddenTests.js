"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

/**
 * Hidden tests: a teammate writes one after the first build; a different person approves it.
 * Only names, authors and test names are ever shown here, never the test source.
 * @typedef {{filename:string, status:string, author_id:number|null, approved_by:number|null, tests:string[]}} HiddenTest
 */
export default function HiddenTests({ rid, me, members }) {
  const [list, setList] = useState([]); const [h, setH] = useState({ filename: "", content: "" }); const [msg, setMsg] = useState("");
  const viewer = me?.role === "viewer";
  const name = (id) => members.find((m) => m.id === id)?.name || "someone";
  const load = useCallback(async () => { try { setList(await api(`/api/rooms/${rid}/holdout/drafts`, { rid })); } catch (e) { setMsg(e.message); } }, [rid]);
  useEffect(() => { load(); }, [load]);
  const run = async (fn, ok) => { setMsg(""); try { await fn(); setMsg(ok); await load(); } catch (e) { setMsg(e.message); } };

  return (
    <div>
      <p className="muted">Written by a teammate after the first build, approved by a different person, then run on every change. Agents never see them, and nobody sees their source here.</p>
      <p role="status" className={msg.endsWith(".") && !msg.includes("must") ? "ok" : "err"}>{msg}</p>
      {list.length ? <table><tbody>{list.map((t) => <tr key={t.filename}>
        <td><code>{t.filename}</code><br /><span className="muted small">{t.tests.join(", ") || "no test functions found"}</span></td>
        <td className="small">by {name(t.author_id)}{t.approved_by ? `, approved by ${name(t.approved_by)}` : ""}</td>
        <td>{t.status}{t.status === "draft" && !viewer && t.author_id !== me.id && <> <button className="go" onClick={() => run(() => api(`/api/rooms/${rid}/holdout/${t.filename}/approve`, { rid, method: "POST" }), "Approved: it now runs on every change.")}>Approve</button></>}
          {t.status === "draft" && t.author_id === me.id && <span className="muted small"> · waiting for someone else to approve</span>}</td></tr>)}</tbody></table>
        : <p className="small muted">None yet.</p>}
      {!viewer && <>
        <label htmlFor="hf">File name</label><input id="hf" value={h.filename} onChange={(e) => setH({ ...h, filename: e.target.value })} placeholder="test_hidden_totals.py" />
        <label htmlFor="hc">Test code (uses the project's own fixtures, such as <code>client</code>)</label><textarea id="hc" value={h.content} onChange={(e) => setH({ ...h, content: e.target.value })} />
        <p /><button onClick={() => run(async () => { await api(`/api/rooms/${rid}/holdout`, { rid, body: h }); setH({ filename: "", content: "" }); }, "Submitted. A teammate must approve it.")}>Submit for approval</button>
      </>}
    </div>
  );
}
