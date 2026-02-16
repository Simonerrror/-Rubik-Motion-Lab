# Rubik Motion Lab

AI-assisted renderer for Rubik's Cube algorithms built on Manim.

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
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`cubeanim` applies a runtime compatibility patch for `manim_rubikscube` automatically.

## Run GUI (Primary)

```bash
source .venv/bin/activate
python scripts/render_ui.py
```

## CLI (Optional)

```bash
source .venv/bin/activate
python scripts/render_algo.py --formula "R U R' U'" --name MyAlgo --group PLL --quality standard
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
source .venv/bin/activate
python -m pytest -q
```

## Media Tracking Policy

Git tracks only curated showcase artifacts in `media/showcase/`.
All heavy render outputs in `media/videos/` are intentionally excluded.
