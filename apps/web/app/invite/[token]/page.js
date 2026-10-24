"use client";
import { useEffect, useState } from "react";
import { api, setToken } from "../../../lib/api";

// Join a workspace with a single-use invite link. Your own login token is shown once.
export default function Invite({ params }) {
  const token = params.token;
  const [info, setInfo] = useState(null); const [err, setErr] = useState("");
  const [name, setName] = useState(""); const [email, setEmail] = useState(""); const [joined, setJoined] = useState(null); const [busy, setBusy] = useState(false);
  useEffect(() => { api(`/api/invites/${encodeURIComponent(token)}`).then(setInfo).catch((e) => setErr(e.message)); }, [token]);

  const accept = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { setJoined(await api(`/api/invites/${encodeURIComponent(token)}/accept`, { body: { name: name.trim(), email: email.trim() } })); }
    catch (x) { setErr(x.message); } finally { setBusy(false); }
  };

  if (joined) return (
    <section style={{ maxWidth: 560 }}>
      <h1>You joined {info?.room_name}</h1>
      <p>This is your login token. It is shown <b>once</b>: copy it now and keep it private.</p>
      <p><code>{joined.token}</code> <button className="quiet" onClick={() => navigator.clipboard?.writeText(joined.token)}>Copy</button></p>
      <p className="muted small">Workspace number: <b>{joined.room_id}</b> · your role: {joined.role}</p>
      <button className="go" onClick={() => { setToken(joined.room_id, joined.token); window.location.href = `/w/${joined.room_id}`; }}>Enter the workspace</button>
    </section>
  );
  return (
    <section style={{ maxWidth: 480 }}>
      <h1>Join a workspace</h1>
      {info ? <p>You are invited to <b>{info.room_name}</b> as a <b>{info.role}</b>{info.role === "viewer" ? " (read-only)" : ""}.</p> : !err && <p className="muted">Checking the invite…</p>}
      <p className="err" role="alert">{err}</p>
      {info && <form onSubmit={accept}>
        <label htmlFor="n">Your name</label><input id="n" value={name} onChange={(e) => setName(e.target.value)} />
        <label htmlFor="e">Email (optional)</label><input id="e" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <p /><button className="go" disabled={!name.trim() || busy}>Join</button>
      </form>}
    </section>
  );
}
