"""Language catalog and map selection behavior tests."""
import json
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

import app
from language_map import (
    build_catalog,
    language_point_positions,
    language_selection_event,
    render_language_map,
    search_languages,
    select_language,
)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.source = Path(self.temp_dir.name) / "languages.csv"
        self.source.write_text(
            "ID,Name,Latitude,Longitude,Glottocode,ISO639P3code,Level\n"
            "mats1244,Matsés,-5.73914,-72.6281,mats1244,mcf,language\n"
            "mats1245,Matsés dialect,-5.7,-72.6,mats1245,mcf,language\n"
            "abkh1242,Abkhaz,91,40,abkh1242,abk,language\n"
            "noco1234,Unlocated,,,noco1234,xyz,language\n"
            "stan1293,English,51,-1,stan1293,eng,language\n"
        )

    def test_catalog_keeps_allowlist_tokens_and_withholds_ambiguous_or_invalid_points(self):
        catalog, coverage = build_catalog(
            self.source,
            ["mcf_Latn", "mcf_Cyrl", "abk_Cyrl", "xyz_Latn", "abs_Latn"],
        )

        matses = next(entry for entry in catalog if entry["model_token"] == "mcf_Latn")
        self.assertEqual(matses["name"], "Matsés")
        self.assertEqual(matses["script"], "Latn")
        self.assertEqual(matses["glottocodes"], ["mats1244", "mats1245"])
        self.assertEqual(matses["match_status"], "ambiguous")
        self.assertIsNone(matses["location"])
        self.assertEqual(select_language(catalog, "mcf_Cyrl")["model_token"], "mcf_Cyrl")
        self.assertIsNone(select_language(catalog, None))

        invalid = next(entry for entry in catalog if entry["model_token"] == "abk_Cyrl")
        self.assertEqual(invalid["match_status"], "invalid_location")
        self.assertIsNone(invalid["location"])
        unlocated = next(entry for entry in catalog if entry["model_token"] == "xyz_Latn")
        self.assertEqual(unlocated["match_status"], "matched_no_location")
        self.assertIsNone(unlocated["location"])
        self.assertEqual(coverage["supported_tokens"], 5)
        self.assertEqual(coverage["unmatched_tokens"], 1)

    def test_unique_valid_language_point_and_search_return_exact_token(self):
        catalog, _ = build_catalog(self.source, ["mcf_Latn", "eng_Latn"])
        # The ambiguous ISO join does not leak either candidate coordinate.
        positions = language_point_positions(catalog)
        self.assertEqual(positions, {"eng_Latn": (51.0, -1.0)})
        self.assertEqual([row["model_token"] for row in search_languages(catalog, "mcf")], ["mcf_Latn"])
        self.assertEqual(search_languages(catalog, "Latn"), catalog)
        self.assertEqual(select_language(catalog, "mcf_Latn")["model_token"], "mcf_Latn")
        with self.assertRaises(ValueError):
            select_language(catalog, "not_supported")

    def test_builder_rejects_duplicate_allowlist_tokens_and_is_deterministic(self):
        with self.assertRaises(ValueError):
            build_catalog(self.source, ["mcf_Latn", "mcf_Latn"])
        first, first_coverage = build_catalog(self.source, ["xyz_Latn", "mcf_Latn"])
        second, second_coverage = build_catalog(self.source, ["xyz_Latn", "mcf_Latn"])
        self.assertEqual(json.dumps(first, ensure_ascii=False), json.dumps(second, ensure_ascii=False))
        self.assertEqual(first_coverage, second_coverage)

    def test_custom_html_click_event_updates_exact_token_and_reset(self):
        catalog, _ = build_catalog(self.source, ["mcf_Latn"])
        selected = app.gr.EventData(None, {"token": "mcf_Latn"})
        automatic = app.gr.EventData(None, {"token": None})

        self.assertEqual(language_selection_event(selected, catalog), "mcf_Latn")
        self.assertIsNone(language_selection_event(automatic, catalog))
        with self.assertRaises(ValueError):
            language_selection_event(app.gr.EventData(None, {"token": "unsupported"}), catalog)


class MapUiTests(unittest.TestCase):
    def test_map_points_have_names_but_are_skipped_in_tab_order(self):
        catalog = [entry for entry in app.LANGUAGE_CATALOG if entry["model_token"] == "eng_Latn"]
        markup = render_language_map(catalog, '<svg viewBox="0 0 1000 500"></svg>')

        class Buttons(HTMLParser):
            def __init__(self):
                super().__init__()
                self.points = []

            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if tag == "button" and "language-point" in attributes.get("class", "").split():
                    self.points.append(attributes)

        buttons = Buttons()
        buttons.feed(markup)
        self.assertEqual(len(buttons.points), 1)
        self.assertEqual(buttons.points[0].get("tabindex"), "-1")
        self.assertEqual(buttons.points[0].get("aria-label"), "English — eng_Latn")

    def test_matses_has_the_pinned_glottolog_location_and_exact_model_token(self):
        matses = next(entry for entry in app.LANGUAGE_CATALOG if entry["name"] == "Matsés")

        self.assertEqual(matses["model_token"], "mcf_Latn")
        self.assertEqual(matses["glottocodes"], ["mats1244"])
        self.assertEqual(
            (matses["location"]["latitude"], matses["location"]["longitude"]),
            (-5.73914, -72.6281),
        )

    def test_native_model_tabs_preserve_public_audio_model_language_order(self):
        demo = app.create_ui()
        self.addCleanup(demo.close)
        config = demo.get_config_file()
        components = {component["id"]: component for component in config["components"]}
        callback = next(dependency for dependency in config["dependencies"] if dependency["api_name"] == "transcribe")
        audio_id, model_id, language_id = callback["inputs"]

        self.assertEqual(components[audio_id]["type"], "audio")
        self.assertEqual(components[model_id]["props"]["value"], app.CTC_MODEL)
        self.assertIsNone(components[language_id]["props"].get("value"))
        self.assertEqual(callback["api_visibility"], "public")
        self.assertTrue(any(c["type"] == "tabs" for c in config["components"]))
        map_component = next(c for c in config["components"] if c["type"] == "html")
        self.assertFalse(map_component["props"]["apply_default_css"])
        self.assertNotIn("<script src=", json.dumps(config))

    @unittest.skipUnless(shutil.which("node"), "Node.js is required to execute Gradio's input transform")
    def test_llm_submission_reads_the_synchronous_map_selection(self):
        demo = app.create_ui()
        self.addCleanup(demo.close)
        config = demo.get_config_file()
        components = {component["id"]: component for component in config["components"]}
        audio_id = next(component_id for component_id, component in components.items() if component["type"] == "audio")
        language_id = next(
            component_id for component_id, component in components.items()
            if component.get("props", {}).get("label") == "Language hint (LLM only)"
        )
        transcript_id = next(
            component_id for component_id, component in components.items()
            if component.get("props", {}).get("label") == "Transcript"
        )
        submission = next(
            dependency for dependency in config["dependencies"]
            if dependency["inputs"] == [audio_id, language_id]
            and dependency["outputs"] == [transcript_id]
        )
        self.assertIsInstance(submission.get("js"), str)
        script = f"""
const transform = eval({json.dumps(submission['js'])});
const map = {{dataset: {{selectedToken: 'mcf_Latn'}}}};
global.document = {{querySelector: selector => selector === '#language-map-control .language-map' ? map : null}};
const audio = {{path: 'fixture.wav'}};
const selected = transform(audio, 'old_Latn');
if (selected[0] !== audio || selected[1] !== 'mcf_Latn') process.exit(2);
map.dataset.selectedToken = '';
const automatic = transform(audio, 'mcf_Latn');
if (automatic[0] !== audio || automatic[1] !== null) process.exit(3);
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
