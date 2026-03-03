# Repository Layout (Apps + Packages)

## Active structure

```text
apps/
  trainer/
  cards-api/
  cards-worker/
  render-ui/

packages/
  cubeanim/src/cubeanim/

tools/
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

legacy/
  cards-web/
```

## Rules

- Single active trainer source is `apps/trainer`.
- `legacy/cards-web` is frozen/deprecated and not part of default workflows.
- `packages/cubeanim/src` is the only Python package root for runtime and tests.
- cards-api root endpoint is service JSON, not legacy HTML.
- Recognizer assets in `apps/trainer/assets/recognizers` are release-snapshot only:
  - build catalog
  - sync recognizers
  - prune non-whitelisted files via `tools/trainer/prune_trainer_assets.py`

## Canonical commands

- `uv run python apps/cards-api/main.py`
- `uv run python apps/cards-worker/main.py`
- `uv run python apps/render-ui/main.py`
- `uv run python tools/render_algo.py`
- `PYTHONPATH=packages/cubeanim/src uv run pytest -q`
