// Empty = same address as this page (the site passes /api on to the backend). Set NEXT_PUBLIC_API only to point elsewhere.
export const API = process.env.NEXT_PUBLIC_API || "";
const key = (rid) => `forgeit:token:${rid}`;
export const getToken = (rid) => { try { return localStorage.getItem(key(rid)) || ""; } catch { return ""; } };
export const setToken = (rid, t) => { try { localStorage.setItem(key(rid), t); } catch {} };

export async function api(path, { rid, method, body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const t = rid ? getToken(rid) : "";
  if (t) headers.Authorization = `Bearer ${t}`;
  const r = await fetch(API + path, { method: method || (body ? "POST" : "GET"), headers, body: body ? JSON.stringify(body) : undefined, cache: "no-store" });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : r.statusText);
  return j;
}
// <video> and EventSource cannot send headers, so they carry the token in the address.
export const withToken = (rid, url) => `${API}${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(getToken(rid))}`;
export { money } from "./util.mjs";

// Workspaces this browser has opened, so the home page can offer them again (names only; tokens stay under their own keys).
export const recent = () => { try { return JSON.parse(localStorage.getItem("forgeit:rooms") || "[]"); } catch { return []; } };
const MAX_RECENT = 30;
export const remember = (id, name) => {
  try {
    const list = recent(), i = list.findIndex((r) => r.id === id);
    if (i >= 0) list[i] = { id, name };                 // keep its place in the side panel, refresh the name
    else list.unshift({ id, name });
    localStorage.setItem("forgeit:rooms", JSON.stringify(list.slice(0, MAX_RECENT)));
  } catch {}
};
// After a workspace is deleted (or you leave it): drop it from the list and drop its login token.
export const forget = (id) => { try { localStorage.setItem("forgeit:rooms", JSON.stringify(recent().filter((r) => r.id !== id))); localStorage.removeItem(key(id)); } catch {} };
