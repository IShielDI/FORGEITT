"use client";
import { useEffect, useRef, useState } from "react";
import { withToken } from "../lib/api";

// Live view of what the agents are doing. Reconnects from the last event it saw.
export default function Feed({ rid, onFinished }) {
  const [lines, setLines] = useState([]); const [live, setLive] = useState(false); const last = useRef(0); const box = useRef(null);
  useEffect(() => {
    let es, stop = false, timer;
    const connect = () => {
      es = new EventSource(withToken(rid, `/api/rooms/${rid}/events?after=${last.current}`));
      es.onopen = () => setLive(true);
      es.onerror = () => { setLive(false); es.close(); if (!stop) timer = setTimeout(connect, 2500); };
      es.onmessage = (m) => {
        const e = JSON.parse(m.data); last.current = e.id;
        setLines((l) => [...l.slice(-299), e]);
        if (e.kind === "finished") onFinished?.(e);
      };
    };
    connect();
    return () => { stop = true; clearTimeout(timer); es?.close(); };
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
      <div className="row small muted"><span aria-live="polite">{live ? "Live" : "Reconnecting…"}</span></div>
      <div className="feed" ref={box} role="log" aria-label="Agent activity">{lines.length ? lines.map(render) : <div className="dim">Nothing yet. Pick an agent, describe a task, and press Run.</div>}</div>
    </div>
  );
}
