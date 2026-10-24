"use client";
import { useEffect, useState, useCallback } from "react";
import { api, getToken, setToken, remember, money } from "../../../lib/api";
import Feed from "../../../components/Feed";
import Ladder from "../../../components/Ladder";
import ChangeFiles from "../../../components/ChangeFiles";
import Files from "../../../components/Files";
import Setup from "../../../components/Setup";
import Credits from "../../../components/Credits";
import Chat from "../../../components/Chat";
import Spec from "../../../components/Spec";
import Plan from "../../../components/Plan";
import Graph from "../../../components/Graph";
import MicButton from "../../../components/MicButton";
import Models from "../../../components/Models";
import WorkspaceNav from "../../../components/WorkspaceNav";
import { ANTHROPIC, modelLabel, pickModel, readiness } from "../../../lib/models.mjs";
import { appendTranscript } from "../../../lib/speech.mjs";

const STATUS = { tests_failed: ["Tests failed", "bad"], rejected_firewall: ["Blocked by the firewall", "bad"], conflict: ["Merge conflict", "bad"], ready: ["Waiting for the referee"], referee: ["Referee running"],
  passed: ["Ready to approve", "ready"], referee_failed: ["Referee found a problem", "bad"], inconclusive: ["Needs a human look"], bootstrap_review: ["First build: review it", "ready"], merged: ["Merged", "good"], undone: ["Undone"] };

const seenKey = (rid) => `forgeit:seen:${rid}`;
const seen = (rid) => { try { return Number(localStorage.getItem(seenKey(rid)) || 0); } catch { return 0; } };
const markSeen = (rid, id) => { try { localStorage.setItem(seenKey(rid), String(id)); } catch {} };

export default function Room({ params }) {
  const rid = Number(params.id);
  const [signedIn, setSignedIn] = useState(null); const [tok, setTok] = useState("");
  const [room, setRoom] = useState(null); const [me, setMe] = useState(null); const [catalog, setCatalog] = useState([]); const [models, setModels] = useState([]); const [changes, setChanges] = useState([]);
  const [view, setView] = useState("chat"); const [team, setTeam] = useState("spec"); const [agent, setAgent] = useState(""); const [model, setModel] = useState(""); const [task, setTask] = useState("");
  const [latestMsg, setLatestMsg] = useState(0); const [seenMsg, setSeenMsg] = useState(() => seen(rid)); const [proposed, setProposed] = useState(0);
  const [sel, setSel] = useState(null); const [drawer, setDrawer] = useState(false); const [err, setErr] = useState(""); const [key, setKey] = useState(""); const [spend, setSpend] = useState("2"); const [busy, setBusy] = useState(false);
  const [providers, setProviders] = useState([]); const [liveModels, setLiveModels] = useState({}); const [freeKey, setFreeKey] = useState("");

  const load = useCallback(async () => {
    try {
      const [r, m, c, ch, md, pv] = await Promise.all([api(`/api/rooms/${rid}`, { rid }), api(`/api/rooms/${rid}/me`, { rid }), api(`/api/rooms/${rid}/catalog`, { rid }), api(`/api/rooms/${rid}/changes`, { rid }), api("/api/models"), api(`/api/rooms/${rid}/me/providers`, { rid }).catch(() => [])]);
      setRoom(r); setMe(m); setCatalog(c); setChanges(ch); setModels(md); setProviders(pv); setSignedIn(true); remember(rid, r.room.name);
      setAgent((a) => a || c[0]?.key || ""); setSel((s) => s ?? ch[0]?.id ?? null);
      // chat activity and what the observer proposed from it (for the unread badge and the spec hint)
      const [last, sp] = await Promise.all([api(`/api/rooms/${rid}/messages?limit=1`, { rid }).catch(() => []), api(`/api/rooms/${rid}/spec`, { rid }).catch(() => null)]);
      const newest = last[0];
      if (newest && newest.member_id === m.id) { setSeenMsg((v) => Math.max(v, newest.id)); markSeen(rid, newest.id); }  // your own message is never "unread"
      setLatestMsg(newest?.id || 0); setProposed(sp ? sp.items.filter((i) => i.status === "proposed").length : 0);
    } catch (e) { if (/sign in|token|401/i.test(e.message)) setSignedIn(false); else setErr(e.message); }
  }, [rid]);
  useEffect(() => { setSignedIn(getToken(rid) ? null : false); if (getToken(rid)) load(); }, [rid]);
  useEffect(() => { if (!signedIn) return; const t = setInterval(load, 5000); return () => clearInterval(t); }, [signedIn, load]);
  useEffect(() => { if (view === "chat" && latestMsg > seenMsg) { setSeenMsg(latestMsg); markSeen(rid, latestMsg); } }, [view, latestMsg, seenMsg, rid]);

  const frame = (body) => <div className="shell"><WorkspaceNav current={rid} name={room?.room.name} /><div className="shell-main">{body}</div></div>;
  if (signedIn === false) return frame(
    <section className="panel-view view"><h1>Sign in to workspace {rid}</h1>
      <p className="muted">Use the token from your invite. Lost it? Ask the owner to send a new invite.</p>
      <form onSubmit={(e) => { e.preventDefault(); setToken(rid, tok.trim()); setErr(""); load(); }}>
        <label htmlFor="t">Your token</label><input id="t" type="password" autoFocus value={tok} onChange={(e) => setTok(e.target.value)} />
        <p className="err" role="alert">{err}</p>
        <div className="actions"><button className="go" disabled={!tok.trim()}>Sign in</button></div></form></section>);
  if (!room || !me) return frame(<p className="muted">{err || "Loading…"}</p>);

  const blankFirst = room.room.mode === "blank" && !room.room.bootstrapped;
  const picked = catalog.find((c) => c.key === agent);
  const myAgent = room.agents.find((a) => a.member_id === me.id);
  const running = myAgent?.status === "running";
  const left = room.budget?.me?.own_remaining ?? 0, funded = left > 0.05;
  // the providers with any live model lists merged in, the model this run would use, and whether it can start
  const provs = providers.map((p) => (liveModels[p.id] ? { ...p, models: [...new Set([...p.models, ...liveModels[p.id]])] } : p));
  const useModel = pickModel(model, picked?.model, provs);
  const status = readiness(useModel, provs, funded);
  const needClaude = status.provider?.id === ANTHROPIC && !status.provider.ready;
  const needFree = status.provider?.free && !status.provider.ready;
  const freeReady = provs.some((p) => p.free && p.ready);
  const run = async () => {
    setErr(""); setBusy(true);
    try { await api(`/api/rooms/${rid}/run`, { rid, body: { agent, task, model: useModel || null } }); setTask(""); }
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
  const saveFreeKey = async () => {
    setErr("");
    try { await api(`/api/rooms/${rid}/me/keys/${status.provider.id}`, { rid, method: "PUT", body: { key: freeKey.trim() } }); setFreeKey(""); load(); }
    catch (e) { setErr(e.message); }
  };
  const finished = async () => {                    // an agent just ended: show its newest change
    await load();
    try { const ch = await api(`/api/rooms/${rid}/changes`, { rid }); if (ch[0]) { setSel(ch[0].id); setDrawer(true); } } catch {}
  };
  const open = (id) => { setSel(id); setDrawer(true); };

  return frame(
    <div className={"ws" + (drawer && view === "work" ? " with-drawer" : "")}>
      <div className="ws-head">
        <div>
          <h1>{room.room.name}</h1>
          <div className="chips">
            <span className="chip">{me.name}{me.is_owner ? ", owner" : ""}</span>
            <span className={"chip" + (room.sandbox === "docker" ? "" : " warn")} title={room.sandbox === "docker" ? "Agent commands run in Docker with no network" : "Docker was not found, so real agents are blocked"}>{room.sandbox === "docker" ? "Docker sandbox" : "No sandbox"}</span>
            {me.has_key && <button className="chip" onClick={() => setView("credits")}>Claude key ends {me.key_last4} · {money(left)} left</button>}
            {!me.has_key && <button className={"chip" + (freeReady ? " free" : " warn")} onClick={() => setView("models")}>{freeReady ? "Free models ready" : "No model ready yet"}</button>}
          </div>
        </div>
        <div className="seg" role="tablist" aria-label="Workspace sections">
          {[["chat", "Chat"], ["work", "Work"], ["models", "Models"], ["team", "Spec & plan"], ["credits", "Credits"], ["setup", "Setup"]].map(([k, l]) => (
            <button key={k} role="tab" aria-selected={view === k} onClick={() => setView(k)}>
              {l}{k === "chat" && view !== "chat" && latestMsg > seenMsg && <span className="unread" aria-label="new messages"> •</span>}
              {k === "team" && proposed > 0 && <span className="count" aria-label={`${proposed} proposed spec items`}> {proposed}</span>}
            </button>))}
        </div>
      </div>

      {view === "chat" && (
        <div className="view">
          <p className="muted small chat-intro">
            Talk through what to build here. An observer reads the discussion and proposes requirements and decisions for the spec; nothing counts until a person confirms it.
            {proposed > 0 && <> <button className="link" onClick={() => { setTeam("spec"); setView("team"); }}>{proposed} proposed {proposed === 1 ? "item is" : "items are"} waiting in the spec</button></>}
          </p>
          <Chat rid={rid} me={me} members={room.members} />
        </div>)}
      {view === "team" && (
        <div className="view">
          <div className="subnav" role="tablist" aria-label="Spec and plan">
            {[["spec", "Spec"], ["plan", "Plan"], ["graph", "Graph"], ["files", "Files"]].map(([k, l]) => <button key={k} role="tab" aria-selected={team === k} onClick={() => setTeam(k)}>{l}</button>)}
          </div>
          {team === "spec" && <Spec rid={rid} me={me} />}
          {team === "plan" && <Plan rid={rid} me={me} members={room.members} blankFirst={blankFirst} />}
          {team === "graph" && <Graph rid={rid} />}
          {team === "files" && <Files rid={rid} />}
        </div>)}
      {view === "models" && <div className="view"><Models rid={rid} me={me} providers={provs} reload={load}
        onLive={(id, list) => setLiveModels((l) => ({ ...l, [id]: list }))} onUse={(m) => { setModel(m); setView("work"); }} /></div>}
      {view === "credits" && <div className="view"><Credits rid={rid} me={me} members={room.members} /></div>}
      {view === "setup" && <div className="view"><Setup rid={rid} me={me} room={room} catalog={catalog} models={models} members={room.members} reload={load} /></div>}
      {view === "work" && (
        <div className="view">
          {needFree && (
            <section className="card stack" style={{ marginBottom: "1.4rem" }}>
              <h2>Add a free {status.provider.label} key</h2>
              <p className="muted">{status.provider.note} Free tiers cost no credits. The key is stored encrypted and used only by the platform; agents never see it. <a href={status.provider.signup_url} target="_blank" rel="noreferrer noopener">Get a free key</a>, or <button className="link" onClick={() => setView("models")}>pick another model</button>.</p>
              <form className="row" onSubmit={(e) => { e.preventDefault(); saveFreeKey(); }}>
                <input className="grow" type="password" autoComplete="off" aria-label={`${status.provider.label} key`} value={freeKey} onChange={(e) => setFreeKey(e.target.value)} placeholder="Paste your free key" />
                <button disabled={!freeKey.trim()}>Save key</button></form>
              <p className="err" role="alert">{err}</p>
            </section>)}
          {needClaude && (
            <section className="card stack" style={{ marginBottom: "1.4rem" }}>
              <h2>Connect your Claude key, or pick a free model</h2>
              <p className="muted">Claude runs on your own key and your own credits. It is stored encrypted and never shown again. Don't have one? <button className="link" onClick={() => setView("models")}>Use a free model instead</button>.</p>
              <div><label htmlFor="k">Anthropic API key</label><input id="k" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} placeholder="sk-ant-…" /></div>
              <div><label htmlFor="sp">Dollars of this key the workspace may use</label><input id="sp" inputMode="decimal" value={spend} onChange={(e) => setSpend(e.target.value)} />
                <p className="muted small">Agents pause at 90% of this amount and ask you what to do.</p></div>
              <p className="err" role="alert">{err}</p>
              <div className="actions"><button onClick={connect} disabled={!key}>Connect key</button></div>
            </section>)}

          <section className="compose">
            <h2>{blankFirst ? "Describe what to build first" : "What should an agent do?"}</h2>
            {blankFirst && <p className="muted">This project is empty. The first task writes a short spec, the tests that check it and the first version of the app. Once you approve it, it becomes the locked original every later change is checked against.</p>}
            <div className="agents" role="radiogroup" aria-label="Agent">
              {catalog.map((c) => <button key={c.key} role="radio" aria-checked={agent === c.key} className={"agent" + (agent === c.key && running ? " working" : "")} onClick={() => { setAgent(c.key); setModel(""); }}>{c.label}</button>)}
            </div>
            <div className="agent-line"><span>{picked?.description || "Pick an agent."}</span>
              <select aria-label="Model" value={useModel} onChange={(e) => setModel(e.target.value)}>
                {provs.length ? provs.map((p) => <optgroup key={p.id} label={`${p.label} · ${p.free ? "free" : "paid"}${p.ready ? "" : " (needs a key)"}`}>
                  {p.models.map((m) => <option key={m} value={m}>{modelLabel(m, provs)}</option>)}</optgroup>)
                  : models.map((m) => <option key={m}>{m}</option>)}
                {useModel && !provs.some((p) => p.models.includes(useModel)) && <option value={useModel}>{useModel}</option>}
              </select></div>
            <textarea id="task" aria-label="Task" value={task} onChange={(e) => setTask(e.target.value)} placeholder={blankFirst ? "A small web app where…" : "Describe the change in plain words"} />
            <div className="row"><MicButton label="Dictate the task" onText={(t) => setTask((cur) => appendTranscript(cur, t))} /></div>
            {!needClaude && !needFree && <p className="err" role="alert">{err}</p>}
            <div className="actions">
              <button className="go" onClick={run} disabled={!task.trim() || !agent || !status.ready || busy || running}>{running ? "Working…" : blankFirst ? "Build the first version" : "Run"}</button>
              {running && <button className="quiet" onClick={() => api(`/api/rooms/${rid}/agents/${myAgent.name}/stop`, { rid, method: "POST" }).catch((e) => setErr(e.message))}>Stop</button>}
              {!status.ready && <span className="muted small">{status.reason}</span>}
            </div>
          </section>

          <section className="block"><h2>Activity</h2><Feed rid={rid} onFinished={finished} /></section>
          <section className="block"><h2>Changes</h2>
            {changes.length ? changes.map((c) => { const [label, tone] = STATUS[c.status] || [c.status.replace(/_/g, " ")]; return (
              <button key={c.id} className="chg" aria-current={drawer && sel === c.id} onClick={() => open(c.id)}>
                <span><b>{c.summary}</b><small>{c.agent.replace("-agent", "")}</small></span><span className="pill" data-s={tone}>{label}</span></button>); })
              : <p className="muted">Nothing yet. When an agent finishes, its change appears here to check and approve.</p>}
          </section>
        </div>
      )}

      <aside className={"drawer" + (drawer && view === "work" ? " open" : "")} aria-label="Verdict" aria-hidden={!(drawer && view === "work")}>
        <div className="drawer-head"><h2>Verdict</h2><button className="quiet" onClick={() => setDrawer(false)}>Close</button></div>
        {sel ? <><Ladder rid={rid} id={sel} me={me} onChanged={load} /><ChangeFiles rid={rid} id={sel} /></> : <p className="muted">Pick a change to see how it was checked.</p>}
      </aside>
    </div>
  );
}
