set shell := ["zsh", "-cu"]

default:
  @just --list

api:
  uv run python apps/cards-api/main.py

worker interval="1" workers="1" manim_threads="1":
  uv run python apps/cards-worker/main.py --interval {{interval}} --workers {{workers}} --manim-threads {{manim_threads}}

worker-once workers="1" manim_threads="1":
  uv run python apps/cards-worker/main.py --once --workers {{workers}} --manim-threads {{manim_threads}}

ui:
  uv run python apps/render-ui/main.py

render formula name group="NO_GROUP" quality="draft" repeat="1":
  uv run python tools/render_algo.py --formula "{{formula}}" --name "{{name}}" --group "{{group}}" --quality {{quality}} --repeat {{repeat}}

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
  PYTHONPATH=packages/cubeanim/src python3 -m py_compile cubist.py packages/cubeanim/src/cubeanim/*.py tools/render_algo.py apps/render-ui/main.py apps/cards-api/main.py apps/cards-worker/main.py tools/trainer/build_trainer_catalog.py tools/trainer/prune_trainer_assets.py

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

dev-port:
  @./scripts/dev/dev_tmux.sh port

dev-tmuxp:
  tmuxp load -y .tmuxp/cards-dev.yaml -s "$$(./scripts/dev/dev_tmux.sh name)-tmuxp"

dev-all:
  @./scripts/dev/dev_worktrees.sh up

dev-all-ls:
  @./scripts/dev/dev_worktrees.sh ls

dev-all-stop:
  @./scripts/dev/dev_worktrees.sh stop
