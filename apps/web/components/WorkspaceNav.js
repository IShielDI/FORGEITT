"use client";
import { useEffect, useState } from "react";
import { recent } from "../lib/api";

const COLLAPSED = "forgeit:nav-collapsed";

/**
 * Side panel of the workspaces this browser has opened, like the chat list in an AI app.
 * Names and numbers only; each workspace's login token stays under its own key.
 * @param {{current: number, name?: string}} props
 */
export default function WorkspaceNav({ current, name }) {
  const [rooms, setRooms] = useState([]); const [collapsed, setCollapsed] = useState(false); const [open, setOpen] = useState(false);
  useEffect(() => { setRooms(recent()); try { setCollapsed(localStorage.getItem(COLLAPSED) === "1"); } catch {} }, [current, name]);
  const toggle = () => { const v = !collapsed; setCollapsed(v); try { localStorage.setItem(COLLAPSED, v ? "1" : "0"); } catch {} };

  return (
    <>
      <button className="nav-open quiet" aria-label="Show workspaces" aria-expanded={open} onClick={() => setOpen(true)}>☰ Workspaces</button>
      {open && <div className="nav-scrim" onClick={() => setOpen(false)} aria-hidden="true" />}
      <nav className={"wsnav" + (collapsed ? " collapsed" : "") + (open ? " open" : "")} aria-label="Workspaces">
        <div className="wsnav-head">
          {!collapsed && <b>Workspaces</b>}
          <button className="quiet icon desk-only" onClick={toggle} aria-label={collapsed ? "Expand the workspace list" : "Collapse the workspace list"} title={collapsed ? "Expand" : "Collapse"}>{collapsed ? "»" : "«"}</button>
          <button className="quiet icon phone-only" onClick={() => setOpen(false)} aria-label="Close the workspace list">✕</button>
        </div>
        <a className="wsnav-new" href="/" title="Start or join a workspace">{collapsed ? "+" : "+ New or join"}</a>
        <ul>
          {rooms.map(({ id, name: n }) => ({ id, name: n || `Workspace ${id}` })).map((r) => (
            <li key={r.id}>
              <a href={`/w/${r.id}`} aria-current={r.id === current ? "page" : undefined} title={`${r.name} (workspace ${r.id})`}>
                <span className="wsnav-dot" aria-hidden="true">{r.name.slice(0, 1).toUpperCase()}</span>
                {!collapsed && <span className="wsnav-name">{r.name}<small>#{r.id}</small></span>}
              </a>
            </li>))}
          {!rooms.length && !collapsed && <li className="muted small">Workspaces you open appear here.</li>}
        </ul>
      </nav>
    </>
  );
}
