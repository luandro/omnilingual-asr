"""Real browser regression for the offline language map.

Run inside browser-harness with the local fake-inference fixture at :7861.
This script only exercises map UI; it never submits audio or inference work.
"""

import json
from time import monotonic, sleep


new_tab("http://127.0.0.1:7861")
wait_for_load()
sleep(2)
cdp("Emulation.setDeviceMetricsOverride", width=1400, height=1000, deviceScaleFactor=1, mobile=False)

# Open the Large model tab through its accessible browser node.
deadline = monotonic() + 15
large = None
while monotonic() < deadline:
    nodes = cdp("Accessibility.getFullAXTree")["nodes"]
    large = next((n for n in nodes if n.get("name", {}).get("value", "").startswith("Large") and n.get("role", {}).get("value") == "tab"), None)
    if large:
        break
    sleep(.2)
assert large, "Large model tab is missing from the accessibility tree"
box = cdp("DOM.getBoxModel", backendNodeId=large["backendDOMNodeId"])["model"]["content"]
click_at_xy(sum(box[0::2]) / 4, sum(box[1::2]) / 4)
sleep(1)

js("document.querySelector('#language-map-control .language-map-viewport')?.scrollIntoView({block:'center'})")
sleep(.2)

state = js("""(() => {
  const map = document.querySelector('#language-map-control .language-map');
  const viewport = map?.querySelector('.language-map-viewport');
  if (!map || !viewport) return {ready:false};
  const v = viewport.getBoundingClientRect();
  const point = [...map.querySelectorAll('.language-point')].find(p => {
    const r=p.getBoundingClientRect(), x=r.x+r.width/2, y=r.y+r.height/2;
    return x>=v.left&&x<=v.right&&y>=v.top&&y<=v.bottom&&document.elementFromPoint(x,y)===p;
  });
  if (!point) return {ready:false};
  const r = point.getBoundingClientRect();
  return {ready:true, point:{x:r.x+r.width/2,y:r.y+r.height/2}, viewport:{x:v.x,y:v.y,width:v.width,height:v.height}, label:point.getAttribute('aria-label'), token:point.dataset.token};
})()""")
assert state.get("ready"), "language map did not render in the Large tab"

def center():
    return js(f"""(() => {{ const p=document.querySelector('#language-map-control .language-point[data-token={json.dumps(state['token'])}]'); const r=p.getBoundingClientRect(); return {{x:r.x+r.width/2,y:r.y+r.height/2}}; }})()""")

def point_size():
    return js(f"""(() => {{ const p=document.querySelector('#language-map-control .language-point[data-token={json.dumps(state['token'])}]'); const r=p.getBoundingClientRect(); return {{w:r.width,h:r.height}}; }})()""")

def transform_state():
    return js("""(() => { const map=document.querySelector('#language-map-control .language-map'); const m=new DOMMatrixReadOnly(getComputedStyle(map.querySelector('.language-map-layer')).transform); return {scale:m.a,x:m.e,y:m.f,selected:map.dataset.selectedToken||''}; })()""")

def click(x, y):
    cdp("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
    cdp("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", clickCount=1)
    sleep(.15)

def click_tab(prefix):
    nodes = cdp("Accessibility.getFullAXTree")["nodes"]
    tab = next(n for n in nodes if n.get("name", {}).get("value", "").startswith(prefix) and n.get("role", {}).get("value") == "tab")
    cdp("DOM.scrollIntoViewIfNeeded", backendNodeId=tab["backendDOMNodeId"])
    box = cdp("DOM.getBoxModel", backendNodeId=tab["backendDOMNodeId"])["model"]["content"]
    click_at_xy(sum(box[0::2]) / 4, sum(box[1::2]) / 4)
    sleep(.25)

def move(x, y):
    cdp("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)

move(state["point"]["x"], state["point"]["y"])
sleep(.2)
hovered = center()
assert abs(hovered["x"] - state["point"]["x"]) <= .5 and abs(hovered["y"] - state["point"]["y"]) <= .5, "marker center moved on hover at 1x"
tooltip = js("""(() => { const t=document.querySelector('#language-map-control .language-map-tooltip'); if(!t)return null; const s=getComputedStyle(t); const r=t.getBoundingClientRect(); return {text:t.textContent,visible:s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0}; })()""")
assert tooltip and tooltip["visible"], "hover does not show the full language tooltip"
assert state["token"] in tooltip["text"] and state["label"].split(" — ")[0] in tooltip["text"], "tooltip omits language name or exact model token"

# Mouse wheel over the map must change the view transform without selecting a token.
viewport = state["viewport"]
cdp("Input.dispatchMouseEvent", type="mouseWheel", x=viewport["x"]+viewport["width"]/2, y=viewport["y"]+viewport["height"]/2, deltaY=-240, deltaX=0)
sleep(.25)
after_wheel = js("""(() => { const map=document.querySelector('#language-map-control .language-map'); return {transform:getComputedStyle(map.querySelector('.language-map-layer')).transform,selected:map.dataset.selectedToken||''}; })()""")
assert after_wheel["transform"] != "none" and after_wheel["transform"] != "matrix(1, 0, 0, 1, 0, 0)", "wheel over viewport did not zoom the map"
assert after_wheel["selected"] == "", "map navigation changed selected language"
wheel_view = transform_state()
assert wheel_view["scale"] > 1, "wheel transform did not increase scale"
assert abs(wheel_view["x"] - (viewport["width"] / 2) * (1-wheel_view["scale"])) < 3, "wheel zoom was not anchored at its horizontal pointer position"
assert abs(wheel_view["y"] - (viewport["height"] / 2) * (1-wheel_view["scale"])) < 3, "wheel zoom was not anchored at its vertical pointer position"

# The hovered point remains a fixed-size screen-space target and hover remains stationary when zoomed.
point_before = center()
point_size_before = point_size()
move(point_before["x"], point_before["y"])
sleep(.15)
point_after = center()
point_size_after = point_size()
assert abs(point_after["x"]-point_before["x"]) <= .5 and abs(point_after["y"]-point_before["y"]) <= .5, "marker center moved on hover while zoomed"
assert abs(point_size_after["w"]-point_size_before["w"]) <= .5 and abs(point_size_after["h"]-point_size_before["h"]) <= .5, "marker hit target changes size while zoomed"

# Controls are a right-side vertical stack with comfortable targets.
controls = js("""(() => [...document.querySelectorAll('#language-map-control [data-zoom]')].map(b=>{const r=b.getBoundingClientRect();return {name:b.getAttribute('aria-label')||b.textContent,x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,h:r.height,top:r.top};}))()""")
assert [c["name"] for c in controls] == ["Zoom in", "Zoom out", "Reset"], "zoom controls are in the wrong order"
assert all(c["w"] >= 40 and c["h"] >= 40 for c in controls), "a zoom control target is smaller than 40px"
assert all(controls[i]["top"] < controls[i+1]["top"] for i in range(2)), "zoom controls are not vertically stacked"
assert all(c["x"] > viewport["x"] + viewport["width"] / 2 for c in controls), "zoom controls are not on the viewport's right side"
search_box = js("""(() => {const r=document.querySelector('#language-map-control #language-query').getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};})()""")
click(search_box["x"], search_box["y"])
for _ in range(2):
    cdp("Input.dispatchKeyEvent", type="rawKeyDown", key="Tab", code="Tab", windowsVirtualKeyCode=9)
    cdp("Input.dispatchKeyEvent", type="keyUp", key="Tab", code="Tab", windowsVirtualKeyCode=9)
keyboard_focus = js("""(() => {const e=document.activeElement,s=getComputedStyle(e);return{label:e.getAttribute('aria-label'),outline:s.outlineStyle,width:parseFloat(s.outlineWidth)};})()""")
assert keyboard_focus["label"] == "Zoom in" and keyboard_focus["outline"] != "none" and keyboard_focus["width"] >= 2, "keyboard focus does not reach an accessibly named, visibly focused zoom control"

# Stationary marker click selects its exact token. Reset restores the view and preserves selection.
click(controls[2]["x"], controls[2]["y"])
point = center()
click(point["x"], point["y"])
assert transform_state()["selected"] == state["token"], "stationary marker click did not select its exact model token"
for _ in range(18):
    click(controls[0]["x"], controls[0]["y"])
assert abs(transform_state()["scale"] - 12) < .02, "zoom-in control did not reach the 12x upper bound"
at_limit = transform_state()["scale"]
click(controls[1]["x"], controls[1]["y"])
assert 1 <= transform_state()["scale"] < at_limit, "zoom-out control did not reduce the scale"
click(controls[2]["x"], controls[2]["y"])
reset = transform_state()
assert abs(reset["scale"]-1) < .01 and abs(reset["x"]) < .5 and abs(reset["y"]) < .5, "Reset did not restore the whole-world view"
assert reset["selected"] == state["token"], "Reset cleared the selected language"

# Dragging from a marker and releasing over a different marker must not select either.
click(controls[0]["x"], controls[0]["y"])
points = js("""(() => [...document.querySelectorAll('#language-map-control .language-point')].map(p=>{const r=p.getBoundingClientRect();return {token:p.dataset.token,x:r.x+r.width/2,y:r.y+r.height/2};}).filter(p=>document.elementFromPoint(p.x,p.y)?.dataset.token===p.token))()""")
drag_start = next((p for p in points if p["token"] == state["token"]), None)
drag_target = next((p for p in points if p["token"] != state["token"] and ((p["x"]-drag_start["x"])**2+(p["y"]-drag_start["y"])**2)**.5 > 30), None) if drag_start else None
assert drag_start and drag_target, "fixture lacks two unobscured markers for drag suppression"
pan_before = transform_state()
cdp("Input.dispatchMouseEvent", type="mouseMoved", x=drag_start["x"], y=drag_start["y"])
cdp("Input.dispatchMouseEvent", type="mousePressed", x=drag_start["x"], y=drag_start["y"], button="left", clickCount=1)
cdp("Input.dispatchMouseEvent", type="mouseMoved", x=drag_target["x"], y=drag_target["y"], button="left")
cdp("Input.dispatchMouseEvent", type="mouseReleased", x=drag_target["x"], y=drag_target["y"], button="left", clickCount=1)
sleep(.2)
pan_after = transform_state()
assert abs(pan_after["x"]-pan_before["x"]) > 1 or abs(pan_after["y"]-pan_before["y"]) > 1, "mouse drag did not pan the view"
assert pan_after["selected"] == state["token"], "drag release over another marker changed the selected token"
view_before_hide = transform_state()
click_tab("Small")
click_tab("Large")
view_after_show = transform_state()
assert all(abs(view_after_show[k]-view_before_hide[k]) < 1 for k in ("scale", "x", "y")), "hiding and reopening Large reset the map view"
later = js("""(() => {const p=[...document.querySelectorAll('#language-map-control .language-point')].find(p=>document.elementFromPoint((r=>r.x+r.width/2)(p.getBoundingClientRect()),(r=>r.y+r.height/2)(p.getBoundingClientRect()))?.dataset.token===p.dataset.token);if(!p)return null;const r=p.getBoundingClientRect();return {token:p.dataset.token,x:r.x+r.width/2,y:r.y+r.height/2};})()""")
assert later, "no unobscured marker remains after panning"
click(later["x"], later["y"])
assert transform_state()["selected"] == later["token"], "a later deliberate click was suppressed after dragging"

# A two-contact touch sequence pinches around a moving midpoint without selecting a language.
v = js("""(() => {const r=document.querySelector('#language-map-control .language-map-viewport').getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height};})()""")
cx, cy = v["x"]+v["w"]/2, v["y"]+v["h"]/2
pinch_before = transform_state()
cdp("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=2)
cdp("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x":cx-35,"y":cy,"id":1},{"x":cx+35,"y":cy,"id":2}])
cdp("Input.dispatchTouchEvent", type="touchMove", touchPoints=[{"x":cx-75,"y":cy+8,"id":1},{"x":cx+75,"y":cy+8,"id":2}])
cdp("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
sleep(.2)
cdp("Emulation.setTouchEmulationEnabled", enabled=False)
pinch_after = transform_state()
assert pinch_after["scale"] > pinch_before["scale"] + .2, "two-finger touch pinch did not zoom the map"
assert abs(pinch_after["scale"] - min(12, pinch_before["scale"] * (150/70))) < .08, "pinch scale did not track the two-finger distance ratio"
assert transform_state()["selected"] == later["token"], "pinch changed the selected token"

# A viewport resize keeps the view bounded; reset still returns to the world view.
cdp("Emulation.setDeviceMetricsOverride", width=900, height=750, deviceScaleFactor=1, mobile=False)
sleep(.3)
assert 1 <= transform_state()["scale"] <= 12.01, "resize left scale outside the supported bounds"
controls = js("""(() => [...document.querySelectorAll('#language-map-control [data-zoom]')].map(b=>{const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};}))()""")
click(controls[2]["x"], controls[2]["y"])
assert abs(transform_state()["scale"]-1) < .01, "Reset failed after viewport resize"

# Narrow viewports keep the complete control stack inside the map without page overflow.
for width, height in ((390, 844), (320, 740)):
    cdp("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False)
    sleep(.3)
    js("document.querySelector('#language-map-control .language-map-viewport')?.scrollIntoView({block:'center'})")
    sleep(.1)
    geometry = js("""(() => {const v=document.querySelector('#language-map-control .language-map-viewport').getBoundingClientRect();const controls=[...document.querySelectorAll('#language-map-control [data-zoom]')].map(b=>{const r=b.getBoundingClientRect();return{left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};});return{viewport:{left:v.left,right:v.right,top:v.top,bottom:v.bottom,width:v.width,height:v.height},controls,documentWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth};})()""")
    area = geometry["viewport"]
    assert area["height"] >= 170, f"{width}px viewport did not retain the minimum map height"
    assert all(c["left"] >= area["left"] and c["right"] <= area["right"] and c["top"] >= area["top"] and c["bottom"] <= area["bottom"] for c in geometry["controls"]), f"a zoom control is clipped at {width}px"
    assert all(c["width"] >= 40 and c["height"] >= 40 for c in geometry["controls"]), f"a touch target is too small at {width}px"
    assert geometry["documentWidth"] <= geometry["clientWidth"] + 1, f"map causes horizontal overflow at {width}px"
cdp("Emulation.setDeviceMetricsOverride", width=1400, height=1000, deviceScaleFactor=1, mobile=False)

print("PASS: hover, tooltip, wheel, drag, pinch, controls, bounds, reset, resize, mobile control fit, exact click, drag suppression, and selection isolation")
