import { test } from "node:test";
import assert from "node:assert/strict";
import { money, wsUrl, mergeMessages } from "./util.mjs";

test("money formats dollars with two decimals", () => {
  assert.equal(money(1.5), "$1.50");
  assert.equal(money(null), "$0.00");
});

test("wsUrl uses the page host and the secure scheme on https", () => {
  assert.equal(wsUrl("", { protocol: "http:", host: "localhost:3000" }, "/api/rooms/1/ws", { token: "a b" }), "ws://localhost:3000/api/rooms/1/ws?token=a%20b");
  assert.equal(wsUrl("", { protocol: "https:", host: "x.trycloudflare.com" }, "/p"), "wss://x.trycloudflare.com/p");
  assert.equal(wsUrl("http://127.0.0.1:8000", { protocol: "https:", host: "ignored" }, "/p"), "ws://127.0.0.1:8000/p");
});

test("mergeMessages de-duplicates and keeps id order", () => {
  const out = mergeMessages([{ id: 1 }, { id: 3 }], [{ id: 2 }, { id: 3 }]);
  assert.deepEqual(out.map((m) => m.id), [1, 2, 3]);
});
