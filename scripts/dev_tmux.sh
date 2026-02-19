#!/usr/bin/env bash
set -euo pipefail

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required. Install tmux first."
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"
repo_name="$(basename "$repo_root")"
branch_name="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo detached)"
worktree_path="$(pwd -P)"
repo_key="$(printf "%s" "$repo_name" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9_-' '-')"

hash_short="$(printf "%s" "$worktree_path" | shasum | awk '{print substr($1,1,8)}')"
raw_session_name="${repo_name}-${branch_name}-${hash_short}"
session_name="$(printf "%s" "$raw_session_name" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9_-' '-')"
session_name="${session_name#-}"
session_name="${session_name%-}"

if [ -z "$session_name" ]; then
  session_name="manim-tests-${hash_short}"
fi

cmd="${1:-up}"
cards_port="${CUBEANIM_CARDS_PORT:-8008}"
python_bin="${CUBEANIM_PYTHON_BIN:-}"

if ! [[ "$cards_port" =~ ^[0-9]+$ ]]; then
  echo "CUBEANIM_CARDS_PORT must be an integer, got: $cards_port"
  exit 2
fi

if [ -n "$python_bin" ] && [ ! -x "$python_bin" ]; then
  echo "CUBEANIM_PYTHON_BIN is not executable: $python_bin"
  exit 2
fi

create_session() {
  if tmux has-session -t "$session_name" 2>/dev/null; then
    return 0
  fi

  local api_exec
  local worker_exec
  local py_q
  local root_q

  if [ -n "$python_bin" ]; then
    py_q="$(printf '%q' "$python_bin")"
    root_q="$(printf '%q' "$worktree_path")"
    api_exec="PYTHONPATH=${root_q} ${py_q} -c 'import uvicorn; uvicorn.run(\"scripts.cards_api:app\", host=\"127.0.0.1\", port=${cards_port}, reload=True)'"
    worker_exec="PYTHONPATH=${root_q} ${py_q} scripts/cards_worker.py"
  else
    api_exec="uv run python -c 'import uvicorn; uvicorn.run(\"scripts.cards_api:app\", host=\"127.0.0.1\", port=${cards_port}, reload=True)'"
    worker_exec='uv run python scripts/cards_worker.py'
  fi

  api_start_cmd="clear; echo \"[cards_api:${cards_port}]\"; if lsof -nP -iTCP:${cards_port} -sTCP:LISTEN >/dev/null 2>&1; then echo \"Port ${cards_port} is already in use. Stop old API first.\"; exit 1; fi; ${api_exec}"
  worker_start_cmd="clear; echo \"[cards_worker]\"; ${worker_exec}"

  tmux new-session -d -s "$session_name" -n cards -c "$worktree_path"
  tmux set-option -t "$session_name" remain-on-exit on
  tmux respawn-pane -k -t "$session_name:cards.0" "$api_start_cmd"
  tmux split-window -h -t "$session_name:cards" -c "$worktree_path"
  tmux respawn-pane -k -t "$session_name:cards.1" "$worker_start_cmd"
  tmux select-layout -t "$session_name:cards" even-horizontal
  tmux select-window -t "$session_name:cards"
}

attach_session() {
  if [ -n "${TMUX:-}" ]; then
    tmux switch-client -t "$session_name"
  else
    tmux attach-session -t "$session_name"
  fi
}

case "$cmd" in
  up|attach)
    create_session
    attach_session
    ;;
  create)
    create_session
    echo "Created: $session_name"
    ;;
  stop|kill)
    if tmux has-session -t "$session_name" 2>/dev/null; then
      tmux kill-session -t "$session_name"
      echo "Stopped: $session_name"
    else
      echo "No active session: $session_name"
    fi
    ;;
  ls|list)
    tmux list-sessions -F '#{session_name}' | grep -E "^${repo_key}-" || true
    ;;
  name)
    echo "$session_name"
    ;;
  port)
    echo "$cards_port"
    ;;
  *)
    echo "Usage: $0 [up|attach|create|stop|ls|name|port]"
    exit 2
    ;;
esac
