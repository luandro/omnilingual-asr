# Project workflows and operational lessons

## Source map

| Surface | Read | Verify |
| --- | --- | --- |
| Proxy | deploy/matses-voice/worker/src/worker.js, wrangler.toml | Workers runtime, actual bindings |
| D1 | deploy/matses-voice/worker/schema.sql | Insert/readback, duplicates, migration |
| Voice page | deploy/matses-voice/page/index.html | Mock + CDP, then authorized HTTPS flow |
| GPU | deploy/bootstrap.py, control.py, endpoint*.json, handler.py | Boundary tests, worker logs, real speech |
| Gradio/map | app.py, ui/, docs/superpowers/ | Fixture CDP, app/map tests |

Read deploy/matses-voice/README.md, deploy/README.md, deploy/VERIFICATION.md and
deploy/MAP_VERIFICATION.md. Source/live state supersede dated reports. Resolve
endpoint IDs from current configuration; do not copy old IDs/prices into changes.

## Cloudflare proxy and D1

Production Worker: matses-asr-proxy at
https://matses-asr-proxy.mangadl.workers.dev; page origin:
https://matses-voz.surge.sh. Confirm these in source before use. Proxy fixes model
omniASR_LLM_7B_v2 and language mcf_Latn; do not accept arbitrary browser endpoint,
model or upstream URL overrides.

Preserve/test these contracts:

- OPTIONS preflight; GET /health returns model/language. Health does not test DB,
  secret presence or inference. Wrong methods return 405; unknown paths 404.
- POST /run accepts WAV base64, cap 8,000,000 encoded characters, RIFF/WAVE/fmt
  header checks, and returns job ID. Header checks are not complete decoding.
  Test invalid JSON/base64, wrong audio, oversize, missing secret, upstream error,
  malformed response and absent ID. Bound bytes during ingestion: Content-Length
  alone and current post-buffer checks do not prevent excessive allocation.
- GET /status/:id restricts ID format; COMPLETED requires matching model. Preserve
  FAILED/CANCELLED/TIMED_OUT, polling and stale-response/restart behavior. Review
  job-result access separately from CORS; knowledge of an ID is not user auth.
- POST /feedback validates IDs, transcript, contiguous word indexes, original
  phrase matching tokens, and nonempty changed correction. Await prepared insert.
  Duplicate client_id succeeds with duplicate:true: submission idempotency, not
  user identity. Test phrases, invalid indexes, duplicates, missing DB, DB error.
  Review forged-label risk; validation alone does not prove job ownership.
- feedback stores text/model/language, never audio. rate_log stores IP/kind/time;
  pruning removes entries older than three days during checks. Limits per ten
  minutes: run 10, feedback 20, status 60. Errors fail open. workers.dev did not
  support the dashboard WAF route used for this case; do not assume WAF protection.

Local page checks, separate terminals from repo root:

```sh
node --check deploy/matses-voice/worker/src/worker.js
node deploy/matses-voice/test/mock-worker.mjs
python3 -m http.server 8000 --directory deploy/matses-voice/page
```

Browser-harness URL:
http://127.0.0.1:8000/?worker=http://127.0.0.1:8999&maxSec=4
Add &test=1 for dummy transcript/feedback without mic. Correction FalhaRun forces
an error. Overrides only work on localhost. Mock tests page behavior, not DB.
Recording caps at 180s, 16kHz mono WAV. Test record/upload, restart, terminal errors
without resubmission, correction retry/duplicate handling, mobile layout, focus
and labels, and safe rendering of untrusted transcript text.

For actual Worker/D1, from deploy/matses-voice/worker:

```sh
npx wrangler --version
npx wrangler d1 execute matses-feedback --local --file schema.sql
npx wrangler dev
npx wrangler deploy --dry-run
```

Check installed CLI help/schema before changing flags. No existing npm test script
or TS project is assumed. Add targeted runtime tests for proxy/DB changes; Node
mock is insufficient. Workers Vitest can auto-inject nodejs_compat, concealing a
production mismatch. Use local synthetic rows, not community feedback.

When production deployment is authorized, npx wrangler deploy uses wrangler.toml
and binding DB for matses-feedback. cloudflare.config.ts/new-config could not
express D1 in the recorded version: cf deploy stripped DB and /feedback returned
500 Server misconfigured. Restore with Wrangler if this recurs. A newer CLI
requires schema and actual-binding proof before changing this route. Existing
secrets persist; set/rotate via npx wrangler secret put RUNPOD_API_KEY.

Remote schema application is a separate data change. CREATE TABLE IF NOT EXISTS
does not migrate existing tables; test explicit column/uniqueness/index migrations
locally and preserve labels. Never run --remote or publish merely for a review.
After authorized publish verify actual DB/secret bindings, CORS/error paths and a
designated synthetic feedback insert/readback: health alone misses missing DB.
Real /run incurs GPU charges. Static publication is separate: from
deploy/matses-voice, npx surge page https://matses-voz.surge.sh. HTTPS is required
for microphone. Do not export private feedback as diagnostic output.

## Runpod deployment and inference boundary

Management REST host: https://api.runpod.io, POST/GET /v2/serverless,
GET/PATCH /v2/serverless/{id}. Inference host is different:
https://api.runpod.ai/v2/{endpoint}/run and /status/{job}. Preserve bearer auth,
JSON requests and control.py User-Agent; catalog previously needed that header.
Catalog: /v2/catalog/gpus?include=AVAILABILITY&product=SERVERLESS. Use serverless
pool IDs, not raw GPU IDs; refresh stock/prices. control.py currently reads repo
.env even if environment credentials exist; account for this without printing it.

bootstrap.py is the active public digest-pinned PyTorch route with pinned upstream
revision, startup apt/pip installs, pip check and embedded local handler via
ASR_HANDLER_B64. PATCH removes name/type. Use endpoint-7b.json for 7B changes;
do not unintentionally change CTC. Preserve compatible PyTorch/torchaudio 2.8.0,
CUDA 12.6, fairseq2 0.6.0 unless deliberately upgrading with native-import and
real inference verification. 7B needs more disk/24GB pool; recorded Blackwell MIG
exclusion reflects compatibility, not merely capacity.

IMAGE_AUTH_ERROR came from an unpublished image. Before enabling/switching any
endpoint, verify exact manifest/digest publication, anonymous pull for public
images (or correct private registry credentials), compatible architecture and
worker startup. Local build/tag is not publication. Optional baked images require
push/access checks first; the current public-base bootstrap avoids huge uploads.

True cold starts install dependencies/download checkpoints (7B was about 29GiB).
Initialization and idle timeout are billed worker time. FlashBoot can retain an
initialized worker/cache, not guarantee warmth, persistence or free startup.
Keep min 0/max 1 workers and short idle timeout unless authorized otherwise; no
network volume is assumed. Separate queue/startup delay from execution time.
Old latency/price observations are not promises. Spending alerts and caps need
current verification; CORS and fail-open rate limiting cannot ensure a cost cap.

Use deploy/worker_logs.py ENDPOINT_ID WORKER_ID for bounded redacted snapshots.
Inspect install/native import/checkpoint/ready state without dumping env payloads.
Check final queues/workers after smokes. Recover known job IDs rather than retrying
ambiguous submissions. Boundary tests in a compatible runtime:

```sh
python3 -m unittest discover -s deploy -p 'test_*.py'
```

Missing native dependencies/incompatible runtime means blocked verification.
Trace app/proxy/handler routing: CTC ignores hints; LLM passes one per 30s chunk.
Check stereo downmix, 16kHz conversion, invalid base64, duration and model identity.

Only for authorized billed checks use deploy/smoke.py, smoke_7b.py and
deploy/gradio_smoke.py, consulting their current CLI.
Assert known spoken phrase and actual model for short/multichunk audio, then real
Gradio callback. COMPLETED/nonempty text is insufficient: 300M CTC failed English
in both deployed/reference inference despite successful status. English evidence
is not Matsés accuracy; use target-language speech and human review. Chunks can
split words; there are no word timestamps. Gradio defaults localhost; LAN access
is an explicit HOST/SERVER_NAME choice. Selection must never submit paid jobs.

## Browser-harness CDP and map regression

Use browser-harness for browser work, including visual/accessibility review.
This workflow needs no sibling impeccable/agent-browser skill. Start fixture:

```sh
.venv-ui/bin/python deploy/map_browser_fixture.py
```

It serves fake inference on localhost:7861. Then from repo root:

```sh
browser-harness <<'PY'
from pathlib import Path
exec(compile(Path('deploy/check_map_navigation.py').read_text(),
             'deploy/check_map_navigation.py', 'exec'))
PY
```

Use local CDP. browser-harness --doctor diagnoses connection failures; browser
remote-debugging consent may be required. Report that prerequisite if blocked.
First navigation new_tab(url), then wait_for_load(). Inspect filtered accessibility
nodes for controls; js(...) for canvas/SVG geometry; CDP input for gestures;
screenshots for desktop/mobile. DOM assertions alone do not prove alignment.

Follow deploy/MAP_VERIFICATION.md including its superseding navigation update:
hover full name/token, pointer-anchored wheel, fixed marker centers/size, pan and
click suppression followed by deliberate selection, moving-midpoint pinch,
touchCancel recovery, 1x–12x bounds, vertical controls, Reset preserving selection,
resize and tab view preservation. Check 390px/320px no overflow/clipped controls;
narrow-map minimum height 170px. Keyboard search avoids thousands of marker tab
stops. Test accent-insensitive Matsés, ArrowDown/Enter, automatic reset and delayed
selection submission: synchronous payload must match visible token. CTC hides map
and sends no stale hint; LLM sends selected token. Selection causes no external
inference request. Fixture evidence is not speech accuracy or live API proof;
emulated touch is not physical-device verification.

Preserve searchable unplotted tokens, licenses, pinned catalog/SVG sources/hashes
and coverage in ui/provenance.json. No geolocation/runtime tiles/data fetch for
styling. Consult docs/superpowers plans but verify current implementation. Stop
only temporary processes created by the task, preserving unrelated servers.
