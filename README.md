# Rubik Motion Lab

Repository for the static Rubik trainer, local cards service/runtime, and a local-only Manim authoring tool.

## Layout

- `apps/trainer` — primary static trainer (public root `/`)
- `apps/cards-worker` — local artifact queue worker
- `apps/render-ui` — local GUI renderer
- `packages/cubeanim/src/cubeanim_domain` — pure shared domain logic
- `packages/cubeanim/src/cubeanim_renderer` — Manim-only local renderer stack
- `packages/cubeanim/src/cubeanim` — compatibility facade for legacy imports
- `tools` — CLI tools (`render_algo`, `cards_runtime`, trainer build, F2L import)
- `legacy/cards-web` — frozen deprecated web UI snapshot
- `db/cards/{schema.sql,seed.sql}` — DB schema/seed source
- `apps/cards-api` — deprecated compatibility shim, excluded from active workflow

Detailed structure and migration notes: `docs/REPO_LAYOUT.md`.
Trainer UX manual: `docs/TRAINER_MANUAL.md`.
Local renderer architecture: `docs/RENDERER_SPLIT.md`.

## Install

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Optional for browser smoke:

```bash
uv run python -m playwright install chromium
```

## Main commands

```bash
uv run python apps/render-ui/main.py
uv run python tools/render_algo.py --formula "R U R' U'" --name MyAlgo --group PLL --quality standard
uv run python apps/cards-worker/main.py --workers 1 --manim-threads 1
uv run python tools/cards_runtime.py reset-runtime
```

Or use `just`:

```bash
just ui
just render "R U R' U'" my_algo PLL draft
just worker
just cards-reset-runtime
```

## Trainer build

```bash
just trainer-build
just trainer-manual
just trainer-serve port=8011
```

`trainer-build` generates `apps/trainer/data/catalog-v1.json`, syncs recognizers, and prunes unused recognizer assets.

## Local renderer

- Manim is no longer treated as a remote/backend renderer for the trainer.
- The local renderer writes artifacts under `data/local-renderer/`.
- `apps/render-ui` and `tools/render_algo.py` are private authoring tools and are not part of the web runtime.

## Cards runtime

- Active cards flow is local-only: `CardsService`, runtime DB/recognizers, and `apps/cards-worker`.
- Trainer smoke must not hit `/api/*`; the static trainer reads catalog/assets directly.
- Runtime admin operations should use `tools/cards_runtime.py`, not the deprecated HTTP layer.

## Tests

```bash
PYTHONPATH=packages/cubeanim/src uv run pytest -q
SMOKE_STRICT=1 PYTHONPATH=packages/cubeanim/src uv run pytest -q tests/e2e/test_cards_trainer_smoke.py -s
```

- `tests/legacy` and the deprecated cards API shim are out of the active test perimeter.
- Legacy cards web UI is archived under `legacy/cards-web` and excluded from active flow.
