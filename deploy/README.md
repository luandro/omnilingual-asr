# Runpod deployment

The local Gradio app selects between two queue-based Runpod GPU endpoints. The
default remains `omniASR_CTC_1B_v2`; `omniASR_LLM_7B_v2` is the second choice.
CTC recognizes supported languages automatically and ignores language hints.
LLM accepts an optional language code to guide transcription.

## Local app

Put `RUNPOD_API_KEY` in the repository's `.env`. The CTC endpoint uses
`RUNPOD_ENDPOINT_ID` when set, then `endpoint_id` in `deployment-state.json`.
The LLM endpoint uses `RUNPOD_ENDPOINT_ID_7B` when set, then that model's entry
in the `endpoints` map. The API key stays in the local Python process.

```sh
python3 -m venv .venv-ui
.venv-ui/bin/pip install -r requirements-ui.txt
.venv-ui/bin/python app.py
```

Open http://127.0.0.1:7860. Upload or record audio, then choose the Small CTC or
Large LLM tab. The Large tab includes a searchable map and an automatic/no-hint
reset. Selecting a point or search result changes the language hint only; it
does not upload audio or start a transcription. The checked-in catalog loads
offline without importing GPU model dependencies. Input is limited to 6 MB
locally and 10 minutes in the worker;
uncompressed WAV can hit the size limit before the duration limit.
The worker splits recordings into 30-second chunks. Chunk boundaries can split
words; review long-audio transcripts around those boundaries. No word-level
timestamps are generated.

Audio leaves the local machine and is processed by Runpod. The API key remains
in the local Python process. Runpod retains completed asynchronous job results
for 30 minutes. The app binds to localhost by default and does not create a
public share.

## LAN access

`python app.py` always binds to `127.0.0.1`. To expose the UI on the local
network, set `HOST=0.0.0.0` (or `SERVER_NAME=0.0.0.0`):

```sh
HOST=0.0.0.0 .venv-ui/bin/python app.py
```

Then open `http://<your-machine-ip>:7860` from another device on the same LAN.

## Language catalog and map sources

`ui/catalog.json` is built from the exact supported-token allowlist and the
Glottolog 5.3 CLDF snapshot pinned in `ui/provenance.json`. Glottolog data is
licensed CC BY 4.0; the Natural Earth 1:110m world outline is public domain.
The provenance file records source revisions, retrieval date, source and output
hashes, attribution, and catalog coverage. Unmatched languages remain
searchable; ambiguous or missing locations are not plotted.

To regenerate, fetch the exact commit-pinned CSV and GeoJSON URLs in
`ui/provenance.json`, then run:

```sh
.venv-ui/bin/python scripts/build_language_catalog.py \
  --glottolog-csv /path/to/languages.csv \
  --world-geojson /path/to/ne_110m_land.geojson
```

## CTC endpoint: public runtime with startup installation

The CTC endpoint uses a public, digest-pinned PyTorch 2.8.0 / CUDA 12.6
runtime. `deploy/bootstrap.py` installs the exact upstream repository revision
`81f51e224ce9e74b02cc2a3eaf21b2d91d743455` and the serving dependencies at startup.
It embeds the local handler as code in the endpoint environment; no personal
API key is included in the image or bootstrap configuration.

```sh
python3 deploy/bootstrap.py create
# To update this deployment instead of creating another endpoint:
python3 deploy/bootstrap.py update 2wsnqm6tycznbh
```

A true cold start installs dependencies and downloads the checkpoint before
accepting work. This can take several minutes and is billed as worker time.
FlashBoot can retain the initialized worker and its cache, but is not a guarantee
that every subsequent request starts warm. The local app allows 20 minutes for
queue time, startup, and inference. No persistent network volume is billed.

## LLM 7B endpoint

The LLM 7B endpoint uses the same handler with `MODEL_CARD=omniASR_LLM_7B_v2`.
Create it from its dedicated template or update the existing endpoint with that
template:

```sh
python3 deploy/bootstrap.py create deploy/endpoint-7b.json
python3 deploy/bootstrap.py update 6kxhw59ss9q9ze deploy/endpoint-7b.json
```

The configured endpoint ID is `6kxhw59ss9q9ze`. It uses the `AMPERE_24` pool,
excludes the incompatible Blackwell MIG type, has 100 GB disk, FlashBoot, a
five-second idle timeout, zero minimum workers, and one maximum worker. The live
catalog quoted $0.69/hour of active compute at validation time; price and GPU
availability can change.

Live checks on 2026-09-29 passed with `eng_Latn`: direct API transcription of an
11-second recording returned the expected English speech in one chunk; a
55-second recording returned the expected repeated speech across two chunks.
An 11-second recording also passed through local Gradio with both CTC 1B and
LLM 7B selected. These checks establish the tested English fixtures, not
accuracy across other languages or recording conditions.

This route avoids uploading the multi-GB runtime and model layers over the local
connection. The baked image below is an optional alternative for reducing work
performed at worker startup; it is not required by the current deployment.
The image must be built and published before switching the endpoint to it.

## Optional baked image and endpoint

```sh
docker build -t luandrodd/omnilingual-asr:runpod-ctc-1b-v1 .
docker push luandrodd/omnilingual-asr:runpod-ctc-1b-v1
python3 deploy/control.py create deploy/endpoint.json
```

`deploy/endpoint.json` specifies the lowest-price 16 GB GPU pool, one maximum
worker, zero always-on workers, five-second idle timeout, and FlashBoot. No
network volume is attached. Checkpoint and tokenizer downloads populate the
fairseq2 cache during the image build, so the worker does not need to download
model weights at every start. `.env` is excluded from the image and Git.

For the baked image, the first request can take several minutes while Runpod pulls the image and
loads the model. Active compute is billed even during initialization and idle
timeout; zero minimum workers avoids continuously running a GPU. The selected
1B CTC variant fits the selected tier and has faster decoding
than the LLM models. Accuracy varies by language and recording quality.

The container pins PyTorch/torchaudio 2.8.0 CUDA 12.6 and fairseq2 0.6.0. These
native dependencies must remain compatible when updating the image.

## API contract

The CTC endpoint ID is `2wsnqm6tycznbh`; the LLM 7B endpoint ID is
`6kxhw59ss9q9ze`. Both IDs are recorded in `deployment-state.json`.

POST `https://api.runpod.ai/v2/ENDPOINT_ID/run` with a bearer API key. Both
models accept `audio_base64`; LLM can also receive a language code:

```json
{"input":{"audio_base64":"BASE64_WAV_OR_FLAC","language":"eng_Latn"}}
```

Poll GET `/status/JOB_ID` until `COMPLETED`, then read `output.text`. Failure
states are `FAILED`, `CANCELLED`, and `TIMED_OUT`. Do not automatically resubmit
a job after an ambiguous submission timeout, as that can duplicate billed work.

```sh
python3 deploy/smoke.py /path/to/audio.wav 'known words from the recording'
.venv-ui/bin/python deploy/gradio_smoke.py /path/to/audio.wav
.venv-ui/bin/python deploy/gradio_smoke.py /path/to/audio.wav --model omniASR_LLM_7B_v2 --language eng_Latn
.venv-ui/bin/python deploy/gradio_smoke.py /path/to/audio.wav PRECEDING_JOB_ID 'known words' --model omniASR_LLM_7B_v2 --language eng_Latn
```

The smoke check prints submission, state transitions, and the complete result.
An optional expected phrase checks recognizable speech rather than merely a
nonempty response. The 300M v2 CTC model failed the English speech fixture in
both this deployment and the unmodified local reference pipeline; it is not
the deployed model.
`deployment-state.json` contains public deployment identifiers, not credentials.
