"use client";
import { useEffect, useRef, useState } from "react";
import { api, API, getToken } from "../lib/api";
import { mergeMessages, wsUrl } from "../lib/util.mjs";
import { appendTranscript } from "../lib/speech.mjs";
import MicButton from "./MicButton";

/**
 * Team chat: history plus live updates over a WebSocket (falls back to polling when the socket
 * cannot connect, e.g. through a proxy). Messages are plain text, never rendered as HTML.
 * @param {{rid: number, me: {id: number, role: string}, members: {id: number, name: string, role?: string}[]}} props
 */
export default function Chat({ rid, me, members }) {
  const [msgs, setMsgs] = useState([]); const [text, setText] = useState(""); const [live, setLive] = useState(false); const [err, setErr] = useState("");
  const box = useRef(null); const sock = useRef(null);
  const viewer = me?.role === "viewer";

  useEffect(() => {
    let stop = false, poll, retry;
    const load = async () => { try { const page = await api(`/api/rooms/${rid}/messages?limit=100`, { rid }); setMsgs((l) => mergeMessages(l, page)); } catch (e) { setErr(e.message); } };
    const connect = () => {
      const ws = new WebSocket(wsUrl(API, window.location, `/api/rooms/${rid}/ws`, { token: getToken(rid) }));
      sock.current = ws;
      ws.onopen = () => { setLive(true); clearInterval(poll); };
      ws.onmessage = (e) => { const d = JSON.parse(e.data); if (d.type === "message") setMsgs((l) => mergeMessages(l, [d.message])); else if (d.type === "error") setErr(d.detail); };
      ws.onclose = () => { setLive(false); if (!stop) { clearInterval(poll); poll = setInterval(load, 3000); retry = setTimeout(connect, 5000); } };
    };
    load(); connect();
    return () => { stop = true; clearInterval(poll); clearTimeout(retry); sock.current?.close(); };
  }, [rid]);
  useEffect(() => { box.current?.scrollTo(0, box.current.scrollHeight); }, [msgs]);

  const send = async (e) => {
    e.preventDefault(); const body = text.trim(); if (!body) return; setErr("");
    try {
      if (sock.current?.readyState === WebSocket.OPEN) sock.current.send(JSON.stringify({ body }));
      else { const m = await api(`/api/rooms/${rid}/messages`, { rid, body: { body } }); setMsgs((l) => mergeMessages(l, [m])); }
      setText("");
    } catch (x) { setErr(x.message); }
  };

  return (
    <div className="cols" style={{ gridTemplateColumns: "minmax(0,1fr) 15rem" }}>
      <section>
        <div className="row small muted"><span aria-live="polite">{live ? "Live" : "Reconnecting… (updates every few seconds)"}</span></div>
        <div className="feed chat" ref={box} role="log" aria-label="Team chat">
          {msgs.length ? msgs.map((m) => <div key={m.id}><b>{m.author || "someone"}</b> <span className="dim small">{new Date(m.ts * 1000).toLocaleTimeString()}</span><div>{m.body}</div></div>) : <div className="dim">No messages yet. Say what you want to build.</div>}
        </div>
        <p className="err" role="alert">{err}</p>
        {viewer ? <p className="muted small">You are a viewer: you can read the chat but not post.</p> : (
          <form className="row" onSubmit={send}>
            <input className="grow" value={text} onChange={(e) => setText(e.target.value)} placeholder="Message the team (or press the mic and speak)" aria-label="Message" maxLength={4000} />
            <MicButton label="Dictate a message" onText={(t) => setText((cur) => appendTranscript(cur, t).slice(0, 4000))} />
            <button disabled={!text.trim()}>Send</button>
          </form>)}
      </section>
      <aside>
        <h2>Members</h2>
        <ul className="plain">{members.map((m) => <li key={m.id}>{m.name}<span className="muted small"> · {m.role || (m.is_owner ? "owner" : "member")}</span></li>)}</ul>
      </aside>
    </div>
  );
}
