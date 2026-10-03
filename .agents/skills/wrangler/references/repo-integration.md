# Runpod and browser integration checks

## GPU deployment boundary

Read `deploy/README.md`, `deploy/bootstrap.py`, `deploy/control.py`, endpoint templates, `deploy/worker_logs.py`, and `deployment-state.json` without reading or printing credentials. Historical evidence in `deploy/VERIFICATION.md` is fixture-specific, not current endpoint health or general language accuracy.

- Management REST uses `https://api.runpod.io/v2/serverless` (POST create, GET list/detail, PATCH update). The existing bootstrap update drops immutable `name` and `type`. GPU catalog uses `/v2/catalog/gpus?include=AVAILABILITY&product=SERVERLESS`; keep the helper's User-Agent, which matters for catalog access. Reuse existing endpoints rather than creating another billed deployment on every retry.
- Inference is a different host: `https://api.runpod.ai/v2/<endpoint>/run`, then `/status/<job>`. Both use bearer credentials server-side. Do not confuse management v2 field shapes with older GraphQL or inference input JSON. Inspect current helper/template and official Runpod documentation before changing API fields.
- `deploy/bootstrap.py` uses a public digest-pinned PyTorch base, installs dependencies on cold start, and embeds `deploy/handler.py` into endpoint environment. Preserve the pinned upstream revision and compatible PyTorch/torchaudio 2.8.0 CUDA 12.6 / fairseq2 0.6.0 combination unless the task calls for an upgrade. Do not switch it to the optional Dockerfile image by accident.
- `IMAGE_AUTH_ERROR` requires checking image existence, registry publication, anonymous access for a public image, and exact tag/digest/platform before enabling workers. A built local image or successful endpoint-create response is not publication evidence. For private images verify the configured registry credential separately without exposing it. Check worker startup logs after correcting access; repeated inference submissions do not fix an inaccessible image.
- A true cold start bills dependency installation, checkpoint download, model loading, inference, and idle timeout. Zero minimum workers avoids an always-on GPU; it does not make startup free. FlashBoot can retain initialized/cache state but does not guarantee warm starts or replace persistent storage. An idle/ready FlashBoot slot is not proof of a continuously running worker. Inspect live worker/queue counts and logs; do not claim readiness from endpoint health constants.
- Keep minimum/maximum workers, GPU compatibility, disk, timeout, and network-volume costs deliberate. The documented LLM template uses zero minimum/one maximum, a five-second idle timeout, and excludes incompatible Blackwell MIG. Verify live settings and prices before spending claims. Do not raise capacity to fix a startup failure.

For an authorized update from repo root: `python3 deploy/bootstrap.py update "$RUNPOD_ENDPOINT_ID"`; for LLM pass `deploy/endpoint-7b.json` as the final argument using the intended LLM endpoint ID. Creation and update mutate live state. Avoid dumping complete management responses, which can include endpoint environment and embedded code. Use the bootstrap's selected-field output and sanitized logs.

For authorized billed smoke checks, use `deploy/smoke.py` for direct API and `deploy/gradio_smoke.py` for the real UI path, following `deploy/README.md` arguments. Verify expected speech and returned model, not merely nonempty text or HTTP 200. CTC ignores language hints; LLM passes them. Poll the existing job through queue/startup with a bounded timeout; never automatically resubmit an ambiguous timed-out POST or terminal failure. English fixture success does not establish Matsés accuracy. GPU-dependent checks blocked by runtime incompatibility are neither pass nor inference failure.

## Unbilled map regression through CDP

Read `deploy/MAP_VERIFICATION.md`; its navigation update supersedes the earlier button-only zoom description. Source paths are `app.py`, `language_map.py`, `ui/`, and design plans under `docs/superpowers/`. Keep provenance, supported-token coverage, attribution and coordinates pinned; do not relabel representative points as language boundaries or recording locations.

Use browser-harness for repo browser interactions. This workflow is self-contained and does not require loading agent-browser or another UI skill. Start the real Gradio interface with fake external transport from repo root, using the UI-compatible Python environment:

```sh
.venv-ui/bin/python deploy/map_browser_fixture.py
# Separate terminal, from the same repository root:
browser-harness <<'PYCODE'
from pathlib import Path
exec(compile(Path('deploy/check_map_navigation.py').read_text(),
             'deploy/check_map_navigation.py', 'exec'))
PYCODE
```

The fixture is localhost:7861; the normal app is localhost:7860. Do not accidentally test paid inference on the normal port. If `.venv-ui` is unavailable, choose a compatible environment from `requirements-ui.txt`; do not silently install GPU dependencies for browser-only checks.

Browser-harness attaches through CDP to the running browser. For a connection problem run `browser-harness --doctor`; local Chrome may require enabling remote debugging and accepting its permission prompt. Use `new_tab(url)` for first navigation, then `wait_for_load()`. Prefer the accessibility tree and coordinate interactions; canvas geometry needs targeted JS/DOM inspection or screenshots. Use `BU_CDP_URL`/`BU_CDP_WS` only when needed for the configured endpoint. Avoid a paid cloud browser unless authorized; close task-started processes and sessions when finished without disrupting existing ones.

Verify the real caller and submitted payload, not just selected text:

- Search Matsés/accent-insensitive Matses and keyboard ArrowDown/Enter selects exact `mcf_Latn`; unplotted languages stay searchable. Markers remain outside the tab order.
- LLM submit reads synchronous selected token even if the selection callback is delayed; CTC submit uses its own model and no hint after LLM selection. Automatic detection clears the hint; map Reset preserves selection.
- Hover names/tokens, fixed-size dots, anchored wheel and moving-midpoint pinch, drag click suppression, deliberate later click, touchCancel recovery, 1x–12x bounds, resize and tab-switch preservation.
- At 390px and 320px, no horizontal overflow and all stacked controls fit. Inspect desktop/mobile screenshots for visual changes. Browser-emulated touch does not establish physical-device behavior.

Run relevant existing contracts (`deploy/test_language_map.py`, `deploy/test_app.py` when present, and the tests documented in MAP_VERIFICATION.md) using the compatible environment. The fixture validates callbacks and UI, not ASR speech accuracy. Report current checks separately from dated verification records; a browser connection failure is an unverified check. UI-only tasks do not require changing Runpod endpoints, Worker secrets, or submitting real jobs.
