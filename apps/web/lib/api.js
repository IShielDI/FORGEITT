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
