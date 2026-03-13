set shell := ["zsh", "-cu"]

default:
  @just --list

cards-reset-runtime:
  PYTHONPATH=packages/cubeanim/src uv run python tools/cards_runtime.py reset-runtime

test:
  PYTHONPATH=packages/cubeanim/src uv run pytest -q

smoke-ui:
  SMOKE_STRICT=1 PYTHONPATH=packages/cubeanim/src uv run pytest -q tests/e2e/test_cards_trainer_smoke.py -s

trainer-build output="apps/trainer":
  PYTHONPATH=packages/cubeanim/src uv run python tools/trainer/build_trainer_catalog.py --output {{output}} --assets-dir {{output}}/assets --base-catalog-url ./assets

trainer-manual:
  uv run python tools/trainer/build_manual_doc.py

trainer-serve port="8011":
  cd apps/trainer && python3 -m http.server {{port}}

trainer-export input="apps/trainer/profile.json":
  PYTHONPATH=packages/cubeanim/src uv run python tools/trainer/profile_codec_cli.py export --input {{input}}

check:
  PYTHONPATH=packages/cubeanim/src python3 -m py_compile packages/cubeanim/src/cubeanim/*.py tools/cards_runtime.py tools/trainer/build_trainer_catalog.py tools/trainer/prune_trainer_assets.py

dev:
  @./scripts/dev/dev_tmux.sh up

dev-create:
  @./scripts/dev/dev_tmux.sh create

dev-stop:
  @./scripts/dev/dev_tmux.sh stop

dev-ls:
  @./scripts/dev/dev_tmux.sh ls

dev-name:
  @./scripts/dev/dev_tmux.sh name

dev-tmuxp:
  tmuxp load -y .tmuxp/cards-dev.yaml -s "$$(./scripts/dev/dev_tmux.sh name)-tmuxp"

dev-all:
  @./scripts/dev/dev_worktrees.sh up

dev-all-ls:
  @./scripts/dev/dev_worktrees.sh ls

dev-all-stop:
  @./scripts/dev/dev_worktrees.sh stop
