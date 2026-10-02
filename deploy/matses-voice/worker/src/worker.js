// Proxy for the private RunPod omniASR_LLM_7B_v2 endpoint used by the Matsés page.
// The RunPod API key never leaves this Worker. It is bound as the RUNPOD_API_KEY
// secret and used only for upstream calls. Nothing is logged or persisted.
const RUNPOD_BASE = "https://api.runpod.ai/v2/";
const ENDPOINT_ID = "6kxhw59ss9q9ze";
const MODEL = "omniASR_LLM_7B_v2";
const LANGUAGE = "mcf_Latn";
const MAX_ENCODED = 8000000;

const ALLOWED_ORIGIN = "https://matses-voz.surge.sh";

function corsHeaders() {
  const allow = ALLOWED_ORIGIN;
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

function json(env, data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders(), "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

function bare(env, status) {
  return new Response(null, { status, headers: corsHeaders() });
}

const RATE = { run: 10, feedback: 20, status: 60, windowMs: 10 * 60 * 1000 };

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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    try {
      if (request.method === "OPTIONS") return bare(env, 204);
      if (path === "/health") {
        if (request.method !== "GET") return json(env, { error: "Method not allowed" }, 405);
        return json(env, { ok: true, model: MODEL, language: LANGUAGE });
      }
      if (path === "/run") {
        if (request.method !== "POST") return json(env, { error: "Method not allowed" }, 405);
        if (!env.RUNPOD_API_KEY) return json(env, { error: "Server misconfigured" }, 500);
        let body;
        try {
          body = await request.json();
        } catch (err) {
          return json(env, { error: "Body must be JSON" }, 400);
        }
        const audio = body && body.audio_base64;
        if (typeof audio !== "string" || audio.length === 0) {
          return json(env, { error: "audio_base64 required" }, 400);
        }
        if (audio.length > MAX_ENCODED) return json(env, { error: "Encoded audio too large" }, 413);
        let head = "";
        try {
          head = atob(audio.slice(0, 44)).slice(0, 16);
        } catch (err) {
          return json(env, { error: "Invalid base64" }, 400);
        }
        if (head.slice(0, 4) !== "RIFF" || head.slice(8, 12) !== "WAVE" || head.slice(12, 16) !== "fmt ") {
          return json(env, { error: "Audio must be a WAV file" }, 400);
        }
        if (await rateLimited(env, request, "run")) {
          return json(env, { error: "Muitas solicitações. Aguarde alguns minutos." }, 429);
        }
        const upstream = await fetch(RUNPOD_BASE + ENDPOINT_ID + "/run", {
          method: "POST",
          headers: {
            "Authorization": "Bearer " + env.RUNPOD_API_KEY,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ input: { audio_base64: audio, language: LANGUAGE } }),
        });
        if (!upstream.ok) return json(env, { error: "Upstream error " + upstream.status }, 502);
        const job = await upstream.json();
        if (!job.id) return json(env, { error: "Upstream returned no job id" }, 502);
        return json(env, { id: job.id, status: job.status });
      }

      const statusMatch = path.match(/^\/status\/([A-Za-z0-9-]{8,64})$/);
      if (statusMatch) {
        if (request.method !== "GET") return json(env, { error: "Method not allowed" }, 405);
        if (await rateLimited(env, request, "status")) {
          return json(env, { error: "Muitas solicitações. Aguarde alguns minutos." }, 429);
        }
        const upstream = await fetch(RUNPOD_BASE + ENDPOINT_ID + "/status/" + statusMatch[1], {
          headers: { "Authorization": "Bearer " + env.RUNPOD_API_KEY },
        });
        if (!upstream.ok) return json(env, { error: "Upstream error " + upstream.status }, 502);
        const job = await upstream.json();
        const jobStatus = job.status;
        if (jobStatus === "COMPLETED") {
          const output = job.output || {};
          if (output.model !== MODEL) {
            return json(env, { status: "FAILED", error: "Model identity mismatch" });
          }
          return json(env, { status: "COMPLETED", text: output.text === undefined ? "" : output.text });
        }
        if (["FAILED", "CANCELLED", "TIMED_OUT"].includes(jobStatus)) {
          return json(env, { status: jobStatus, error: job.error || jobStatus });
        }
        return json(env, { status: jobStatus });
      }
      if (path === "/feedback") {
        if (request.method !== "POST") return json(env, { error: "Method not allowed" }, 405);
        if (!env.DB) return json(env, { error: "Server misconfigured" }, 500);
        const raw = await request.text();
        if (raw.length > 524288) return json(env, { error: "Feedback too large" }, 413);
        let body;
        try {
          body = JSON.parse(raw);
        } catch (err) {
          return json(env, { error: "Dados inválidos." }, 400);
        }
        if (!body || typeof body !== "object") return json(env, { error: "Dados inválidos." }, 400);
        if (typeof body.job_id !== "string" || !/^[A-Za-z0-9-]{8,64}$/.test(body.job_id)) {
          return json(env, { error: "Dados inválidos." }, 400);
        }
        if (typeof body.client_id !== "string" || body.client_id.length < 8 || body.client_id.length > 64) {
          return json(env, { error: "Dados inválidos." }, 400);
        }
        if (typeof body.transcript !== "string" || !body.transcript || body.transcript.length > 4000) {
          return json(env, { error: "Dados inválidos." }, 400);
        }
        const ix = body.word_indexes;
        if (!Array.isArray(ix) || !ix.length || ix.length > 1000) {
          return json(env, { error: "Dados inválidos." }, 400);
        }
        for (let k = 0; k < ix.length; k++) {
          if (!Number.isInteger(ix[k]) || ix[k] < 0 || ix[k] > 999) {
            return json(env, { error: "Dados inválidos." }, 400);
          }
          if (k > 0 && ix[k] !== ix[k - 1] + 1) {
            return json(env, { error: "Dados inválidos." }, 400);
          }
        }
        if (body.word_index !== ix[0]) return json(env, { error: "Dados inválidos." }, 400);
        const toks = body.transcript.split(/\s+/).filter(Boolean);
        if (ix[ix.length - 1] >= toks.length) return json(env, { error: "Dados inválidos." }, 400);
        if (typeof body.original !== "string" || body.original !== toks.slice(ix[0], ix[ix.length - 1] + 1).join(" ")) {
          return json(env, { error: "Dados inválidos." }, 400);
        }
        if (typeof body.correction !== "string" || !body.correction.trim() || body.correction.length > 200) {
          return json(env, { error: "Dados inválidos." }, 400);
        }
        if (body.correction.trim() === body.original) return json(env, { error: "Dados inválidos." }, 400);
        if (await rateLimited(env, request, "feedback")) {
          return json(env, { error: "Muitas solicitações. Aguarde alguns minutos." }, 429);
        }
        const stmt = "INSERT INTO feedback (client_id, job_id, model, language, transcript, word_index, word_count, original, correction, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))";
        try {
          await env.DB.prepare(stmt)
            .bind(body.client_id, body.job_id, MODEL, LANGUAGE, body.transcript, ix[0], ix.length, body.original, body.correction.trim())
            .run();
          return json(env, { ok: true });
        } catch (err) {
          const msg = String((err && err.message) || err);
          if (/UNIQUE/i.test(msg)) return json(env, { ok: true, duplicate: true });
          return json(env, { error: "Não foi possível salvar agora." }, 500);
        }
      }
      return json(env, { error: "Not found" }, 404);
    } catch (err) {
      return json(env, { error: "Upstream unreachable" }, 502);
    }
  },
};
