# Browser checks at deployment boundaries

These are repository contracts, not promises that a live service currently
matches them. Inspect current configuration and authorized deployment scope.
Browser checks alone cannot prove GPU initialization, upstream identity, or D1
persistence. Keep credentials in environment variables/secret bindings.

## Runpod

Read `deploy/bootstrap.py`, `deploy/control.py`, `deploy/worker_logs.py`,
`deploy/README.md`, and `deploy/VERIFICATION.md`. Bootstrap uses a public
digest-pinned PyTorch base and embeds the current handler, installing packages
and fetching pinned upstream code at true cold start. Check the exact
PyTorch/torchaudio, fairseq2, CUDA wheels, upstream revision, model card, GPU
pool VRAM, disk, and timeout together. `pip check` does not prove GPU inference.

Management uses `https://api.runpod.io`: REST v2 `POST /v2/serverless` creates;
`PATCH /v2/serverless/{endpoint_id}` updates. The bootstrap update removes
`name` and `type`. Use the nested `gpu`, `workers`, `scaling`, and `env` fields
from current repo config, not unrelated GraphQL or legacy API examples. The
control helper sends Bearer `$RUNPOD_API_KEY`, JSON, and a User-Agent; catalog
queries previously required that User-Agent. GPU pool IDs differ from raw GPU
IDs. Do not print keys or full secret-bearing configuration.

Inference is a separate host: `https://api.runpod.ai/v2/{endpoint_id}`. Submit
`/run`, retain the job ID, and poll `/status/{job_id}` to a terminal result;
reserve `/runsync` for short jobs. Timeout/in-queue does not justify duplicate
submission. Inspect worker logs and exact returned model identity, not only a
job ID or endpoint creation response. Use the repo smoke scripts only when
paid inference is authorized; inspect their inputs/configuration first.

`IMAGE_AUTH_ERROR` occurs before handler execution: check registry visibility,
digest existence, pull authorization, and endpoint image configuration before
changing Python. Before enabling workers or exposing a new endpoint, verify
that its image is actually published and pullable by the worker environment,
with the intended digest/platform. A successful local build, tag, config edit,
or image name does not prove publication. Bootstrap's public pinned base avoids
an unpublished/private custom-image dependency; still verify its availability.
Do not enable endpoints against an image that has not passed publication checks.

Scale-to-zero (`workers.min=0`) avoids continuously warm workers, not cold-start
charges. Dependency installs, checkpoint downloads, initialization, and active
workers consume billed time. FlashBoot may retain initialized state and reduce
subsequent startup latency; it does not bake dependencies into the image,
guarantee a warm worker, or eliminate true cold starts. Recheck present limits,
idle timeout, rates, and spending controls rather than quoting historical cost.
Bound worker counts and test jobs, capture cold/warm timing separately, and stop
polling at a documented terminal/deadline condition. Never claim Matsés accuracy
from an English smoke test or fixture transcript.

## Cloudflare proxy and D1

Read `deploy/matses-voice/README.md`, `worker/src/worker.js`,
`worker/wrangler.toml`, `worker/schema.sql`, and `page/index.html` under
`deploy/matses-voice/`. The production Worker is `matses-asr-proxy`; the page's
configured worker URL and allowed production origin are the source of truth.
The proxy locks `omniASR_LLM_7B_v2` and `mcf_Latn`, keeps `RUNPOD_API_KEY` in a
Worker secret, and binds D1 as `DB` to `matses-feedback`.

Use Wrangler from `deploy/matses-voice/worker/` for an authorized deployment:
`npx wrangler deploy`. The repo documents that `cf deploy` strips the D1 binding,
causing `/feedback` to return 500; restore with Wrangler and verify bindings.
Do not infer that `cloudflare.config.ts` replaces `wrangler.toml` safely.
Set secrets via Wrangler's secret input, never static HTML, committed files,
query strings, browser storage, or printed command arguments. Remote schema
application and production feedback tests are writes; do not run them for a
browser-only task. Local mock success does not verify a remote schema/binding.

Verify `/health` model/language, CORS/preflight for the page origin, method/input
rejections, upload cap and WAV header handling, `/run` job ID, terminal
`/status/{id}` handling, upstream model mismatch rejection, and clear error
states. CORS controls browser reads; it is not caller authentication or a
complete spending guard. Do not proxy arbitrary upstream endpoints or expose
upstream credentials. Preserve no-store response behavior and input validation.

Feedback is text correction storage: transcript, selected word span, original,
correction, model/language stamp, and metadata. Verify server validation and
parameter-bound D1 inserts. Audio is not persisted. The source's introductory
"nothing persisted" comment is not an accurate description of feedback or
`rate_log`: D1 stores feedback and IP-based rate records. Rate limits include
run, feedback, and status, and fail open if D1 fails; a healthy `/health` alone
proves neither abuse controls nor feedback writes. workers.dev cannot rely on
dashboard WAF rules as a substitute for these code controls.

For an authorized release, verify remote DB binding/schema, retained secret,
worker health and origin behavior before publishing the static page; inspect
its baked URL before `npx surge` publication. HTTPS is required for microphone
capture outside localhost. Verify the published page as served, then distinguish
UI, feedback persistence, and real transcription evidence. Do not add audio or
full transcript logging to debug production failures. Use synthetic text for
explicitly authorized persistence tests; do not read community feedback merely
to confirm a deployment.
