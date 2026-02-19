set shell := ["zsh", "-cu"]

default:
  @just --list

api:
  uv run python scripts/cards_api.py

worker interval="1":
  uv run python scripts/cards_worker.py --interval {{interval}}

worker-once:
  uv run python scripts/cards_worker.py --once

ui:
  uv run python scripts/render_ui.py

render formula name group="NO_GROUP" quality="draft" repeat="1":
  uv run python scripts/render_algo.py --formula "{{formula}}" --name "{{name}}" --group "{{group}}" --quality {{quality}} --repeat {{repeat}}

test:
  PYTHONPATH=. uv run pytest -q

check:
  python3 -m py_compile cubist.py cubeanim/*.py scripts/render_algo.py scripts/render_ui.py scripts/cards_api.py scripts/cards_worker.py

dev:
  @./scripts/dev_tmux.sh up

dev-create:
  @./scripts/dev_tmux.sh create

dev-stop:
  @./scripts/dev_tmux.sh stop

dev-ls:
  @./scripts/dev_tmux.sh ls

dev-name:
  @./scripts/dev_tmux.sh name

dev-port:
  @./scripts/dev_tmux.sh port

dev-tmuxp:
  tmuxp load -y .tmuxp/cards-dev.yaml -s "$$(./scripts/dev_tmux.sh name)-tmuxp"

dev-all:
  @./scripts/dev_worktrees.sh up

dev-all-ls:
  @./scripts/dev_worktrees.sh ls

dev-all-stop:
  @./scripts/dev_worktrees.sh stop
