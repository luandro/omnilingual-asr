---
name: impeccable
description: Improve Omnilingual ASR interfaces, including the Gradio transcription UI, canvas/SVG language map, and Matsés voice page. Use for scoped design, UX, accessibility, responsive layout, interaction regression, or UI hardening; consult deployment guidance only when a UI change crosses the Runpod or Cloudflare proxy boundary.
license: Apache-2.0
---

# Impeccable for Omnilingual ASR

Deliver a complete, usable interface grounded in the existing product and the user's brief. Refinement preserves identity, factual copy, behavior, and scope; redesign changes the visual world while preserving product truth and working contracts. Missing PRODUCT.md or DESIGN.md does not make an existing interface greenfield.

## Project workflow

1. Read [reference/project.md](reference/project.md) first. It owns project paths, browser verification, runtime contracts, and deployment pitfalls. For a map task, also read repo-root `deploy/MAP_VERIFICATION.md`, including its superseding navigation section. For the voice page, inspect `deploy/matses-voice/README.md` and the actual proxy/schema.
2. Read the one command playbook below that fits the request, then inspect the target and incumbent CSS, tokens, assets, and relevant plans in `docs/superpowers/`. Use existing context files when present; do not create them merely to unblock a narrow fix.
3. Read [reference/craft-floor.md](reference/craft-floor.md) immediately before UI edits. The user's brief wins over generic style bans. Prefer Operate mode for transcription and language selection: clarity, keyboard access, and reliable task completion precede decoration. Read mode fits documentation; Persuade and Experience apply only to surfaces with those goals.
4. Implement the smallest complete change across the real caller and callback boundary. Preserve model tokens, attribution, no-hint behavior, and the distinction between local selection and billed inference.
5. Verify in bounded passes: desktop/mobile and interaction checks together, fix demonstrated defects in one batch, then confirm. Avoid endless cosmetic loops; unresolved correctness failures remain blockers and need targeted investigation. Report implemented, fixture-verified, live-verified, and hardware-tested evidence separately.

## Standalone operation and precedence

This directory contains the design playbooks; no sibling skill, npm installer, framework template, or external agent is required. `SKILL.src.md` mirrors this entrypoint; keep both aligned when editing. Repo paths are relative to the repo root; reference links are relative to this directory.

For optional helper commands, set `IMPECCABLE_SKILL_DIR` to the directory from which this skill was loaded (staged or installed). Keep cwd at the project root. Commands below mean design intents, not guaranteed shell commands.

The copied Node helpers currently import absent `scripts/lib/` modules. They are retained as operational source, not a functioning mandatory toolchain. Do not run `context.mjs`, detector/hooks, live servers, pinning, or doctor as setup; read context/source directly and use browser-harness. If explicitly asked to repair helpers, inspect transitive imports and validate the entire dependency closure first. A syntax check alone does not establish runtime readiness. Do not fetch an installer or replace this project skill as a side effect.

Project workflow and user scope override generic playbook instructions to initialize context, persist critique files, run helpers, change hooks, require handoffs, or use another browser tool. Under read-only or directory-limited work, do not write reports or temporary artifacts outside the authorized path. Do not spawn agents unless requested. Optional agents under `agents/` supply role guidance, not dependencies. No implicit deploy, paid job, remote D1 write, or GPU configuration change follows from a design request.

Use browser-harness CDP for browser interaction; the standalone commands and fallback are in [reference/project.md](reference/project.md). An agent-browser skill is optional and does not replace the repo's CDP workflow.

## Commands

| Command | Category | Description | Reference |
|---|---|---|---|
| `craft [feature]` | Build | Deprecated alias for an ordinary new-work request | [reference/craft.md](reference/craft.md) |
| `shape [feature]` | Build | Plan UX/UI before writing code | [reference/shape.md](reference/shape.md) |
| `init` | Build | Capture durable product context in PRODUCT.md | [reference/init.md](reference/init.md) |
| `document` | Build | Generate DESIGN.md from existing project code | [reference/document.md](reference/document.md) |
| `extract [target]` | Build | Pull reusable tokens and components into design system | [reference/extract.md](reference/extract.md) |
| `critique [target]` | Evaluate | UX design review with heuristic scoring | [reference/critique.md](reference/critique.md) |
| `audit [target]` | Evaluate | Technical quality checks (a11y, perf, responsive) | [reference/audit.md](reference/audit.md) · native: [reference/audit.native.md](reference/audit.native.md) |
| `polish [target]` | Refine | Final quality pass before shipping | [reference/polish.md](reference/polish.md) |
| `bolder [target]` | Refine | Amplify safe or bland designs | [reference/bolder.md](reference/bolder.md) |
| `quieter [target]` | Refine | Tone down aggressive or overstimulating designs | [reference/quieter.md](reference/quieter.md) |
| `distill [target]` | Refine | Strip to essence, remove complexity | [reference/distill.md](reference/distill.md) |
| `harden [target]` | Refine | Production-ready: errors, i18n, edge cases | [reference/harden.md](reference/harden.md) |
| `onboard [target]` | Refine | Design first-run flows, empty states, activation | [reference/onboard.md](reference/onboard.md) |
| `animate [target]` | Enhance | Add purposeful animations and motion | [reference/animate.md](reference/animate.md) |
| `colorize [target]` | Enhance | Add strategic color to monochromatic UIs | [reference/colorize.md](reference/colorize.md) |
| `typeset [target]` | Enhance | Improve typography hierarchy and fonts | [reference/typeset.md](reference/typeset.md) |
| `layout [target]` | Enhance | Fix spacing, rhythm, and visual hierarchy | [reference/layout.md](reference/layout.md) |
| `delight [target]` | Enhance | Add personality and memorable touches | [reference/delight.md](reference/delight.md) |
| `overdrive [target]` | Enhance | Push past conventional limits | [reference/overdrive.md](reference/overdrive.md) |
| `clarify [target]` | Fix | Improve UX copy, labels, and error messages | [reference/clarify.md](reference/clarify.md) |
| `adapt [target]` | Fix | Adapt for different devices and screen sizes | [reference/adapt.md](reference/adapt.md) · native: [reference/adapt.native.md](reference/adapt.native.md) |
| `optimize [target]` | Fix | Diagnose and fix UI performance | [reference/optimize.md](reference/optimize.md) |
| `live` | Iterate | Visual variant mode: pick elements in the browser, generate alternatives | [reference/live.md](reference/live.md) |

## Routing and finish

An explicit or clearly implied command selects its playbook. With no target or intent, offer two or three concrete choices grounded in the visible project; do not auto-run a redesign. Otherwise perform the requested improvement directly. New surfaces can use [reference/new-work.md](reference/new-work.md) for direction; its random concept/helper mechanics are optional here, and pinned aesthetics take precedence.

Finish with concise changes, why they help, checks actually completed, and material verification limits. Do not turn screenshots, green mocks, historical evidence, HTTP 200, or deployment configuration into claims of current end-to-end transcription accuracy.
