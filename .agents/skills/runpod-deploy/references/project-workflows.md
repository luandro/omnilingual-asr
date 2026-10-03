# Project runbook

## Configuration that actually executes

- `deploy/bootstrap.py` overrides the template image with its public digest-pinned
  PyTorch base, installs dependencies and a pinned upstream revision on cold start,
  then executes local `deploy/handler.py` encoded as `ASR_HANDLER_B64`. Local
  library edits are not shipped through this route. Change the source revision
  or publish a tested custom image when library changes are required.
- `deploy/endpoint.json` selects CTC 1B, 30GB disk, AMPERE_16. Its custom-image
  tag is not publication evidence and is overridden by bootstrap.
  `deploy/endpoint-7b.json` selects LLM 7B, 100GB disk, AMPERE_24, and excludes
  a known incompatible Blackwell MIG type. Recheck actual GPU architecture and
  native ABI; a pool label or minCudaVersion alone is insufficient.
- Both templates use min 0, max 1, five-second idle timeout, and FlashBoot.
  Keep template, handler, client mapping, and result model identity consistent.
  CTC ignores language hints; LLM supports them. Do not silently replace models.
- `app.py` resolves `RUNPOD_ENDPOINT_ID` and `RUNPOD_ENDPOINT_ID_7B` with
  `deployment-state.json` fallback. `smoke.py` requires legacy `endpoint_id`;
  `smoke_7b.py` requires `endpoints["omniASR_LLM_7B_v2"]`. Bootstrap prints
  endpoint IDs but does not save state. Inspect resolvers before changing it.
- `deploy/control.py` reads root `.env` unconditionally, even with exported
  credentials. Provide that ignored file (it may be empty with an exported key).
  Its GET/create output can include endpoint env; inspect privately and redact
  before sharing. Review HTTP error bodies too. Do not print keys or encoded
  handler payloads; base64 is encoding, not secrecy.

## Release gates

1. Confirm target endpoint, model, required client features, spending authority,
   and queued/in-flight work. Existing authorization suffices; do not ask again.
   Remote inspection commands, when in scope:

   ```sh
   python3 deploy/control.py catalog
   python3 deploy/control.py get "$RUNPOD_ENDPOINT_ID"
   ```

2. Before enabling workers, require a completed manifest at the exact custom
   image tag/digest and a pull with the intended public/private access. Inspect
   architecture, native ABI, handler/assets, and secret exclusions. Local Docker
   login does not configure Runpod registry access. Partial pushes are not
   publication. For bootstrap, verify anonymous access to the pinned base and
   availability of pinned source/dependency URLs. Use the IMAGE_AUTH_ERROR
   diagnosis in `runpod.md` before assuming private-registry permissions.

3. Run unbilled checks in a prepared compatible environment:

   ```sh
   python3 -m unittest discover -s deploy -p 'test_bootstrap.py'
   python3 -m unittest discover -s deploy -p 'test_app.py'
   python3 -m unittest discover -s deploy -p 'test_language_map.py'
   ```

   Run `test_handler.py` separately with matching torch/torchaudio/fairseq2.
   Mock calls verify input boundaries, not GPU quality. Run native imports and
   `pip check` inside the intended runtime; a UI-only venv proves neither ABI
   compatibility nor GPU inference. Missing dependencies are blocked checks.

4. With deployment authorized, select one action and the exact template:

   ```sh
   python3 deploy/bootstrap.py create deploy/endpoint.json
   python3 deploy/bootstrap.py update "$RUNPOD_ENDPOINT_ID" deploy/endpoint.json
   python3 deploy/bootstrap.py update "$RUNPOD_ENDPOINT_ID_7B" deploy/endpoint-7b.json
   ```

   These are alternatives, not a batch. For a new 7B endpoint use
   `create deploy/endpoint-7b.json`. PATCH strips name/type. Read back actual
   configuration; compare management workers/version/staleness, queue health,
   and startup logs. Inspect one bounded log snapshot:

   ```sh
   python3 deploy/worker_logs.py "$RUNPOD_ENDPOINT_ID" "$WORKER_ID"
   ```

   SSE timeout is not worker failure. Distinguish stock/throttling from image
   pull, dependency installation, and ABI failures. Refer to `runpod.md` for
   stale-worker recovery; draining/restarting can interrupt production jobs.

5. Submit known speech only within paid-test authority and preserve the job ID:

   ```sh
   python3 deploy/smoke.py "$AUDIO_FIXTURE" 'fellow americans'
   python3 deploy/smoke_7b.py "$AUDIO_FIXTURE"
   python3 deploy/gradio_smoke.py "$AUDIO_FIXTURE" "$JOB_ID" 'fellow americans' --model omniASR_LLM_7B_v2 --language eng_Latn
   ```

   Choose tests for the intended model. The phrase/7B script assume the JFK
   English fixture; adapt expected words for other speech. Gradio smoke waits
   on the preceding API job then submits another paid job through localhost:7860.
   Verify result model/chunks, longer recordings, and requested-language quality.
   COMPLETED or nonempty text alone is insufficient. Resume polling the same ID
   after local timeout; do not automatically resubmit ambiguous failures.

6. Observe queue drain, active idle timeout, and scale-down. Separate observed
   lifecycle from configured limits and retained FlashBoot slots. Report actual
   model, current GPU rate, startup/install/download overhead, latency, client
   contract, and language-validation limits. Historical English evidence in
   `deploy/VERIFICATION.md` is not fresh release evidence or Matsés accuracy.
   Never widen spend or restart unrelated endpoints without task authority.

## API boundary

This repo uses bearer-auth JSON REST at `https://api.runpod.io/v2/serverless`
for management and `https://api.runpod.ai/v2/{endpoint_id}` for queue requests.
Preserve its User-Agent workaround and pool-based GPU configuration. `runpod.md`
lists catalog, PATCH, workers, SSE, health, and terminal-state patterns.
Do not interchange REST v1 `rest.runpod.io` payloads, GraphQL template fields,
or queue IDs. Refresh official schemas before introducing fields; provider CLIs
may use different versions than these helpers.

## Matsés voice production boundary

`deploy/matses-voice/` is a static page plus a live Cloudflare Worker, not another
GPU server. Read its README, `worker/wrangler.toml`, `worker/src/worker.js`,
`worker/schema.sql`, and `page/index.html` before changes. Worker name is
`matses-asr-proxy`; D1 binding `DB` points at `matses-feedback`. Derive current
endpoint/origin/page URL from source; do not copy old deployment IDs.

- Proxy pins LLM 7B and `mcf_Latn`, exposes `/run`, `/status/{id}`, `/health`,
  and `/feedback`, and checks completed result model identity. Keep
  `RUNPOD_API_KEY` in a Worker secret, never in page JavaScript or evidence.
- Preserve WAV/header and encoded-size validation, CORS, terminal failure
  handling, feedback bounds/contiguous indexes, prepared SQL, and deduplication.
  CORS is not authentication. D1 rate limits fail open on absent/broken DB;
  `/health` proves neither upstream inference nor D1 persistence.
- Feedback stores text corrections/transcripts/model stamps, not audio.
  Rate logs also store IP/time/kind: the source comment claiming nothing is
  persisted is not a privacy contract. Do not export community text or write
  production test feedback without authorization.
- Use `npx wrangler deploy --dry-run`, then authorized `npx wrangler deploy`
  from `deploy/matses-voice/worker/`. Do not use `cf deploy`: the recorded
  failure stripped D1 binding and made `/feedback` return 500. Wrangler restores
  the declared binding. Secret updates and remote schema application need task
  authority; never recreate the production database or reapply schema blindly.
- Test the proxy with mocked upstream and local/test D1. For the page, run
  `node deploy/matses-voice/test/mock-worker.mjs` (8999) and
  `python3 -m http.server 8000 --directory deploy/matses-voice/page` in managed
  sessions. Browse
  `http://127.0.0.1:8000/?worker=http://127.0.0.1:8999&maxSec=4&test=1`
  for feedback-only testing; omit test=1 for recording. Correction `FalhaRun`
  forces an error. Overrides work only on localhost. The mock does not verify
  deployed proxy code, D1 persistence, or speech quality.
- After an authorized release, check deployed routes and binding/secret presence
  without exposing values, authorized feedback persistence and duplicate handling,
  and HTTPS microphone access. Paid end-to-end recording is a separate check.
  Preserve the existing production URL, endpoint, and data unless asked otherwise.

## Unbilled map regression with browser-harness CDP

Read `deploy/MAP_VERIFICATION.md`, including the later navigation update;
`ui/` assets and `docs/superpowers/` plans provide design context. Old screenshots
and counts are historical evidence, not passing checks on changed code.

Start `python3 deploy/map_browser_fixture.py` in a managed session with the UI
dependencies and endpoint mappings required by `app.py`. It runs real UI with
fake external transport at localhost:7861. Keep it separate from the real
localhost:7860 service. Use installed browser-harness with local Chrome CDP:

```sh
browser-harness --doctor
browser-harness <<'PY'
from pathlib import Path
exec(compile(Path('deploy/check_map_navigation.py').read_text(),
             'deploy/check_map_navigation.py', 'exec'))
PY
```

Harness pre-imports `new_tab`, `wait_for_load`, `cdp`, `js`, and `click_at_xy`.
Initial navigation uses `new_tab(url)`. If debugging is disabled, have the user
enable it at `chrome://inspect/#remote-debugging` and accept Chrome's prompt,
then retry. No cloud browser or other installed browser skill is required.
Inspect accessibility nodes first; use DOM geometry/screenshots for canvas/SVG.

Verify wheel anchoring, drag/click suppression, moving pinch midpoint,
touchCancel recovery, fixed marker centers/sizes, full tooltip names/tokens,
1x–12x bounds, Reset preserving language, automatic detection clearing it,
view preservation across tabs, and unclipped controls at 390px/320px.
The navigation script covers many gestures but never submits inference.
Separately verify accent-insensitive Matsés search and keyboard `mcf_Latn`
selection, LLM payload preserving the token even with delayed callbacks, and
CTC payload dropping it. Check no geolocation/external tiles or browser key.
Mock payload tests, browser-emulated touch, physical hardware, and real speech
accuracy are distinct evidence. Stop only test sessions started for this task.
