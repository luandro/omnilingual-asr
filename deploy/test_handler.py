"""Worker boundary tests; model calls are mocked, audio decoding is real."""
import base64
import io
import unittest
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf

with patch("omnilingual_asr.models.inference.pipeline.ASRInferencePipeline"):
    import handler


def audio(seconds, sample_rate=16000, stereo=False, subtype="PCM_16"):
    waveform = np.full((seconds * sample_rate, 2 if stereo else 1), 0.5, dtype=np.float32)
    encoded = io.BytesIO()
    sf.write(encoded, waveform, sample_rate, format="WAV", subtype=subtype)
    return base64.b64encode(encoded.getvalue()).decode()


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = Mock()
        self.patch = patch.object(handler, "pipeline", self.pipeline)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_long_stereo_audio_is_chunked_and_downmixed(self):
        self.pipeline.transcribe.return_value = ["first", "second", "last"]
        with patch.object(handler, "MODEL", "omniASR_CTC_1B_v2"):
            result = handler.handler({"input": {"audio_base64": audio(61, stereo=True), "language": "eng_Latn"}})
        chunks = self.pipeline.transcribe.call_args.args[0]
        self.assertEqual([len(c["waveform"]) for c in chunks], [480000, 480000, 16000])
        self.assertTrue(all(c["waveform"].ndim == 1 for c in chunks))
        self.assertTrue(all(c["sample_rate"] == 16000 for c in chunks))
        self.assertEqual(self.pipeline.transcribe.call_args.kwargs, {"lang": None, "batch_size": 1})
        self.assertEqual(result["text"], "first second last")
        self.assertEqual(result["chunks"], 3)
        self.assertEqual(result["duration_seconds"], 61)
        self.assertFalse(result["language_conditioning_supported"])

    def test_language_hint_is_passed_for_each_llm_chunk(self):
        self.pipeline.transcribe.return_value = ["first", "second", "last"]
        with patch.object(handler, "MODEL", "omniASR_LLM_7B_v2"):
            result = handler.handler({"input": {"audio_base64": audio(61), "language": "eng_Latn"}})
        self.assertEqual(self.pipeline.transcribe.call_args.kwargs,
                         {"lang": ["eng_Latn", "eng_Latn", "eng_Latn"], "batch_size": 1})
        self.assertEqual(result["text"], "first second last")
        self.assertEqual(result["model"], "omniASR_LLM_7B_v2")
        self.assertTrue(result["language_conditioning_supported"])

    def test_duration_limit_precedes_model_call(self):
        with self.assertRaisesRegex(ValueError, "600 seconds"):
            handler.handler({"input": {"audio_base64": audio(601, sample_rate=8000, subtype="PCM_U8")}})
        self.pipeline.transcribe.assert_not_called()

    def test_invalid_base64_precedes_model_call(self):
        with self.assertRaises(ValueError):
            handler.handler({"input": {"audio_base64": "!not-base64!"}})
        self.pipeline.transcribe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
