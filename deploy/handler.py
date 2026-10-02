import base64
import io
import os

import runpod
import soundfile as sf
from omnilingual_asr.models.inference.pipeline import ASRInferencePipeline
from omnilingual_asr.models.wav2vec2_llama.lang_ids import supported_langs

MODEL = os.getenv("MODEL_CARD", "omniASR_CTC_1B_v2")
pipeline = ASRInferencePipeline(model_card=MODEL, device="cuda")


def handler(job):
    data = job["input"]
    encoded = data.get("audio_base64")
    if not isinstance(encoded, str) or not encoded or len(encoded) > 8_000_000:
        raise ValueError("Provide audio_base64, at most 8 MB encoded")
    audio = base64.b64decode(encoded, validate=True)
    with sf.SoundFile(io.BytesIO(audio)) as recording:
        duration = len(recording) / recording.samplerate
        if not 0 < duration <= 600:
            raise ValueError("Recording must be between 0 and 600 seconds")
        sample_rate = recording.samplerate
        waveform = recording.read(dtype="float32", always_2d=True).mean(axis=1)
    language = data.get("language") or None
    if language is not None and language not in supported_langs:
        raise ValueError("Unsupported language code")
    chunk_frames = sample_rate * 30
    chunks = [
        {"waveform": waveform[start:start + chunk_frames], "sample_rate": sample_rate}
        for start in range(0, len(waveform), chunk_frames)
    ]
    is_ctc = MODEL.startswith("omniASR_CTC_")
    texts = pipeline.transcribe(chunks,
        lang=[language] * len(chunks) if language and not is_ctc else None,
        batch_size=1)
    return {"text": " ".join(texts), "model": MODEL,
            "duration_seconds": duration, "chunks": len(chunks),
            "language_conditioning_supported": not is_ctc}


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
