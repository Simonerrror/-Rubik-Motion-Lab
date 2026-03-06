# Local Renderer Split Guide

Manim is now treated as a private local authoring tool, not as a trainer backend or remote service.

## 1) Runtime boundary

- `apps/trainer` stays independent from Manim.
- `packages/cubeanim/src/cubeanim_domain` contains the shared cube/domain logic:
  - formula parsing
  - move normalization and inversion
  - sandbox timeline assembly
  - F2L/OLL/PLL start-state resolution
- `packages/cubeanim/src/cubeanim_renderer` contains the Manim-only stack:
  - scene setup
  - executor
  - render orchestration
  - Rubik 3D Manim primitives
- `packages/cubeanim/src/cubeanim` remains a compatibility facade for legacy imports during migration.

## 2) Local renderer workflow

- GUI-first entrypoint: `uv run python apps/render-ui/main.py`
- Optional CLI smoke wrapper: `uv run python tools/render_algo.py --formula "R U R' U'" --name MyAlgo --group PLL --quality draft`
- Artifacts are written under `data/local-renderer/` and are not part of web runtime assets.

## 3) Removed service model

- Remote renderer backends are removed.
- HTTP `/plan` and `/render` are removed from the active architecture.
- `CUBEANIM_RENDER_BACKEND=http`, `CUBEANIM_RENDER_API_URL`, and `CUBEANIM_RENDER_API_TIMEOUT_SEC` are no longer supported.
- `cards/*` no longer import the old render service module directly.

## 4) Verification model

- Canonical domain fixtures live in `tests/fixtures/domain/formula_golden.json`.
- Python domain tests validate full `formula -> timeline -> states` parity.
- Trainer JS tests validate parser/beat parity against the same fixture set.
- Product-facing files are protected by architecture guardrail tests against direct renderer/Manim imports.
