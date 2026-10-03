---
name: agent-browser
description: Verify and debug omnilingual-asr browser interfaces with browser-harness CDP. Use for Gradio language-map gestures, accessibility, responsive layout, model/language payload regressions, and the Matsés voice recording and feedback UI. Includes local unbilled fixtures and production proxy verification boundaries.
---

# agent-browser — omnilingual-asr

Use this skill for `app.py`, `language_map.py`, `ui/`, and
`deploy/matses-voice/`. It is a standalone project workflow; no other skill or
CLI-generated skill text is required. Commands below run from the repository
root unless a `cd` is shown. Read `references/operations.md` when verification
crosses Runpod, Cloudflare, D1, or publication boundaries.

## 1. Choose the verification boundary

- Map behavior: real Gradio callbacks with fake inference on localhost:7861.
- Voice UX: static page plus local mock Worker; microphone requires localhost
  or HTTPS. Fake transcripts verify interaction, never ASR accuracy.
- Production: inspect the configured URL and worker health first. Real audio
  submission creates a paid GPU job; feedback writes persistent text to D1.
  Use them only within the task's authorization. UI-only work needs neither.

Read `deploy/MAP_VERIFICATION.md`, including its later navigation update, and
relevant `docs/superpowers/` plans before changing map behavior. Those reports
are historical evidence, not proof of the current files or production state.

## 2. Attach through browser-harness

```sh
browser-harness --doctor
browser-harness <<'PY'
new_tab("http://127.0.0.1:7861")
wait_for_load()
print(page_info())
PY
```

`browser-harness` preimports helpers and ensures its daemon. First navigation
uses `new_tab`, subsequent navigation can use `goto_url`; use `ensure_real_tab()`
for stale/internal tabs. Default daemon attaches to local Chrome/Chromium CDP.
`BU_CDP_URL` supplies an HTTP DevTools endpoint resolved to WebSocket;
`BU_CDP_WS` supplies a WebSocket endpoint. Do not invent browser/profile IDs.
If local Chrome is disconnected, run diagnostics and enable remote debugging
at `chrome://inspect/#remote-debugging`; user interaction is required for the
browser's Allow prompt. Retry the failed command; do not delete profiles.

Prefer accessible role/name discovery, coordinate clicks, and targeted state
checks. Filter the accessibility tree before printing it:

```sh
browser-harness <<'PY'
nodes = cdp("Accessibility.getFullAXTree")["nodes"]
tab = next(n for n in nodes
           if n.get("role", {}).get("value") == "tab"
           and n.get("name", {}).get("value", "").startswith("Large"))
cdp("DOM.scrollIntoViewIfNeeded", backendNodeId=tab["backendDOMNodeId"])
q = cdp("DOM.getBoxModel", backendNodeId=tab["backendDOMNodeId"])["model"]["content"]
click_at_xy(sum(q[0::2])/4, sum(q[1::2])/4)
print(js("document.querySelector('#language-map-control .language-map')?.dataset.selectedToken"))
PY
```

Recompute geometry after scroll, zoom, resize, or rerender. Negative/offscreen
coordinates require scrolling first. CDP target order differs from visible tab
order; omnibox popups are not work tabs. Coordinate events traverse iframe and
shadow boundaries; DOM inspection helps canvas/SVG widgets where AX is sparse.
Use raw `cdp("Domain.method", ...)` for wheel, touch, keyboard, and viewport
emulation. Inspect screenshots for layout; DOM assertions alone miss clipping.

## 3. Run the map regression

In a separate terminal, use the existing compatible UI environment:

```sh
.venv-ui/bin/python -u deploy/map_browser_fixture.py
```

The fixture binds localhost:7861, replaces external transport, and prints
`fixture_submission` model/language evidence. It must remain test-only. Verify
that port 7861 belongs to this fixture before submitting test audio. Never
point the fixture or fake credentials at production.

```sh
browser-harness <<'PY'
from pathlib import Path
exec(compile(Path('deploy/check_map_navigation.py').read_text(),
             'deploy/check_map_navigation.py', 'exec'))
PY
```

The navigation script submits no audio. It covers stationary hover/name/token,
fixed screen-space marker size, pointer-anchored wheel zoom, drag pan, suppressed
drag-release selection, later deliberate clicks, pinch distance ratio, 1x–12x
bounds, right-side vertical controls, visible keyboard focus, Reset preserving
selection, hidden-tab view preservation, resize, and unclipped controls/no
horizontal overflow at 390px and 320px. Add moving-midpoint pinch and touchCancel
recovery checks for touch changes. CDP-emulated touch is not physical-device
verification.

For selection or submission changes, additionally exercise:

- Search `Matsés`, accent-insensitive `Matses`, and `mcf`; ArrowDown/Enter selects
  exact `mcf_Latn`. Search retains supported languages without map locations.
- Submit fixture audio in Large: model `omniASR_LLM_7B_v2`, hint `mcf_Latn`.
  Delay the selection callback by 20 seconds and submit immediately: the
  synchronous selected token must still reach the payload.
- Switch to Small after selection: `omniASR_CTC_1B_v2`, no hint, map hidden.
- Automatic detection clears both visible and synchronous state and sends null;
  map Reset preserves language. Compatibility `/transcribe` retains its model
  and hint contract. Tab changes must not reuse a stale model/hint.

Map points are representative locations, not boundaries or recording sites.
Preserve attribution/provenance and supported tokens; runtime map interaction
needs no geolocation or external tiles. Preserve keyboard search rather than
adding thousands of marker tab stops. Selection alone must not invoke inference.
Do not restore obsolete 2:1 narrow-map geometry: the navigation update requires
170px minimum height and aligned SVG stretch. Inspect actual rendered Gradio
styles, target sizes, focus, contrast, loading/error text, and pointer-transparent
tooltips. Test the real UI after fixture checks without submitting paid work.

## 4. Run the Matsés voice regression

Start each service in its own terminal and track the processes created:

```sh
node deploy/matses-voice/test/mock-worker.mjs
```

```sh
python3 -m http.server 8000 --directory deploy/matses-voice/page
```

Open through `new_tab`:
`http://127.0.0.1:8000/?worker=http://127.0.0.1:8999&maxSec=4`.
Append `&test=1` for dummy-transcript feedback without microphone use. These
query overrides work only on localhost. Inspect `page/index.html` and the mock
before assuming other test hooks.

Check record/stop, loading/polling, transcript word/phrase selection, correction
submit, retry after failure, and restart state. Correction `FalhaRun` forces a
mock 500. Check disabled/double-submit behavior, error copy, mobile fit, keyboard
focus, and transcript/correction rendering with punctuation and accented text.
Terminal failed jobs must not automatically resubmit. Test microphone capture
separately from feedback-only mode; distinguish permission denial, no device,
and successful capture. The app caps recordings at 180 seconds and uploads
16kHz mono WAV under the handler's 8 MB encoded cap.

## 5. Record evidence and clean up

Report target URL, fixture/live boundary, viewport, actions/assertions,
model/hint evidence when exercised, console/network errors, screenshot findings,
and remaining gaps. Distinguish implemented, static-tested, browser-tested,
real inference-tested, and physical-device-tested. Old reports, HTTP 200,
healthy proxy, mocked output, and screenshots do not establish speech accuracy
or remote worker readiness. Run relevant existing app/map tests in a compatible
runtime; record blocked checks honestly. Do not invent passing results.

Stop only fixture/mock processes and tabs created for this task; restore CDP
viewport/touch overrides. Keep keys, audio, transcripts, and unrelated tabs out
of screenshots and logs. Use available signed-in SSO where unambiguous; ask for
passwords, MFA, consent, or ambiguous account choice. Do not send messages or
modify accounts merely because browser control is available.

## Optional agent-browser CLI and remote sessions

If explicitly requested, inspect the installed version with
`agent-browser skills get core` (`--full` for command reference). It offers AX
`@eN` refs, sessions, auth state, video, and specialized electron/dogfood/
derive-client/vercel-sandbox/agentcore workflows; load version-matched help for
those tasks. Do not assume refs survive navigation. Installation is optional,
not a prerequisite for this project workflow. Its observability dashboard uses
port 4848; remain on the dashboard origin, which proxies session traffic.

For authorized isolated cloud browsers, authenticate with
`browser-harness auth login`, or pipe `$BROWSER_USE_API_KEY` to
`browser-harness auth login --api-key-stdin`. Start with
`start_remote_daemon("task-browser")` and use `BU_NAME=task-browser` on every
subsequent harness invocation. Cloud browsers bill until stopped/time out;
agree on lifecycle and stop with `stop_remote_daemon("task-browser")` when done.
Do not switch accidentally back to the local default daemon. Domain skills are
off by default; if `BH_DOMAIN_SKILLS=1`, read matching files under
`$BH_AGENT_WORKSPACE/domain-skills/` before site-specific interaction. Optional
helper additions belong in `$BH_AGENT_WORKSPACE/agent_helpers.py` when the task
allows that location. Connection help: https://github.com/browser-use/browser-harness/blob/main/install.md;
mechanic references: https://github.com/browser-use/browser-harness/tree/main/interaction-skills.
