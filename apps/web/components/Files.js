"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

/**
 * Browse the project as it is now on main: every file, and its contents. Read-only.
 * Changes waiting for approval are not here yet; open them on the Work tab to see their files.
 * @param {{rid: number}} props
 */
export default function Files({ rid }) {
  const [files, setFiles] = useState(null); const [err, setErr] = useState(""); const [path, setPath] = useState(""); const [file, setFile] = useState(null);
  useEffect(() => { api(`/api/rooms/${rid}/files`, { rid }).then(setFiles).catch((e) => setErr(e.message)); }, [rid]);
  const open = async (p) => {
    setPath(p); setFile(null);
    try { setFile(await api(`/api/rooms/${rid}/files/content?path=${encodeURIComponent(p)}`, { rid })); } catch (e) { setFile({ text: e.message }); }
  };
  if (err) return <p className="err">{err}</p>;
  if (!files) return <p className="muted">Loading…</p>;
  return (
    <div>
      <p className="muted small">The project as it is now, including every approved change. A change waiting for approval is not here yet: open it on the Work tab to see its files.</p>
      <div className="files-view">
        <ul className="plain file-list" aria-label="Project files">
          {files.map((p) => <li key={p}><button className="link" aria-current={p === path} onClick={() => open(p)}><code>{p}</code></button></li>)}
          {!files.length && <li className="muted small">No files yet.</li>}
        </ul>
        <div className="file-body">
          {!path && <p className="muted">Pick a file to read it.</p>}
          {path && <><h3><code>{path}</code></h3>
            <pre className="tall">{!file ? "Loading…" : file.binary ? "(binary file, not shown)" : file.text + (file.truncated ? "\n… (cut short: file is large)" : "")}</pre></>}
        </div>
      </div>
    </div>
  );
}
