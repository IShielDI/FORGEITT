"use client";
import { useEffect, useState, useCallback } from "react";
import { api, getToken, setToken } from "../../../lib/api";
import Feed from "../../../components/Feed";
import Ladder from "../../../components/Ladder";
import Setup from "../../../components/Setup";
import Credits from "../../../components/Credits";

const STATUS = { tests_failed: "tests failed", rejected_firewall: "rejected by the firewall", conflict: "merge conflict", ready: "waiting for the referee", referee: "referee running",
  passed: "checked, ready to approve", referee_failed: "referee found a problem", inconclusive: "needs a human look", bootstrap_review: "first build, needs review", merged: "merged", undone: "undone" };

export default function Room({ params }) {
  const rid = Number(params.id);
  const [signedIn, setSignedIn] = useState(null); const [tok, setTok] = useState("");
  const [room, setRoom] = useState(null); const [me, setMe] = useState(null); const [catalog, setCatalog] = useState([]); const [models, setModels] = useState([]); const [changes, setChanges] = useState([]);
  const [tab, setTab] = useState("work"); const [agent, setAgent] = useState(""); const [model, setModel] = useState(""); const [task, setTask] = useState("");
  const [sel, setSel] = useState(null); const [err, setErr] = useState(""); const [key, setKey] = useState(""); const [spend, setSpend] = useState("2"); const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [r, m, c, ch, md] = await Promise.all([api(`/api/rooms/${rid}`, { rid }), api(`/api/rooms/${rid}/me`, { rid }), api(`/api/rooms/${rid}/catalog`, { rid }), api(`/api/rooms/${rid}/changes`, { rid }), api("/api/models")]);
      setRoom(r); setMe(m); setCatalog(c); setChanges(ch); setModels(md); setSignedIn(true);
      setAgent((a) => a || c[0]?.key || ""); setSel((s) => s ?? ch[0]?.id ?? null);
    } catch (e) { if (/sign in|token|401/i.test(e.message)) setSignedIn(false); else setErr(e.message); }
  }, [rid]);
  useEffect(() => { setSignedIn(getToken(rid) ? null : false); if (getToken(rid)) load(); }, [rid]);
  useEffect(() => { if (!signedIn) return; const t = setInterval(load, 5000); return () => clearInterval(t); }, [signedIn, load]);

  if (signedIn === false) return (
    <section style={{ maxWidth: 420 }}><h1>Sign in to workspace {rid}</h1>
      <p className="err" role="alert">{err}</p>
      <label htmlFor="t">Your token</label><input id="t" type="password" value={tok} onChange={(e) => setTok(e.target.value)} />
      <p /><button onClick={() => { setToken(rid, tok.trim()); setErr(""); load(); }}>Sign in</button></section>);
  if (!room || !me) return <p className="muted">{err || "Loading…"}</p>;

  const blankFirst = room.room.mode === "blank" && !room.room.bootstrapped;
  const picked = catalog.find((c) => c.key === agent);
  const myAgent = room.agents.find((a) => a.member_id === me.id);
  const running = myAgent?.status === "running";
  const run = async () => {
    setErr(""); setBusy(true);
    try { await api(`/api/rooms/${rid}/run`, { rid, body: { agent, task, model: model || null } }); setTask(""); }
    catch (e) { setErr(e.message); } finally { setBusy(false); setTimeout(load, 800); }
  };
  const connect = async () => {
    setErr("");
    try {
      const dollars = parseFloat(spend);
      if (!(dollars > 0)) throw new Error("Say how many dollars of your key this workspace may use.");
      await api(`/api/rooms/${rid}/me/key`, { rid, body: { anthropic_key: key.trim() } });
      await api(`/api/rooms/${rid}/contribute`, { rid, body: { amount: dollars } });
      setKey(""); load();
    } catch (e) { setErr(e.message); }
  };
  const funded = (room.budget?.me?.own_remaining ?? 0) > 0.05;

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div><h1>{room.room.name}</h1><p className="muted small">Signed in as <b>{me.name}</b>{me.is_owner ? " (owner)" : ""} · agents run {room.sandbox === "docker" ? "in Docker, with no network" : <span className="err">without isolation (no Docker found)</span>}</p></div>
      </div>
      <div className="tabs" role="tablist">
        {[["work", "Work"], ["credits", "Credits"], ["setup", "Setup"]].map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}
      </div>

      {tab === "credits" && <Credits rid={rid} me={me} members={room.members} />}
      {tab === "setup" && <Setup rid={rid} me={me} room={room} catalog={catalog} models={models} reload={load} />}
      {tab === "work" && (
        <div className="cols">
          <aside>
            <h2>Agents</h2>
            {catalog.map((c) => <button key={c.key} className="pick" aria-pressed={agent === c.key} onClick={() => { setAgent(c.key); setModel(""); }}>{c.label}<small>{c.description}</small></button>)}
            <section className="panel">
              <h2>Your Claude key</h2>
              {me.has_key ? <p className="small ok">Connected (ends in {me.key_last4}). It is stored encrypted and never shown again.</p> : <>
                <p className="small">Agents run on your own key and your own credits. Paste it to start.</p>
                <label htmlFor="k">Anthropic API key</label><input id="k" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} placeholder="sk-ant-…" />
                <label htmlFor="sp">Dollars of this key the workspace may use</label><input id="sp" inputMode="decimal" value={spend} onChange={(e) => setSpend(e.target.value)} />
                <p className="muted small">You stay in control: agents pause at 90% of this amount and ask you what to do.</p>
                <p /><button onClick={connect} disabled={!key}>Connect key</button></>}
              {me.has_key && !funded && <p className="err small">Your budget is used up. Add more in the Credits tab.</p>}
            </section>
          </aside>

          <section>
            <h2>{blankFirst ? "Describe what to build first" : "Give the agent a task"}</h2>
            {blankFirst && <p className="muted">This project is empty. The first task writes a short spec, the tests that check it, and the first version of the app. You review it, and once you approve it, it becomes the locked original that every later change is checked against.</p>}
            <div className="row"><b>{picked?.label || "Pick an agent"}</b>
              <select aria-label="Model" style={{ width: "auto" }} value={model || picked?.model || ""} onChange={(e) => setModel(e.target.value)}>{models.map((m) => <option key={m}>{m}</option>)}</select></div>
            <label htmlFor="task">Task</label>
            <textarea id="task" value={task} onChange={(e) => setTask(e.target.value)} placeholder={blankFirst ? "A small web app where…" : "What should the agent change?"} />
            <p className="err" role="alert">{err}</p>
            <div className="row">
              <button className="go" onClick={run} disabled={!task.trim() || !agent || !me.has_key || !funded || busy || running}>{running ? "Working…" : blankFirst ? "Build the first version" : "Run"}</button>
              {running && <button className="quiet" onClick={() => api(`/api/rooms/${rid}/agents/${myAgent.name}/stop`, { rid, method: "POST" }).catch((e) => setErr(e.message))}>Stop</button>}
              {!me.has_key && <span className="muted small">Connect your key first.</span>}
              {me.has_key && !funded && <span className="muted small">No budget left to spend.</span>}
            </div>
            <section className="panel"><h2>Activity</h2><Feed rid={rid} onFinished={() => { load(); }} /></section>
            <section className="panel"><h2>Changes</h2>
              {changes.length ? changes.map((c) => <button key={c.id} className="chg" aria-current={sel === c.id} onClick={() => setSel(c.id)}><b>{c.summary}</b><br /><span className="muted small">{c.agent.replace("-agent", "")} · {STATUS[c.status] || c.status}</span></button>) : <p className="muted">No changes yet.</p>}
            </section>
          </section>

          <aside>
            <h2>Verdict</h2>
            {sel ? <Ladder rid={rid} id={sel} me={me} onChanged={load} /> : <p className="muted">When an agent finishes, its change is checked here step by step, and a person approves it.</p>}
          </aside>
        </div>
      )}
    </div>
  );
}
