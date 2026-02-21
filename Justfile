set shell := ["zsh", "-cu"]

default:
  @just --list

api:
  uv run python scripts/app/cards_api.py

worker interval="1" workers="1" manim_threads="1":
  uv run python scripts/app/cards_worker.py --interval {{interval}} --workers {{workers}} --manim-threads {{manim_threads}}

worker-once workers="1" manim_threads="1":
  uv run python scripts/app/cards_worker.py --once --workers {{workers}} --manim-threads {{manim_threads}}

ui:
  uv run python scripts/app/render_ui.py

render formula name group="NO_GROUP" quality="draft" repeat="1":
  uv run python scripts/tools/render_algo.py --formula "{{formula}}" --name "{{name}}" --group "{{group}}" --quality {{quality}} --repeat {{repeat}}

test:
  PYTHONPATH=. uv run pytest -q

check:
  python3 -m py_compile cubist.py cubeanim/*.py scripts/tools/render_algo.py scripts/app/render_ui.py scripts/app/cards_api.py scripts/app/cards_worker.py

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
