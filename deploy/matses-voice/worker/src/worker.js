// Proxy for the private RunPod omniASR_LLM_7B_v2 endpoint used by the Matsés page.
// The RunPod API key never leaves this Worker. It is bound as the RUNPOD_API_KEY
// secret and used only for upstream calls. Transcripts, corrections and audio
// are stored (R2 + D1) to build training labels; audio retention is disclosed
// in the page consent copy. Persist failures are logged via console.log only.
const RUNPOD_BASE = "https://api.runpod.ai/v2/";

// Profile registry: worker owns language/model/endpoint/origins per deployment.
const PROFILES = {
  mcf: {
    language: "mcf_Latn",
    model: "omniASR_LLM_7B_v2",
    endpointId: "6kxhw59ss9q9ze",
    origins: ["https://matses-voz.surge.sh"],
  },
};
const DEFAULT_PROFILE = "mcf";
const MAX_ENCODED = 8000000;

function allOrigins() {
  const set = new Set();
  for (const p of Object.values(PROFILES)) for (const o of p.origins) set.add(o);
  return [...set];
}

function corsHeaders(request) {
  const origin = (request && request.headers.get("Origin")) || "";
  const allow = origin && allOrigins().includes(origin) ? origin : "";
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

function json(env, request, data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders(request), "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

function bare(env, request, status) {
  return new Response(null, { status, headers: corsHeaders(request) });
}

const RATE = { run: 10, feedback: 20, status: 240, windowMs: 10 * 60 * 1000 };

function resolveProfile(body) {
  const id = body && body.profile;
  if (id === undefined || id === null || id === "") return DEFAULT_PROFILE;
  if (typeof id !== "string" || !/^[a-z][a-z0-9]{1,7}$/.test(id)) return null;
  return PROFILES[id] ? id : null;
}


async function rateLimited(env, request, kind) {
  if (!env.DB) return false;
  try {
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const now = Date.now();
    const res = await env.DB.batch([
      env.DB.prepare("DELETE FROM rate_log WHERE ts < ?").bind(now - 3 * 24 * 60 * 60 * 1000),
      env.DB.prepare("INSERT INTO rate_log (ip, kind, ts) VALUES (?, ?, ?)").bind(ip, kind, now),
      env.DB.prepare("SELECT COUNT(*) AS n FROM rate_log WHERE ip = ? AND kind = ? AND ts > ?").bind(ip, kind, now - RATE.windowMs),
    ]);
    const n = (res && res[2] && res[2].results && res[2].results[0] && res[2].results[0].n) || 0;
    return n > RATE[kind];
  } catch (err) {
    return false;
  }
}

async function persistRun(env, profId, jobId, audioB64) {
  if (!env.AUDIO || !env.DB) return;
  try {
    const raw = atob(audioB64);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const key = profId + "/" + jobId + ".wav";
    await env.AUDIO.put(key, bytes, {
      httpMetadata: { contentType: "audio/wav" },
    });
    await env.DB.prepare(
      "INSERT INTO runs (job_id, profile, model, language, audio_key) VALUES (?, ?, ?, ?, ?)"
    ).bind(jobId, profId, PROFILES[profId].model, PROFILES[profId].language, key).run();
  } catch (e) {
    console.log("persistRun failed for " + profId + "/" + jobId + ": " + String((e && e.message) || e));
  }
}

async function statusUpstream(env, request, profId, jobId) {
  const prof = PROFILES[profId];
  const upstream = await fetch(RUNPOD_BASE + prof.endpointId + "/status/" + jobId, {
    headers: { "Authorization": "Bearer " + env.RUNPOD_API_KEY },
  });
  if (!upstream.ok) return json(env, request, { error: "Upstream error " + upstream.status }, 502);
  const job = await upstream.json();
  const jobStatus = job.status;
  if (jobStatus === "COMPLETED") {
    const output = job.output || {};
    if (output.model !== prof.model) {
      return json(env, request, { status: "FAILED", error: "Model identity mismatch" });
    }
    const text = output.text === undefined ? "" : output.text;
    if (env.DB) {
      try {
        await env.DB.prepare("UPDATE runs SET transcript = ? WHERE job_id = ?")
          .bind(text, jobId).run();
      } catch (e) {
        console.log("runs transcript update failed for " + jobId + ": " + String((e && e.message) || e));
      }
    }
    return json(env, request, { status: "COMPLETED", text: text });
  }
  if (["FAILED", "CANCELLED", "TIMED_OUT"].includes(jobStatus)) {
    return json(env, request, { status: jobStatus, error: job.error || jobStatus });
  }
  return json(env, request, { status: jobStatus });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    try {
      if (request.method === "OPTIONS") return bare(env, request, 204);
      if (path === "/health") {
        if (request.method !== "GET") return json(env, request, { error: "Method not allowed" }, 405);
        return json(env, request, { ok: true, profiles: Object.keys(PROFILES) });
      }
      if (path === "/run") {
        if (request.method !== "POST") return json(env, request, { error: "Method not allowed" }, 405);
        if (!env.RUNPOD_API_KEY) return json(env, request, { error: "Server misconfigured" }, 500);
        let body;
        try {
          body = await request.json();
        } catch (err) {
          return json(env, request, { error: "Body must be JSON" }, 400);
        }
        const audio = body && body.audio_base64;
        if (typeof audio !== "string" || audio.length === 0) {
          return json(env, request, { error: "audio_base64 required" }, 400);
        }
        if (audio.length > MAX_ENCODED) return json(env, request, { error: "Encoded audio too large" }, 413);
        let head = "";
        try {
          head = atob(audio.slice(0, 44)).slice(0, 16);
        } catch (err) {
          return json(env, request, { error: "Invalid base64" }, 400);
        }
        if (head.slice(0, 4) !== "RIFF" || head.slice(8, 12) !== "WAVE" || head.slice(12, 16) !== "fmt ") {
          return json(env, request, { error: "Audio must be a WAV file" }, 400);
        }
        const profId = resolveProfile(body);
        if (!profId) return json(env, request, { error: "Unknown profile" }, 400);
        const prof = PROFILES[profId];
        const lang = prof.language;
        const epId = prof.endpointId;
        if (await rateLimited(env, request, "run")) {
          return json(env, request, { error: "Muitas solicitações. Aguarde alguns minutos." }, 429);
        }
        const upstream = await fetch(RUNPOD_BASE + epId + "/run", {
          method: "POST",
          headers: {
            "Authorization": "Bearer " + env.RUNPOD_API_KEY,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ input: { audio_base64: audio, language: lang } }),
        });
        if (!upstream.ok) return json(env, request, { error: "Upstream error " + upstream.status }, 502);
        const job = await upstream.json();
        if (!job.id) return json(env, request, { error: "Upstream returned no job id" }, 502);
        await persistRun(env, profId, job.id, audio);
        return json(env, request, { id: job.id, status: job.status });
      }

      const profStatusMatch = path.match(/^\/status\/([a-z][a-z0-9]{1,7})\/([A-Za-z0-9-]{8,64})$/);
      const statusMatch = path.match(/^\/status\/([A-Za-z0-9-]{8,64})$/);
      if (profStatusMatch) {
        if (request.method !== "GET") return json(env, request, { error: "Method not allowed" }, 405);
        const pid = profStatusMatch[1];
        if (await rateLimited(env, request, "status")) {
          return json(env, request, { error: "Muitas solicitações. Aguarde alguns minutos." }, 429);
        }
        if (!PROFILES[pid]) return json(env, request, { error: "Unknown profile" }, 400);
        return await statusUpstream(env, request, pid, profStatusMatch[2]);
      }
      if (statusMatch) {
        if (request.method !== "GET") return json(env, request, { error: "Method not allowed" }, 405);
        if (await rateLimited(env, request, "status")) {
          return json(env, request, { error: "Muitas solicitações. Aguarde alguns minutos." }, 429);
        }
        return await statusUpstream(env, request, DEFAULT_PROFILE, statusMatch[1]);
      }
      if (path === "/feedback") {
        if (request.method !== "POST") return json(env, request, { error: "Method not allowed" }, 405);
        if (!env.DB) return json(env, request, { error: "Server misconfigured" }, 500);
        const raw = await request.text();
        if (raw.length > 524288) return json(env, request, { error: "Feedback too large" }, 413);
        let body;
        try {
          body = JSON.parse(raw);
        } catch (err) {
          return json(env, request, { error: "Dados inválidos." }, 400);
        }
        if (!body || typeof body !== "object") return json(env, request, { error: "Dados inválidos." }, 400);
        const profId = resolveProfile(body);
        if (!profId) return json(env, request, { error: "Unknown profile" }, 400);
        const prof = PROFILES[profId];
        const verdict = body.verdict === "correct" ? "correct" : "correction";
        const isConfirm = verdict === "correct";
        if (typeof body.job_id !== "string" || !/^[A-Za-z0-9-]{8,64}$/.test(body.job_id)) {
          return json(env, request, { error: "Dados inválidos." }, 400);
        }
        if (typeof body.client_id !== "string" || body.client_id.length < 8 || body.client_id.length > 64) {
          return json(env, request, { error: "Dados inválidos." }, 400);
        }
        if (typeof body.transcript !== "string" || !body.transcript || body.transcript.length > 4000) {
          return json(env, request, { error: "Dados inválidos." }, 400);
        }
        if (await rateLimited(env, request, "feedback")) {
          return json(env, request, { error: "Muitas solicitações. Aguarde alguns minutos." }, 429);
        }
        if (isConfirm) {
          const stmt = "INSERT INTO feedback (client_id, job_id, model, language, profile, verdict, transcript, word_index, word_count, original, correction, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, '', '', strftime('%Y-%m-%dT%H:%M:%SZ','now'))";
          try {
            await env.DB.prepare(stmt)
              .bind(body.client_id, body.job_id, prof.model, prof.language, profId, verdict, body.transcript)
              .run();
            return json(env, request, { ok: true });
          } catch (err) {
            return insertFallback(env, request, body, profId, prof, verdict, err);
          }
        }
        const ix = body.word_indexes;
        if (!Array.isArray(ix) || !ix.length || ix.length > 1000) {
          return json(env, request, { error: "Dados inválidos." }, 400);
        }
        for (let k = 0; k < ix.length; k++) {
          if (!Number.isInteger(ix[k]) || ix[k] < 0 || ix[k] > 999) {
            return json(env, request, { error: "Dados inválidos." }, 400);
          }
          if (k > 0 && ix[k] !== ix[k - 1] + 1) {
            return json(env, request, { error: "Dados inválidos." }, 400);
          }
        }
        if (body.word_index !== ix[0]) return json(env, request, { error: "Dados inválidos." }, 400);
        const toks = body.transcript.split(/\s+/).filter(Boolean);
        if (ix[ix.length - 1] >= toks.length) return json(env, request, { error: "Dados inválidos." }, 400);
        if (typeof body.original !== "string" || body.original !== toks.slice(ix[0], ix[ix.length - 1] + 1).join(" ")) {
          return json(env, request, { error: "Dados inválidos." }, 400);
        }
        if (typeof body.correction !== "string" || !body.correction.trim() || body.correction.length > 200) {
          return json(env, request, { error: "Dados inválidos." }, 400);
        }
        if (body.correction.trim() === body.original) return json(env, request, { error: "Dados inválidos." }, 400);
        const stmt = "INSERT INTO feedback (client_id, job_id, model, language, profile, verdict, transcript, word_index, word_count, original, correction, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))";
        try {
          await env.DB.prepare(stmt)
            .bind(body.client_id, body.job_id, prof.model, prof.language, profId, verdict, body.transcript, ix[0], ix.length, body.original, body.correction.trim())
            .run();
          return json(env, request, { ok: true });
        } catch (err) {
          return insertFallback(env, request, body, profId, prof, verdict, err);
        }
      }

async function insertFallback(env, request, body, profId, prof, verdict, err) {
  const msg = String((err && err.message) || err);
  if (/UNIQUE/i.test(msg)) return json(env, request, { ok: true, duplicate: true });
  if (/no (?:such column|column named)/i.test(msg)) {
    return json(env, request, { error: "Server upgrading, try again." }, 503);
  }
  return json(env, request, { error: "Não foi possível salvar agora." }, 500);
}

      return json(env, request, { error: "Not found" }, 404);
    } catch (err) {
      return json(env, request, { error: "Upstream unreachable" }, 502);
    }
  },
};
