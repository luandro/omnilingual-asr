# Runpod mechanics and failure lessons

Observed during an Omnilingual ASR deployment on 2026-09-29. Refresh schemas,
availability, prices, result retention, and dependency releases before reuse.

## Credentials and image publication

- Keep `RUNPOD_API_KEY` in an ignored `.env` or the process environment. Read it
  without printing values, shell tracing, command-line interpolation, or dumps
  of request headers. Redact credentials from HTTP errors and diagnostic output.
- Local `docker login` authorizes the local client; it does not supply private
  registry credentials to Runpod. A private image requires credentials in the
  endpoint's documented registry-authentication settings. Public images must
  have a real published manifest accessible anonymously.
- `IMAGE_AUTH_ERROR: repository is private or does not exist` is ambiguous.
  Resolve exact registry/namespace/tag, inspect completed push/manifest, and test
  anonymous access before assuming private permissions. Creating an endpoint
  before its image is published produced this error in the observed deployment.
- Suspend the affected deployment's worker allocation while correcting an
  unpublished image when authorized. Do not scale down unrelated endpoints.
- A Docker Hub CLI token may permit push but not Hub management-API repository
  creation. Do not confuse a management API 401 with a failed registry login.
- Multi-GB CUDA and checkpoint layers can overwhelm a slow upload connection.
  Estimate size/throughput early. A cancelled push does not publish the tag,
  even if some layers uploaded. Retain local artifacts; avoid destructive fixes.
- Use `.dockerignore` and explicit `COPY` scopes to exclude `.env`, Docker
  credentials, virtualenvs, Git, cache junk, and deployment state. Inspect the
  built image for secret exclusions and intended assets rather than trusting
  ignore rules alone.

## API pattern verified at the time

Management base: `https://api.runpod.io`; queue base: `https://api.runpod.ai`.
Use `Authorization: Bearer <key>`, JSON content type, and an explicit User-Agent
such as `project-deployer/1.0`. A urllib request initially received a Cloudflare
403 without a custom User-Agent; adding one worked. A 403 can have other causes;
inspect the response, permissions, and official endpoint rather than assuming.

Relevant management paths:

- GET `/v2/catalog/gpus?include=AVAILABILITY&product=SERVERLESS`
- GET/POST `/v2/serverless`
- GET/PATCH `/v2/serverless/{endpoint_id}`
- GET `/v2/serverless/{endpoint_id}/workers`
- GET `/v2/serverless/{endpoint_id}/workers/{worker_id}/logs`
  with `source=container&tail=12` (SSE stream)

Queue paths: POST `/v2/{id}/run`, GET `/v2/{id}/status/{job_id}`, and
GET `/v2/{id}/health`. Poll until `COMPLETED`, `FAILED`, `CANCELLED`, or
`TIMED_OUT`; preserve the returned job ID. Check current docs for retention.
Do not blindly repeat a POST after an ambiguous timeout: it can duplicate billed
work. A local polling timeout does not establish server-side cancellation.

Historical endpoint configuration example, not a current schema guarantee:

```json
{
  "name": "project-inference",
  "image": "PUBLIC_PUBLISHED_IMAGE_OR_DIGEST",
  "type": "QUEUE",
  "gpu": {"pools": ["AMPERE_16"], "count": 1, "minCudaVersion": "12.6"},
  "workers": {"min": 0, "max": 1, "idleTimeout": 5},
  "scaling": {"type": "QUEUE_DELAY", "queueDelay": 4},
  "timeout": 600000,
  "disk": 30,
  "flashboot": "FLASHBOOT",
  "env": {"MODEL_CARD": "PROJECT_MODEL_CARD"}
}
```

Do not copy create-only fields into PATCH without checking its accepted fields.
The observed helper excluded `name` and `type` from its update payload. Verify
the returned configuration, not just the request's intended values.

## Worker lifecycle and diagnostics

- Worker records can include cached idle slots, throttled workers, and stale
  releases even with max workers 1. Compare `endpointVersion`, `version`, and
  `isStale`, actual model in job output, queue health, and container startup.
- A configuration PATCH does not prove all warm workers immediately use it.
  In the observed release, explicitly setting max workers 0, waiting for the
  affected endpoint's worker list to become empty, then restoring max 1 cleared
  stale releases. This can interrupt jobs: obtain authority, account for queued
  and in-flight work, and cancel only authorized tests. Do not use reflexively.
- Throttling/stock delays and container boot failures are different. Consult
  current compatible GPU availability before widening the pool and disclose
  any cost increase. An API health summary can differ from the management list
  during transitions; inspect both rather than treating either as conclusive.
- Read logs with a deadline and bounded tail/output. SSE read timeout means the
  snapshot ended, not necessarily that the worker failed. Download progress can
  be joined with carriage returns: display the final `\r` segment to avoid
  reporting stale 0% progress. Redact credentials even in exceptions.

## Public-base bootstrap alternative

The working deployment used a public PyTorch CUDA image pinned by digest,
explicit `entrypoint: ["/bin/bash", "-lc"]`, and a `cmd` list containing a bash
startup script with `set -euo pipefail`. The script installed OS dependencies,
matching native wheels, an exact project Git revision, and the worker SDK;
`pip check` preceded handler execution. The handler code was passed via a
base64 environment field and compiled/executed in the container. Base64 is
encoding, not secrecy; never embed a personal API key in that field.

This route avoided the large local image upload but does dependency installation
and model downloading on true cold starts. Prefer publishing a baked image for
frequent requests or stricter reproducibility; dependency pins alone are not a
full transitive lock. Source pinning and digest pinning serve different purposes.

Prices observed: AMPERE_16 $0.58/hour serverless compute; AMPERE_24 $0.69/hour.
Active startup and idle timeout contribute to costs, not only inference. A
network volume trades recurring storage and regional constraints for persistent
cache; no volume was needed for the sporadic-use deployment. Catalog values and
availability are not commitments about future cost or capacity.

## Local Gradio integration

Use a small UI-only virtualenv (`gradio`, `requests`, `python-dotenv`) rather
than installing the GPU model locally. Bind localhost with sharing disabled.
Read the key server-side; never expose it to browser JavaScript or UI config.

The observed app used `gr.Audio(type="filepath", sources=["upload", "microphone"],
format="wav")`, a queued callback that base64-encoded audio, submitted `/run`,
polled status, and returned `output.text`. Adapt upload/body limits to API limits
and account for base64 expansion and Gradio format conversion. Worker validation
is still required; UI checks alone do not protect an API endpoint.

Test the real callback using `gradio_client.Client`, `handle_file`, and the
actual published API name; confirm expected speech, not merely nonempty output.
Browser inspection verifies rendered upload/microphone/output controls but is
not proof of GPU inference. Keep startup/polling deadlines explicit (20 minutes
was used here), and show the existing job ID when local waiting expires.

Official documentation entry points:
- https://docs.runpod.io/serverless/overview
- https://docs.runpod.io/serverless/workers/handlers/overview
- https://docs.runpod.io/serverless/endpoints/send-requests
- https://docs.runpod.io/serverless/endpoints/endpoint-configurations
