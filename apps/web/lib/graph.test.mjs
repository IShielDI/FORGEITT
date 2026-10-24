import { test } from "node:test";
import assert from "node:assert/strict";
import { layout } from "./graph.mjs";

const nodes = [{ id: "a" }, { id: "b" }, { id: "c" }, { id: "d" }];
const edges = [{ source: "a", target: "b" }, { source: "b", target: "c" }];

test("layout places every node inside the canvas", () => {
  const pos = layout(nodes, edges, 400, 300);
  for (const n of nodes) {
    assert.ok(pos[n.id].x >= 20 && pos[n.id].x <= 380 && pos[n.id].y >= 20 && pos[n.id].y <= 280);
  }
});

test("layout is deterministic for the same graph", () => {
  assert.deepEqual(layout(nodes, edges, 400, 300), layout(nodes, edges, 400, 300));
});

test("linked nodes end up closer than unlinked ones", () => {
  const pos = layout(nodes, edges, 400, 300);
  const dist = (p, q) => Math.hypot(pos[p].x - pos[q].x, pos[p].y - pos[q].y);
  assert.ok(dist("a", "b") < dist("a", "d"));
});
