# AGENTS.md

## Project Overview

Omnilingual ASR — open-source speech recognition for 1600+ languages (Meta AI
Research). Three loosely coupled deliverables share this repo:

1. **Python library** (`src/omnilingual_asr/`) — fairseq2/torch models,
   datasets, and inference pipeline (cards, datasets, models subpackages).
2. **Local Gradio UI** (`app.py`, `language_map.py`, `ui/`) — audio
   upload/recording against Runpod serverless endpoints, with a searchable
   language map (`ui/catalog.json` loads offline, no GPU deps).
3. **Deployments** (`deploy/`) — Runpod handler/bootstrap/smoke tooling, plus
   `deploy/matses-voice/`: a white-label static voice page (vanilla JS),
   a Cloudflare Worker proxy (D1 feedback, R2 audio), and Node tests.

Stack: Python 3.10–3.13 (`>=3.10,<3.14`), fairseq2 0.5.2–0.6.0, torch,
gradio 6.x, Cloudflare Workers (wrangler), Node ≥22 for tests (`node:test`,
no root `package.json`).

Code navigation: `graft/` is a generated repo map — `grep` its markdown nodes
for symbols/`file:line`, run `graft ask "<task>"`, or `graft callers <symbol>`
for the call graph.

## Setup Commands

Two environments with different weight. Do not mix them.

**Full library env (heavy — torch + fairseq2):**

```sh
sudo apt-get install libsndfile1          # audio support
pip install -e ".[dev,data]"              # library + dev/test tools
pip install runpod==1.8.1                 # not in pyproject; deploy/test_handler.py needs it (pin matches deploy/bootstrap.py)
```

CI installs `torch==2.5.1` (CPU wheel) and the fairseq2 nightly for pt2.5.1
first — see `.github/workflows/lint_and_test.yaml` if the resolver struggles.

**Light UI/test env (verified in this workspace):**

```sh
python3 -m venv .venv-ui
.venv-ui/bin/pip install -r requirements-ui.txt
.venv-ui/bin/pip install soundfile pytest   # test-only; not in requirements-ui.txt
```

**Secrets:** copy `.env.example` to `.env` (gitignored). It holds
`RUNPOD_API_KEY` and endpoint IDs. The key is server-side only — the Gradio
process reads it from `.env`, the Matsés Worker gets it as a Wrangler secret
binding (`npx wrangler secret put RUNPOD_API_KEY`). Never commit it, never
hardcode it, never log it, never expose it to browsers.

## Development Workflow

- Local UI: `.venv-ui/bin/python app.py` → http://127.0.0.1:7860.
  Binds to localhost by default; `HOST=0.0.0.0` for LAN. Details in
  `deploy/README.md`.
- Matsés page + mock Worker (no Runpod needed):

  ```sh
  cd deploy/matses-voice
  node test/mock-worker.mjs &                     # 127.0.0.1:8999
  python3 -m http.server 8000 --directory page
  ```

  Open `http://127.0.0.1:8000/?worker=http://127.0.0.1:8999&maxSec=4`.
  `MOCK_SCENARIO=queue|immediate|noerror` selects the `/status` script.
  Full manual-test matrix: `deploy/matses-voice/README.md`.

## Testing Instructions

**Light tier (no torch; both verified green in this workspace):**

```sh
.venv-ui/bin/python -m pytest deploy/test_app.py deploy/test_language_map.py deploy/test_bootstrap.py   # 17 pass
cd deploy/matses-voice && node --test "test/*.test.mjs"                                                 # 27 pass
```

**Heavy tier (requires the full library env):**

```sh
pytest tests/                # unit tests; tests/conftest.py imports torch
pytest deploy/test_handler.py   # Worker boundary tests; imports omnilingual_asr + runpod (model calls mocked)
```

Notes:

- Bare `pytest` runs only `tests/` (pyproject `testpaths`); `deploy/test_*.py`
  must be named explicitly.
- Do not run `pytest` at the repo root without the heavy env — collection
  fails immediately on `import torch`.
- Slow tests may be marked `@pytest.mark.slow` (see CONTRIBUTING.md); none
  currently are.
- Node tests need no install step; they mock `fetch`/DOM/audio and use a
  fake clock. They assert the loading timer, stage messages, and Worker
  `/status` shaping.

## Code Style

CI gates every PR on (order matters; see `.github/workflows/lint_and_test.yaml`):

```sh
isort --check .     # autofix: isort .
black --check .     # autofix: black .
flake8 .
mypy --show-error-codes --check-untyped-defs --ignore-missing-imports --implicit-optional --implicit-reexport .
```

- `pre-commit install` once; hooks run trailing-whitespace, black, isort,
  mypy, flake8 (`pre-commit run --all-files`).
- mypy is strict for `src` and `tests` (`[tool.mypy]` in pyproject).
- flake8 ignores `E`/`Y` (Black owns formatting); isort profile `black`.

## Build and Deployment

- **Runpod endpoints:** `deploy/README.md` — `deploy/bootstrap.py` creates or
  updates endpoints from `endpoint.json` / `endpoint-7b.json`; state in
  `deployment-state.json`.
- **Matsés Worker:** `cd deploy/matses-voice/worker && npx wrangler deploy`.
  D1 binding `DB` (database `matses-feedback`), R2 bucket `matses-audio`.
- **Matsés page:** `cd deploy/matses-voice && npx surge page https://matses-voz.surge.sh`
  (HTTPS is required for microphone access).

### Generated file — never hand-edit

`deploy/matses-voice/page/mcf/index.html` is built from
`page/template.html` + `langs/mcf.json` (run from `deploy/matses-voice/`):

```sh
node tools/build-page.mjs     # idempotent; run after ANY template/langs change
```

The build fails on unsubstituted `__TOKENS__` and on i18n strings containing
`"`, `'`, `<`, `>`, `\`, or newlines. `page/index.html` is a separate
hand-maintained standalone copy (hardcoded PT strings, no profile segment in
the status URL) — edit it directly, but keep its fix in sync with
`template.html`.

## Security Considerations

- Runpod API key is server-side only: `.env` for the Gradio process, a
  Wrangler secret binding for the Worker. Never in client payloads, browser
  JS, logs, or commits.
- Observability must not expose audio, transcripts, credentials, or IPs
  (standing constraint on Worker/page changes).
- Worker validates request bodies and rate-limits (`RATE` map in
  `worker/src/worker.js`); page never auto-resubmits after ambiguous
  failures.

## Pull Request Guidelines (from CONTRIBUTING.md)

1. Branch from `main`; add tests for new code; update docs when APIs change.
2. `pytest tests/` green; `isort . && black .` and `mypy && flake8 .` clean.
3. Clear commit messages: what changed and why.

## Project Skills

`.claude/skills/` holds repo-specific agent skills — load the matching one
before touching those areas: `runpod-deploy`, `cloudflare`,
`workers-best-practices`, `wrangler`, `agent-browser`, `impeccable`.

## Gotchas

- Two test tiers: light (`.venv-ui`, Node) vs heavy (torch/fairseq2). State
  which one you used when reporting test results.
- `deploy/test_handler.py` needs `runpod` plus the full package importable;
  its pipeline is mocked but module-level imports are real.
- The Gradio app reads `src/.../lang_ids.py` via AST on purpose — importing
  that package pulls GPU dependencies. Follow the same pattern when adding
  code that only needs the language list.
- Matsés Worker rate limits and the Runpod spending guard are deliberate —
  do not loosen them without an explicit request.
