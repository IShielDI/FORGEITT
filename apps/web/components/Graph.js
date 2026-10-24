"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { layout } from "../lib/graph.mjs";

/**
 * The project's memory graph: requirements, decisions, contracts, tasks, parts, files, changes and
 * failures, joined by the links the platform records. Agents get only the slice connected to their task.
 * @typedef {{id:string, type:string, label:string, status:string}} GNode
 * @typedef {{source:string, target:string, relation:string}} GEdge
 */
const COLORS = { requirement: "#2e7d4f", decision: "#3b6fd1", suggestion: "#b08a1e", question: "#8a8f98", contract: "#8e44ad",
  task: "#e07a1f", part: "#a3b18a", file: "#5b7083", change: "#16a3a3", commit: "#94a3b8", failure: "#be3a2b" };
const W = 900, H = 560;

export default function Graph({ rid }) {
  const [data, setData] = useState(null); const [err, setErr] = useState(""); const [sel, setSel] = useState(null);
  const [hidden, setHidden] = useState({ commit: true }); const [query, setQuery] = useState("");
  const [view, setView] = useState({ x: 0, y: 0, k: 1 }); const drag = useRef(null);
  const load = useCallback(async () => { try { setData(await api(`/api/rooms/${rid}/graph`, { rid })); } catch (e) { setErr(e.message); } }, [rid]);
  useEffect(() => { load(); }, [load]);

  const shown = useMemo(() => {
    if (!data) return null;
    const nodes = data.nodes.filter((n) => !hidden[n.type]);
    const ids = new Set(nodes.map((n) => n.id));
    const edges = data.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    return { nodes, edges, pos: layout(nodes, edges, W, H) };
  }, [data, hidden]);
  if (!shown) return <p className="muted">{err || "Loading the project map…"}</p>;

  const types = [...new Set(data.nodes.map((n) => n.type))].sort();
  const neighbours = sel ? new Set(shown.edges.flatMap((e) => (e.source === sel ? [e.target] : e.target === sel ? [e.source] : []))) : null;
  const q = query.trim().toLowerCase();
  const dim = (id) => (sel && id !== sel && !neighbours.has(id)) || (q && !shown.nodes.find((n) => n.id === id)?.label.toLowerCase().includes(q));
  const byId = Object.fromEntries(shown.nodes.map((n) => [n.id, n]));
  const links = sel ? shown.edges.filter((e) => e.source === sel || e.target === sel) : [];

  const onWheel = (e) => { e.preventDefault(); const k = Math.min(4, Math.max(0.3, view.k * (e.deltaY < 0 ? 1.1 : 0.9))); setView({ ...view, k }); };
  const onDown = (e) => { drag.current = { x: e.clientX - view.x, y: e.clientY - view.y }; };
  const onMove = (e) => { if (drag.current) setView({ ...view, x: e.clientX - drag.current.x, y: e.clientY - drag.current.y }); };
  const onUp = () => { drag.current = null; };

  return (
    <div className="cols" style={{ gridTemplateColumns: "minmax(0,1fr) 20rem" }}>
      <section>
        <div className="row">
          <input className="grow" placeholder="Find a node" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Find a node" />
          <button className="quiet" onClick={load}>Refresh</button>
          <button className="quiet" onClick={() => setView({ x: 0, y: 0, k: 1 })}>Reset view</button>
        </div>
        <div className="row small" style={{ margin: ".5rem 0" }}>{types.map((t) => (
          <label key={t} className="row" style={{ margin: 0, gap: ".25rem", color: "var(--ink)" }}>
            <input type="checkbox" style={{ width: "auto" }} checked={!hidden[t]} onChange={() => setHidden({ ...hidden, [t]: !hidden[t] })} />
            <i style={{ width: 10, height: 10, borderRadius: 5, background: COLORS[t] || "#999", display: "inline-block" }} />{t}
          </label>))}</div>
        <svg className="graph" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Project memory graph" onWheel={onWheel} onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}>
          <g transform={`translate(${view.x},${view.y}) scale(${view.k})`}>
            {shown.edges.map((e, i) => { const a = shown.pos[e.source], b = shown.pos[e.target];
              return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="g-edge" opacity={dim(e.source) || dim(e.target) ? 0.08 : 0.5} />; })}
            {shown.nodes.map((n) => { const p = shown.pos[n.id];
              return <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={dim(n.id) ? 0.15 : 1} onMouseDown={(ev) => ev.stopPropagation()} onClick={() => setSel(sel === n.id ? null : n.id)} style={{ cursor: "pointer" }}>
                <circle r={n.type === "part" ? 9 : 6} fill={COLORS[n.type] || "#999"} stroke={n.status === "failing" || n.status === "tests_failed" ? "#be3a2b" : sel === n.id ? "var(--whistle)" : "var(--paper)"} strokeWidth={sel === n.id || n.status === "failing" ? 3 : 1.5} />
                {(view.k > 0.8 || n.type === "part" || sel === n.id) && <text x="9" y="4" className="g-label">{n.label.length > 32 ? n.label.slice(0, 31) + "…" : n.label}</text>}
              </g>; })}
          </g>
        </svg>
        <p className="muted small">Scroll to zoom, drag to move. When a task starts, its agent gets only the files and items connected to it (see Relevant files in its context).</p>
      </section>
      <aside>
        <h2>{sel ? byId[sel]?.label : "Select a node"}</h2>
        {sel ? <>
          <p className="small muted">{byId[sel]?.type}{byId[sel]?.status ? ` · ${byId[sel].status}` : ""}</p>
          <ul className="plain small">{links.map((e, i) => { const other = e.source === sel ? e.target : e.source;
            return <li key={i}><span className="muted">{e.source === sel ? e.relation + " →" : "← " + e.relation}</span> <button className="quiet" style={{ padding: ".1rem .4rem" }} onClick={() => setSel(other)}>{byId[other]?.label || other}</button></li>; })}</ul>
        </> : <p className="muted small">Click a requirement to see the tasks implementing it, a task to see its files and contracts, or a failure to see where it was routed.</p>}
        <p className="small muted">{shown.nodes.length} nodes · {shown.edges.length} links</p>
      </aside>
    </div>
  );
}
