# Deployment verification — 2026-09-29

Endpoint: `2wsnqm6tycznbh`. Source revision:
`81f51e224ce9e74b02cc2a3eaf21b2d91d743455`.

The live endpoint uses the public PyTorch image pinned in `bootstrap.py`, not
the unpublished Docker Hub image. Anonymous image access and successful worker
startup verify the original `IMAGE_AUTH_ERROR` is resolved.

Deployed model: `omniASR_CTC_1B_v2`, CUDA inference, bfloat16. The smaller
`omniASR_CTC_300M_v2` returned incorrect text for the English fixture both on
Runpod and through the unmodified local CPU/float32 reference pipeline. It was
rejected despite successful job status codes.

The fixture is the public JFK recording from
[whisper.cpp](https://github.com/ggml-org/whisper.cpp/blob/master/samples/jfk.wav).

| Check | Observed result |
| --- | --- |
| Direct API, 11-second speech | Expected “fellow americans” phrase; coherent full transcript; 1 chunk; 1,190 ms job execution |
| Direct API, fixture repeated to 55 seconds | Expected phrase and all five repetitions; 2 chunks; 854 ms job execution |
| Local Gradio upload, 11-second speech | Same coherent transcript through the running app callback |
| Local Gradio upload, 55-second speech | All five repetitions returned; expected-phrase assertion passes |
| Browser rendering | Upload, microphone, submit, and transcript controls present at localhost:7860 |
| Worker boundary tests | 3 pass: stereo downmix/chunking, duration rejection, invalid base64 rejection |
| Local Python compilation and diff whitespace | Pass |
| Local UI dependency consistency | `pip check` passes |
| Final endpoint health | Queue and in-progress counts 0; running workers 0; one idle/ready FlashBoot slot retained |
| Credential exclusions | `.env`, UI virtualenv, and deployment state ignored by Git; Docker copy excludes secrets |

The short API request's 330,599 ms delay included waiting across deployment
recycling and cold startup; it is not a clean cold-start benchmark. Initializing
workers incurs compute charges. Warm inference timings are not guarantees.

Live configuration verified: `AMPERE_16`, one GPU per worker, minimum workers 0,
maximum workers 1, idle timeout 5 seconds, FlashBoot enabled, disk 30 GB, no
network volume. The live catalog quoted $0.58/hour serverless compute for this
tier; prices and availability can change.

Only the English fixture is accuracy-validated here. Other languages, noisy
recordings, and speech crossing chunk boundaries require application-specific
testing. CTC provides no language conditioning; neither endpoint provides word-level timestamps.

## Improved LLM 7B v2 and shared Gradio

Added endpoint `6kxhw59ss9q9ze` with `MODEL_CARD=omniASR_LLM_7B_v2`,
using the same public digest-pinned runtime, source revision, and shared handler.
The existing CTC endpoint was not updated. The new worker initialized on an
RTX A5000 with CUDA and bfloat16; the checkpoint download was approximately
29.1 GiB. No Docker Hub image publication or registry credentials were required.

| New check | Observed result |
| --- | --- |
| LLM API, 11-second English fixture with `eng_Latn` | Coherent expected phrase; actual model identity matches; 1 chunk; 2,420 ms execution |
| LLM API, 55-second repeated fixture with `eng_Latn` | Coherent repetitions and expected phrase; 2 chunks; 7,823 ms execution |
| Shared Gradio, LLM selection with English hint | Coherent expected phrase through the real callback |
| Shared Gradio, default CTC selection | Coherent expected phrase through the real callback |
| Served Gradio configuration | Two model options, CTC default, language selector with automatic option and 1,672 supported codes |
| Client contract and UI configuration tests | 8 pass; HTTP mocked, not inference proof |
| Bootstrap configuration test | 1 pass; alternate template preserves default configuration |
| Worker boundary tests | 4 pass, including per-chunk LLM language propagation; model inference mocked |
| Original repository tests | 5 pass in a temporary compatible runtime container |
| Final endpoint queues | Both empty, no jobs in progress, no failed jobs |

LLM short job: `0d2592ba-db70-42fa-8d77-8799aab749bf-u1`.
LLM long job: `24572463-c661-4c15-8ced-466a0dc22a6b-u1`.
The initial short job had 200,745 ms queue/startup delay; the warm long job had
443 ms delay. These observations are not guaranteed latency or accuracy benchmarks.

Live LLM configuration: `AMPERE_24`, CUDA minimum 12.6, Blackwell 24 GB MIG
excluded for compatibility, one GPU, disk 100 GB, worker minimum 0 / maximum 1,
idle timeout 5 seconds, FlashBoot enabled, no network volume. Catalog quote:
$0.69/hour active serverless compute, versus $0.58/hour for the unchanged CTC
tier. Initialization and idle timeout are billed; pricing and GPU stock can change.

The current model/language selectors were checked through Gradio configuration
and real API-client uploads, not a fresh browser rendering check. English is the
only language validated with real speech. Gradio UI introspection tests emit
asyncio ResourceWarning notices despite passing.
