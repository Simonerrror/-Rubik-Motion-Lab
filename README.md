# Rubik Motion Lab

AI-assisted renderer for Rubik's Cube algorithms built on Manim.

## Current Status (2026-03-03)

- Trainer is now static-first (`trainer/`) and does not require `/api`.
- Trainer data is built into `trainer/data/catalog-v1.json` with recognizers in `trainer/assets/recognizers/**`.
- Render backend (`scripts/app/cards_api.py` + `scripts/app/cards_worker.py`) is preserved as legacy mode.
- Top recognizers are generated and stored by group (`F2L` / `OLL` / `PLL`).

## What This Project Does

Rubik Motion Lab turns cube formulas into polished animations with:

- robust formula parsing (`cubeanim.formula`)
- deterministic cube state preparation from inverse moves (`set_state` path)
- smooth move execution with easing and timing policy
- GUI-first workflow (`scripts/app/render_ui.py`) and optional CLI (`scripts/tools/render_algo.py`)
- render planning, naming conflict handling, and catalog persistence

## AI-Assisted Evolution

This repository intentionally preserves an incremental history:

1. one-shot baseline prototype
2. targeted fixes and behavior hardening
3. motion/visual polish
4. storage and DX refinement

See `docs/AI_ASSISTED_DEV_STORY.md` for commit-level details.

## Install

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

`manim-rubikscube` is installed from the local patched package in
`vendor/manim-rubikscube` for Manim `0.19.x` compatibility.

For browser smoke tests, install Playwright Chromium once:

```bash
uv run python -m playwright install chromium
```

## Run GUI (Primary)

```bash
uv run python scripts/app/render_ui.py
```

## CLI (Optional)

```bash
uv run python scripts/tools/render_algo.py --formula "R U R' U'" --name MyAlgo --group PLL --quality standard
```

## Trainer (static, no API)

Build static trainer catalog + recognizer assets:

```bash
just trainer-build
```

Serve locally:

```bash
just trainer-serve port=8011
```

Open `http://127.0.0.1:8011/`.

Mobile-first isolated entrypoint:

- `http://127.0.0.1:8011/mobile.html`

Profile transfer format:

- storage key: `cards_trainer_profile_v1`
- schema version: `1`
- codec: `base64url(gzip(json))`

CLI helper for payload export from local JSON:

```bash
just trainer-export input=trainer/profile.json
```

## Web Cards (FastAPI + HTML/JS)

Legacy scope for server-side queue + video rendering.

```bash
uv run python scripts/app/cards_api.py
```

Open `http://127.0.0.1:8008/`.

Run render worker in a second terminal:

```bash
uv run python scripts/app/cards_worker.py --workers 1 --manim-threads 1
```

Renderer backend selection (split-ready):

- default: local in-process renderer (`CUBEANIM_RENDER_BACKEND=local`)
- remote HTTP renderer: set
  - `CUBEANIM_RENDER_BACKEND=http`
  - `CUBEANIM_RENDER_API_URL=http://127.0.0.1:9010`
  - optional `CUBEANIM_RENDER_API_TIMEOUT_SEC=60`

HTTP contract expected by the cards worker:

- `POST /plan` -> `{ action, output_name, final_path, reason }`
- `POST /render` -> `{ output_name, final_path, action }`

Detailed split notes: `docs/RENDERER_SPLIT.md`.

## Render backend (legacy)

Legacy render path entrypoints are kept for API/worker deployments:

- `scripts/app/cards_api.py`
- `scripts/app/cards_worker.py`

Trainer UI at `trainer/` intentionally does not call `/api`.

Run the UI smoke suite against the running API:

```bash
just smoke-ui
```

Use a custom base URL if needed:

```bash
just smoke-ui base_url=http://127.0.0.1:8010
```

## Persistent Dev Sessions (No Copy-Paste Between Worktrees)

Use `tmux` + `just` to keep core processes alive and re-attach instantly per worktree:

```bash
just dev
```

- creates (or reuses) a worktree-specific tmux session
- starts `cards_api` and `cards_worker`
- re-attaches on the next run instead of relaunching everything

Useful commands:

```bash
just dev-ls
just dev-stop
just test
just render "R U R' U'" my_algo PLL draft
```

Run all worktrees from one place:

```bash
just dev-all
just dev-all-ls
just dev-all-stop
```

- `dev-all` starts detached sessions for every git worktree
- ports are assigned sequentially from `8008` (`8008`, `8009`, `8010`, ...)
- if present, shared interpreter `./.venv/bin/python` is reused for all worktrees
- override base port with `CUBEANIM_CARDS_BASE_PORT=8100 just dev-all`

Optional `tmuxp` preset:

```bash
just dev-tmuxp
```

## Render Contract

- Output path: `media/videos/<GROUP>/<QUALITY>/<NAME>.mp4`
- Quality folders: `draft | standard | high | final`
- Legacy quality aliases (`ql/qm/qh/qk`) are still accepted in input.

## Motion / Visual Defaults

- single move: `0.65s`
- double-turn move (`*2`): `1.7x` single move
- inter-move pause: `5%` of single move
- easing: `ease_in_out_sine`
- internal cubie faces: softened dark tone (not pure black)

## Quality Rule

Default for iterations is `draft`/`standard`.
Use `high`/`final` only for final export.

## Testing

```bash
python3 -m py_compile cubist.py cubeanim/*.py scripts/tools/render_algo.py scripts/app/render_ui.py scripts/app/cards_api.py scripts/app/cards_worker.py
PYTHONPATH=. uv run pytest -q
just smoke-ui
SMOKE_STRICT=1 PYTHONPATH=. uv run pytest -q tests/e2e/test_cards_trainer_smoke.py -s
```

## Deployment

Vercel static config is in `vercel.json` (serves `trainer/` with SPA fallback).

GitHub Pages flow:

1. `just trainer-build`
2. Copy `trainer/` contents to deployment root (`docs/` or `gh-pages` branch).
3. Publish as static site.

GitHub Actions auto-deploy:

- Workflow: `.github/workflows/deploy-trainer-pages.yml`
- Trigger: push to `main` when `trainer/**` changes (or manual `workflow_dispatch`)
- Source artifact: `trainer/`

## Media Tracking Policy

Git tracks only curated showcase artifacts in `media/showcase/`.
All heavy render outputs in `media/videos/` are intentionally excluded.
