// Drives each page's inline script in a vm sandbox with a deterministic clock,
// stub DOM, stub audio stack and scripted fetch responses. The key regression
// covered here: the loading-seconds counter must keep accumulating across
// status polls (it used to restart from 0:00 on every 3s poll). Run with:
//   node --test test/loading-state.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PAGES = [
  { name: "standalone", file: path.join(HERE, "..", "page", "index.html") },
  { name: "mcf", file: path.join(HERE, "..", "page", "mcf", "index.html") },
];

const QUEUED = "Na fila — aguardando processamento.";
const WORKING = "Processando o áudio...";
const PREPARING = "Preparando o áudio...";
const UPLOADING = "Enviando o áudio...";
const UPDATING = "Não foi possível atualizar o andamento. Tentando de novo...";
const STARTUP_HINT =
  "Após um período sem uso, o serviço pode levar alguns minutos para iniciar.";

// Yield real event-loop turns so both microtasks and platform promises
// (e.g. Blob.arrayBuffer) settle between steps.
const flush = async () => {
  for (let i = 0; i < 10; i++) await new Promise((r) => setImmediate(r));
};

function makeElement(id) {
  const listeners = {};
  return {
    id,
    hidden: false,
    disabled: false,
    textContent: "",
    innerHTML: "",
    value: "",
    placeholder: "",
    className: "",
    type: "",
    lang: "",
    dataset: {},
    children: [],
    isConnected: true,
    addEventListener(ev, fn) { (listeners[ev] || (listeners[ev] = [])).push(fn); },
    removeEventListener() {},
    setAttribute(k, v) { this["attr_" + k] = String(v); },
    removeAttribute(k) { delete this["attr_" + k]; },
    getAttribute(k) { return k in this ? this["attr_" + k] : null; },
    appendChild(c) { this.children.push(c); return c; },
    remove() {},
    focus() {},
    select() {},
    click() {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    fire(ev, arg) {
      const evObj = arg || { preventDefault() {}, target: this };
      for (const fn of listeners[ev] || []) fn(evObj);
    },
  };
}

function loadPage(page) {
  const html = fs.readFileSync(page.file, "utf8");
  const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
  assert.ok(scriptMatch, page.name + ": inline script not found");
  const script = scriptMatch[1];
  const ids = new Set([...html.matchAll(/id="([^"]+)"/g)].map((m) => m[1]));

  let now = 0;
  let nextTid = 1;
  const timers = new Map();
  const fakeSetTimeout = (fn, ms) => {
    const id = nextTid++;
    timers.set(id, { fn, at: now + (ms || 0), every: null });
    return id;
  };
  const fakeSetInterval = (fn, ms) => {
    const id = nextTid++;
    timers.set(id, { fn, at: now + (ms || 0), every: ms || 1 });
    return id;
  };
  const fakeClear = (id) => { timers.delete(id); };
  const advance = async (ms) => {
    const target = now + ms;
    for (;;) {
      let bestId = null;
      let bestAt = Infinity;
      for (const [id, t] of timers) {
        if (t.at <= target && t.at < bestAt) { bestAt = t.at; bestId = id; }
      }
      if (bestId === null) break;
      const t = timers.get(bestId);
      now = t.at;
      if (t.every != null) t.at += t.every; else timers.delete(bestId);
      t.fn();
      await flush();
    }
    now = target;
  };

  const els = new Map();
  const document = {
    getElementById(id) {
      if (!ids.has(id)) return null; // faithful: unknown ids are null like in a browser
      if (!els.has(id)) els.set(id, makeElement(id));
      return els.get(id);
    },
    createElement: (tag) => makeElement("<" + tag + ">"),
    querySelectorAll: () => [],
    querySelector: () => null,
    addEventListener() {},
    body: makeElement("body"),
    hidden: false,
    execCommand() {},
  };

  class FakeMediaRecorder {
    static isTypeSupported() { return true; }
    constructor() { this.state = "inactive"; this.mimeType = "audio/webm"; }
    start() { this.state = "recording"; }
    stop() {
      this.state = "stopped";
      if (this.ondataavailable) this.ondataavailable({ data: new Blob([new Uint8Array(64)]) });
      if (this.onstop) this.onstop();
    }
  }
  class FakeAudioContext {
    async decodeAudioData() { return { duration: 2, sampleRate: 48000, length: 96000 }; }
    close() {}
  }
  class FakeOfflineAudioContext {
    constructor(ch, len) { this.len = len; this.destination = {}; }
    createBufferSource() { return { connect() {}, start() {}, buffer: null }; }
    async startRendering() { return { getChannelData: () => new Float32Array(this.len) }; }
  }

  const state = { runCalls: 0, polls: 0, statusScript: [], runFails: false };
  const jsonResp = (body, status = 200) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
  const fetchStub = async (url) => {
    const u = String(url);
    if (u.includes("/run")) {
      state.runCalls += 1;
      if (state.runFails) return jsonResp({ error: "boom" }, 500);
      return jsonResp({ id: "job-12345678", status: "IN_QUEUE" });
    }
    if (u.includes("/status")) {
      const i = state.polls;
      state.polls += 1;
      const item = state.statusScript[i] !== undefined ? state.statusScript[i] : state.statusScript[state.statusScript.length - 1];
      if (item instanceof Error) throw item;
      if (item === undefined) throw new Error("statusScript exhausted");
      return jsonResp(item);
    }
    return jsonResp({ error: "unexpected url " + u }, 404);
  };

  class FakeDate extends Date {
    static now() { return now; }
  }
  const sandbox = {
    console,
    document,
    Date: FakeDate,
    location: { search: "?worker=http://127.0.0.1:8999", hostname: "localhost" },
    navigator: {
      mediaDevices: { getUserMedia: async () => ({ getTracks: () => [] }) },
      clipboard: null,
    },
    window: {
      AudioContext: FakeAudioContext,
      MediaRecorder: FakeMediaRecorder,
      open() {},
    },
    MediaRecorder: FakeMediaRecorder,
    AudioContext: FakeAudioContext,
    OfflineAudioContext: FakeOfflineAudioContext,
    Blob,
    URLSearchParams,
    btoa,
    atob,
    crypto: globalThis.crypto,
    fetch: fetchStub,
    performance: { now: () => now },
    setTimeout: fakeSetTimeout,
    clearTimeout: fakeClear,
    setInterval: fakeSetInterval,
    clearInterval: fakeClear,
    queueMicrotask: (fn) => Promise.resolve().then(fn),
  };
  sandbox.window = Object.assign(sandbox.window, {
    webkitAudioContext: undefined,
    location: sandbox.location,
  });

  vm.createContext(sandbox);
  vm.runInContext(script, sandbox, { filename: page.name + ".html" });

  const el = (id) => {
    const e = document.getElementById(id);
    assert.ok(e, page.name + ": element #" + id + " missing from page");
    return e;
  };

  return {
    page, state, el, advance, ids,
    click: (id) => el(id).fire("click"),
    async recordAndSend() {
      this.click("rec");
      await flush();
      this.click("stop"); // -> processRecording -> /run -> pollLoop
      await flush();
    },
  };
}

for (const page of PAGES) {
  test(page.name + ": loading timer accumulates across polls and stages render", async () => {
    const h = loadPage(page);
    h.state.statusScript = [
      { status: "IN_QUEUE" },
      { status: "IN_PROGRESS", delayTime: 45000 },
      { status: "COMPLETED", text: "hello world" },
    ];
    await h.recordAndSend();

    assert.equal(h.el("loading").hidden, false, "loading section visible");
    assert.equal(h.el("loadtimer").textContent, "0:00");
    assert.equal(h.el("loadstage").textContent, QUEUED);
    assert.equal(h.el("loadstartup").hidden, false, "startup hint visible while queued");

    await h.advance(3000); // poll 1: still queued
    assert.equal(h.el("loadtimer").textContent, "0:03");
    assert.equal(h.el("loadstage").textContent, QUEUED);

    await h.advance(3000); // poll 2: working, queue wait shown
    assert.equal(h.el("loadtimer").textContent, "0:06", "timer must not reset after a poll");
    assert.equal(h.el("loadstage").textContent, WORKING + " (Tempo na fila: 0:45)");
    assert.equal(h.el("loadstartup").hidden, false, "startup hint visible while working");

    await h.advance(3000); // poll 3: completed
    assert.equal(h.el("loadtimer").textContent, "0:09", "timer must not reset after a poll");
    assert.equal(h.el("result").hidden, false, "result section visible");
    assert.equal(h.el("loading").hidden, true);

    const frozen = h.el("loadtimer").textContent;
    await h.advance(10000);
    assert.equal(h.el("loadtimer").textContent, frozen, "timer stopped after completion");
    assert.equal(h.state.runCalls, 1, "exactly one /run submission");
  });

  test(page.name + ": transient poll failures show updating stage, then recover", async () => {
    const h = loadPage(page);
    h.state.statusScript = [
      new Error("network down"),
      new Error("network down"),
      { status: "IN_PROGRESS" },
      { status: "COMPLETED", text: "ok" },
    ];
    await h.recordAndSend();

    await h.advance(3000); // poll 1 fails
    assert.equal(h.el("loadstage").textContent, UPDATING);
    assert.equal(h.el("error").hidden, true, "one failure is not fatal");
    assert.equal(h.el("loadstartup").hidden, true, "startup hint hidden while updating");

    await h.advance(3000); // poll 2 fails
    assert.equal(h.el("loadstage").textContent, UPDATING);
    assert.equal(h.el("loadtimer").textContent, "0:06", "timer keeps running through failures");

    await h.advance(3000); // poll 3 recovers
    assert.equal(h.el("loadstage").textContent, WORKING);
    assert.equal(h.el("loadtimer").textContent, "0:09");

    await h.advance(3000); // poll 4 completes
    assert.equal(h.el("result").hidden, false);
  });

  test(page.name + ": five consecutive failures end in the error screen", async () => {
    const h = loadPage(page);
    h.state.statusScript = [new Error("down")]; // repeated for every poll
    await h.recordAndSend();
    for (let i = 0; i < 5; i++) await h.advance(3000);
    assert.equal(h.el("error").hidden, false);
    const frozen = h.el("loadtimer").textContent;
    await h.advance(10000);
    assert.equal(h.el("loadtimer").textContent, frozen, "timer stopped after fatal failure");
    assert.equal(h.state.polls, 5, "no polls after giving up");
  });

  test(page.name + ": terminal status without error field still ends in error", async () => {
    const h = loadPage(page);
    h.state.statusScript = [{ status: "FAILED" }];
    await h.recordAndSend();
    await h.advance(3000);
    assert.equal(h.el("error").hidden, false);
    assert.equal(h.el("errmsg").textContent, "FAILED");
  });

  test(page.name + ": cancel stops the timer and invalidates pending polls", async () => {
    const h = loadPage(page);
    h.state.statusScript = [{ status: "IN_PROGRESS" }, { status: "COMPLETED", text: "late" }];
    await h.recordAndSend();
    await h.advance(1000);
    assert.equal(h.el("loadtimer").textContent, "0:01");

    h.click("cancel");
    assert.equal(h.el("idle").hidden, false);
    assert.equal(h.el("loadstage").textContent, "", "stage cleared on cancel");
    assert.equal(h.el("loadstartup").hidden, true, "startup hint cleared on cancel");

    const frozen = h.el("loadtimer").textContent;
    await h.advance(30000);
    assert.equal(h.el("loadtimer").textContent, frozen, "timer stopped after cancel");
    assert.equal(h.state.polls, 0, "pending poll was cancelled");
    assert.equal(h.el("result").hidden, true, "no late result after cancel");
  });

  test(page.name + ": submission failure ends in error with the timer frozen", async () => {
    const h = loadPage(page);
    h.state.runFails = true;
    await h.recordAndSend();
    assert.equal(h.el("error").hidden, false);
    assert.equal(h.el("errmsg").textContent, "boom", "server-provided error surfaces");
    assert.equal(h.el("loadstage").textContent, "", "stage cleared on failure");
    const frozen = h.el("loadtimer").textContent;
    await h.advance(10000);
    assert.equal(h.el("loadtimer").textContent, frozen, "timer stopped after failure");
    assert.equal(h.state.polls, 0, "no polls after submission failure");
  });

  test(page.name + ": a fresh attempt after failure gets a fresh timer epoch", async () => {
    const h = loadPage(page);
    h.state.runFails = true;
    await h.recordAndSend();
    assert.equal(h.el("error").hidden, false);

    h.state.runFails = false;
    h.state.statusScript = [{ status: "IN_PROGRESS" }, { status: "COMPLETED", text: "second try" }];
    // Advance the clock so the new epoch assertion fails if loadTimerStart ever
    // stops resetting loadStart (both attempts starting at t=0 would mask it).
    await h.advance(60_000);
    h.click("retry");
    assert.equal(h.el("idle").hidden, false, "retry returns to idle (no auto-resubmit)");
    await h.recordAndSend();
    assert.equal(h.state.runCalls, 2, "second /run after retry");
    assert.equal(h.el("loadtimer").textContent, "0:00", "new attempt starts a new epoch");
    await h.advance(3000);
    assert.equal(h.el("loadtimer").textContent, "0:03");
    await h.advance(3000);
    assert.equal(h.el("result").hidden, false, "second attempt completes");
  });

  test(page.name + ": poll deadline expiry ends in the error screen", async () => {
    const h = loadPage(page);
    h.state.statusScript = [{ status: "IN_PROGRESS" }]; // never finishes
    await h.recordAndSend();
    await h.advance(1_204_000); // POLL_DEADLINE_MS is 20 min; one poll past it
    assert.equal(h.el("error").hidden, false);
    assert.equal(h.el("errmsg").textContent, "Tempo esgotado. Tente de novo.");
    assert.equal(h.el("loadstartup").hidden, true, "startup hint cleared on timeout");
    const frozen = h.el("loadtimer").textContent;
    await h.advance(10000);
    assert.equal(h.el("loadtimer").textContent, frozen, "timer stopped after deadline");
  });
}
