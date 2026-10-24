"use client";
import { useEffect, useState } from "react";
import { api, setToken, recent, remember } from "../lib/api";

export default function Home() {
  const [view, setView] = useState("home");           // home | create | join
  const [rooms, setRooms] = useState([]);
  useEffect(() => { setRooms(recent()); }, []);
  const made = (m) => { remember(m.id, m.name); sessionStorage.setItem("forgeit:made", JSON.stringify(m)); window.location.href = "/welcome"; };
  return (
    <div>
      {view === "home" && <Landing rooms={rooms} go={setView} />}
      {view === "create" && <Create back={() => setView("home")} done={made} />}
      {view === "join" && <Join back={() => setView("home")} />}
    </div>
  );
}

function Landing({ rooms, go }) {
  return (
    <div className="view">
      <section className="hero">
        <h1>Forged by agents.<br />Checked by a referee.</h1>
        <p>Your team and its AI agents build one project together. Every change is tested before a person approves it.</p>
      </section>
      {!!rooms.length && (
        <section className="recent">
          <h2>Your workspaces</h2>
          {rooms.map((r) => <a key={r.id} href={`/w/${r.id}`}><b>{r.name}</b><span className="muted small">Workspace {r.id}</span></a>)}
        </section>
      )}
      <div className="choices">
        <button className="choice" onClick={() => go("create")}><h2>Start a workspace</h2><p>Set up a project, then invite your team.</p></button>
        <button className="choice" onClick={() => go("join")}><h2>Join a workspace</h2><p>You have an invite link, or a workspace number and token.</p></button>
      </div>
    </div>
  );
}

function Create({ back, done }) {
  const [step, setStep] = useState(0); const [name, setName] = useState(""); const [me, setMe] = useState(""); const [mates, setMates] = useState([{ name: "", email: "" }]);
  const [template, setTemplate] = useState("blank"); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const next = () => {
    setErr("");
    if (step === 0 && !name.trim()) return setErr("Give the workspace a name.");
    if (step === 1 && !me.trim()) return setErr("Add your own name.");
    if (step === 1 && mates.some((t) => t.name.trim() && t.email.trim() && !/^\S+@\S+\.\S+$/.test(t.email.trim()))) return setErr("One of the email addresses does not look right.");
    setStep(step + 1);
  };
  const create = async () => {
    setBusy(true); setErr("");
    try {
      const r = await api("/api/rooms", { body: { name: name.trim(), members: [{ name: me.trim() }, ...mates.filter((t) => t.name.trim()).map((t) => ({ name: t.name.trim(), email: t.email.trim() }))], template } });
      done({ ...r, name: name.trim() });
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  const starts = [["blank", "A blank project", "An agent builds the first version. Once you approve it, it becomes the locked original."],
    ["sample", "The demo shop", "A small store with tests already written, good for trying ForgeIt out."],
    ["todo", "A todo app", "A small todo list with tests already written."]];
  return (
    <div className="panel-view view" key={step}>
      <button className="link back" onClick={step ? () => setStep(step - 1) : back}>Back</button>
      <div className="steps" aria-hidden="true">{[0, 1, 2].map((i) => <i key={i} className={i <= step ? "on" : ""} />)}</div>
      {step === 0 && <>
        <h1>Name your workspace</h1>
        <label htmlFor="n">Workspace name</label><input id="n" autoFocus value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && next()} placeholder="Hackathon team" />
      </>}
      {step === 1 && <>
        <h1>What should we call you?</h1>
        <p className="muted">You are the owner.</p>
        <label htmlFor="me">Your name</label><input id="me" autoFocus value={me} onChange={(e) => setMe(e.target.value)} placeholder="Your name" />
        <h3 style={{ marginTop: "1.3rem" }}>Your teammates (optional)</h3>
        <p className="muted small">Each gets the workspace number and their own token by email. If mail is not set up, you will see them on the next screen. You can add more later under Setup, then People.</p>
        {mates.map((t, i) => <div className="row" key={i} style={{ marginBottom: ".4rem" }}>
          <input aria-label={`Teammate ${i + 1} name`} placeholder="Name" value={t.name} onChange={(e) => setMates(mates.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
          <input className="grow" type="email" aria-label={`Teammate ${i + 1} email`} placeholder="Email" value={t.email} onChange={(e) => setMates(mates.map((x, j) => j === i ? { ...x, email: e.target.value } : x))} />
          {mates.length > 1 && <button className="quiet" onClick={() => setMates(mates.filter((_, j) => j !== i))}>Remove</button>}
        </div>)}
        <button className="quiet" onClick={() => setMates([...mates, { name: "", email: "" }])}>Add another</button>
      </>}
      {step === 2 && <>
        <h1>Where do you start?</h1>
        {starts.map(([k, t, d]) => <button key={k} className="pick-card" aria-pressed={template === k} onClick={() => setTemplate(k)}><b>{t}</b><span>{d}</span></button>)}
      </>}
      <p className="err" role="alert">{err}</p>
      <div className="actions">{step < 2 ? <button onClick={next}>Continue</button> : <button className="go" onClick={create} disabled={busy}>{busy ? "Creating…" : "Create workspace"}</button>}</div>
    </div>
  );
}

function Join({ back }) {
  const [link, setLink] = useState(""); const [num, setNum] = useState(""); const [tok, setTok] = useState(""); const [err, setErr] = useState(""); const [other, setOther] = useState(false);
  const useLink = (e) => {
    e.preventDefault(); setErr("");
    const m = link.trim().match(/\/invite\/([^/?#\s]+)/); const code = m ? m[1] : link.trim();
    if (!code) return setErr("Paste the link or the invite code from your invite email.");
    window.location.href = `/invite/${encodeURIComponent(code)}`;
  };
  const useToken = (e) => { e.preventDefault(); setToken(num.trim(), tok.trim()); window.location.href = `/w/${num.trim()}`; };
  return (
    <div className="panel-view view">
      <button className="link back" onClick={back}>Back</button>
      <h1>Join a workspace</h1>
      <form onSubmit={useLink}>
        <label htmlFor="l">Your invite link or invite code</label><input id="l" autoFocus value={link} onChange={(e) => setLink(e.target.value)} placeholder="Paste the link or the code from your invite email" />
        <p className="err" role="alert">{err}</p>
        <div className="actions"><button className="go" disabled={!link.trim()}>Continue</button></div>
      </form>
      <p style={{ marginTop: "1.6rem" }}><button className="link" onClick={() => setOther(!other)} aria-expanded={other}>Already joined? Sign in with a workspace number and token</button></p>
      {other && <form onSubmit={useToken} className="view">
        <label htmlFor="num">Workspace number</label><input id="num" inputMode="numeric" value={num} onChange={(e) => setNum(e.target.value)} />
        <label htmlFor="tk">Your token</label><input id="tk" type="password" value={tok} onChange={(e) => setTok(e.target.value)} />
        <div className="actions"><button disabled={!num || !tok}>Open workspace</button></div>
      </form>}
    </div>
  );
}
