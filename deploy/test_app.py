"""Local client contract tests; Runpod HTTP calls are mocked."""
import json
import inspect
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class TranscribeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.audio_path = Path(self.temp_dir.name) / "sample.wav"
        self.audio_path.write_bytes(b"wav fixture")
        self.state_path = Path(self.temp_dir.name) / "deployment-state.json"
        self.state_path.write_text(json.dumps({
            "endpoint_id": "small-id",
            "endpoints": {
                "omniASR_CTC_1B_v2": "small-id",
                "omniASR_LLM_7B_v2": "large-id",
            },
        }))
        self.state_patch = patch.object(app, "STATE_PATH", self.state_path, create=True)
        self.state_patch.start()
        self.addCleanup(self.state_patch.stop)
        self.env_patch = patch.dict(os.environ, {
            "RUNPOD_API_KEY": "test-key",
            "RUNPOD_ENDPOINT_ID": "",
            "RUNPOD_ENDPOINT_ID_7B": "",
        }, clear=False)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def mock_job(self, model, text="recognized speech"):
        return (
            unittest.mock.Mock(status_code=200, json=lambda: {"id": "job-id"}),
            unittest.mock.Mock(status_code=200, json=lambda: {
                "status": "COMPLETED",
                "output": {"text": text, "model": model},
            }),
        )

    def call_with_job(self, model, language=None):
        submit, status = self.mock_job(model)
        with patch.object(app.requests, "post", return_value=submit) as post, \
                patch.object(app.requests, "get", return_value=status):
            text = app.transcribe(str(self.audio_path), model=model, language=language)
        return text, post

    def test_routes_llm_and_sends_selected_language(self):
        text, post = self.call_with_job("omniASR_LLM_7B_v2", "eng_Latn")

        self.assertEqual(text, "recognized speech")
        self.assertEqual(post.call_args.args[0], "https://api.runpod.ai/v2/large-id/run")
        self.assertEqual(post.call_args.kwargs["json"]["input"]["language"], "eng_Latn")

    def test_routes_ctc_and_ignores_stale_language(self):
        text, post = self.call_with_job("omniASR_CTC_1B_v2", "eng_Latn")

        self.assertEqual(text, "recognized speech")
        self.assertEqual(post.call_args.args[0], "https://api.runpod.ai/v2/small-id/run")
        self.assertNotIn("language", post.call_args.kwargs["json"]["input"])

    def test_unknown_model_is_rejected_before_submission(self):
        with patch.object(app.requests, "post") as post:
            with self.assertRaises(app.gr.Error):
                app.transcribe(str(self.audio_path), model="unknown")
        post.assert_not_called()

    def test_missing_selected_endpoint_is_actionable(self):
        self.state_path.write_text(json.dumps({"endpoint_id": "small-id"}))

        with patch.object(app.requests, "post") as post:
            with self.assertRaisesRegex(app.gr.Error, "RUNPOD_ENDPOINT_ID_7B"):
                app.transcribe(str(self.audio_path), model="omniASR_LLM_7B_v2")
        post.assert_not_called()

    def test_legacy_endpoint_id_remains_ctc_fallback(self):
        self.state_path.write_text(json.dumps({"endpoint_id": "legacy-small"}))
        text, post = self.call_with_job("omniASR_CTC_1B_v2")

        self.assertEqual(text, "recognized speech")
        self.assertEqual(post.call_args.args[0], "https://api.runpod.ai/v2/legacy-small/run")

    def test_completed_result_must_match_selected_model(self):
        submit, status = self.mock_job("omniASR_CTC_1B_v2")
        with patch.object(app.requests, "post", return_value=submit), \
                patch.object(app.requests, "get", return_value=status):
            with self.assertRaisesRegex(app.gr.Error, "model identity"):
                app.transcribe(str(self.audio_path), model="omniASR_LLM_7B_v2")

    def test_ui_config_exposes_ordered_public_callback_and_supported_languages(self):
        demo = app.create_ui().queue()
        self.addCleanup(demo.close)
        config = demo.get_config_file()
        components = {component["id"]: component for component in config["components"]}
        audio_component = next(c for c in config["components"] if c["type"] == "audio")
        model_component = next(c for c in config["components"] if c.get("props", {}).get("label") == "Model")
        language_component = next(
            c for c in config["components"]
            if c.get("props", {}).get("label") == "Language hint (LLM only)"
        )
        callback = next(dependency for dependency in config["dependencies"] if dependency["api_name"] == "transcribe")

        self.assertEqual(callback["inputs"], [audio_component["id"], model_component["id"], language_component["id"]])
        self.assertEqual(callback["api_visibility"], "public")
        self.assertEqual(model_component["props"]["value"], app.CTC_MODEL)
        self.assertIn(("Large — LLM 7B v2", app.LLM_MODEL), model_component["props"]["choices"])
        language_values = {value for _, value in language_component["props"]["choices"]}
        self.assertIn("eng_Latn", language_values)
        self.assertIn("por_Latn", language_values)
        self.assertEqual(components[callback["outputs"][0]]["props"]["label"], "Transcript")

    def test_launcher_settings_match_installed_gradio_signature(self):
        demo = app.create_ui()
        self.addCleanup(demo.close)
        signature = inspect.signature(demo.launch)

        signature.bind(server_name="127.0.0.1", share=False)
        self.assertNotIn("flagging_mode", signature.parameters)


if __name__ == "__main__":
    unittest.main()
