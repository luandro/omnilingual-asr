# Browser regression

Use browser-harness CDP; no sibling skill is required. Read
`deploy/MAP_VERIFICATION.md` and relevant `docs/superpowers/` plans. Historical
results provide contracts to rerun, not current proof. Use the compatible existing
UI Python (often `.venv-ui/bin/python`); do not casually upgrade fairseq2/CUDA.

## Language map

Start `deploy/map_browser_fixture.py` as a separate managed process. It serves
real UI with fake inference on 7861; real Gradio normally runs on 7860. Verify
the fixture responds without replacing/restarting the user's app. From repo root:

```sh
browser-harness <<'PY'
from pathlib import Path
exec(compile(Path('deploy/check_map_navigation.py').read_text(),
             'deploy/check_map_navigation.py', 'exec'))
PY
```

The navigation script submits no audio. Fixture payload checks are unbilled mocks,
not speech validation. Check Matsés/Matses search → `mcf_Latn`, ArrowDown/Enter,
LLM model/hint payload, synchronous selection despite delayed callback, and
automatic reset to null. CTC hides map and sends no hint after LLM selection.
Tab switches preserve view; Map Reset preserves selection, automatic clears it.

Rerun hover stationary center/full name/token, fixed marker size, wheel pointer
anchoring, drag/click suppression then deliberate selection, pinch ratio/moving
midpoint, touchCancel, 1x–12x bounds, first Reset after pinch, resize, right-side
vertical controls and 390px/320px overflow/clipping. Inspect screenshots plus
DOM geometry; emulated touch is not physical-device evidence. Search provides
keyboard access; thousands of dots must not become thousands of tab stops.
Preserve `ui/provenance.json`, supported-token coverage, pinned input/hash checks
when regenerating. Selection must not invoke inference, geolocation, external
map tiles or expose credentials.

## Voice page

From `deploy/matses-voice/`, run `node test/mock-worker.mjs` and a separate
`python3 -m http.server 8000 --directory page`. Open
`http://127.0.0.1:8000/?worker=http://127.0.0.1:8999&maxSec=4`;
append `&test=1` for feedback without mic. Correction `FalhaRun` forces a 500.
Overrides are localhost-only; verify they cannot activate in production.

Exercise record/stop, WAV upload, loading, completed/empty transcript, terminal
failure without resubmission, word/phrase correction, duplicate retry, save
failure, restart and stale async responses. Check Portuguese states, focus,
mobile layout and HTTPS mic permissions. Mock success does not test the real
Worker/D1/Runpod. Production transcription costs money; synthetic feedback
writes also require authorized task scope.

## CDP mechanics and reporting

```sh
browser-harness --doctor
browser-harness <<'PY'
new_tab("http://127.0.0.1:7861")
wait_for_load()
print(page_info())
PY
```

First navigation uses `new_tab`. Attach through default local daemon or
`BU_CDP_URL` (HTTP DevTools endpoint)/`BU_CDP_WS`. Named remote daemons require
matching `BU_NAME` for every call. Chrome must allow remote debugging; obtain
user interaction for its permission popup and retry if blocked. Do not start a
paid cloud browser for routine local regression.

Filter `cdp("Accessibility.getFullAXTree")["nodes"]` by role/name, get visible
center via `DOM.getBoxModel`, and `click_at_xy`. Use targeted `js(...)` state/
geometry and screenshots for canvas/SVG missing from AX. Avoid full AX dumps.
After navigation `wait_for_load`; stale/internal tabs use `ensure_real_tab`.
Raw CDP provides mouse/touch and viewport emulation. Restore overrides and stop
only test processes started for the task. A blocked check is unverified, not pass.

Report local mocks, actual browser, live bindings/persistence, paid inference and
physical hardware separately, with tested artifact/source identity when available.
