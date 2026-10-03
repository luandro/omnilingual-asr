# Matsés voice: project runbook

## Establish the contract

Read `deploy/matses-voice/README.md`, Worker source, TOML, schema and page
configuration together. Source currently names Worker `matses-asr-proxy`, D1
`matses-feedback` bound as `DB`, page `https://matses-voz.surge.sh`, and proxy
`https://matses-asr-proxy.mangadl.workers.dev`. Recheck deployed state; these are
source-derived discovery hints, not current remote verification. Use env vars
`WORKER_URL`, `ENDPOINT_ID`, `WORKER_ID`, `AUDIO_FILE` for runtime values.
Never print `.env`, keys, Authorization headers, audio or full transcripts.

Trace page → 16 kHz mono WAV/base64 → POST `/run` → GET `/status/{id}` →
transcript → POST `/feedback`. The Worker fixes `omniASR_LLM_7B_v2` and
`mcf_Latn`; preserve that boundary and Portuguese states/errors.

## Workers review

- GET `/health` reports constants; it checks neither D1 nor backend readiness.
- POST `/run` requires `audio_base64`, caps encoded length at 8,000,000 characters,
  sniffs RIFF/WAVE/fmt, and submits `{input:{audio_base64,language}}`. Header
  sniffing is not full WAV validation; Python owns decode. Preserve fixed
  upstream routing rather than accepting arbitrary endpoint/model/URL input.
- GET `/status/{id}` constrains job IDs and verifies completed output model.
  FAILED, CANCELLED and TIMED_OUT are terminal; never automatically resubmit
  paid jobs. Preserve mismatch handling and sanitized upstream failures.
- OPTIONS and errors must carry correct CORS; JSON is `Cache-Control: no-store`.
  Fixed-origin CORS restricts browsers, not arbitrary callers or billing abuse.
- Keep module `fetch(request, env)`, per-request secret access, parameterized SQL,
  awaited writes and sanitized errors. Keep credentials out of static HTML and
  request bodies out of logs; inference stays outside the Worker.
- D1 limits currently count per IP over ten minutes: run 10, feedback 20,
  status 60; old rate rows are removed after three days. Missing DB/query errors
  fail open. Test unavailable DB and thresholds: health can pass while spending
  protection silently disappears. workers.dev has no dashboard WAF-rule path
  used by this project; do not assume adding a rule protects this proxy.
- The source comment claiming nothing is persisted is stale: feedback stores
  text and rate limiting stores IPs. Audio is not persisted by this Worker.

## D1 semantics

Feedback requires valid job/client IDs, transcript, contiguous integer indexes,
matching original phrase/first index, and a nonempty changed correction. Storage
stamps model/language, UTC creation time and word count. `client_id` is UNIQUE:
a retry returns `{ok:true,duplicate:true}` without replacing the correction.
Client IDs must distinguish intended records. Test words, phrases, invalid
ranges, duplicates and DB errors through the real handler, not only the page mock.

`CREATE TABLE IF NOT EXISTS` does not upgrade existing tables. Inspect deployed
columns/indexes, including `word_count` and `rate_log`; use explicit migrations
and a verified recovery/export strategy for existing data. Do not recreate a DB
to repair its binding. Verify with aggregates/counts instead of dumping labels.
Curate feedback before training; collected labels do not prove speech accuracy.

## Wrangler and publication

Run in `deploy/matses-voice/worker/`. Use the lockfile and installed Wrangler;
check version/account before remote actions. OAuth or `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID` supply auth. The key belongs in Worker secret
`RUNPOD_API_KEY`, never a public variable. Existing secrets normally persist;
avoid unnecessary rotation. Local secrets belong in private dev configuration.

```sh
npx wrangler --version
npx wrangler whoami
npx wrangler d1 execute matses-feedback --local --file schema.sql
npx wrangler dev --config wrangler.toml
# Packaging only, not remote binding/inference proof.
npx wrangler deploy --config wrangler.toml --dry-run
```

Critical lesson: `cloudflare.config.ts` currently cannot express D1 in its
new-config format. `cf deploy` has stripped `env.DB`, causing feedback 500
"Server misconfigured" and bypassing DB limits. Use TOML with Wrangler. Revisit
only after installed schema support and a disposable binding-retention test.

When remote deployment is authorized, inspect the target account/database and
recoverable schema, apply only necessary migrations, and deploy:

```sh
# Initial provisioning only; this does not migrate existing columns.
npx wrangler d1 execute matses-feedback --remote --file schema.sql
npx wrangler deploy --config wrangler.toml
```

Explicit local/remote flags prevent confusing local success with production.
Check current flags against official [D1 commands](https://developers.cloudflare.com/d1/wrangler-commands/)
and [Wrangler commands](https://developers.cloudflare.com/workers/wrangler/commands/),
plus installed schema; library references may age.

After deploy verify live DB binding, health constants, CORS/invalid boundaries,
and an authorized synthetic feedback record with persisted count. Retry its ID
for deduplication. Dry run, uploaded code and health 200 do not prove persistence;
feedback success does not prove inference. Keep prior deployment/recovery info;
code rollback does not roll back D1 data.

Static page publishes separately through Surge, not Pages/Worker assets:
`npx surge page https://matses-voz.surge.sh` from `deploy/matses-voice/`, when
authorized. Verify baked proxy URL, HTTPS microphone access and localhost-only
query overrides. Do not publish as a side effect of documentation work.

## Runpod handoff

Read `deploy/README.md`, endpoint configs, handler, client and
`deploy/VERIFICATION.md`; historical results are not current readiness.
Management uses `https://api.runpod.io/v2/serverless` (POST create, GET
list/detail, PATCH update); catalog is
`/v2/catalog/gpus?include=AVAILABILITY&product=SERVERLESS`. Inference uses the
separate host `https://api.runpod.ai/v2/{endpoint}/run`, `/status/{job_id}`,
and health. Preserve Bearer auth and deployer's User-Agent (catalog previously
needed it); use catalog GPU pool IDs, not raw GPU device IDs.

`deploy/bootstrap.py` uses a public digest-pinned PyTorch base, pinned upstream
revision, encoded local handler, cold-start apt/pip installs and `pip check`.
Keep Torch/torchaudio/fairseq2/CUDA wheel compatibility together. Initialize the
model pipeline once per worker, not per request.

Before enabling any new image, verify registry manifest, intended architecture,
digest, anonymous pullability or configured auth, and actual worker startup.
A local tag/build or accepted endpoint config is not publication.
`IMAGE_AUTH_ERROR` calls for checking image existence/visibility, digest,
architecture and credentials first. The public pinned base resolved the earlier
unpublished-image failure without a large local upload. Avoid repeatedly creating
endpoints as troubleshooting.

True cold starts install/download on billable GPU time. FlashBoot can retain
initialized state/cache; it guarantees neither warmth nor free startup. Zero
minimum workers is not proof of zero charges; an idle/ready FlashBoot slot is
not an actively running worker. Inspect queue, health, active workers and billing.
Preserve worker/idle caps unless needed; choose cheapest live GPU quotes only
after VRAM and compatibility checks, with spending limits/alerts as appropriate.

Use bounded `python3 deploy/worker_logs.py "$ENDPOINT_ID" "$WORKER_ID"`
snapshots to distinguish image startup, installs, checkpoint download and ready
state. Avoid unbounded logs/repeated paid retries. For authorized paid smoke,
inspect `deploy/smoke.py` and `deploy/gradio_smoke.py` arguments, use known speech
with expected words, and poll the same job to terminal status. Verify model,
hint and intelligible text, then real proxy/page path. Silence, canned mocks,
English success and screenshots do not establish Matsés accuracy. Report
cold/warm timing and verified inference separately.
