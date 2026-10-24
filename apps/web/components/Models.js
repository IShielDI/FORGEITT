"use client";
import { useState } from "react";
import { api } from "../lib/api";
import { modelLabel, statusText } from "../lib/models.mjs";

/**
 * Model providers, Cline-style: free tiers first (Gemini, Groq, OpenRouter, ...), Claude on your own key.
 * Keys are stored encrypted on the platform; agents never see them. Only the last 4 characters come back.
 * @param {{rid: number, me: {role: string}, providers: import("../lib/models.mjs").Provider[], reload: () => void, onLive: (id: string, models: string[]) => void, onUse: (model: string) => void}} props
 */
export default function Models({ rid, me, providers, reload, onLive, onUse }) {
  const [keys, setKeys] = useState({}); const [msg, setMsg] = useState({}); const [busy, setBusy] = useState("");
  const viewer = me?.role === "viewer";
  const say = (id, text) => setMsg((m) => ({ ...m, [id]: text }));
  const act = async (id, fn, ok) => {
    setBusy(id); say(id, "");
    try { await fn(); say(id, ok); reload(); } catch (e) { say(id, e.message); } finally { setBusy(""); }
  };
  const save = (p) => act(p.id, async () => {
    await api(`/api/rooms/${rid}/me/keys/${p.id}`, { rid, method: "PUT", body: { key: (keys[p.id] || "").trim() } });
    setKeys((k) => ({ ...k, [p.id]: "" }));
  }, "Key saved.");
  const remove = (p) => act(p.id, () => api(`/api/rooms/${rid}/me/keys/${p.id}`, { rid, method: "DELETE" }), "Your key was removed.");
  const live = (p) => act(p.id, async () => {
    const list = await api(`/api/rooms/${rid}/me/providers/${p.id}/models`, { rid });
    onLive(p.id, list);
    if (!list.length) throw new Error("No models came back.");
  }, "Model list updated.");

  const free = providers.filter((p) => p.free), paid = providers.filter((p) => !p.free);
  const Card = (p) => (
    <section key={p.id} className="card stack provider" data-ready={p.ready}>
      <div className="row">
        <h3 className="grow">{p.label}</h3>
        <span className={"chip" + (p.free ? " free" : "")}>{p.free ? "Free tier" : "Paid"}</span>
      </div>
      <p className={"small " + (p.ready ? "ok" : "muted")}>{statusText(p)}</p>
      {p.note && <p className="muted small">{p.note}</p>}
      <div className="models-list">
        {p.models.slice(0, 8).map((m) => <button key={m} className="quiet small" disabled={!p.ready} onClick={() => onUse(m)} title={p.ready ? "Use this model on the Work tab" : "Add a key first"}>{modelLabel(m, providers)}</button>)}
        {p.models.length > 8 && <span className="muted small">+{p.models.length - 8} more in the Work list</span>}
      </div>
      {p.free && p.needs_key && !viewer && (
        <form className="row" onSubmit={(e) => { e.preventDefault(); save(p); }}>
          <input className="grow" type="password" autoComplete="off" aria-label={`${p.label} key`} placeholder={p.source === "yours" ? "Paste a new key to replace yours" : "Paste your free key"}
            value={keys[p.id] || ""} onChange={(e) => setKeys((k) => ({ ...k, [p.id]: e.target.value }))} />
          <button disabled={!keys[p.id]?.trim() || busy === p.id}>Save</button>
          {p.source === "yours" && <button type="button" className="quiet" onClick={() => remove(p)}>Remove</button>}
        </form>)}
      <div className="row small">
        <a href={p.signup_url} target="_blank" rel="noreferrer noopener">{p.needs_key ? `Get a ${p.free ? "free " : ""}key` : "Install Ollama"}</a>
        {p.free && p.ready && <button className="link" onClick={() => live(p)} disabled={busy === p.id}>Show current models</button>}
      </div>
      {msg[p.id] && <p role="status" className={/saved|removed|updated/.test(msg[p.id]) ? "ok small" : "err small"}>{msg[p.id]}</p>}
    </section>);

  return (
    <div className="stack">
      <p className="muted">Pick any model below for your agents. Free tiers need no credits: paste a free key (it takes a minute to get one) or use a shared demo key if the host set one up. Keys are stored encrypted and used only by the platform; agents never see them.</p>
      <h2>Free models</h2>
      <div className="provider-grid">{free.map(Card)}</div>
      <h2>Paid</h2>
      <div className="provider-grid">{paid.map((p) => (
        <section key={p.id} className="card stack provider" data-ready={p.ready}>
          <div className="row"><h3 className="grow">{p.label}</h3><span className="chip">Paid</span></div>
          <p className={"small " + (p.ready ? "ok" : "muted")}>{statusText(p)}</p>
          <p className="muted small">{p.note} To connect it, pick a Claude model on the Work tab.</p>
          <div className="models-list">{p.models.map((m) => <button key={m} className="quiet small" onClick={() => onUse(m)}>{m}</button>)}</div>
        </section>))}</div>
    </div>
  );
}
