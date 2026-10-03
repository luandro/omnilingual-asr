# Project workflow and operational contracts

Read only the section relevant to the task. Paths below start at the repository root. Source and live configuration outrank historical docs; inspect them before changing behavior. This reference supplies the essential runpod-deploy, cloudflare, wrangler, workers-best-practices, and agent-browser lessons without requiring those sibling skills.

## Choose the surface and trace the boundary

| Surface | Sources and evidence | Preserve |
|---|---|---|
| Gradio transcription | `app.py`, `deploy/test_app.py`, `requirements-ui.txt` | Small CTC default; Large LLM hint; public `/transcribe` API; server-side credentials |
| Language map | `language_map.py`, `ui/`, `scripts/build_language_catalog.py`, `deploy/test_language_map.py`, `deploy/MAP_VERIFICATION.md`, `docs/superpowers/` | Offline data, exact supported tokens, attribution, search for unplotted languages, selection/submission contract |
| Matsés voice | `deploy/matses-voice/page/index.html`, `worker/src/worker.js`, `worker/schema.sql`, `worker/wrangler.toml`, `test/mock-worker.mjs` within `deploy/matses-voice/` | Record → queue → poll → transcript → correction → restart; fixed model/language; secrets in Worker |
| Inference/deployment boundary | `deploy/handler.py`, `deploy/bootstrap.py`, `deploy/control.py`, endpoint JSON, `deployment-state.json`, `deploy/README.md`, `deploy/VERIFICATION.md` | Native dependency compatibility, model identity, chunking, queue states, billed work boundaries |

Read existing product/design context and relevant plan, then actual implementation. Do not apply React, Svelte, or bundler conventions to Gradio or the single static HTML page. Gradio HTML has its own styling/event lifecycle; preserve scoped CSS and `apply_default_css=False` where present. A Python-only edit can break client JS timing; inspect both sides.

## Map invariants

- Small uses `omniASR_CTC_1B_v2` and ignores hints. Large uses `omniASR_LLM_7B_v2` and accepts a token such as `mcf_Latn`. Selection alone must not submit audio or call Runpod.
- The visibly selected language must reach the submitted payload even when the Gradio selection callback is delayed. Exercise the synchronous client selection path as well as the Python callback. After selecting Matsés in Large, switching to Small must submit no hint. Automatic detection clears both visible and synchronous selection state.
- Accent-insensitive Matses/Matsés search and code search must find `mcf_Latn`. ArrowDown/Enter selects a result; search is the keyboard alternative to thousands of markers. Avoid making every marker a tab stop.
- Preserve exact supported-token coverage, including unmatched/missing-coordinate entries in search. Points represent language locations, not borders, speaker addresses, or recording sites. No geolocation or live tile/data requests. Keep `ui/provenance.json`, pinned sources, hashes, and attribution when regenerating assets; cosmetic changes do not justify regeneration.
- Current navigation supersedes the older geometry in `deploy/MAP_VERIFICATION.md`: stationary point centers and fixed screen-space sizes, pointer-transparent tooltip with full name/token, drag pan with click suppression, later deliberate click selection, wheel/trackpad anchored zoom, moving-midpoint pinch, 1x–12x bounds, and vertically stacked controls.
- Map Reset restores navigation and preserves language selection; automatic detection clears the hint. Preserve view across Small/Large tab switches. Resize must keep dots aligned with the stretched SVG/canvas coordinate transform. At 320px and 390px widths, check the 170px minimum map height, unclipped controls, and no page overflow. Test touchCancel recovery and the first Reset click after pinch.

## Browser regression: CDP and unbilled fixtures

Use an existing compatible UI environment; creating a venv/installing dependencies is setup work only when needed and authorized. From repo root, start the real UI with fake external transport:

```sh
.venv-ui/bin/python deploy/map_browser_fixture.py
```

Keep that process handle for cleanup; do not kill unrelated listeners. It serves port 7861, while the actual app normally serves 7860. The fixture replaces `app.requests` and prints submitted model/hint. Never use it as speech-accuracy evidence. Run the checked-in regression through the harness, not directly as ordinary Python:

```sh
browser-harness <<'PY'
from pathlib import Path
exec(compile(Path('deploy/check_map_navigation.py').read_text(),
             'deploy/check_map_navigation.py', 'exec'))
PY
```

For a manual check, the harness pre-imports helpers:

```sh
browser-harness <<'PY'
new_tab('http://127.0.0.1:7861')
wait_for_load()
print(page_info())
PY
```

First navigation uses `new_tab`, not `goto_url`. Prefer accessibility role/name discovery via `cdp('Accessibility.getFullAXTree')`, filter before printing, resolve `backendDOMNodeId` via `DOM.getBoxModel`, and click the viewport box center with `click_at_xy`. Use `js(...)` for targeted state/payload inspection or canvas/SVG details missing from AX. Inspect screenshots when geometry matters. Await visible state rather than relying solely on fixed sleeps. A DOM-triggered click alone does not validate gesture behavior.

If connection fails, run `browser-harness --doctor`; local Chrome needs remote debugging enabled and may require the user's Allow click. Do not substitute an unrequested cloud browser or paid session. Use existing `BU_CDP_URL` (HTTP DevTools endpoint), `BU_CDP_WS`, or `BU_NAME` when configured. If harness is unavailable, report the browser check blocked; static tests are useful but cannot replace it. No separate agent-browser installation is necessary.

Batch desktop/mobile checks plus mouse, keyboard, wheel, and emulated touch. Reproduce delayed selection before submitting, verify actual fixture model/hint, Reset vs automatic, tab changes, clipping, marker geometry, and cancellation. Browser-emulated touch is not physical-device testing. Check the real app's rendering separately without submitting a paid job.

For app/map changes, run focused tests in the compatible environment:

```sh
.venv-ui/bin/python -m pytest deploy/test_app.py deploy/test_language_map.py
```

Use `deploy/test_bootstrap.py` only for bootstrap changes; worker boundary tests in `deploy/test_handler.py` need compatible inference dependencies and mock model calls. Record environment-blocked checks as blocked. Existing Gradio asyncio ResourceWarnings do not establish a new defect or successful end-to-end inference. Avoid importing fairseq2/GPU dependencies into the offline catalog/UI path.

## Matsés page and production proxy

The page is plain HTML/JS, with no build step. It fixes Matsés `mcf_Latn` and LLM 7B, produces 16kHz mono WAV, caps recording at 180 seconds, and uses the existing Worker to keep `RUNPOD_API_KEY` out of client code. Preserve record permissions, denial recovery, visible loading/queue states, tappable transcript words, contiguous phrase correction, retry/error states, and restart. Use the existing Portuguese copy unless the brief requests another language; avoid invented accuracy claims.

For unbilled local checks, from `deploy/matses-voice/` run each server in a separately tracked process:

```sh
node test/mock-worker.mjs
python3 -m http.server 8000 --directory page
```

Open `http://127.0.0.1:8000/?worker=http://127.0.0.1:8999&maxSec=4` with browser-harness. Append `&test=1` for feedback-only dummy text. Correction `FalhaRun` forces an error response. These overrides work only on localhost; do not enable them in production. Microphone capture requires a secure context: localhost for development, HTTPS for production. Test denied permission, double taps, slow polling, terminal failures, correction errors, duplicate feedback, and restart. Mock feedback does not prove D1 persistence.

The production Worker is named `matses-asr-proxy`; resolve its URL from page configuration and its D1 identity from `worker/wrangler.toml`, rather than copying account IDs into instructions. CORS currently permits the deployed Surge page origin. CORS restricts browsers, not arbitrary callers; do not describe it as authentication. The `/health` response confirms code/model/language metadata, not Runpod readiness, secret presence, or D1 binding.

Proxy contracts to preserve:

- `/run` validates body, encoded size, and WAV header, then submits one upstream job with the fixed language. `/status/:id` polls that job and rejects a COMPLETED result whose model identity mismatches. Terminal FAILED/CANCELLED/TIMED_OUT jobs are not automatically resubmitted.
- `/feedback` validates job/client IDs, transcript, contiguous word indexes and matching original text, and a nonempty changed correction. Use parameterized D1 statements. Preserve `client_id` uniqueness/idempotency: duplicate feedback returns success without another row. The proxy stamps model/language; do not trust arbitrary browser values.
- Feedback persists transcript/correction text, not audio. `rate_log` also stores client IP, request kind, and time; its current cleanup window is three days. The source's old “nothing persisted” comment is not the actual privacy contract. Do not log credentials, raw audio, or arbitrary request bodies.
- D1-backed rate limits cover run, feedback, and status. Missing DB or D1 errors fail open for limiting; feedback with missing DB returns 500. Do not claim a hard spending cap. A workers.dev route cannot use dashboard WAF rules as a replacement for these code limits.

Deployment workflow, only when authorized:

1. Inspect `worker/package.json`, lockfile, `wrangler.toml`, source, and schema. Use the locked project CLI. From the Worker directory, `npx wrangler deploy --dry-run` checks packaging without publishing; distinguish this from live deployment.
2. Deploy with `npx wrangler deploy` to preserve `[[d1_databases]]` and `DB`. The verified `cf deploy` path strips this binding; `/feedback` then fails with “Server misconfigured”. Do not use it for this Worker until the binding capability is independently proven. An already-authorized repair uses Wrangler and then rechecks the binding/feedback path.
3. Secret changes use `npx wrangler secret put RUNPOD_API_KEY`, never literal keys in arguments, browser code, reports, or tracked files. Existing secrets persist across deployments; redeploying does not require rotating them.
4. Schema application is a separate remote write: `npx wrangler d1 execute matses-feedback --remote --file schema.sql` from the Worker directory. Inspect current schema first: CREATE TABLE IF NOT EXISTS does not migrate existing columns. Use local D1 for development; do not alter production schema merely for UI verification.
5. Confirm the deployed version, route, origin, secret binding presence without reading its value, and `DB` binding. An authorized controlled feedback write plus a narrowly scoped D1 read can verify persistence/idempotency; do not insert synthetic training labels without authorization. Check the UI against the deployed Worker separately from publishing the page.
6. Page publication uses the existing Surge workflow, `npx surge page <authorized-page-url>` from `deploy/matses-voice/`. It does not deploy the Worker. Preserve HTTPS and the configured allowed origin.

A real `/run` is billable GPU work. Prefer mocks during design. Spending alerts/limits and endpoint max-worker/idle settings are operational controls, not UI side effects. Disabling the workers.dev route is an emergency action only within the user's authorized scope.

## Runpod boundary: management v2, startup, and publication

Use repo helpers and configuration as the concrete contract; verify provider docs when changing API behavior. `deploy/control.py` loads `.env` without printing its credential; some responses may include endpoint environment fields, so redact management output before sharing. Do not read or print the credential file to discover configuration.

- Management uses `https://api.runpod.io`: GPU catalog GET `/v2/catalog/gpus?include=AVAILABILITY&product=SERVERLESS`, list/create `/v2/serverless`, get/PATCH `/v2/serverless/<endpoint-id>`. Use Bearer `RUNPOD_API_KEY`, JSON Content-Type, and the helper's User-Agent; catalog access previously required that User-Agent. Pool IDs, not raw GPU IDs, select serverless hardware.
- Job execution is a different host: `https://api.runpod.ai/v2/<endpoint-id>/run`, then `/status/<job-id>`. Do not mix management and execution URLs or replace these REST patterns with old GraphQL template assumptions.
- `deploy/bootstrap.py create [CONFIG_PATH]` constructs a new deployment; `update ENDPOINT_ID [CONFIG_PATH]` PATCHes one, omitting name/type. The 7B template is `deploy/endpoint-7b.json`. Inspect selected model, endpoint mapping, GPU pool/exclusions, disk, workers, idle timeout, and FlashBoot before mutation. A UI task does not authorize either command.
- Bootstrap deliberately uses a public digest-pinned PyTorch runtime and a pinned upstream revision, embeds the handler in `ASR_HANDLER_B64`, and installs dependencies on true cold start. Preserve compatible PyTorch/torchaudio CUDA wheels and fairseq2 native ABI; the current pins are in bootstrap, not an instruction to silently upgrade. `pip check` is necessary but cannot prove CUDA/native loading or model correctness.
- `IMAGE_AUTH_ERROR` is an image-pull/publication/access problem, not evidence of bad model code. Confirm repository/tag/digest exists, intended architecture is available, and anonymous pulling succeeds for a public image. A local build or push command starting is not publication evidence. For a private image, configure credentials only through the authorized provider mechanism.
- Before enabling or repointing an endpoint to a baked image, confirm the remote manifest/digest and pull access from a clean context, then validate container startup/handler registration. Never point production at the unpublished optional Docker Hub image. The existing bootstrap route avoids that publication dependency.
- True cold starts perform apt/pip installs and checkpoint downloads before serving. Initialization and idle timeout cost worker time; zero minimum workers avoids always-on compute but does not make startup free. FlashBoot can retain initialized state/cache and reduce later startup work; it does not guarantee warm requests or durable storage. Do not claim warm execution timings measure cold start. Avoid attached network volumes or worker increases as incidental design fixes.
- Worker logs use `/v2/serverless/<endpoint-id>/workers/<worker-id>/logs`, container source and bounded tail/stream. `deploy/worker_logs.py` takes endpoint and worker IDs and redacts the key. Bound log collection and polling; use observed job/worker IDs, not invented management subcommands.
- Ambiguous submission timeouts can already have queued work. Poll a known job ID rather than automatically submitting again. Stop on terminal failures and report useful recovery without an automatic paid retry loop.

For authorized real smoke tests, inspect `deploy/smoke.py`, `deploy/smoke_7b.py`, and `deploy/gradio_smoke.py` for their current arguments. Use a known speech fixture and expected words, verify actual returned model and chunk count, then the real Gradio callback. A successful status with wrong text is failure: the smaller 300M model was rejected despite COMPLETED jobs. Historical English checks in `deploy/VERIFICATION.md` prove those fixtures at that time, not current deployment health or Matsés accuracy.

The handler splits audio into 30-second chunks and does not provide word timestamps; boundaries may split words. Keep client input limits distinct from the Worker's encoded cap and handler duration cap. Never promise private/on-device inference: audio is sent to Runpod even though the UI/server keeps credentials private. Recheck price, GPU availability, endpoint state, and billing controls live when needed; do not present old quoted prices as current.

## Finish evidence

State the changed surface and user-visible result, relevant test/fixture/browser evidence, and outstanding limits. Separate local rendering, mock transport contracts, production binding/persistence, live model transcription, and physical-device behavior. Preserve existing operational records; update only evidence actually obtained. No deployment, cloud writes, or paid inference is required to improve the skill itself.
