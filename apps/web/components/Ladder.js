"use client";
import { useEffect, useState } from "react";
import { api, withToken } from "../lib/api";

const ref = (c) => c?.evidence?.referee;
function rungs(c) {
  const ev = c.evidence || {}, tests = ev.tests?.tests || [], vis = tests.filter((t) => !t.hidden), hid = tests.filter((t) => t.hidden);
  const bad = (a) => a.filter((t) => !t.passed);
  const r = ref(c);
  const out = [];
  if (ev.routed && !r) out.push({ t: "Failure routing", s: "fail", d: "Where the failure most likely comes from", routed: ev.routed });
  if (ev.firewall) out.push({ t: "Firewall", s: "fail", d: "This change touched protected files, so it was rejected: " + ev.firewall.map((f) => f.path).join(", ") });
  else if (ev.conflict) out.push({ t: "Merge", s: "fail", d: `It conflicts with ${ev.conflict.conflict_with}. The owner has to resolve it.` });
  out.push(vis.length ? { t: "Locked tests", s: bad(vis).length ? "fail" : "pass", d: bad(vis).length ? bad(vis).map((t) => t.name).join(", ") + " failed" : `${vis.length} passed` } : { t: "Locked tests", s: ev.firewall || ev.conflict ? "skip" : "wait", d: "Not run yet" });
  out.push(hid.length ? { t: "Hidden tests", s: bad(hid).length ? "fail" : "pass", d: bad(hid).length ? bad(hid).map((t) => t.name.replace(/.*::/, "")).join(", ") + " failed" : `${hid.length} passed (the agent never saw these)` } : { t: "Hidden tests", s: "skip", d: "None yet. Add some in Setup." });
  if (r) {
    const v = r.verdict, s = v === "pass" ? "pass" : v === "not_run" ? "wait" : ["inconclusive", "service_error"].includes(v) ? "wait" : "fail";
    out.push({ t: "Referee in a real browser", s, d: r.reason, v: v.replace(/_/g, " "), standin: r.runner === "local-standin", routed: r.routed });
  } else {
    const noRun = c.status === "tests_failed" || ev.firewall || ev.conflict || c.kind === "bootstrap" || c.verdict === "tests_only" || c.status === "merged" || c.status === "undone";
    out.push({ t: "Referee in a real browser", s: noRun ? "skip" : "wait",
      d: c.kind === "bootstrap" ? "Starts with the next change, once a customer journey is written in Setup."
        : c.verdict === "tests_only" ? "No customer journey is defined for this project, so only the locked tests were used."
        : noRun ? "Did not run for this change." : "Waiting for the referee." });
  }
  return out;
}

export default function Ladder({ rid, id, me, onChanged }) {
  const [c, setC] = useState(null); const [err, setErr] = useState(""); const [ack, setAck] = useState(false); const [merge, setMerge] = useState(null);
  const load = async () => { try { setC(await api(`/api/changes/${id}`, { rid })); setMerge((await api(`/api/rooms/${rid}/merges`, { rid })).find((m) => m.undone === 0 && JSON.parse(m.change_ids).includes(id)) || null); } catch (e) { setErr(e.message); } };
  useEffect(() => { setC(null); setAck(false); load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, [id]);
  if (!c) return <p className="muted">{err || "Loading…"}</p>;
  const act = async (fn) => { setErr(""); try { await fn(); await load(); onChanged?.(); } catch (e) { setErr(e.message); } };
  const rs = rungs(c), r = ref(c), ev = c.evidence || {};
  const canApprove = c.status === "passed" || c.status === "bootstrap_review" || (c.status === "inconclusive" && ack);
  const batch = ev.batch, run = r?.runs?.[0], vid = r?.runner === "tinyfish" && batch ? withToken(rid, `/api/evidence/${rid}/${batch}/${run?.label || "combined"}-run${(run?.attempts?.length || 1) - 1}/run.mp4`) : null;
  return (
    <div>
      <h2>{c.summary}</h2>
      <p className="muted small">by {c.agent.replace("-agent", "")} · {c.status.replace(/_/g, " ")}</p>
      <ol className="ladder">
        {rs.map((x, i) => (
          <li key={i} data-s={x.s}>
            <h3>{x.t}</h3>
            {x.v && <p className="verdict">{x.v}</p>}
            <p>{x.d}</p>
            {x.standin && <p className="err">This was the offline stand-in, not a real browser run. It is not a TinyFish verdict.</p>}
            {x.routed && <p>Sent to <b>{x.routed.assigned_to || x.routed.owner || x.routed.part}</b> ({x.routed.part}{x.routed.confidence != null ? `, confidence ${Math.round(x.routed.confidence * 100)}%: likely, not certain` : ""}): {x.routed.why}{x.routed.triage ? " · low confidence, so the workspace owner triages it" : ""}</p>}
            {x.t.startsWith("Referee") && vid && <video controls src={vid} onError={(e) => (e.currentTarget.style.display = "none")} />}
          </li>
        ))}
        <li data-s={c.status === "merged" ? "pass" : canApprove ? "wait" : "skip"}>
          <h3>Human approval</h3>
          <p>{c.status === "merged" ? "Merged." : c.status === "undone" ? "Merged, then undone." : canApprove ? "Everything above checked out. A person decides." : "Not ready to approve."}</p>
          {c.status === "bootstrap_review" && <p className="err">Read the spec and tests below first. Once approved they become the locked original.</p>}
          {c.status === "inconclusive" && <label className="row"><input type="checkbox" style={{ width: "auto" }} checked={ack} onChange={(e) => setAck(e.target.checked)} /> I looked at the evidence and want to merge anyway</label>}
          <div className="row">
            {c.status !== "merged" && c.status !== "undone" && <button className="go" disabled={!canApprove} onClick={() => act(() => api(`/api/rooms/${rid}/approve`, { rid, body: { change_ids: [id], allow_inconclusive: ack } }))}>Approve and merge</button>}
            {c.status === "merged" && merge && <button className="quiet" onClick={() => act(() => api(`/api/rooms/${rid}/undo/${merge.id}`, { rid, method: "POST" }))}>Undo this merge</button>}
          </div>
        </li>
      </ol>
      <p className="err" role="alert">{err}</p>
      {!!c.attempts?.length && <details><summary>{c.attempts.length} blocked attempt(s) by this agent</summary><ul>{c.attempts.map((a) => <li key={a.id} className="small">{a.action}: <code>{a.path}</code></li>)}</ul></details>}
      {!!ev.tests?.checks?.length && <details><summary>Checks ({ev.tests.profile || "standard"} profile{ev.tests.isolation ? `, mirror: ${ev.tests.isolation === "docker" ? "isolated container" : "host (not isolated)"}` : ""})</summary>
        <table><tbody>{ev.tests.checks.map((k) => <tr key={k.name}><td>{k.name.replace(/_/g, " ")}</td><td>{k.status}</td><td className="small"><code>{k.command}</code></td><td className="small">exit {k.exit_code ?? "–"} · {k.duration_ms} ms</td></tr>)}</tbody></table>
      </details>}
      {ev.diff?.stat && <details open={c.status === "bootstrap_review"}><summary>What changed</summary><pre>{c.status === "bootstrap_review" ? ev.diff.diff : ev.diff.stat}</pre></details>}
    </div>
  );
}
