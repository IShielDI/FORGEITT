"use client";
import { useEffect, useState } from "react";
import { setToken } from "../../lib/api";

// Shown once, right after a workspace is created: the owner's login.
export default function Welcome() {
  const [m, setM] = useState(null); const [show, setShow] = useState(false);
  useEffect(() => { try { setM(JSON.parse(sessionStorage.getItem("forgeit:made") || "null")); } catch {} }, []);
  if (!m) return <section className="panel-view"><h1>Nothing to show</h1><p className="muted">Start a workspace from the home page.</p><p><a href="/">Go home</a></p></section>;
  const owner = m.members.find((x) => x.is_owner) || m.members[0]; const mates = m.members.filter((x) => !x.is_owner);
  const enter = () => { setToken(m.id, owner.token); sessionStorage.removeItem("forgeit:made"); window.location.href = `/w/${m.id}`; };
  return (
    <section className="panel-view view stack">
      <h1>{m.name} is ready</h1>
      <div className="card">
        <h2>Your login</h2>
        <p className="muted small">Shown once. Save it somewhere private: you need it to sign in on another device. This browser is already set up.</p>
        {show ? <p><code className="token">{owner.token}</code> <button className="quiet" onClick={() => navigator.clipboard?.writeText(owner.token)}>Copy</button></p> : <p><button className="quiet" onClick={() => setShow(true)}>Show my login</button></p>}
        <p className="muted small">Workspace number: <b>{m.id}</b></p>
      </div>
      {mates.length > 0 && <div className="card">
        <h2>Your teammates</h2>
        <p className="muted small">Workspace number <b>{m.id}</b>. {mates.some((x) => !x.mailed) ? "Mail is not set up for some of them, so send these privately. Shown once." : "Everyone below was emailed their workspace number and token."}</p>
        {mates.map((x) => <div className="invite-row" key={x.id}><span><b>{x.name}</b> <span className="muted small">{x.mailed ? "emailed" : "not emailed"}</span></span>
          {!x.mailed && <span><code className="token">{x.token}</code> <button className="quiet" onClick={() => navigator.clipboard?.writeText(`Workspace ${m.id}, token ${x.token}`)}>Copy</button></span>}</div>)}
      </div>}
      <div className="card">
        <h2>Adding more people later</h2>
        <p className="muted small">Open Setup, then People, and create a single-use invite link.</p>
      </div>
      <div className="actions"><button className="go" onClick={enter}>Open the workspace</button></div>
    </section>
  );
}
