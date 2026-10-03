---
name: workers-best-practices
description: >-
  Author and review the omnilingual-asr Cloudflare Worker proxy, D1 feedback,
  and production configuration. Use for deploy/matses-voice changes, Wrangler
  deployments, Runpod integration boundaries, and transcription/map browser
  regressions. Includes standalone workflows and operational pitfalls.
---

# Workers best practices for omnilingual-asr

This Python/fairseq2 repo has a small JavaScript edge proxy, not a TypeScript
Workers starter. Preserve working architecture; fix issues whose benefit clearly
outweighs churn. Repository paths below are relative to the repo root. Reference
links are relative to this skill; no sibling skill is required.

## Workflow

1. Read [project workflows](references/project-workflows.md) for the affected
   boundary. Trace static page → Worker → Runpod → Python handler, feedback → D1,
   or Gradio → model endpoint. Read whole relevant files, not only diffs.
2. Retrieve current official docs for APIs/configuration being changed. Use
   [review guidance](references/review.md) and [rules/examples](references/rules.md).
   Validate against installed schemas/types too: latest docs do not prove support
   in the pinned toolchain. Report retrieval failures rather than inventing APIs.
3. Verify locally first, then in the real runtime/bindings appropriate to the
   change. Mocks do not prove D1 persistence, production deployment or accuracy.
4. Report file:line evidence, impact, smallest justified fix, checks and limits.
   Distinguish implemented, locally verified, remotely verified and untested.

## Project rules

- Use Wrangler with `deploy/matses-voice/worker/wrangler.toml`. The recorded
  `cf deploy` stripped DB and broke feedback; do not use it for this Worker.
- Keep RUNPOD_API_KEY server-side; no keys in static HTML, Gradio config, logs,
  screenshots or command output. Use Worker secrets rather than config vars.
- Await required D1 inserts before success; use prepared statements/bound values.
  CORS is not authentication. Existing D1 rate limiting fails open and can leave
  billed submissions unprotected when DB is absent or failing.
- Bound bodies before buffering. Post-parse length checks do not bound memory.
  Validate upstream shapes/model identity and preserve terminal job failures.
- Await, return or use ctx.waitUntil for promises; void alone neither handles
  rejection nor extends lifetime. Do not destructure ctx. No request-scoped
  mutable globals; module constants are fine.
- Keep existing JavaScript and TOML unless a necessary feature requires change.
  Generate Env when introducing type checking; do not force TS migration or
  unconditional tsc into this JS package. Enable nodejs_compat only when needed.
  Compatibility-date upgrades require regression checks, not an age-only rule.
- Use Cloudflare bindings for D1; external Runpod HTTPS is appropriate. Add
  Queues/Workflows/Hyperdrive only for demonstrated needs, not checklist parity.
- Observability should use redacted metadata, never audio, transcripts,
  corrections, credentials or client IP logs. D1 intentionally stores feedback
  text and rate-limit IPs; do not repeat the stale claim that nothing persists.
- No automatic resubmission after ambiguous Runpod timeouts or terminal failure:
  duplicates can duplicate GPU charges. UI/map changes need no paid inference.

## Retrieval sources

- [Workers best practices](https://developers.cloudflare.com/workers/best-practices/workers-best-practices/)
- [D1 prepared statements](https://developers.cloudflare.com/d1/worker-api/prepared-statements/)
- [Wrangler commands](https://developers.cloudflare.com/workers/wrangler/commands/)
- [Compatibility dates](https://developers.cloudflare.com/workers/configuration/compatibility-dates/)
- [Runpod docs](https://docs.runpod.io/) for current management/job APIs

Use installed Wrangler schema for reproducibility and current docs/types to
identify drift. Record tool versions and unresolved mismatches. Dated repo
verification reports provide history, not proof of current remote state.
