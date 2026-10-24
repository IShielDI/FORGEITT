// Deterministic force-directed layout for the project graph (no dependencies, unit-tested).

/** Small seeded PRNG so the same graph always lays out the same way. */
function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

/**
 * @param {{id:string}[]} nodes
 * @param {{source:string,target:string}[]} edges
 * @param {number} width
 * @param {number} height
 * @param {number} iterations
 * @returns {Record<string,{x:number,y:number}>}
 */
export function layout(nodes, edges, width, height, iterations = 250) {
  const rand = rng(nodes.length * 7919 + edges.length);
  const pos = {};
  nodes.forEach((n) => { pos[n.id] = { x: width / 2 + (rand() - 0.5) * width * 0.8, y: height / 2 + (rand() - 0.5) * height * 0.8 }; });
  const area = width * height, k = Math.min(110, Math.sqrt(area / Math.max(1, nodes.length)) * 0.5);
  const cx = width / 2, cy = height / 2, gravity = 0.012;
  let temp = width / 8;
  for (let it = 0; it < iterations; it++) {
    const disp = Object.fromEntries(nodes.map((n) => [n.id, { x: 0, y: 0 }]));
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = pos[nodes[i].id], b = pos[nodes[j].id];
        const dx = a.x - b.x, dy = a.y - b.y, d = Math.max(0.01, Math.hypot(dx, dy)), f = (k * k) / d;
        disp[nodes[i].id].x += (dx / d) * f; disp[nodes[i].id].y += (dy / d) * f;
        disp[nodes[j].id].x -= (dx / d) * f; disp[nodes[j].id].y -= (dy / d) * f;
      }
    }
    for (const e of edges) {
      const a = pos[e.source], b = pos[e.target];
      if (!a || !b) continue;
      const dx = a.x - b.x, dy = a.y - b.y, d = Math.max(0.01, Math.hypot(dx, dy)), f = (d * d) / k;
      disp[e.source].x -= (dx / d) * f; disp[e.source].y -= (dy / d) * f;
      disp[e.target].x += (dx / d) * f; disp[e.target].y += (dy / d) * f;
    }
    for (const n of nodes) {
      // gentle pull toward the centre keeps small graphs from drifting into the corners
      disp[n.id].x += (cx - pos[n.id].x) * gravity * k;
      disp[n.id].y += (cy - pos[n.id].y) * gravity * k;
    }
    for (const n of nodes) {
      const d = disp[n.id], len = Math.max(0.01, Math.hypot(d.x, d.y)), p = pos[n.id];
      p.x = Math.min(width - 20, Math.max(20, p.x + (d.x / len) * Math.min(len, temp)));
      p.y = Math.min(height - 20, Math.max(20, p.y + (d.y / len) * Math.min(len, temp)));
    }
    temp *= 0.97;
  }
  return pos;
}
