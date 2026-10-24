import { test } from "node:test";
import assert from "node:assert/strict";
import { modelLabel, pickModel, providerOf, readiness, statusText } from "./models.mjs";

const P = (id, over = {}) => ({ id, label: id, free: id !== "anthropic", ready: false, needs_key: id !== "ollama", source: null, key_last4: null, signup_url: "", note: "", models: [`${id}:m1`], ...over });
const providers = [P("anthropic", { models: ["claude-sonnet-5-5"] }), P("groq"), P("openrouter"), P("ollama", { ready: true, source: "local", models: ["ollama:qwen2.5-coder:7b"] })];

test("providerOf reads a known prefix; anything else is Claude", () => {
  assert.equal(providerOf("groq:llama-3.3", providers), "groq");
  assert.equal(providerOf("openrouter:qwen/qwen3-coder:free", providers), "openrouter");
  assert.equal(providerOf("claude-sonnet-5-5", providers), "anthropic");
  assert.equal(providerOf("acme:x", providers), "anthropic");
  assert.equal(modelLabel("ollama:qwen2.5-coder:7b", providers), "qwen2.5-coder:7b");
});

test("pickModel prefers the person's pick, then a usable default, then a cloud free tier over local", () => {
  assert.equal(pickModel("groq:x", "claude-sonnet-5-5", providers), "groq:x");
  assert.equal(pickModel("", "claude-sonnet-5-5", providers), "ollama:qwen2.5-coder:7b");
  const withGroq = providers.map((p) => (p.id === "groq" ? { ...p, ready: true, source: "demo" } : p));
  assert.equal(pickModel("", "claude-sonnet-5-5", withGroq), "groq:m1");
  const withClaude = providers.map((p) => (p.id === "anthropic" ? { ...p, ready: true } : p));
  assert.equal(pickModel("", "claude-sonnet-5-5", withClaude), "claude-sonnet-5-5");
});

test("readiness: free tiers need only a key, Claude also needs credits", () => {
  assert.equal(readiness("groq:m1", providers, false).ready, false);
  assert.match(readiness("groq:m1", providers, false).reason, /free groq key/);
  assert.equal(readiness("ollama:qwen2.5-coder:7b", providers, false).ready, true);
  const withClaude = providers.map((p) => (p.id === "anthropic" ? { ...p, ready: true } : p));
  assert.equal(readiness("claude-sonnet-5-5", withClaude, false).ready, false);
  assert.equal(readiness("claude-sonnet-5-5", withClaude, true).ready, true);
});

test("statusText says where the key comes from", () => {
  assert.equal(statusText(P("groq", { source: "yours", key_last4: "1234" })), "Ready: your key ending 1234");
  assert.equal(statusText(P("groq", { source: "demo" })), "Ready: shared demo key");
  assert.equal(statusText(P("groq")), "Needs a free key");
});
