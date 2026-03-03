# Renderer Split Guide

This repository now supports renderer backend decoupling for cards workflow.

## 1) New boundary

Cards pipeline talks only to `RendererClient`:

- local implementation: `LocalRendererClient`
- remote implementation: `HttpRendererClient`

Implementation location: `packages/cubeanim/src/cubeanim/cards/renderer_client.py`.

`CardsService` no longer imports `plan_formula_render` / `render_formula` directly.

## 2) Env configuration

Local mode (default):

```bash
export CUBEANIM_RENDER_BACKEND=local
```

Remote mode:

```bash
export CUBEANIM_RENDER_BACKEND=http
export CUBEANIM_RENDER_API_URL=http://127.0.0.1:9010
export CUBEANIM_RENDER_API_TIMEOUT_SEC=60
```

## 3) Remote API contract

`POST /plan`

- request:
  - `request`: render request fields (`formula`, `name`, `display_name`, `group`, `quality`, `repeat`, `play`, `manim_*`)
  - `repo_root`: absolute path as string
- response body (or `data` wrapper):
  - `action`
  - `output_name`
  - `final_path`
  - `reason`

`POST /render`

- request:
  - `request`: same object as above
  - `repo_root`
  - `allow_rerender`
- response body (or `data` wrapper):
  - `output_name`
  - `final_path`
  - `action`

## 4) Extraction recommendation

For dedicated renderer repository, move:

- `packages/cubeanim/src/cubeanim/render_base.py`
- `packages/cubeanim/src/cubeanim/render_service.py`
- `packages/cubeanim/src/cubeanim/models.py`
- `packages/cubeanim/src/cubeanim/utils.py`
- `cubist.py`
- optional CLI wrapper: `tools/render_algo.py`

Keep in cards repository:

- `apps/cards-api/main.py`
- `apps/cards-worker/main.py`
- `packages/cubeanim/src/cubeanim/cards/*`
- frontend and DB schema/seed.
