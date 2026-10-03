---
name: runpod-deploy
description: Deploy and troubleshoot omnilingual-asr GPU inference on Runpod Serverless using deploy/bootstrap.py and REST management API v2. Use for endpoint creation and updates, image publication and IMAGE_AUTH_ERROR, fairseq2 compatibility, FlashBoot and cold-start costs, worker logs, speech smoke tests, and Gradio or Matsés voice client verification.
---

# Runpod deployment for omnilingual-asr

Deliver a callable, verified endpoint and a working requested client, not merely
a built image or a successful job status. Preserve the user's model and UI
requirements; an economical alternative is not automatically feature-equivalent.

## Scope and discovery

- Read local instructions, model requirements, and existing UI; preserve unrelated work.
  A Hugging Face Space can have a separate application repository even when the
  model repository contains no UI. Inspect the named demo before rebuilding it.
- Separate the model library, checkpoint variant, application, and hosting
  provider. Identify whether language conditioning, timestamps, video,
  subtitles, or long audio are required before choosing a smaller model.
- API credentials plus registry login can be sufficient; installing a Runpod
  CLI is not inherently necessary. Confirm deployment/spending authorization
  before creating endpoints or running billed tests. Keep other endpoints alone.
- Refresh official Runpod schemas, GPU stock/prices, image availability, and
  native dependency compatibility. Historical values below are examples.

Read [references/project-workflows.md](references/project-workflows.md) first for
repo commands and release gates, then [references/runpod.md](references/runpod.md)
for deployment mechanics. All references are bundled; no other installed skill
is required. Commands use the repository root unless explicitly stated.
For Omnilingual ASR, also read
[references/omnilingual-asr.md](references/omnilingual-asr.md).

## Decisions that matter

1. Choose the least expensive compatible GPU and model that pass representative
   quality tests. Memory fit, CUDA architecture support, throughput, cold-start
   expense, and required features all matter. Report any capability change.
2. For sporadic use, start with zero minimum workers, one maximum worker, a short
   idle timeout, and no unneeded persistent volume. Choose warm workers/storage
   only when latency and expected frequency justify their recurring cost.
3. Prefer a published, dependency-ready image for repeatable cold starts. If
   local uploads are prohibitively slow, a public pinned base with startup
   installation can unblock deployment; disclose that installation/download
   overhead is billed and repeats on true cold starts.
4. FlashBoot is a cache optimization, not a guarantee of warm service. Do not
   claim an idle/ready slot means continuous billing or free compute without
   checking provider semantics. Startup, inference, and active idle timeout are
   billable; retained state does not guarantee a warm worker. Refresh
   [pricing](https://docs.runpod.io/serverless/pricing) and
   [configuration semantics](https://docs.runpod.io/serverless/endpoints/endpoint-configurations).

## Verification and handoff

- Check publication/pullability before enabling an endpoint using a custom
  image. Successful local builds and partial pushes do not establish this.
- Verify actual deployed image, checkpoint, configuration, endpoint revision,
  and worker health after every material change; stale workers can use old code.
- Test malformed inputs and resource bounds separately from GPU inference.
- Submit a known speech fixture and assert expected spoken words. A nonempty
  transcript or `COMPLETED` status can still be wrong. Test longer recordings
  when chunking is provided, then the real local client callback and UI.
- Observe an empty queue and the idle transition after verification. Distinguish
  configured worker limits from observed worker records and billing guarantees.
- Hand off endpoint ID/API contract, restart command, actual model and features,
  approximate current active-compute cost, cold-start behavior, credential
  exclusions, and validation limits. Record reproducible evidence without keys.
- Stop on a missing authority, incompatible runtime, or repeated unexplained
  quality failure. Do not silently expand GPU spend, replace the user's model,
  delete unrelated resources, or keep retrying ambiguous submissions.
