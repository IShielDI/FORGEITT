"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

const LABEL = { A: "added", M: "changed", D: "deleted", R: "renamed" };

/**
 * The files one change added, changed or deleted, with each file's diff or full text.
 * Read-only; hidden tests are never listed (the server leaves them out).
 * @param {{rid: number, id: number}} props
 */
export default function ChangeFiles({ rid, id }) {
  const [data, setData] = useState(null); const [err, setErr] = useState("");
  const [open, setOpen] = useState(null); const [mode, setMode] = useState("diff"); const [body, setBody] = useState("");
  useEffect(() => {
    setData(null); setOpen(null); setErr("");
    api(`/api/changes/${id}/files`, { rid }).then(setData).catch((e) => setErr(e.message));
  }, [rid, id]);

  const show = async (f, how) => {
    setOpen(f.path); setMode(how); setBody("Loading…");
    try {
      if (how === "diff") setBody((await api(`/api/changes/${id}/files/diff?path=${encodeURIComponent(f.path)}`, { rid })).diff || "(no text changes)");
      else {
        const r = await api(`/api/rooms/${rid}/files/content?ref=${data.commit}&path=${encodeURIComponent(f.path)}`, { rid });
        setBody(r.binary ? "(binary file, not shown)" : r.text + (r.truncated ? "\n… (cut short: file is large)" : ""));
      }
    } catch (e) { setBody(e.message); }
  };

  if (err) return <p className="muted small">Files: {err}</p>;
  if (!data) return <p className="muted small">Loading the files…</p>;
  return (
    <section className="change-files">
      <h3>Files in this change ({data.files.length})</h3>
      {data.files.length ? <ul className="plain">
        {data.files.map((f) => <li key={f.path}>
          <div className="row small">
            <span className={`fstat s-${f.status}`}>{LABEL[f.status] || f.status}</span>
            <code className="grow">{f.path}</code>
            <button className="link" onClick={() => show(f, "diff")}>What changed</button>
            {f.status !== "D" && <button className="link" onClick={() => show(f, "file")}>Whole file</button>}
          </div>
          {open === f.path && <pre aria-label={`${mode === "diff" ? "Changes to" : "Contents of"} ${f.path}`}>{body}</pre>}
        </li>)}
      </ul> : <p className="muted small">This change did not touch any files.</p>}
    </section>
  );
}
