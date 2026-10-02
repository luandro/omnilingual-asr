#!/usr/bin/env python3
"""Build the checked-in offline language catalog and Natural Earth SVG."""

from __future__ import annotations

import argparse
import ast
from datetime import date
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from language_map import build_catalog


GLOTTOLOG_REVISION = "072ca0d0410039fb8b779be8fc165bac575d2cda"
GLOTTOLOG_URL = f"https://raw.githubusercontent.com/glottolog/glottolog-cldf/{GLOTTOLOG_REVISION}/cldf/languages.csv"
GLOTTOLOG_LICENSE = "CC BY 4.0"
GLOTTOLOG_SHA256 = "1a50a393bc81568b656f9522be18aa4f80f38e94309ba6c863d583234adfbb89"
NATURAL_EARTH_REVISION = "ca96624a56bd078437bca8184e78163e5039ad19"
NATURAL_EARTH_URL = f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/{NATURAL_EARTH_REVISION}/geojson/ne_110m_land.geojson"
NATURAL_EARTH_LICENSE = "Public domain"
NATURAL_EARTH_SHA256 = "9e0729ee253ca7d7a5c4ae9395fb1902264c5377c52e224d13dd85010e2835d9"
ASR_REVISION = "81f51e224ce9e74b02cc2a3eaf21b2d91d743455"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_supported_tokens(path: Path) -> list[str]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    for statement in module.body:
        target = statement.target if isinstance(statement, ast.AnnAssign) else None
        if isinstance(statement, ast.Assign) and any(getattr(item, "id", None) == "supported_langs" for item in statement.targets):
            target = statement.targets[0]
        if getattr(target, "id", None) == "supported_langs":
            tokens = ast.literal_eval(statement.value)
            if isinstance(tokens, list) and all(isinstance(item, str) for item in tokens):
                if len(tokens) != len(set(tokens)):
                    raise ValueError("model allowlist contains duplicate tokens")
                return tokens
    raise ValueError(f"No literal supported_langs list found in {path}")


def _project(longitude: float, latitude: float) -> tuple[float, float]:
    return ((longitude + 180) / 360 * 1000, (90 - latitude) / 180 * 500)


def build_world_svg(source: Path, target: Path) -> None:
    """Convert pinned Natural Earth land polygons to a local equirectangular SVG."""
    geojson = json.loads(source.read_text(encoding="utf-8"))
    paths = []
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry") or {}
        kind = geometry.get("type")
        coordinates = geometry.get("coordinates", [])
        polygons = [coordinates] if kind == "Polygon" else coordinates if kind == "MultiPolygon" else []
        for polygon in polygons:
            if not polygon:
                continue
            exterior = polygon[0]
            if len(exterior) < 4:
                continue
            points = [_project(float(point[0]), float(point[1])) for point in exterior]
            path_data = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points) + " Z"
            paths.append(f'<path d="{path_data}"/>')
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 500" role="img" aria-label="World land outline">'
           + "".join(paths) + "</svg>\n")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(svg, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glottolog-csv", type=Path, required=True)
    parser.add_argument("--world-geojson", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ui")
    args = parser.parse_args()

    allowlist_path = ROOT / "src/omnilingual_asr/models/wav2vec2_llama/lang_ids.py"
    supported = load_supported_tokens(allowlist_path)
    glottolog_sha = sha256(args.glottolog_csv)
    natural_earth_sha = sha256(args.world_geojson)
    if glottolog_sha != GLOTTOLOG_SHA256:
        raise ValueError(f"Glottolog snapshot checksum differs from the pinned source: {glottolog_sha}")
    if natural_earth_sha != NATURAL_EARTH_SHA256:
        raise ValueError(f"Natural Earth checksum differs from the pinned source: {natural_earth_sha}")
    catalog, coverage = build_catalog(args.glottolog_csv, supported)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = args.output_dir / "catalog.json"
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    build_world_svg(args.world_geojson, args.output_dir / "world_land.svg")
    catalog_sha = sha256(catalog_path)
    provenance = {
        "catalog_version": 1,
        "generated_by": "scripts/build_language_catalog.py",
        "retrieved_date": date.today().isoformat(),
        "catalog_sha256": catalog_sha,
        "asr_supported_tokens": {
            "source": "src/omnilingual_asr/models/wav2vec2_llama/lang_ids.py",
            "revision": ASR_REVISION,
            "sha256": sha256(allowlist_path),
        },
        "glottolog": {
            "citation": "Hammarström, Harald; Forkel, Robert; Haspelmath, Martin; Bank, Sebastian. 2026. Glottolog 5.3. Leipzig: Max Planck Institute for Evolutionary Anthropology.",
            "url": GLOTTOLOG_URL,
            "revision": GLOTTOLOG_REVISION,
            "release": "5.3",
            "cldf_revision_dataset_label": "CLDF snapshot v5.2.1 derived from Glottolog v5.3",
            "license": GLOTTOLOG_LICENSE,
            "sha256": glottolog_sha,
            "local_name_override": {"mcf": "Matsés"},
        },
        "map_outline": {
            "source": "Natural Earth 1:110m land polygons",
            "url": NATURAL_EARTH_URL,
            "revision": NATURAL_EARTH_REVISION,
            "license": NATURAL_EARTH_LICENSE,
            "sha256": natural_earth_sha,
        },
        "coverage": coverage,
    }
    (args.output_dir / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"catalog": str(catalog_path), "coverage": coverage, "catalog_sha256": catalog_sha}, sort_keys=True))


if __name__ == "__main__":
    main()
