# Omnilingual ASR deployment case study

Historical evidence: deployment on 2026-09-29, upstream source revision
`81f51e224ce9e74b02cc2a3eaf21b2d91d743455`, package 0.2.0. These are tested
examples, not mandatory choices or promises about later releases.

## Library versus demo versus checkpoint

- `facebookresearch/omnilingual-asr` supplies the Python inference/training
  library and multiple CTC, LLM, and Unlimited model variants. The checked-out
  upstream model repository had no Gradio application; this project now has `app.py`.
- `facebook/omniasr-transcriptions` is a separate Hugging Face Docker Space
  application: React/Vite frontend, Flask backend, language selection, media
  processing, forced alignment, and subtitles. Its inference wrapper imports
  `omnilingual_asr`; it is not a separate model family.
- The Space's published code defaults to `omniASR_LLM_7B` through `MODEL_NAME`;
  deployment environment settings can override it. Its README also mentions
  1B defaults, so prefer executable configuration over contradictory prose and
  do not claim to know hidden hosted environment overrides.
- A newly written Gradio client with `omniASR_CTC_1B_v2` is not feature-equivalent
  to that Space. If the user wants the original demo, reuse/adapt its application
  source and retain required backend capabilities rather than silently choosing
  CTC and omitting language selection or subtitles.

## Matching native runtime

The tested combination was Python 3.11, torch/torchaudio 2.8.0 CUDA 12.6,
fairseq2 0.6.0, `runpod==1.8.1`, and `soundfile==0.13.1`. Matching torch and
torchaudio versions and the fairseq2 native wheel's torch/CUDA ABI is essential.
Use the appropriate native wheel index, not only the default package index:

```sh
pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
pip install 'fairseq2[arrow]==0.6.0' --extra-index-url https://fair.pkg.atmeta.com/fairseq2/whl/pt2.8.0/cu126
```

OS packages included libsndfile, build-essential, and cmake; the Git bootstrap
also required git. KenLM builds consumed part of startup. Run `pip check` AND
native imports; dependency consistency alone does not prove ABI compatibility.

The public base was `pytorch/pytorch:2.8.0-cuda12.6-cudnn9-runtime`, pinned to
`sha256:dab81780fd94483b67b4b5679cc0024939b08e48540d39476d284cb29002ed69`.
Inspect public manifest, Python version, default entrypoint/CMD, and anonymous
access before reusing any image; names alone do not establish compatibility.

Do not blindly add AMPERE_24 as a fallback: the catalog included a Blackwell
MIG 24GB product in that pool. CUDA 12.6 PyTorch wheels did not provide the
needed Blackwell sm_120 support. Filter actual GPUs by architecture/runtime,
not simply pool label, memory, or minimum driver CUDA version.

## Model selection and quality evidence

- The first LLM Unlimited 300M baked checkpoint was approximately 6.5GB; its
  image was approximately 14GB and the local push was cancelled before manifest
  publication due to low upload throughput. A local image existed, not a
  published registry tag. This did not demonstrate that LLM inference failed.
- CTC 300M v2 downloaded approximately 1.3GB and completed the API job, but
  returned mostly whitespace and an unrelated character for an English JFK
  speech fixture. The unmodified CPU/float32 reference pipeline reproduced it;
  blaming the UI, downmix, GPU precision, or worker handler was unsupported.
  This is a fixture/version-specific finding, not a universal CTC 300M ban.
- CTC 1B v2 (approximately 3.9GB decimal / 3.63GiB checkpoint) passed on the
  same AMPERE_16 tier. The 11-second recording produced coherent expected words;
  a 55-second repeated fixture passed across two chunks. Both lengths also
  passed through the running local Gradio callback. Job execution was about
  1,190ms and 854ms respectively; do not generalize timings to other inputs.
- Only English was quality-validated. Test the user's languages, noise, chunk
  boundaries, and domain before recommending an accuracy-equivalent replacement.

## Language and audio behavior

- CTC ignores the `lang` argument; adding an enabled dropdown to a CTC-only app
  misleadingly implies conditioning. LLM models accept language/script codes
  such as `eng_Latn`, and upstream recommends using known codes for quality.
  Populate options from installed supported language IDs, not a hand-picked
  list falsely presented as complete. Feature/model changes require disclosure.
- Non-streaming CTC and standard LLM inference in this version accepted at most
  40 seconds per sample. Unlimited LLM variants provide a different long-audio
  path. The observed CTC handler used 30-second segments and batch size 1;
  segmentation can cut words and does not supply word-level timestamps.
- The pipeline accepts file paths, encoded bytes, or decoded dictionaries:
  `{"waveform": float_array_or_tensor, "sample_rate": rate}`. Plain floating
  NumPy arrays are not encoded audio; use the dictionary representation. The
  pipeline handles resampling/normalization, so preserve the true sample rate.
- SoundFile decoding used float32, `always_2d=True`, and channel averaging to
  mono before segmentation. The example bounded encoded input to 8,000,000
  characters, local file size to 6,000,000 bytes, and duration to 600 seconds.
  Validate base64 and duration before expensive model calls. These are chosen
  application bounds, not model or Runpod universal limits.
- Unit tests mocked model calls but decoded real audio, checking 61-second
  stereo chunk sizes 30/30/1 seconds, mono shape, rate, malformed base64, and
  over-duration rejection. They were not evidence of GPU quality.

## Prefetch pitfalls

Prefetch both checkpoint and tokenizer when baking an image. In fairseq2 0.6.0,
the card checkpoint field is a string; reading it directly with `as_(Uri)` was
incorrect. The working pattern was:

```python
from fairseq2.assets import AssetDownloadManager, get_asset_store
from fairseq2.runtime.dependency import get_dependency_resolver
from fairseq2.utils.uri import Uri
from fairseq2.data.tokenizers.hub import load_tokenizer

card = get_asset_store().retrieve_card(model_name)
uri = Uri.maybe_parse(card.field("checkpoint").as_(str))
if uri is None:
    raise ValueError("Invalid checkpoint URI")
manager = get_dependency_resolver().resolve(AssetDownloadManager)
manager.download_model(uri, model_name)
load_tokenizer(model_name)
```

Initialize one `ASRInferencePipeline` on CUDA before starting the worker SDK;
reuse it across jobs. Expose model identity/chunk count in results so validation
can detect stale releases or accidental model switches. Keep the baked model,
handler default, endpoint environment, and deployment state consistent.

## Sources and local evidence

- https://github.com/facebookresearch/omnilingual-asr
- https://github.com/facebookresearch/omnilingual-asr/blob/main/src/omnilingual_asr/models/inference/README.md
- https://github.com/facebookresearch/fairseq2/tree/v0.6.0
- https://huggingface.co/spaces/facebook/omniasr-transcriptions/tree/main
- https://huggingface.co/spaces/facebook/omniasr-transcriptions/blob/main/server/env_vars.py
- https://huggingface.co/spaces/facebook/omniasr-transcriptions/blob/main/server/inference/mms_model_pipeline.py
- https://github.com/ggml-org/whisper.cpp/blob/master/samples/jfk.wav

Original workspace evidence and reusable code (may move):
`deploy/VERIFICATION.md`, `deploy/handler.py`, `deploy/bootstrap.py`,
`deploy/prefetch.py`, `deploy/smoke.py`, `deploy/gradio_smoke.py`,
`deploy/worker_logs.py`, `deploy/test_handler.py`, and root `app.py`/`Dockerfile`.
Paths are relative to the repository root. The skill references
capture the essential lessons without requiring that checkout to exist.
