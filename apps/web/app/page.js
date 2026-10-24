"use client";
import { useState } from "react";
import { api, setToken } from "../lib/api";

export default function Home() {
  const [openId, setOpenId] = useState(""); const [openTok, setOpenTok] = useState("");
  const [name, setName] = useState(""); const [people, setPeople] = useState(""); const [template, setTemplate] = useState("blank");
  const [made, setMade] = useState(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);

  const open = (e) => { e.preventDefault(); setToken(openId, openTok.trim()); window.location.href = `/w/${openId}`; };
  const create = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      const members = people.split(",").map((s) => s.trim()).filter(Boolean).map((n) => ({ name: n }));
      if (!name.trim() || !members.length) throw new Error("Give the workspace a name and at least one person.");
      setMade(await api("/api/rooms", { body: { name: name.trim(), members, template } }));
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };

  if (made) return (
    <section style={{ maxWidth: 640 }}>
      <h1>Workspace ready</h1>
      <p>Each person gets one login token. It is shown <b>once</b>: copy yours now and send the others theirs privately.</p>
      <table><thead><tr><th>Person</th><th>Token</th><th></th></tr></thead><tbody>
        {made.members.map((m) => (
          <tr key={m.id}><td>{m.name}{m.is_owner ? " (owner)" : ""}</td><td><code>{m.token}</code></td>
            <td><button className="quiet" onClick={() => navigator.clipboard?.writeText(m.token)}>Copy</button> <button onClick={() => { setToken(made.id, m.token); window.location.href = `/w/${made.id}`; }}>Enter as {m.name}</button></td></tr>
        ))}
      </tbody></table>
      <p className="muted small">Workspace number: <b>{made.id}</b>. To come back later, open it with your number and token.</p>
    </section>
  );

  return (
    <div className="cols" style={{ gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr)", maxWidth: 980 }}>
      <section>
        <h1>Start a workspace</h1>
        <p className="muted">Your team shares one project. Each person brings their own Claude key and uses their own agents.</p>
        <form onSubmit={create}>
          <label htmlFor="n">Workspace name</label><input id="n" value={name} onChange={(e) => setName(e.target.value)} />
          <label htmlFor="p">People (comma separated, the first is the owner)</label><input id="p" value={people} onChange={(e) => setPeople(e.target.value)} placeholder="Riya, Aman, Kriti" />
          <label htmlFor="t">Starting point</label>
          <select id="t" value={template} onChange={(e) => setTemplate(e.target.value)}>
            <option value="blank">Blank project: the first approved build becomes the original</option>
            <option value="sample">Demo shop: a small store with tests already written</option>
            <option value="todo">Todo app: a small todo list with tests already written</option>
          </select>
          <p className="err" role="alert">{err}</p>
          <button disabled={busy}>Create workspace</button>
        </form>
      </section>
      <section>
        <h2>Open a workspace</h2>
        <form onSubmit={open}>
          <label htmlFor="i">Workspace number</label><input id="i" value={openId} onChange={(e) => setOpenId(e.target.value)} inputMode="numeric" />
          <label htmlFor="k">Your token</label><input id="k" type="password" value={openTok} onChange={(e) => setOpenTok(e.target.value)} />
          <p />
          <button disabled={!openId || !openTok}>Open</button>
        </form>
      </section>
    </div>
  );
}
