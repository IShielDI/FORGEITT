// Pure helpers shared by the UI (and unit-tested with `node --test`).

/** @param {number|string|null|undefined} x dollars @returns {string} e.g. "$1.50" */
export const money = (x) => "$" + Number(x || 0).toFixed(2);

/**
 * WebSocket address for a path on the API.
 * @param {string} api NEXT_PUBLIC_API ("" means the page's own host)
 * @param {{protocol: string, host: string}} loc window.location
 * @param {string} path e.g. "/api/rooms/1/ws"
 * @param {Record<string,string>} params query parameters (values are URI-encoded)
 */
export function wsUrl(api, loc, path, params = {}) {
  const base = api ? new URL(api) : new URL(`${loc.protocol}//${loc.host}`);
  const scheme = base.protocol === "https:" ? "wss:" : "ws:";
  const qs = Object.entries(params).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");
  return `${scheme}//${base.host}${path}${qs ? "?" + qs : ""}`;
}

/** Merge new chat messages into a list by id, keeping order and dropping duplicates. */
export function mergeMessages(list, incoming) {
  const seen = new Set(list.map((m) => m.id));
  return [...list, ...incoming.filter((m) => !seen.has(m.id))].sort((a, b) => a.id - b.id);
}
