# Language map: sources, provenance, and future integration

Research recorded 2026-09-29 (Brazil/Acre). The initial offline map and model-tab
interface are now implemented; the research below distinguishes confirmed
observations from proposals for richer future metadata.

## Goal and current interface

Replace language selection by raw codes with a searchable language map, while
retaining an accessible list alternative and the existing transcription API.
Display names such as `Matsés — mcf`; submit the exact model token `mcf_Latn`.
Readable names can be added before implementing a map.

Before the map change, `app.py` read the literal `supported_langs` list and built
dropdown choices as `(code, code)`. Names were absent because no metadata source
was joined. The current implementation joins a pinned Glottolog catalog instead.
The LLM accepts a language hint; CTC ignores it and transcribes automatically.
Selecting a language on the map must not silently select a different model or
claim to condition CTC inference. Automatic/no-hint remains an option for LLM.

## Source inventory

| Source | Useful fields / role | Limitations |
| --- | --- | --- |
| [`lang_ids.py`](../src/omnilingual_asr/models/wav2vec2_llama/lang_ids.py) | Exact supported `{language}_{script}` tokens; authoritative UI hint allowlist for the pinned source | Codes, not readable names or locations; 1,672 entries observed |
| [`languges_lookup_table.parquet`](../src/omnilingual_asr/models/wav2vec2_llama/languges_lookup_table.parquet) | Columns `lang: string`, `index: int64`; tokenizer lookup | Despite its name, not a language-name or coordinate table; filename spelling is upstream |
| [Meta language globe](https://aidemos.atmeta.com/omnilingualasr/language-globe) | Readable names, ISO codes, scripts, family, coordinates; sometimes corpus and vitality | Compiled website data; attribution/version for individual fields not exposed in inspected bundle |
| [Glottolog](https://glottolog.org/) and [data repository](https://github.com/glottolog/glottolog) | Glottocodes, ISO associations, names/aliases, classification, representative locations | ISO mapping is not necessarily one-to-one; locations are not territories or recording sites |
| [ISO 639-3 tables](https://iso639-3.sil.org/code_tables/download_tables) | Standard language identifier and reference-name crosswalk | Not a coordinate source; availability/download format must be checked during import |
| [Omnilingual ASR corpus](https://huggingface.co/datasets/facebook/omnilingual-asr-corpus) | Additional corpus metadata; dataset documentation describes a `glottocode` column | Optional enrichment; neither recordings nor their locations were examined in this research |
| [`per_language_results_table_7B_llm_asr.csv`](../per_language_results_table_7B_llm_asr.csv) | `Language`, `Training Hours`, `CER`, joined by exact language-script token | README associates this table with original 7B results; do not present as measured V2 or local-deployment accuracy |

The model source revision used by the current Runpod bootstrap is
`81f51e224ce9e74b02cc2a3eaf21b2d91d743455`. Future catalogs should record the
revision from which their supported-token list was generated.

## What the globe inspection established

The page HTML loads this public asset:

`https://aidemos.atmeta.com/omnilingualasr/assets/index-6b06d2b4.js`

The downloaded asset SHA-256 was:

`b4c9411f1e6b099f34a2eedd34f31b5d9952bc9367163abfda7388f1e32ea927`

The inspected bundle embeds a language array named `M9` (a build-specific,
minified identifier, not a stable API). Its globe rendering reads each record's
`latitude` and `longitude` through `pointLat` and `pointLng`. Search uses `name`
and `iso639P3code`. The inspected coordinate path does not require a separate
coordinate-service request; this does not imply the entire site has no APIs.

The Matsés record contained:

```json
{
  "iso639P3code": "mcf",
  "mms_version": "omniasr",
  "language_family": "Pano-Tacanan",
  "scripts": ["Latn"],
  "latitude": -5.73914,
  "longitude": -72.6281,
  "name": "Matsés",
  "corpus": "omsf",
  "vitality": "Vulnerable"
}
```

The [Glottolog Matsés record](https://glottolog.org/resource/languoid/id/mats1244)
identifies `mcf` and `mats1244`. Its embedded map data contains exactly the same
latitude/longitude. The local tokenizer table contains `mcf_Latn` at index 887.
That numeric index is not an ISO identifier or a portable language ID.

**Confirmed:** the Meta point and inspected Glottolog point match for Matsés.
**Inference:** the globe likely uses Glottolog-derived coordinate metadata.
**Not established:** direct import versus an intermediary, source release,
coverage-wide match, collection date, or provenance of every name/vitality field.
No `Glottolog` attribution or source-map URL was found in the inspected bundle.
The Meta vitality label must not be treated as equivalent to Glottolog's current
endangerment classification without checking definitions and dates.

The temporary downloaded bundle is not a durable repository asset. The URL and
hash above identify the inspected build; no full bundle is vendored here. A
future importer needs a pinned, legally reusable source snapshot rather than a
dependency on minified variable names or a mutable website build.

## Proposed cross-source catalog

Use the model-supported token list as the base, not every point on Meta's globe
or every Glottolog language. Split at the last underscore to obtain language
identifier and script, preserving the original token unchanged. Treat the ISO
interpretation as a join candidate to validate, not an assumption for all tokens.

```text
supported model token -> language identifier + script
                     -> ISO name / aliases
                     -> Glottolog candidate(s) -> representative location(s)
                     -> Meta record for comparison / optional enrichment
```

Suggested catalog entry (illustrative contract, not an implemented file):

```json
{
  "model_token": "mcf_Latn",
  "iso639_3": "mcf",
  "script": "Latn",
  "display_name": "Matsés",
  "glottocodes": ["mats1244"],
  "locations": [{
    "latitude": -5.73914,
    "longitude": -72.6281,
    "kind": "representative_language_location",
    "source": "glottolog",
    "source_record": "mats1244"
  }],
  "match_status": "reviewed",
  "provenance": {
    "name": {"source": "meta_globe", "snapshot_sha256": "b4c9411f1e6b099f34a2eedd34f31b5d9952bc9367163abfda7388f1e32ea927"},
    "location": {"source": "glottolog", "release": null},
    "support": {"source": "omnilingual_asr", "revision": "81f51e224ce9e74b02cc2a3eaf21b2d91d743455"}
  }
}
```

Record source URL, revision/release, retrieval date, checksum, license, and any
local override for each imported dataset. Preserve raw source fields separately
from normalized display values. A missing release in the example is unresolved
research, not permission to ship an unversioned catalog.

Join requirements:

- Exact identifiers first; no fuzzy name matching as an automatic authority.
- Multiple scripts for one language remain distinct valid model choices. A map
  point can open a language panel with script options rather than duplicate dots.
- Multiple Glottolog candidates stay explicit and reviewable; do not silently
  collapse languages, dialects, retired ISO codes, or macrolanguage relationships.
- Missing coordinates remain selectable in search/list, not plotted at `(0, 0)`.
- Validate finite coordinates and latitude/longitude ranges; use `[longitude,
  latitude]` for GeoJSON, unlike the named latitude/longitude record fields.
- Conflicting names or positions produce a review report. Prefer documented,
  community-reviewed overrides over changing raw source records.
- Keep coverage totals for exact matches, missing names, missing locations,
  ambiguous matches, and unsupported external entries.

## Location meaning, licensing, and community safeguards

[Glottolog's coordinate documentation](https://github.com/glottolog/glottolog/blob/master/SOURCES.md#language-locations)
describes representative points assembled from varied sources, including maps
and contributed observations. They can describe historical or demographic
locations. They are not authoritative community boundaries, precise settlements,
speaker locations, or where the ASR training recordings were made.

The inspected Glottolog site identifies CC BY 4.0 licensing. Check the exact
download release's license and include attribution before redistribution. Meta
website metadata has no verified redistribution license in this research; public
access does not itself grant reuse rights. Upstream code licensing does not
automatically license separate website data, photographs, or audio.

Community corrections and preferred names need an explicit review path. Do not
infer ethnicity, political boundaries, speaker counts, or current vitality from
a point. Avoid adding precise community/recording locations without authority.

## Suggested implementation sequence and acceptance checks

1. Build a pinned local catalog and mismatch report from the allowlist, ISO names,
   and Glottolog; compare Meta records where useful. Resolve licenses before
   vendoring data. Inspect multiple matches before claiming broad provenance.
2. Add readable, searchable labels to the current selector using that same
   catalog; preserve exact submitted model tokens and an unknown-name fallback.
3. Add map selection backed by the catalog, with keyboard-accessible list/search,
   mobile behavior, overlapping-point handling, and script selection. A map
   replaces visual selection, not the backend's language validation.
4. Verify Matsés label -> `mcf_Latn`, English and Portuguese, a multiscript
   language, ambiguous crosswalk, absent name/location, and out-of-range point.
5. Verify LLM submission contains the selected token and CTC submission contains
   no hint. Selecting a point must not upload audio or submit a billed job.
6. Show location caveats and attribution in the interface. Keep credentials and
   audio out of map assets; do not add browser geolocation requirements.

Existing Runpod endpoints and payload format need no redeployment solely for
names or map selection. Richer map views and metadata enrichment remain open.

## Implemented first version

- `language_map.py` normalizes the exact ISO-to-Glottolog join and renders a
  self-contained SVG/HTML map with named search, keyboard selection, zoom, and
  automatic/no-hint reset. Search supports names, codes, and script names.
- `scripts/build_language_catalog.py` verifies pinned Glottolog/Natural Earth
  input checksums before generating local `ui/catalog.json`, `ui/world_land.svg`,
  and `ui/provenance.json`. Catalog and outline independently regenerated byte
  for byte. No Meta bundle data is redistributed.
- Catalog: 1,672 supported language-script tokens; 1,635 mapped entries; 36
  unmatched name/ISO joins; one named entry without coordinates. Those 37 remain
  searchable and are not plotted at zero coordinates. Points represent tokens,
  not necessarily 1,635 distinct languages or communities.
- Actual entries use `name` and a nullable `location` object, plus ISO identifier,
  script/script name, candidate Glottocodes, and join status. The richer example
  contract above remains a proposal, not the exact shipped JSON schema.
- `app.py` has native Small/CTC and Large/LLM tabs, fixed-model submit callbacks,
  and a hidden compatibility path preserving public `/transcribe` inputs in
  audio/model/language order. LLM submission reads the synchronous map choice
  so a delayed selection response cannot submit the previous language hint.
- [Map verification](../deploy/MAP_VERIFICATION.md) separates real browser/routing
  checks with fake external inference from previously validated speech inference.

Next metadata work: review the 36 unmatched identifiers against ISO retirement
and macrolanguage tables, with explicit crosswalks and source provenance rather
than fuzzy automatic joins. Names and representative locations are not proof of
model accuracy for those languages.
