---
name: wrangler
description: Operate and verify Cloudflare Wrangler for omnilingual-asr, especially the production Matsés voice Worker proxy and D1 feedback storage. Use for Worker configuration, local development, secrets, deployment, logs, database changes, and rollback.
---

# Wrangler for omnilingual-asr

This skill is standalone. Commands below start at the repository root unless a `cd` is shown. Repository files describe intended configuration; verify live state before calling it current. Loading this skill does not authorize deployments, remote database writes, paid inference, or dependency upgrades. Continue within the user's existing authorization without adding redundant approval gates.

## Start with the actual deployment

Read `deploy/matses-voice/README.md`, `deploy/matses-voice/worker/wrangler.toml`, `worker/src/worker.js` under that directory, and `worker/schema.sql`. Inspect `worker/package.json` and its lockfile for the installed CLI. The static page is `deploy/matses-voice/page/index.html`; it has no build step. Python/fairseq2 inference runs on Runpod, not in the Worker.

The checked-in production target is `matses-asr-proxy`, D1 database `matses-feedback`, binding `DB`, and secret `RUNPOD_API_KEY`. The page uses `https://matses-asr-proxy.mangadl.workers.dev`; its allowed browser origin is `https://matses-voz.surge.sh`. Read those constants again before deploying; do not duplicate deployment IDs in new tooling.

**Use Wrangler with the existing TOML configuration.** This repo records that `cf deploy` with `cloudflare.config.ts` strips D1: `/feedback` then returns 500 `Server misconfigured`. Restore the binding through an authorized Wrangler deploy. Do not migrate to JSONC, remove the database ID, introduce environments, or bump compatibility dates merely to follow generic advice. A new environment needs its own explicit bindings and secrets; adding its name alone does not isolate data.

```sh
cd deploy/matses-voice/worker
npx --no-install wrangler --version
npx --no-install wrangler whoami
npx --no-install wrangler deploy --dry-run
```

Use the locked project-local Wrangler, not a global binary or an implicit latest download. If installation is needed and allowed, `npm ci` in this directory preserves the lockfile. Check `--help`, the installed `node_modules/wrangler/config-schema.json`, and [official Wrangler docs](https://developers.cloudflare.com/workers/wrangler/) for changing flags/config fields. Prefer Wrangler over hand-built Cloudflare API requests. The [general CLI reference](references/cli-reference.md) preserves additional service guidance; read it only for the service involved.

## Local Worker and D1 verification

From `deploy/matses-voice/worker`:

```sh
npx --no-install wrangler d1 execute matses-feedback --local --file schema.sql
npx --no-install wrangler dev --local
```

Use an ignored `.dev.vars` for local secrets, never a real credential in examples, command arguments, output, browser code, or committed files. Inspect for `remote: true` before treating local dev as isolated. Avoid submitting valid audio to a locally running proxy with a real Runpod key unless paid inference is in scope. `/health` only reports constants; it does not verify the secret, database, GPU readiness, or transcription.

Trace and check these boundaries when changing the Worker:

- `/run`: POST JSON `audio_base64`, nonempty and at most 8,000,000 encoded characters; WAV header gate; upstream `{input: {audio_base64, language: "mcf_Latn"}}`. This header check does not validate the whole WAV; inference validates audio downstream.
- `/status/<job>`: GET with the existing job-ID constraint; forward queue states, surface `FAILED`, `CANCELLED`, `TIMED_OUT`, and require completed output model `omniASR_LLM_7B_v2`. No automatic resubmission after terminal failure or ambiguous submission timeout.
- `/feedback`: validate contiguous `word_indexes`, matching first `word_index`, original phrase against transcript tokens, correction limits, and immutable server-side model/language stamps. Parameterized SQL and UNIQUE `client_id` make retries idempotent: duplicates return success without another row.
- `feedback` stores transcript/corrections, no audio. `rate_log` separately persists client IP/kind/timestamp; do not claim the Worker stores no client data. Current limits per ten minutes are run 10, feedback 20, status 60. D1 rate-limit failures fail open; missing DB breaks feedback but can leave paid `/run` traffic working.
- CORS emits the fixed allowed origin; it is browser policy, not authentication or an abuse barrier for direct HTTP callers. Preserve method checks, size limits, safe error responses, and `Cache-Control: no-store`; avoid logging audio, text corrections, credentials, or upstream bodies containing private data.

For browser UX use the mock from `deploy/matses-voice`:

```sh
node test/mock-worker.mjs
# Separate terminal:
python3 -m http.server 8000 --directory page
```

Open `http://127.0.0.1:8000/?worker=http://127.0.0.1:8999&maxSec=4`; add `&test=1` for feedback without microphone use. `FalhaRun` forces the mock error path. Overrides work only on localhost. This mock checks page behavior, not the actual Worker, D1 binding, or inference. Exercise actual Worker handlers with isolated/local D1 or an upstream stub when those contracts change; do not add a new test framework merely for a docs/config edit.

## Database changes and release

Always specify `--local` or `--remote` for D1 commands. Confirm account, Worker, database ID, and environment from configuration first. The repo currently uses `schema.sql`, not a migrations directory. `CREATE TABLE IF NOT EXISTS` does not add columns to existing tables. For schema evolution, inspect the existing schema and use deliberate migrations; test on local data and keep the previous Worker compatible during rollout. Never overwrite feedback data to make a schema test pass.

Before an authorized production schema change, inspect schema read-only and establish a backup/recovery plan. Export only when necessary to a protected, ignored destination: it contains community text and rate-log IPs. Consult [D1 commands](https://developers.cloudflare.com/workers/wrangler/commands/d1/) and [migrations](https://developers.cloudflare.com/d1/reference/migrations/) for the installed CLI. Use the existing database; automatic provisioning can silently create an empty replacement.

After local verification and dry-run, an authorized release uses:

```sh
# From deploy/matses-voice/worker; this immediately changes live traffic.
npx --no-install wrangler deploy
npx --no-install wrangler versions list
npx --no-install wrangler tail matses-asr-proxy --format json
```

Bound log collection and stop its process after verification. Secret values persist across ordinary deploys; inspect secret names with `wrangler secret list`, never values. Set `RUNPOD_API_KEY` with the interactive `wrangler secret put RUNPOD_API_KEY` prompt or protected file input, never echo or shell tracing. Do not deploy with unset/replacement credentials just to satisfy a health check.

Verify the deployed URL, version, expected bindings and origin, GET `/health`, OPTIONS, and safe invalid-input cases. Production feedback acceptance needs an explicitly authorized, labeled test correction with a unique `client_id`, a duplicate retry, and a narrowly scoped D1 read confirming one stored row with the correct stamps. `/health` alone can pass when DB is absent. Keep test labels distinguishable from community training labels; do not silently delete production rows. Use a real audio smoke only when billed inference is authorized.

Page publication is separate (`npx surge page https://matses-voz.surge.sh` from `deploy/matses-voice`); Wrangler deployment does not update it. Verify HTTPS microphone access, page Worker URL, CORS, queue/loading states, corrections, and restart. Record deployed version and observed results separately from local/mocked checks. `wrangler rollback <VERSION_ID>` restores Worker code subject to platform constraints; it does not undo D1 writes or schema changes. Evaluate compatibility before rollback.

## Adjacent Runpod and map work

When proxy changes affect GPU endpoints, smoke tests, cold starts, or map selection, read [repo integration checks](references/repo-integration.md). It includes the management-v2 versus inference-v2 distinction, image-publication failure recovery, billing/FlashBoot limits, and unbilled browser-harness CDP regression. These checks are included here so another skill need not be loaded.
