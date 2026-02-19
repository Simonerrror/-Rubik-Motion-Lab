#!/usr/bin/env bash
set -euo pipefail

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required. Install tmux first."
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"
cmd="${1:-up}"
base_port="${CUBEANIM_CARDS_BASE_PORT:-8008}"
controller_script="$repo_root/scripts/dev_tmux.sh"
shared_python_bin="${CUBEANIM_PYTHON_BIN:-}"

if ! [[ "$base_port" =~ ^[0-9]+$ ]]; then
  echo "CUBEANIM_CARDS_BASE_PORT must be an integer, got: $base_port"
  exit 2
fi

if [ ! -x "$controller_script" ]; then
  echo "Missing executable controller script: $controller_script"
  exit 1
fi

if [ -z "$shared_python_bin" ] && [ -x "$repo_root/.venv/bin/python" ]; then
  shared_python_bin="$repo_root/.venv/bin/python"
fi

worktrees=()
while IFS= read -r wt_path; do
  if [ -n "$wt_path" ]; then
    worktrees+=("$wt_path")
  fi
done < <(
  git -C "$repo_root" worktree list --porcelain \
    | awk '/^worktree /{sub(/^worktree /,""); print}' \
    | sort
)

if [ "${#worktrees[@]}" -eq 0 ]; then
  echo "No worktrees found."
  exit 1
fi

run_for_all() {
  local action="$1"
  local idx=0
  local wt
  local port
  local session
  local status
  local failed=0

  for wt in "${worktrees[@]}"; do
    port=$((base_port + idx))
    idx=$((idx + 1))

    if [ -n "$shared_python_bin" ]; then
      session="$(cd "$wt" && CUBEANIM_CARDS_PORT="$port" CUBEANIM_PYTHON_BIN="$shared_python_bin" "$controller_script" name)"
    else
      session="$(cd "$wt" && CUBEANIM_CARDS_PORT="$port" "$controller_script" name)"
    fi

    case "$action" in
      up)
        if [ -n "$shared_python_bin" ]; then
          (cd "$wt" && CUBEANIM_CARDS_PORT="$port" CUBEANIM_PYTHON_BIN="$shared_python_bin" "$controller_script" create >/dev/null)
        else
          (cd "$wt" && CUBEANIM_CARDS_PORT="$port" "$controller_script" create >/dev/null)
        fi
        if tmux has-session -t "$session" 2>/dev/null; then
          echo "UP    $session  $wt  http://127.0.0.1:$port/"
        else
          echo "FAIL  $session  $wt  (session not created)"
          failed=$((failed + 1))
        fi
        ;;
      stop)
        if [ -n "$shared_python_bin" ]; then
          (cd "$wt" && CUBEANIM_CARDS_PORT="$port" CUBEANIM_PYTHON_BIN="$shared_python_bin" "$controller_script" stop >/dev/null || true)
        else
          (cd "$wt" && CUBEANIM_CARDS_PORT="$port" "$controller_script" stop >/dev/null || true)
        fi
        if tmux has-session -t "$session" 2>/dev/null; then
          echo "FAIL  $session  $wt  (session still active)"
          failed=$((failed + 1))
        else
          echo "STOP  $session  $wt"
        fi
        ;;
      ls)
        if tmux has-session -t "$session" 2>/dev/null; then
          status="ACTIVE"
        else
          status="STOPPED"
        fi
        echo "LS    $status  $session  $wt  http://127.0.0.1:$port/"
        ;;
      *)
        echo "Internal error: unsupported action $action"
        exit 2
        ;;
    esac
  done

  if [ "$failed" -gt 0 ]; then
    return 1
  fi
}

case "$cmd" in
  up|create)
    run_for_all up
    ;;
  stop|kill)
    run_for_all stop
    ;;
  ls|list)
    run_for_all ls
    ;;
  *)
    echo "Usage: $0 [up|create|stop|ls]"
    exit 2
    ;;
esac
