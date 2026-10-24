"use client";
import { useEffect, useState } from "react";
import { api, setToken, remember } from "../../../lib/api";

// Join a workspace with a single-use invite link. Looking at the link spends nothing; pressing Join creates your own login, shown once.
export default function Invite({ params }) {
  const token = params.token;
  const [info, setInfo] = useState(null); const [err, setErr] = useState("");
  const [name, setName] = useState(""); const [email, setEmail] = useState(""); const [joined, setJoined] = useState(null); const [busy, setBusy] = useState(false);
  useEffect(() => { api(`/api/invites/${encodeURIComponent(token)}`).then((i) => { setInfo(i); setEmail((v) => v || i.email || ""); setName((v) => v || i.name || ""); }).catch((e) => setErr(e.message)); }, [token]);

  const accept = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      const r = await api(`/api/invites/${encodeURIComponent(token)}/accept`, { body: { name: name.trim(), email: email.trim() } });
      setToken(r.room_id, r.token); remember(r.room_id, info?.room_name || "Workspace"); setJoined(r);
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };

  if (joined) return (
    <section className="panel-view view stack">
      <h1>You are in, {name.trim()}</h1>
      <p>You are signed in to <b>{info?.room_name || `workspace ${joined.room_id}`}</b> in this browser.</p>
      <div className="card">
        <h2>Your login</h2>
        <p className="muted small">Shown once. Save it somewhere private: you need it to sign in on another device or browser. This browser is already signed in.</p>
        <p><code className="token">{joined.token}</code> <button className="quiet" onClick={() => navigator.clipboard?.writeText(joined.token)}>Copy</button></p>
        <p className="muted small">Workspace number: <b>{joined.room_id}</b> · your role: {joined.role}</p>
        {joined.mailed ? <p className="ok small">We also emailed your workspace number and token to {email.trim() || info?.email}.</p>
          : <p className="muted small">{email.trim() ? "We could not email it, so save the token above." : "No email was given, so save the token above."}</p>}
      </div>
      <div className="actions"><button className="go" onClick={() => { window.location.href = `/w/${joined.room_id}`; }}>Open the workspace</button></div>
    </section>
  );
  return (
    <section className="panel-view view">
      <h1>{info ? `Join ${info.room_name}` : "Join a workspace"}</h1>
      {info && <p>You are invited as a <b>{info.role}</b>{info.role === "viewer" ? " (read-only)" : ""}. Joining creates your own login. The link works once, so open it on the device you will use.</p>}
      {!info && !err && <p className="muted">Checking the invite…</p>}
      <p className="err" role="alert">{err}</p>
      {info && <form onSubmit={accept}>
        {info.name ? <p>You are joining as <b>{info.name}</b>: the owner already added you, so your parts of the project are waiting.</p>
          : <><label htmlFor="n">Your name</label><input id="n" autoFocus value={name} onChange={(e) => setName(e.target.value)} /></>}
        <label htmlFor="e">Email (optional: we send your login here for other devices)</label><input id="e" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <div className="actions"><button className="go" disabled={!name.trim() || busy}>{busy ? "Joining…" : "Join"}</button></div>
      </form>}
      {!info && err && <p><a href="/">Back to the home page</a></p>}
    </section>
  );
}
