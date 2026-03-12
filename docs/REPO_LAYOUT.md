# Repository Layout (Apps + Packages)

## Active structure

```text
apps/
  trainer/
  cards-worker/
  render-ui/

packages/
  cubeanim/src/cubeanim/
  cubeanim/src/cubeanim_domain/
  cubeanim/src/cubeanim_renderer/

tools/
  cards_runtime.py
  render_algo.py
  import_f2l_pdf.py
  trainer/
    build_trainer_catalog.py
    profile_codec_cli.py
    prune_trainer_assets.py

db/
  cards/
    schema.sql
    seed.sql

data/
  f2l/best_f2l_from_pdf.yaml
  cards/runtime/   # generated runtime DB/assets (gitignored)
  local-renderer/  # local-only render artifacts/catalog (gitignored or runtime)

legacy/
  cards-web/
```

## Rules

- Single active trainer source is `apps/trainer`.
- Active cards integration is local-only: `CardsService`, `apps/cards-worker`, and runtime files under `data/cards/runtime`.
- `legacy/cards-web` is frozen/deprecated and not part of default workflows.
- `apps/cards-api` is a deprecated compatibility shim and is excluded from active checks/docs/workflows.
- `packages/cubeanim/src` is the only Python package root for runtime and tests.
- `cubeanim_domain` is the shared source of truth for Python-side formula/timeline/start-state logic.
- `cubeanim_renderer` is private local-renderer runtime and should not leak into trainer-web files.
- `cubeanim` is a transitional facade for backward-compatible imports.
- Recognizer assets in `apps/trainer/assets/recognizers` are release-snapshot only:
  - build catalog
  - sync recognizers
  - prune non-whitelisted files via `tools/trainer/prune_trainer_assets.py`

## Canonical commands

- `uv run python apps/cards-worker/main.py`
- `uv run python tools/cards_runtime.py reset-runtime`
- `uv run python apps/render-ui/main.py`
- `uv run python tools/render_algo.py`
- `PYTHONPATH=packages/cubeanim/src uv run pytest -q`
