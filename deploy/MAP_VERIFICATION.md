# Language-map verification — 2026-09-29

The actual local app runs at `http://127.0.0.1:7860`. Small CTC is the default;
the Large LLM tab exposes the map. Runpod endpoints, workers, model cards, and
credentials were not changed by this UI task.

## Data and regeneration

Glottolog 5.3 CLDF commit:
`072ca0d0410039fb8b779be8fc165bac575d2cda`, CC BY 4.0.
Natural Earth commit: `ca96624a56bd078437bca8184e78163e5039ad19`, public domain.
Full input URLs, hashes, attribution, retrieval date, and coverage:
[`ui/provenance.json`](../ui/provenance.json).

Catalog SHA-256:
`7ecde01559860603e568fb73b42e41803564d2ea3c23516a73f43897bac29e4d`.
Independent regeneration from the pinned inputs reproduced both catalog and
SVG outline byte for byte. Catalog covers exactly 1,672 supported tokens:
1,635 plotted, 36 unmatched names/joins, one additional missing location.
Search preserves every supported token, including those not plotted.

## Browser evidence

Browser-harness connected to local headless Chrome. The real interface and
callback code were exercised on the test-only port 7861 with external inference
replaced by `deploy/map_browser_fixture.py`. This does not test speech accuracy.

| Check | Observed result |
| --- | --- |
| Named search | Matsés/mcf search yields `mcf_Latn`; accent-insensitive `Matses` works |
| Keyboard selection | ArrowDown then Enter selects the Matsés result |
| Point selection | Clicking Icelandic point selects `isl_Latn` |
| LLM payload | Browser submission after Matsés selection sends model `omniASR_LLM_7B_v2` and hint `mcf_Latn` |
| CTC tab/payload | Map hidden; submission uses `omniASR_CTC_1B_v2` with no language hint, despite prior LLM selection |
| Automatic reset | Selection event supplies null; synchronous selected-token value clears |
| Delayed selection regression | Before fix, delaying map callback submission by 20 seconds produced hint None despite visible Matsés; after fix, same delay produces hint `mcf_Latn` |
| Gradio HTML styling | Default HTML styles disabled; inactive point geometry is 11px circular, selected marker highlighted |
| Zoom | Shared layer scales 1.5x around selected point; inverse point scale keeps settled inactive marker width 11px |
| Mobile geometry | 390px viewport has no horizontal overflow; map dimensions 302x151 preserve 2:1 alignment |
| Compatibility API | Real Gradio client `/transcribe(audio, LLM_MODEL, eng_Latn)` reaches fake external transport with exact model/hint |
| Live app configuration | Both native tabs and public transcription API present; actual API key absent from config |

Screenshots were inspected at desktop and mobile sizes. Search/list remains the
keyboard alternative; map markers use `tabindex=-1` to avoid 1,635 tab stops.
The UI does not request geolocation or fetch external map tiles/data at runtime.
Map selection alone invokes only the local selection callback, not inference.

## Automated checks

- 8 client/UI contract tests pass.
- 8 catalog/map/JavaScript contract tests pass, including synchronous submission
  selection behavior evaluated in Node and marker keyboard-order markup.
- 1 bootstrap configuration test passes.
- 4 worker boundary tests pass in the compatible runtime, with model calls mocked.
- 5 original repository tests pass in a temporary compatible runtime container.
- Compilation, dependency consistency, and `git diff --check` pass.

Gradio UI-construction tests still emit non-failing asyncio ResourceWarning
notices. No new real Runpod inference jobs were submitted during these UI checks.
Earlier real English transcription evidence remains in [VERIFICATION.md](VERIFICATION.md).
The new interface is not evidence of Matsés or other language transcription accuracy.

## Navigation update — 2026-09-30

This section supersedes the original button-only zoom behavior above.
Dots keep a stationary center and fixed screen-space size. Hover shows the full
language name and model token in a pointer-transparent tooltip. Drag pans;
mouse-wheel/trackpad events and two-contact touch pinch zoom around the pointer
or moving midpoint, within 1x–12x. Controls are vertically stacked on the right.
Map Reset preserves the selected language; automatic detection clears the hint.
Narrow maps have a 170px minimum height with matching SVG stretch, keeping
representative language coordinates aligned and all three controls accessible.

Reproducible unbilled regression (start `deploy/map_browser_fixture.py` first):

```sh
browser-harness <<'PY'
from pathlib import Path
exec(compile(Path('deploy/check_map_navigation.py').read_text(),
             'deploy/check_map_navigation.py', 'exec'))
PY
```

The final run passed hover geometry/name, wheel anchoring, fixed marker size,
drag pan and click suppression, later deliberate selection, pinch distance
ratio, vertical controls and 1x/12x bounds, Reset, resize, Small/Large view
preservation, and unclipped controls/no horizontal overflow at 390px and 320px.
The original hover defect was reproduced before implementation. Additional
browser failures caught hidden-tab pan resets, a swallowed first Reset click
after pinch, and mobile control clipping; all corresponding regressions passed
after fixes.

Separate senior CDP checks passed moving-pinch midpoint anchoring, touchCancel
recovery, and keyboard search selection of `mcf_Latn`. Touch was browser-emulated,
not verified on physical hardware. An independent read-only review approved
the corrected gesture and mobile changes.

The final 16 app/map tests pass, with pre-existing Gradio asyncio ResourceWarnings.
The original repository suite passed all five tests in a disposable compatible
container. `app.py` is byte-identical to its task baseline; catalog and SVG asset
hashes are unchanged. Python compilation and diff whitespace checks pass.

The real localhost:7860 app was restarted and browser-checked for the updated
tooltip and mobile control fit. The temporary fake-inference server was stopped.
No transcription requests, Runpod writes, or new paid browser sessions were
made. Implementation files and prior user work remain uncommitted and intact.
