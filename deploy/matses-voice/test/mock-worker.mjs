// Minimal stand-in for the Cloudflare Worker: emulates /run, /status/:id, /health
// with scripted states so the page can be tested without touching RunPod.
//
// Scenario selector: set MOCK_SCENARIO in the environment when starting.
//   standard (default) 2x IN_PROGRESS (with delayTime) then COMPLETED
//   queue              3x IN_QUEUE, 2x IN_PROGRESS (delayTime 45000), then COMPLETED
//   immediate          first status poll COMPLETED (warm worker)
//   noerror            first status poll FAILED with no error field
// The scripted-failure job (POST /run body {"fail": true}) is independent of
// the scenario and always fails on the first status poll.
import http from "node:http";

const PORT = 8999;
const SCENARIO = process.env.MOCK_SCENARIO || "standard";
const jobs = new Map();
const seen = new Set();
let counter = 0;

http.createServer((req, res) => {
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
  for (const [k, v] of Object.entries(cors)) res.setHeader(k, v);
  res.setHeader("Content-Type", "application/json");
  const url = new URL(req.url, "http://127.0.0.1:" + PORT);
  const path = url.pathname.replace(/\/+$/, "") || "/";

  const done = (status, body) => {
    res.statusCode = status;
    res.end(JSON.stringify(body));
  };

  if (req.method === "OPTIONS") return done(204, {});

  if (path === "/health") {
    if (req.method !== "GET") return done(405, { error: "Method not allowed" });
    return done(200, { ok: true });
  }

  if (path === "/run") {
    if (req.method !== "POST") return done(405, { error: "Method not allowed" });
    let body = "";
    req.on("data", (c) => { body += c; });
    req.on("end", () => {
      let parsed;
      try {
        parsed = JSON.parse(body);
      } catch {
        return done(400, { error: "Body must be JSON" });
      }
      const audio = parsed && parsed.audio_base64;
      if (typeof audio !== "string" || audio.length === 0) return done(400, { error: "audio_base64 required" });
      if (audio.length > 8000000) return done(413, { error: "Encoded audio too large" });
      const bytes = Buffer.from(audio, "base64");
      const u8 = new Uint8Array(bytes);
      const tag = (o, s) => String.fromCharCode(...u8.slice(o, o + s.length));
      if (tag(0, "RIFF") !== "RIFF" || tag(8, "WAVE") !== "WAVE" || tag(12, "fmt ") !== "fmt ") {
        return done(400, { error: "Not a valid WAV (RIFF/WAVE/fmt)" });
      }
      if (parsed.fail) {
        const id = "mockjobfail0001";
        jobs.set(id, { polls: 0 });
        return done(200, { id, status: "IN_QUEUE" });
      }
      counter += 1;
      const id = "mockjob" + String(counter).padStart(8, "0");
      jobs.set(id, { polls: 0 });
      if (audio.length < 1000) return done(400, { error: "audio too short" });
      return done(200, { id, status: "IN_QUEUE" });
    });
    return;
  }

  if (path === "/feedback") {
    if (req.method !== "POST") return done(405, { error: "Method not allowed" });
    let body = "";
    req.on("data", (c) => {
      body += c;
      if (body.length > 524288) req.destroy();
    });
    req.on("end", () => {
      let p;
      try {
        p = JSON.parse(body);
      } catch {
        return done(400, { error: "Dados inválidos." });
      }
      const bad = () => done(400, { error: "Dados inválidos." });
      if (!p || typeof p !== "object") return bad();
      if (typeof p.job_id !== "string" || !/^[A-Za-z0-9-]{8,64}$/.test(p.job_id)) return bad();
      if (typeof p.client_id !== "string" || p.client_id.length < 8) return bad();
      if (typeof p.transcript !== "string" || !p.transcript || p.transcript.length > 4000) return bad();
      if (p.verdict === "correct") {
        // FalhaRun: synthetic value forcing the 500 path (documented in README)
  if (p.correction === "FalhaRun") return done(500, { error: "Erro do servidor." });
        if (seen.has(p.client_id)) return done(200, { ok: true, duplicate: true });
        seen.add(p.client_id);
        return done(200, { ok: true });
      }
      const ix = p.word_indexes;
      if (!Array.isArray(ix) || !ix.length || ix.length > 1000) return bad();
      if (!ix.every((n) => Number.isInteger(n) && n >= 0 && n < 1000)) return bad();
      for (let k = 1; k < ix.length; k++) if (ix[k] !== ix[k - 1] + 1) return bad();
      if (p.word_index !== ix[0]) return bad();
      const toks = p.transcript.split(/\s+/).filter(Boolean);
      if (ix[ix.length - 1] >= toks.length) return bad();
      if (typeof p.original !== "string" || p.original !== toks.slice(ix[0], ix[ix.length - 1] + 1).join(" ")) return bad();
      if (typeof p.correction !== "string" || !p.correction.trim() || p.correction.length > 200) return bad();
      if (p.correction.trim() === p.original) return bad();
      // FalhaRun: synthetic value forcing the 500 path (documented in README)
  if (p.correction === "FalhaRun") return done(500, { error: "Erro do servidor." });
      if (seen.has(p.client_id)) return done(200, { ok: true, duplicate: true });
      seen.add(p.client_id || String(Math.random()));
      return done(200, { ok: true });
    });
    return;
  }

  const m2 = path.match(/^\/status\/[a-z][a-z0-9]{1,7}\/([A-Za-z0-9-]{8,64})$/);
  const path2 = m2 ? "/status/" + m2[1] : path;
  const m = path2.match(/^\/status\/([A-Za-z0-9-]{8,64})$/);
  if (m) {
    if (req.method !== "GET") return done(405, { error: "Method not allowed" });
    const id = m[1];
    const job = jobs.get(id);
    if (!job) return done(404, { error: "Unknown job" });
    job.polls += 1;
    if (id === "mockjobfail0001") return done(200, { status: "FAILED", error: "scripted failure" });
    if (SCENARIO === "noerror") return done(200, { status: "FAILED" });
    if (SCENARIO === "immediate") return done(200, { status: "COMPLETED", text: "Uwesh Fruqui matud (mock transcription)" });
    if (SCENARIO === "queue") {
      if (job.polls <= 3) return done(200, { status: "IN_QUEUE" });
      if (job.polls <= 5) return done(200, { status: "IN_PROGRESS", delayTime: 45000 });
      return done(200, { status: "COMPLETED", text: "Uwesh Fruqui matud (mock transcription)" });
    }
    if (job.polls >= 3) return done(200, { status: "COMPLETED", text: "Uwesh Fruqui matud (mock transcription)" });
    return done(200, { status: "IN_PROGRESS", delayTime: 1200 });
  }

  done(404, { error: "Not found" });
}).listen(PORT, "127.0.0.1", () => console.log("mock worker on " + PORT));
