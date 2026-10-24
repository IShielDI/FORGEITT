"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

// Live view of what the agents are doing.
export default function Feed({ rid, onFinished }) {
  const [lines, setLines] = useState([]); const [live, setLive] = useState(false); const last = useRef(0); const box = useRef(null);
  useEffect(() => {
    // Polls the activity list. Plain requests work through every proxy and tunnel (Cloudflare quick tunnels do not support server-sent events).
    let stop = false, timer, primed = false;
    const tick = async () => {
      try {
        const rows = await api(`/api/rooms/${rid}/events/list?after=${last.current}`, { rid });
        setLive(true);
        if (rows.length) {
          last.current = rows[rows.length - 1].id;
          setLines((l) => { const have = new Set(l.map((e) => e.id)); return [...l, ...rows.filter((e) => !have.has(e.id))].slice(-300); });   // overlapping polls must not repeat lines
          if (primed) rows.filter((e) => e.kind === "finished").forEach((e) => onFinished?.(e));   // history is not news
        }
        primed = true;
      } catch { setLive(false); }
      if (!stop) timer = setTimeout(tick, 1500);
    };
    tick();
    return () => { stop = true; clearTimeout(timer); };
  }, [rid]);
  useEffect(() => { box.current?.scrollTo(0, box.current.scrollHeight); }, [lines]);

  const render = (e) => {
    const d = e.data, who = e.agent.replace("-agent", "");
    if (e.kind === "started") return <div key={e.id} className="dim">{who} starts{d.bootstrap ? " the first build" : ""}: {d.task}</div>;
    if (e.kind === "step") return <div key={e.id}>{who} · step {d.n}{d.text ? `: ${d.text}` : ""}{(d.actions || []).map((a, i) => <div key={i} className="dim">  {a.tool === "bash" ? "$" : a.tool.replace("str_replace_based_edit_tool", "edit")} {a.brief}</div>)}</div>;
    if (e.kind === "result") return d.blocked ? <div key={e.id} className="blocked">Blocked by the firewall: the agent tried to touch protected files.</div> : null;
    if (e.kind === "budget") return <div key={e.id} className="dim">{who} has used {d.checkpoint}% of its credits.</div>;
    if (e.kind === "ended") return <div key={e.id} className="dim">{who} stopped: {d.status}, {d.steps} steps.</div>;
    if (e.kind === "finished") return <div key={e.id} className="done">{d.status === "done" ? `${who} finished. ${d.change_status ? "Change status: " + d.change_status.replace(/_/g, " ") + "." : ""}` : `${who}: ${d.status}. ${d.note || ""}`}</div>;
    return null;
  };
  return (
    <div>
      <div className={"live" + (live ? " on" : "")}><i /><span aria-live="polite">{live ? "Live" : "Reconnecting…"}</span></div>
      <div className="feed" ref={box} role="log" aria-label="Agent activity">{lines.length ? lines.map(render) : <div className="dim">Nothing yet. Pick an agent, describe a task, and press Run.</div>}</div>
    </div>
  );
}
