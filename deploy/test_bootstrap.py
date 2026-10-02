"""Configuration isolation tests; no remote API calls."""
import json
import tempfile
import unittest
from pathlib import Path

import bootstrap


class BootstrapTests(unittest.TestCase):
    def test_second_template_selects_large_model_without_changing_default(self):
        small = bootstrap.configuration()
        template = json.loads((bootstrap.ROOT / "deploy/endpoint.json").read_text())
        template.update(name="test-large", disk=100)
        template["env"]["MODEL_CARD"] = "omniASR_LLM_7B_v2"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.json"
            path.write_text(json.dumps(template))
            large = bootstrap.configuration(path)
        self.assertEqual(large["name"], "test-large")
        self.assertEqual(large["disk"], 100)
        self.assertEqual(large["env"]["MODEL_CARD"], "omniASR_LLM_7B_v2")
        self.assertEqual(large["image"], bootstrap.IMAGE)
        self.assertIn("ASR_HANDLER_B64", large["env"])
        self.assertEqual(bootstrap.configuration(), small)


if __name__ == "__main__":
    unittest.main()
