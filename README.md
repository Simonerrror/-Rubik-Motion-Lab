# Rubik Motion Lab

Repository for Rubik animation/render tooling and static trainer cards.

## Layout

- `apps/trainer` — primary static trainer (public root `/`)
- `apps/cards-api` — FastAPI backend (no embedded web UI)
- `apps/cards-worker` — render queue worker
- `apps/render-ui` — local GUI renderer
- `packages/cubeanim/src/cubeanim` — shared Python core
- `tools` — CLI tools (`render_algo`, trainer build, F2L import)
- `legacy/cards-web` — frozen deprecated web UI snapshot
- `db/cards/{schema.sql,seed.sql}` — DB schema/seed source

Detailed structure and migration notes: `docs/REPO_LAYOUT.md`.

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
uv run python apps/cards-api/main.py
uv run python apps/cards-worker/main.py --workers 1 --manim-threads 1
```

Or use `just`:

```bash
just ui
just render "R U R' U'" my_algo PLL draft
just api
just worker
```

## Trainer build

```bash
just trainer-build
just trainer-serve port=8011
```

`trainer-build` generates `apps/trainer/data/catalog-v1.json`, syncs recognizers, and prunes unused recognizer assets.

## Tests

```bash
PYTHONPATH=packages/cubeanim/src uv run pytest -q
SMOKE_STRICT=1 PYTHONPATH=packages/cubeanim/src uv run pytest -q tests/e2e/test_cards_trainer_smoke.py -s
```

## API notes

- `GET /` on cards-api returns JSON health payload: `{"ok": true, "service": "cards-api"}`
- Runtime assets are served via `/assets` from `data/cards/runtime`
- Legacy cards web UI is archived under `legacy/cards-web` and excluded from active flow
