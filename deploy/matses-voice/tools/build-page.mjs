// White-label page generator: langs/<profile>.json + page/template.html + page/<profile>/index.html
import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();

function fail(msg) {
  console.error("build-page:", msg);
  process.exit(1);
}

function buildTokens(cfg) {
  const toks = {};
  for (const [k, v] of Object.entries(cfg)) {
    toks[k.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toUpperCase()] = v;
  }
  delete toks.STRINGS;
  for (const [k, v] of Object.entries(cfg.strings || {})) {
    toks["STR_" + k.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toUpperCase()] = v;
  }
  return toks;
}

function accentRgb(hex) {
  const h = String(hex || "");
  if (!/^#[0-9a-fA-F]{6}$/.test(h)) fail("bad accent: " + h);
  const r = parseInt(h.slice(1, 3), 16);
  const g = parseInt(h.slice(3, 5), 16);
  const b = parseInt(h.slice(5, 7), 16);
  return "rgba(" + r + "," + g + "," + b;
}

function render(cfg) {
  const toks = buildTokens(cfg);
  toks.ACCENT_RGB_PRE = accentRgb(cfg.accent);
  const tmpl = fs.readFileSync(path.join(ROOT, "page/template.html"), "utf8");
  let out = tmpl;
  const keys = Object.keys(toks).sort((a, b) => b.length - a.length);
  for (const k of keys) {
    out = out.split("__" + k + "__").join(toks[k]);
  }
  const left = out.match(/__[A-Z0-9_]+__/g);
  if (left) fail("unsubstituted tokens: " + [...new Set(left)].join(", "));
  return out;
}

function main() {
  const dir = path.join(ROOT, "langs");
  const names = fs.readdirSync(dir).filter((f) => f.endsWith(".json"));
  if (!names.length) fail("no langs/*.json found");
  for (const f of names) {
    const cfg = JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));
    const profile = String(cfg.profile || "");
    if (!/^[a-z][a-z0-9]{1,7}$/.test(profile)) fail("bad profile in " + f);
    if (!/^https:\/\//.test(String(cfg.workerUrl))) fail("bad workerUrl in " + f);
    if (profile !== f.replace(/\.json$/, "")) fail("profile/filename mismatch: " + f);
    const badChars = /["'<>\\\r\n]/;
    for (const [k, v] of Object.entries(cfg)) {
      if (typeof v === "string" && badChars.test(v)) fail("bad char in " + f + ":" + k);
    }
    for (const [k, v] of Object.entries(cfg.strings || {})) {
      if (typeof v !== "string") fail("strings." + k + " not a string in " + f);
      if (badChars.test(v)) fail("bad char in " + f + ":strings." + k);
    }
    const outDir = path.join(ROOT, "page", profile);
    fs.mkdirSync(outDir, { recursive: true, force: true });
    fs.writeFileSync(path.join(outDir, "index.html"), render(cfg));
    console.log("built", profile);
    fs.mkdirSync(path.join(ROOT, "page", profile), { recursive: true });
  }
}
main();
