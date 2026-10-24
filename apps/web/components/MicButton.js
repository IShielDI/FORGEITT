"use client";
import { useEffect, useRef, useState } from "react";
import { finalText, recognitionClass } from "../lib/speech.mjs";

/**
 * Dictation button: speak, and the words are handed to `onText` (they are never sent by themselves).
 * Uses the browser's speech recognition; hidden when the browser has none.
 * @param {{onText: (text: string) => void, disabled?: boolean, label?: string}} props
 */
export default function MicButton({ onText, disabled = false, label = "Dictate" }) {
  const [supported, setSupported] = useState(false); const [on, setOn] = useState(false); const [err, setErr] = useState("");
  const rec = useRef(null); const push = useRef(onText);
  push.current = onText;
  useEffect(() => { setSupported(!!recognitionClass(typeof window === "undefined" ? undefined : window)); }, []);
  useEffect(() => () => rec.current?.abort(), []);
  if (!supported) return null;

  const start = () => {
    setErr("");
    const Rec = recognitionClass(window);
    const r = new Rec();
    r.lang = navigator.language || "en-US";
    r.interimResults = true;
    r.continuous = true;
    r.onresult = (e) => { const t = finalText(e.results, e.resultIndex); if (t.trim()) push.current(t); };
    r.onerror = (e) => setErr(e.error === "not-allowed" ? "Microphone access was blocked. Allow it in the browser to dictate." : e.error === "no-speech" ? "" : `Dictation stopped (${e.error}).`);
    r.onend = () => setOn(false);
    rec.current = r;
    try { r.start(); setOn(true); } catch { setOn(false); }
  };
  const stop = () => { rec.current?.stop(); setOn(false); };

  return (
    <>
      <button type="button" className={"mic quiet" + (on ? " live" : "")} disabled={disabled} aria-pressed={on} aria-label={on ? "Stop dictation" : label}
        title={on ? "Listening… press to stop" : `${label}: speak and the words appear here, ready to edit. Your browser's speech service turns the audio into text.`}
        onClick={on ? stop : start}>
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10a7 7 0 0 0 14 0" /><path d="M12 17v5" /></svg>
        {on && <span className="small"> Listening</span>}
      </button>
      {err && <span className="err small" role="alert">{err}</span>}
    </>
  );
}
