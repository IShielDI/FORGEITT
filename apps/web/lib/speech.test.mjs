import { test } from "node:test";
import assert from "node:assert/strict";
import { appendTranscript, finalText, recognitionClass } from "./speech.mjs";

test("appendTranscript joins with one space and trims the spoken text", () => {
  assert.equal(appendTranscript("", "  hello  world "), "hello world");
  assert.equal(appendTranscript("Add login", "with Google"), "Add login with Google");
  assert.equal(appendTranscript("Add login   ", "please"), "Add login please");
  assert.equal(appendTranscript("keep", "   "), "keep");
});

test("finalText ignores interim results", () => {
  const r = (t, isFinal) => Object.assign([{ transcript: t }], { isFinal });
  assert.equal(finalText([r("dark ", true), r("mo", false)]), "dark ");
  assert.equal(finalText([r("a ", true), r("b", true)], 1), "b");
});

test("recognitionClass finds the prefixed constructor or reports none", () => {
  function Webkit() {}
  assert.equal(recognitionClass({ webkitSpeechRecognition: Webkit }), Webkit);
  assert.equal(recognitionClass({}), null);
  assert.equal(recognitionClass(undefined), null);
});
