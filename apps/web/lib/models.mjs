// Model choice helpers (pure, unit-tested). A model is "<provider>:<model>" for the free tiers
// (e.g. "groq:llama-3.3-70b-versatile"); a bare name is a Claude model on the member's own key.

/** @typedef {{id: string, label: string, free: boolean, ready: boolean, needs_key: boolean, source: string|null, key_last4: string|null, signup_url: string, note: string, models: string[]}} Provider */

export const ANTHROPIC = "anthropic";

/** Which provider a model reference belongs to. */
export function providerOf(ref, providers) {
  const i = (ref || "").indexOf(":");
  const head = i > 0 ? ref.slice(0, i) : "";
  return head && ref.length > i + 1 && providers.some((p) => p.id === head && p.id !== ANTHROPIC) ? head : ANTHROPIC;
}

/** The model name without its provider prefix, for display. */
export function modelLabel(ref, providers) {
  return providerOf(ref, providers) === ANTHROPIC ? ref : ref.slice(ref.indexOf(":") + 1);
}

/** The model to use: the person's pick, else the agent's default if usable, else the first ready free model. */
export function pickModel(chosen, agentDefault, providers) {
  if (chosen) return chosen;
  const usable = (ref) => providers.find((p) => p.id === providerOf(ref, providers))?.ready;
  if (agentDefault && usable(agentDefault)) return agentDefault;
  const free = providers.find((p) => p.free && p.ready && p.models.length && p.source !== "local")
    || providers.find((p) => p.free && p.ready && p.models.length);
  return free ? free.models[0] : agentDefault || "";
}

/** Can a run start on this model? `funded` matters only for Claude (free tiers cost no credits). */
export function readiness(ref, providers, funded) {
  const provider = providers.find((p) => p.id === providerOf(ref, providers));
  if (!provider) return { ready: false, provider: null, reason: "Pick a model." };
  if (!provider.ready) return { ready: false, provider, reason: provider.free ? `Add a free ${provider.label} key first.` : "Connect your Claude key first, or pick a free model." };
  if (!provider.free && !funded) return { ready: false, provider, reason: "Your budget is used up. Add more under Credits, or pick a free model." };
  return { ready: true, provider, reason: "" };
}

/** Plain-words status for a provider card. */
export function statusText(p) {
  if (p.source === "local") return "Runs on this machine (Ollama), no key needed";
  if (p.source === "yours") return `Ready: your key ending ${p.key_last4}`;
  if (p.source === "demo") return "Ready: shared demo key";
  if (!p.needs_key) return "Not running here: install Ollama and pull a model";
  return p.free ? "Needs a free key" : "Needs your key";
}
