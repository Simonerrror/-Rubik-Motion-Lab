# Rubik Motion Lab

Repository for the static Rubik trainer and local cards runtime.

## Layout

- `apps/trainer` — primary static trainer (public root `/`)
- `packages/cubeanim/src/cubeanim_domain` — temporary in-repo mirror of the shared domain package
- `packages/cubeanim/src/cubeanim` — compatibility facade for legacy imports
- `tools` — CLI tools (`cards_runtime`, trainer build, F2L import)
- `legacy/cards-web` — frozen deprecated web UI snapshot
- `db/cards/{schema.sql,seed.sql}` — DB schema/seed source
- `apps/cards-api` — deprecated compatibility shim, excluded from active workflow

Detailed structure and migration notes: `docs/REPO_LAYOUT.md`.
Trainer UX manual: `docs/TRAINER_MANUAL.md`.
Local split notes: `docs/RENDERER_SPLIT.md`.

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
uv run python tools/cards_runtime.py reset-runtime
```

Or use `just`:

```bash
just trainer-build
just cards-reset-runtime
```

## Trainer build

```bash
just trainer-build
just trainer-manual
just trainer-serve port=8011
```

`trainer-build` generates `apps/trainer/data/catalog-v2.json`, syncs recognizers, and prunes unused recognizer assets.

## Local split

- Trainer is fully JS for formula parsing, start-state resolution, timeline assembly, and playback.
- The Python renderer has been moved out of the active repo graph into a sibling local mini-repo.
- `cubeanim_domain` is being externalized the same way; the in-repo package is a temporary mirror until the dependency is fully pinned.

## Cards runtime

- Active cards flow is local-only: `CardsService`, runtime DB, recognizers, and trainer catalog build.
- Trainer smoke must not hit `/api/*`; the static trainer reads catalog/assets directly.
- Runtime admin operations should use `tools/cards_runtime.py`, not the deprecated HTTP layer.

## Tests

```bash
PYTHONPATH=packages/cubeanim/src uv run pytest -q
SMOKE_STRICT=1 PYTHONPATH=packages/cubeanim/src uv run pytest -q tests/e2e/test_cards_trainer_smoke.py -s
```

- `tests/legacy` and the deprecated cards API shim are out of the active test perimeter.
- Legacy cards web UI is archived under `legacy/cards-web` and excluded from active flow.
