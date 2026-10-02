# Matsés voice page

One static page + one Cloudflare Worker proxy. Page is locked to Matsés
(`mcf_Latn`) and model `omniASR_LLM_7B_v2` on the existing RunPod serverless
endpoint. UX: big record button, loading state, transcript as tappable words,
correction feedback, restart button.

Layout:

```
worker/   Cloudflare Worker proxy (RUNPOD_API_KEY secret + D1 database binding)
page/     index.html — the whole app, no build step
test/     mock-worker.mjs — local stand-in for the Worker
plan/     design docs and multi-model review records
```

## Deploy the Worker

Two CLIs work. **Use wrangler**: it is the only one that can attach the D1
binding today.

```sh
cd worker
npx wrangler deploy          # uses wrangler.toml ([[d1_databases]] binding=DB)
```

Auth: one-time `npx wrangler login` (browser OAuth). The RUNPOD_API_KEY secret
persists across deploys; set once with
`npx wrangler secret put RUNPOD_API_KEY` or a `--secrets-file` on the cf CLI.

**cf CLI (`cf deploy`) also works for code-only changes**, and is verified to
STRIP the D1 binding (new-config format cannot express `d1`/`bindings` yet —
wrangler 4.146's schema rejects the key). After any `cf deploy`, `/feedback`
returns 500 "Server misconfigured"; restore with `npx wrangler deploy`. Do not
use `cf deploy` on this worker until cf/wrangler new-config grows D1 support.

D1: database `matses-feedback` (schema in `worker/schema.sql`, applied with
`npx wrangler d1 execute matses-feedback --remote --file schema.sql -y`).

CORS is locked to `https://matses-voz.surge.sh` (constant in
`worker/src/worker.js`).

## Rate limiting (built in)

The worker rate-limits `/run` (10 per 10 min) and `/feedback` (20 per 10 min)
per client IP using the D1 `rate_log` table; failures fail open. A workers.dev
subdomain cannot take dashboard WAF rules, which is why this lives in code.
Tune limits in `worker/src/worker.js` (`RATE`).

## RunPod spending guard (dashboard, do once)

1. runpod.io → Settings → Billing → set a **spending limit / alert**.
2. Endpoint `6kxhw59ss9q9ze` already caps at 1 max worker + 5s idle timeout.
3. Optional: Cloudflare dashboard → Workers → matses-asr-proxy → disable the
   workers.dev route in an abuse emergency (kills all traffic instantly).

## Point the page at the Worker

`page/index.html` bakes:

```js
const CONFIG_WORKER_URL = "https://matses-asr-proxy.mangadl.workers.dev";
```

## Deploy the page

```sh
npx surge page https://matses-voz.surge.sh
```

HTTPS is required for microphone access; surge serves HTTPS.

## Test locally

```sh
node test/mock-worker.mjs &                     # mock API on 127.0.0.1:8999
python3 -m http.server 8000 --directory page    # page on 127.0.0.1:8000
```

- Full record flow: open
  `http://127.0.0.1:8000/?worker=http://127.0.0.1:8999&maxSec=4`
- Feedback only (skips mic, dummy transcript): append `&test=1`
- Correction `FalhaRun` forces a 500 to test the error state.
- `?worker=` and `?test=1` only work on localhost.

## Pull training labels

```sh
cd worker
npx wrangler d1 execute matses-feedback --remote \
  --command "SELECT original, correction, COUNT(*) n FROM feedback GROUP BY 1,2 ORDER BY n DESC"
```

## Notes

- Recording caps at 180s; 16kHz mono WAV uploads stay under the handler's
  8 MB base64 cap (~187s max).
- First job after idle can take minutes (endpoint has zero min workers).
- Terminal job failures are never resubmitted automatically.
- Feedback stores text only (transcript + corrections + model stamp); audio is
  never persisted. Labels are word/phrase-level text corrections — curate
  before training.
