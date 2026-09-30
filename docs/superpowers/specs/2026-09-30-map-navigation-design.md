# Language map navigation

## Approved interaction design

Improve the existing offline language map in the Large / LLM 7B v2 tab.
Keep the language catalog, representative locations, search, automatic option,
model routing, and transcription API unchanged. No new mapping dependencies,
remote tiles, Runpod changes, or billed inference tests are needed.

## Hover and selection

- Keep each marker's center and hit target stationary during hover and selection,
  including at every zoom level. Use color and an outline for emphasis rather
  than changing layout dimensions or margins.
- Show a promptly visible tooltip containing the full language name and model
  token. The tooltip stays outside the transformed map layer, within the map
  viewport, and cannot intercept pointer events.
- Hover only previews information. A click or a tap selects the exact existing
  language token; map movement never selects a language.
- Hide the tooltip during navigation and when the pointer leaves the marker.
  Keep the selected-language summary and search-based keyboard access intact.

## Navigation

- Use a single viewport transform with explicit scale and translation; avoid
  changing transform origin when selecting a language.
- Drag with a mouse, stylus, or one touch to pan. Two-finger touch pinches zoom
  around the moving midpoint. Pointer cancellation safely ends the gesture.
- Mouse-wheel and trackpad scrolling over the map zoom around the pointer;
  trackpad pinch events using the wheel path work as well. Page scrolling remains
  normal outside the map.
- Keep scale within 1x–12x and constrain translation so the map cannot be lost
  outside the viewport. Markers retain a constant screen-space size.
- Suppress marker clicks after a drag or pinch. A stationary tap remains a
  selection. Navigation controls do not start a map gesture.
- Resize preserves a bounded view; Reset restores the whole-world view without
  clearing the selected language.

## Controls

Place zoom controls in a vertical stack on the right side of the map, ordered
Zoom in (+), Zoom out (−), Reset. Controls have accessible names, visible focus,
and comfortable touch targets. Button zoom is centered on the viewport.

## Validation

Use the local browser harness without submitting transcription jobs. Check:
stationary hover centers at multiple zoom levels; full-name tooltip visibility;
wheel/pointer anchoring; drag pan; touch pinch; click suppression after movement;
normal marker selection; right-side vertical controls; zoom bounds; Reset;
resize; and keyboard access to search and controls. Run existing catalog and app
contract tests to guard language-token and model-routing behavior. Record which
gestures have browser evidence rather than claiming static tests prove them.
