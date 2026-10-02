"""Offline language catalog joins and accessible local map markup."""

from __future__ import annotations

import csv
import html
import json
import math
import unicodedata
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "ui" / "catalog.json"
WORLD_SVG_PATH = ROOT / "ui" / "world_land.svg"
SCRIPT_NAMES = {
    "Arab": "Arabic", "Armn": "Armenian", "Beng": "Bengali", "Bopo": "Bopomofo",
    "Brai": "Braille", "Cyrl": "Cyrillic", "Deva": "Devanagari", "Ethi": "Ethiopic",
    "Geor": "Georgian", "Grek": "Greek", "Gujr": "Gujarati", "Guru": "Gurmukhi",
    "Hang": "Hangul", "Hani": "Han", "Hans": "Simplified Han", "Hant": "Traditional Han",
    "Hebr": "Hebrew", "Jpan": "Japanese", "Khmr": "Khmer", "Knda": "Kannada",
    "Laoo": "Lao", "Latn": "Latin", "Mlym": "Malayalam", "Mymr": "Myanmar",
    "Orya": "Odia", "Sinh": "Sinhala", "Taml": "Tamil", "Telu": "Telugu",
    "Thaa": "Thaana", "Thai": "Thai", "Tibt": "Tibetan", "Vaii": "Vai",
}


def _read_glottolog_rows(source: Path) -> dict[str, list[dict[str, str]]]:
    candidates: dict[str, list[dict[str, str]]] = {}
    with source.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"Name", "Latitude", "Longitude", "Glottocode", "ISO639P3code", "Level"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Glottolog CSV is missing required CLDF language columns")
        for row in reader:
            iso = (row.get("ISO639P3code") or "").strip().lower()
            if iso and (row.get("Level") or "").strip().lower() == "language":
                candidates.setdefault(iso, []).append(row)
    for rows in candidates.values():
        rows.sort(key=lambda row: (row.get("Glottocode", ""), row.get("Name", "")))
    return candidates


def _valid_location(row: dict[str, str]) -> tuple[float, float] | None:
    try:
        latitude = float(row.get("Latitude", ""))
        longitude = float(row.get("Longitude", ""))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude


def build_catalog(source: Path, supported_tokens: Iterable[str]) -> tuple[list[dict], dict[str, int]]:
    """Join supported model tokens to exact ISO-639-3 Glottolog language rows."""
    tokens = list(supported_tokens)
    if len(tokens) != len(set(tokens)):
        raise ValueError("supported model token list contains duplicates")
    if any(not isinstance(token, str) or "_" not in token for token in tokens):
        raise ValueError("supported model tokens must include a language and script")

    by_iso = _read_glottolog_rows(Path(source))
    catalog = []
    for token in sorted(tokens):
        iso, script_and_variant = token.split("_", 1)
        script = script_and_variant.split("_", 1)[0]
        rows = by_iso.get(iso.lower(), [])
        rows_by_code: dict[str, dict[str, str]] = {}
        for row in rows:
            code = (row.get("Glottocode") or "").strip()
            if code:
                rows_by_code[code] = row
        unique_rows = [rows_by_code[code] for code in sorted(rows_by_code)]
        names = sorted({(row.get("Name") or "").strip() for row in unique_rows if (row.get("Name") or "").strip()})
        alias = {"mcf": "Matsés"}.get(iso.lower())
        name = alias or (" / ".join(names) if names else f"Unknown language ({iso})")
        glottocodes = [code for code in sorted(rows_by_code)]
        location = None
        if not unique_rows:
            match_status = "unmatched"
        elif len(unique_rows) > 1:
            match_status = "ambiguous"
        else:
            location = _valid_location(unique_rows[0])
            if location is None:
                match_status = "matched_no_location"
            else:
                latitude, longitude = location
                location = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "kind": "representative_language_location",
                    "source": "glottolog",
                    "source_record": glottocodes[0],
                }
                match_status = "matched"
        if unique_rows and match_status == "matched_no_location":
            raw_location = (unique_rows[0].get("Latitude") or "").strip(), (unique_rows[0].get("Longitude") or "").strip()
            if any(raw_location):
                match_status = "invalid_location"
        catalog.append({
            "model_token": token,
            "name": name,
            "iso639_3": iso,
            "script": script,
            "script_name": SCRIPT_NAMES.get(script, script),
            "glottocodes": glottocodes,
            "location": location,
            "match_status": match_status,
        })

    counts = {"supported_tokens": len(catalog)}
    counts["matched_tokens"] = sum(row["match_status"] == "matched" for row in catalog)
    counts["ambiguous_tokens"] = sum(row["match_status"] == "ambiguous" for row in catalog)
    counts["unmatched_tokens"] = sum(row["match_status"] == "unmatched" for row in catalog)
    counts["without_location_tokens"] = sum(row["match_status"] == "matched_no_location" for row in catalog)
    counts["invalid_location_tokens"] = sum(row["match_status"] == "invalid_location" for row in catalog)
    counts["exact_matches"] = counts["matched_tokens"] + counts["ambiguous_tokens"] + counts["without_location_tokens"] + counts["invalid_location_tokens"]
    counts["missing_names"] = sum(row["name"].startswith("Unknown language (") for row in catalog)
    counts["missing_locations"] = sum(row["match_status"] != "matched" for row in catalog)
    return catalog, counts


def language_point_positions(catalog: Iterable[dict]) -> dict[str, tuple[float, float]]:
    return {
        entry["model_token"]: (entry["location"]["latitude"], entry["location"]["longitude"])
        for entry in catalog
        if entry.get("match_status") == "matched"
        and entry.get("location") is not None
    }


def _normalized(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def search_languages(catalog: Iterable[dict], query: str) -> list[dict]:
    normalized_query = _normalized((query or "").strip())
    if not normalized_query:
        return []
    matches = []
    for entry in catalog:
        searchable = " ".join((entry.get("name", ""), entry.get("model_token", ""), entry.get("iso639_3", ""), entry.get("script", ""), entry.get("script_name", ""), *entry.get("glottocodes", [])))
        if normalized_query in _normalized(searchable):
            matches.append(entry)
    return matches[:100]


def select_language(catalog: Iterable[dict], token: str | None) -> dict | None:
    if token is None or token == "":
        return None
    for entry in catalog:
        if entry.get("model_token") == token:
            return entry
    raise ValueError("unsupported language selection")


def language_selection_event(event, catalog: list[dict]):
    token = getattr(event, "token", None)
    if isinstance(event, dict):
        token = event.get("token")
    entry = select_language(catalog, token)
    return entry["model_token"] if entry else None


def _point_markup(entry: dict) -> str:
    x = (entry["location"]["longitude"] + 180) / 360 * 100
    y = (90 - entry["location"]["latitude"]) / 180 * 100
    token = html.escape(entry["model_token"], quote=True)
    label = html.escape(f"{entry['name']} — {entry['model_token']}", quote=True)
    return f'<button class="language-point" type="button" tabindex="-1" data-token="{token}" aria-label="{label}" title="{label}" style="left:{x:.5f}%;top:{y:.5f}%"></button>'


def render_language_map(catalog: list[dict], world_svg: str | None = None) -> str:
    """Create self-contained map and search markup; JS is attached by Gradio."""
    if world_svg is None:
        world_svg = WORLD_SVG_PATH.read_text(encoding="utf-8")
    # Strip an XML declaration, if present, and scope the SVG viewBox to this map.
    world_svg = world_svg.replace("<?xml version=\"1.0\" encoding=\"UTF-8\"?>", "").strip()
    svg_opening_tag = world_svg.split(">", 1)[0]
    if "preserveAspectRatio=" not in svg_opening_tag:
        world_svg = world_svg.replace("<svg ", '<svg preserveAspectRatio="none" ', 1)
    points = "".join(_point_markup(row) for row in catalog if row.get("match_status") == "matched")
    data = html.escape(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), quote=True)
    return f'''<section class="language-map" data-catalog="{data}" aria-label="Choose a language">
      <div class="language-search">
        <label for="language-query">Find a language</label>
        <input id="language-query" type="search" autocomplete="off" placeholder="Name, code, or script" aria-controls="language-results" />
        <div id="language-results" role="listbox" aria-label="Language search results"></div>
      </div>
      <div class="language-map-viewport" role="group" aria-label="Map of representative language locations" tabindex="0">
        <div class="language-map-layer"><div class="language-map-land">{world_svg}</div>{points}</div>
        <div class="language-map-tooltip" role="status" aria-live="polite" hidden></div>
        <div class="language-map-zoom" aria-label="Map zoom controls">
          <button type="button" data-zoom="in" aria-label="Zoom in">+</button>
          <button type="button" data-zoom="out" aria-label="Zoom out">−</button>
          <button type="button" data-zoom="reset">Reset</button>
        </div>
      </div>
      <div class="language-selection" aria-live="polite">
        <div><strong id="selected-language">Automatic language detection</strong><span id="selected-code">No language hint</span></div>
        <button id="automatic-language" type="button">Use automatic detection</button>
      </div>
      <p class="language-attribution">Map points show representative language locations, not boundaries or recording sites. Language data: <a href="https://glottolog.org/" target="_blank" rel="noreferrer">Glottolog 5.3</a>, <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a>. Map outline: <a href="https://www.naturalearthdata.com/about/terms-of-use/" target="_blank" rel="noreferrer">Natural Earth, public domain</a>.</p>
    </section>'''


MAP_CSS = r"""<style>
.language-map{--ink:#152b45;--ocean:#dcecf3;--land:#8da2ad;--blue:#176da0;--amber:#db8b22;color:var(--ink);font:16px/1.45 system-ui,sans-serif;display:grid;gap:1rem}
.language-search{display:grid;gap:.45rem;max-width:38rem}.language-search label{font-weight:650}.language-search input{border:1px solid #7f919c;border-radius:5px;padding:.7rem .8rem;font:inherit;color:inherit;background:white}.language-map button:focus-visible,.language-search input:focus-visible{outline:3px solid #e4a343;outline-offset:2px}
#language-results{display:grid;max-height:13rem;overflow:auto}.language-result{border:0;border-bottom:1px solid #d4dee3;background:white;color:inherit;text-align:left;padding:.52rem .65rem;font:inherit;cursor:pointer}.language-result:hover,.language-result[aria-selected=true]{background:#e8f2f7}.language-result small{color:#526b7b;margin-left:.35rem}
.language-map-viewport{position:relative;isolation:isolate;aspect-ratio:2/1;overflow:hidden;border:1px solid #abc2ce;border-radius:8px;background:#dcecf3;touch-action:none;overscroll-behavior:contain}.language-map-layer{position:absolute;inset:0;transform-origin:0 0;transition:none;will-change:transform}.language-map-land,.language-map-land svg{position:absolute;inset:0;width:100%;height:100%}.language-map-land path{fill:#8da2ad;stroke:#708894;stroke-width:.5}.language-point{position:absolute;z-index:2;box-sizing:border-box;width:12px!important;height:12px!important;margin:0!important;padding:0;translate:-50% -50%;border:2px solid white;border-radius:50%;background:#176da0;box-shadow:0 0 0 1px #134e70;cursor:pointer;transform:scale(var(--point-scale,1));transform-origin:center}.language-point:hover,.language-point:focus-visible,.language-point.selected{z-index:3;background:#db8b22;outline:2px solid #763f06;outline-offset:1px}.language-map-tooltip{position:absolute;z-index:5;max-width:min(22rem,calc(100% - 12px));padding:.4rem .55rem;border-radius:4px;background:#152b45;color:white;font-size:.85rem;line-height:1.25;box-shadow:0 2px 8px #152b4566;pointer-events:none;white-space:normal}.language-map-tooltip[hidden]{display:none}.language-map-zoom{position:absolute;z-index:6;right:.55rem;top:.55rem;display:flex;flex-direction:column;gap:.35rem}.language-map-zoom button{width:2.75rem;min-width:40px;height:2.75rem;min-height:40px;border:1px solid #657e8a;border-radius:4px;background:white;color:#152b45;font:600 1rem system-ui,sans-serif;cursor:pointer}.language-selection{display:flex;align-items:center;justify-content:space-between;gap:1rem;border-left:4px solid #db8b22;padding:.7rem 1rem;background:#f0f4f5}.language-selection div{display:grid}.language-selection span{color:#526b7b}.language-selection button{border:1px solid #667d8b;border-radius:5px;background:white;padding:.55rem .7rem;color:inherit;font:inherit;cursor:pointer}.language-attribution{margin:0;color:#526b7b;font-size:.9rem}.language-attribution a{color:#165e86}
@media(max-width:600px){.language-map-viewport{min-height:170px}.language-selection{align-items:flex-start;flex-direction:column}.language-attribution{font-size:.82rem}}
@media(prefers-reduced-motion:reduce){.language-map-layer{transition:none}}
</style>"""


MAP_JS = r"""const root = element.querySelector('.language-map');
if (root && !root.dataset.ready) {
  root.dataset.ready = 'true';
  const catalog = JSON.parse(root.dataset.catalog);
  const search = root.querySelector('#language-query');
  const results = root.querySelector('#language-results');
  const name = root.querySelector('#selected-language');
  const code = root.querySelector('#selected-code');
  const layer = root.querySelector('.language-map-layer');
  const viewport = root.querySelector('.language-map-viewport');
  const tooltip = root.querySelector('.language-map-tooltip');
  let mapScale = 1, mapX = 0, mapY = 0, gesture = null, suppressNextClick = false;
  const activePointers = new Map();
  const normalize = value => value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  const size = () => ({width:viewport.clientWidth,height:viewport.clientHeight});
  const applyView = () => {
    const {width,height} = size();
    if (width <= 0 || height <= 0) return;
    mapX = clamp(mapX,width*(1-mapScale),0); mapY = clamp(mapY,height*(1-mapScale),0);
    layer.style.transform = `translate(${mapX}px, ${mapY}px) scale(${mapScale})`;
    layer.style.setProperty('--point-scale', String(1 / mapScale));
  };
  const setScaleAt = (requested,x,y) => {
    const next = clamp(requested,1,12), ratio = next/mapScale;
    mapX = x-(x-mapX)*ratio; mapY = y-(y-mapY)*ratio; mapScale = next; applyView();
  };
  const hideTooltip = () => { tooltip.hidden = true; };
  const showTooltip = point => {
    tooltip.textContent = point.getAttribute('aria-label') || ''; tooltip.hidden = false;
    const marker=point.getBoundingClientRect(), area=viewport.getBoundingClientRect(), half=tooltip.offsetWidth/2;
    const x=clamp(marker.left+marker.width/2-area.left,half+6,area.width-half-6);
    const above=marker.top-area.top-tooltip.offsetHeight-8;
    const y=above>=4?above:marker.bottom-area.top+tooltip.offsetHeight+8;
    tooltip.style.left=`${x}px`; tooltip.style.top=`${clamp(y,4,area.height-4)}px`;
    tooltip.style.transform=above>=4?'translate(-50%, 0)':'translate(-50%, -100%)';
  };
  const choose = token => {
    const entry = catalog.find(item => item.model_token === token);
    if (!entry && token !== null) return;
    root.dataset.selectedToken = entry ? entry.model_token : '';
    name.textContent = entry ? entry.name : 'Automatic language detection';
    code.textContent = entry ? `${entry.model_token} · ${entry.script_name}` : 'No language hint';
    root.querySelectorAll('.language-point').forEach(point => {
      const selected = point.dataset.token === token;
      point.classList.toggle('selected', selected);
    });
    trigger('click', {token: token});
  };
  const fillResults = () => {
    const query = normalize(search.value.trim());
    results.replaceChildren();
    if (!query) return;
    catalog.filter(entry => normalize([entry.name, entry.model_token, entry.iso639_3, entry.script, entry.script_name, ...(entry.glottocodes || [])].join(' ')).includes(query)).slice(0, 100).forEach(entry => {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'language-result'; button.setAttribute('role', 'option');
      button.textContent = entry.name;
      const hint = document.createElement('small'); hint.textContent = `${entry.model_token} · ${entry.script_name}${entry.match_status === 'matched' ? '' : ' · not mapped'}`;
      button.append(hint); button.addEventListener('click', () => choose(entry.model_token)); results.append(button);
    });
  };
  search.addEventListener('input', fillResults);
  search.addEventListener('keydown', event => {
    const options = [...results.querySelectorAll('button')];
    if (!options.length || !['ArrowDown', 'ArrowUp'].includes(event.key)) return;
    event.preventDefault();
    const current = options.indexOf(document.activeElement);
    options[Math.max(0, Math.min(options.length - 1, current + (event.key === 'ArrowDown' ? 1 : -1)))].focus();
  });
  root.querySelectorAll('.language-point').forEach(point=>{
    point.addEventListener('click',()=>choose(point.dataset.token));
    point.addEventListener('pointerenter',()=>{if(!gesture)showTooltip(point);}); point.addEventListener('pointerleave',hideTooltip);
    point.addEventListener('focus',()=>showTooltip(point)); point.addEventListener('blur',hideTooltip);
  });
  root.addEventListener('click',event=>{
    if(!suppressNextClick||event.detail===0)return;
    suppressNextClick=false; event.preventDefault(); event.stopPropagation();
  },true);
  const local=event=>{const r=viewport.getBoundingClientRect();return{x:event.clientX-r.left,y:event.clientY-r.top};};
  const onControl=target=>target instanceof Element&&Boolean(target.closest('.language-map-zoom'));
  viewport.addEventListener('pointerdown',event=>{
    if(event.pointerType==='mouse'&&event.button!==0)return;
    // Clear any touch/drag click suppression on the next intentional pointer action,
    // including controls, which do not enter the map gesture state machine.
    suppressNextClick=false;
    if(onControl(event.target))return;
    event.preventDefault(); hideTooltip(); const p=local(event);
    activePointers.set(event.pointerId,{...p,target:event.target});
    try{viewport.setPointerCapture(event.pointerId);}catch(_){/* Pointer may already have been canceled. */}
    if(activePointers.size===1)gesture={type:'pan',startX:p.x,startY:p.y,x:mapX,y:mapY,moved:false,target:event.target};
    else if(activePointers.size===2){const[a,b]=[...activePointers.values()];gesture={type:'pinch',distance:Math.max(1,Math.hypot(a.x-b.x,a.y-b.y)),scale:mapScale,midX:(a.x+b.x)/2,midY:(a.y+b.y)/2,x:mapX,y:mapY,moved:true};}
  });
  viewport.addEventListener('pointermove',event=>{
    const p=activePointers.get(event.pointerId);if(!p||!gesture)return;const now=local(event);p.x=now.x;p.y=now.y;
    if(gesture.type==='pan'){
      const dx=now.x-gesture.startX,dy=now.y-gesture.startY;if(Math.hypot(dx,dy)>4)gesture.moved=true;
      if(gesture.moved){mapX=gesture.x+dx;mapY=gesture.y+dy;applyView();}
    }else if(activePointers.size>=2){
      const[a,b]=[...activePointers.values()],midX=(a.x+b.x)/2,midY=(a.y+b.y)/2;
      const ratio=Math.hypot(a.x-b.x,a.y-b.y)/gesture.distance;mapScale=clamp(gesture.scale*ratio,1,12);
      const applied=mapScale/gesture.scale;mapX=midX-(gesture.midX-gesture.x)*applied;mapY=midY-(gesture.midY-gesture.y)*applied;
      if(Math.hypot(midX-gesture.midX,midY-gesture.midY)>4||Math.abs(ratio-1)>.02)gesture.moved=true;applyView();
    }
  });
  const rebase=()=>{if(activePointers.size===1){const[p]=activePointers.values();gesture={type:'pan',startX:p.x,startY:p.y,x:mapX,y:mapY,moved:true};}else gesture=null;};
  const finishPointer=(event,canceled=false)=>{
    if(!activePointers.has(event.pointerId))return;const finished=gesture;activePointers.delete(event.pointerId);
    try{if(viewport.hasPointerCapture(event.pointerId))viewport.releasePointerCapture(event.pointerId);}catch(_){/* Browser already released capture. */}
    if(!canceled&&finished&&activePointers.size===0){
      if(finished.moved)suppressNextClick=true;
      else if(finished.target instanceof Element){const marker=finished.target.closest('.language-point');if(marker){choose(marker.dataset.token);suppressNextClick=true;}}
    }
    if(finished?.moved)hideTooltip();rebase();
  };
  viewport.addEventListener('pointerup',event=>finishPointer(event));
  viewport.addEventListener('pointercancel',event=>finishPointer(event,true));
  viewport.addEventListener('lostpointercapture',event=>finishPointer(event,true));
  viewport.addEventListener('wheel',event=>{
    if(onControl(event.target))return;event.preventDefault();const p=local(event),delta=clamp(event.deltaY,-240,240);
    setScaleAt(mapScale*Math.exp(-delta*.002),p.x,p.y);hideTooltip();
  },{passive:false});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){activePointers.clear();gesture=null;hideTooltip();}});
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(()=>applyView()).observe(viewport);
  root.querySelector('#automatic-language').addEventListener('click',()=>choose(null));
  root.querySelectorAll('[data-zoom]').forEach(button=>button.addEventListener('click',()=>{
    if(button.dataset.zoom==='reset'){mapScale=1;mapX=0;mapY=0;applyView();hideTooltip();return;}
    const{width,height}=size();setScaleAt(mapScale*(button.dataset.zoom==='in'?1.5:1/1.5),width/2,height/2);hideTooltip();
  }));
  applyView();
}
"""


LLM_SUBMIT_JS = r"""(audio, language) => {
  const map = document.querySelector('#language-map-control .language-map');
  const selectedToken = map?.dataset.selectedToken || '';
  return [audio, selectedToken || null];
}"""
