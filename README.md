# Rubik Motion Lab

AI-assisted renderer for Rubik's Cube algorithms built on Manim.

## Current Status (2026-02-18)

- Cards workflow is active on FastAPI + vanilla HTML/JS.
- PLL flow is completed: grouped case catalog, active algorithm selection, custom algorithm support, draft/HD queue, and polling updates.
- Top recognizers are generated and stored by group (`F2L` / `OLL` / `PLL`).

## What This Project Does

Rubik Motion Lab turns cube formulas into polished animations with:

- robust formula parsing (`cubeanim.formula`)
- deterministic cube state preparation from inverse moves (`set_state` path)
- smooth move execution with easing and timing policy
- GUI-first workflow (`scripts/render_ui.py`) and optional CLI (`scripts/render_algo.py`)
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

`cubeanim` applies a runtime compatibility patch for `manim_rubikscube` automatically.

## Run GUI (Primary)

```bash
uv run python scripts/render_ui.py
```

## CLI (Optional)

```bash
uv run python scripts/render_algo.py --formula "R U R' U'" --name MyAlgo --group PLL --quality standard
```

## Web Cards (FastAPI + HTML/JS)

```bash
uv run python scripts/cards_api.py
```

Open `http://127.0.0.1:8008/`.

Run render worker in a second terminal:

```bash
uv run python scripts/cards_worker.py
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
python3 -m py_compile cubist.py cubeanim/*.py scripts/render_algo.py scripts/render_ui.py
PYTHONPATH=. uv run pytest -q
```

## Media Tracking Policy

Git tracks only curated showcase artifacts in `media/showcase/`.
All heavy render outputs in `media/videos/` are intentionally excluded.
