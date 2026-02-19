# AGENTS.md

## Render Quality Rule
- Unless explicitly requested, use preview quality only (`draft`/`standard`, or `-ql`/`-qm`).
- Use `high`/`final` (`-qh`/`-qk`) only for final export or direct user request.

## Scene And Layout Invariants
- Keep one visual scene setup (single cube/camera baseline).
- Keep cube centered in frame.
- Algorithm name stays in the top-left corner.
- Formula stays in the bottom-right caption panel.
- Formula text inside the panel must be left-aligned with fixed internal padding (no dynamic text drifting).
- Before changing overlay geometry, validate with a draft render that the panel does not overlap the cube.

## Animation Behavior
- Prepare start case from inverse formula via `set_state` before playback.
- Do not use start fade-in for cube.
- Keep a short pre-start pause (`0.5s`) before first move.
- Support simultaneous moves via `+` (e.g. `U+D`, `U+D'`), rendered as a single beat.
- Simultaneous moves must share the same axis.

## Product Workflow
- Primary workflow is GUI (`scripts/render_ui.py`).
- CLI (`scripts/render_algo.py`) is optional for automation and smoke checks.
- If clipboard shortcuts are unreliable in UI, context menu copy/paste is acceptable.

## Cards Workflow Insights
- Prefer `uv` runtime commands for this repo:
  - `uv run python scripts/cards_api.py`
  - `uv run python scripts/cards_worker.py`
  - `PYTHONPATH=. uv run pytest -q`
- In cards render flow, keep naming split:
  - `RenderRequest.name` = internal storage key (stable/dedupable).
  - `RenderRequest.display_name` = user-facing overlay label in video.
- Treat DB artifacts as valid only when `output_path` exists on disk.
- Worker must not keep DB transaction open during heavy render execution.
- Recognizer assets are grouped by category folders: `recognizers/f2l`, `recognizers/oll`, `recognizers/pll`.

## Git Worktree SOP (for coding agent)

### Goals
- One active feature stream = one worktree folder.
- Mainline sync is predictable.
- No destructive git commands.

### Naming
- Branches must use `codex/*` prefix.
- Worktree folders:
  - `.../manim-tests-main` -> `main`
  - `.../manim-tests-A` -> `codex/A`
  - `.../manim-tests-B` -> `codex/B`
  - `.../manim-tests-C` -> `codex/C`

### Hard rules
1. Never run `git reset --hard` or `git checkout --`.
2. Never rewrite shared history unless explicitly asked.
3. If worktree has uncommitted changes, do not switch branch; commit/stash first.
4. Never develop new feature on merged branch (`codex/A` after merge). Create `codex/A2` from fresh `origin/main`.
5. If conflicts appear during rebase/merge, stop and report exact files.

### Standard flow
1. Update main worktree:
   - `cd .../manim-tests-main`
   - `git fetch origin && git switch main && git pull --ff-only`
2. Start feature branch/worktree:
   - `git worktree add -b codex/<feature> .../manim-tests-<feature> origin/main`
3. Finish feature:
   - push branch, merge via PR into `main`.
4. Sync long-running branch `codex/C`:
   - `cd .../manim-tests-C`
   - `git fetch origin`
   - `git rebase origin/main`  (or `git merge origin/main` if requested)
5. Reuse old worktree folder for next feature:
   - delete old branch locally if merged
   - create new branch from `origin/main` in same folder.

### Priority queue for agent
- First: keep `main` updated.
- Second: keep long-running branches rebased on `origin/main`.
- Third: create new feature branches from `origin/main` only.
