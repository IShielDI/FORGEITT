// Helpers for voice dictation (pure, unit-tested). The browser does the speech recognition.

/** The browser's SpeechRecognition constructor, or null when this browser has none (e.g. Firefox). */
export function recognitionClass(win) {
  if (!win) return null;
  return win.SpeechRecognition || win.webkitSpeechRecognition || null;
}

/** Append dictated text to what is already typed, with exactly one space between them. */
export function appendTranscript(current, spoken) {
  const said = (spoken || "").replace(/\s+/g, " ").trim();
  if (!said) return current || "";
  const base = (current || "").replace(/\s+$/, "");
  return base ? `${base} ${said}` : said;
}

/** Final text from a SpeechRecognition result list, starting at `fromIndex`. */
export function finalText(results, fromIndex = 0) {
  let out = "";
  for (let i = fromIndex; i < results.length; i++) {
    if (results[i].isFinal) out += results[i][0].transcript;
  }
  return out;
}
