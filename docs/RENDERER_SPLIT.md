# Local Split Guide

Main repo no longer carries the Python renderer in its active package graph.

## 1) Runtime boundary

- `apps/trainer` stays independent from Manim.
- `packages/cubeanim/src/cubeanim_domain` contains the shared cube/domain logic:
  - formula parsing
  - move normalization and inversion
  - sandbox timeline assembly
  - F2L/OLL/PLL start-state resolution
- The Manim-only stack lives in a sibling local mini-repo (`cubeanim-renderer-py`).
- `packages/cubeanim/src/cubeanim` remains a compatibility facade only for non-render legacy imports during migration.

## 2) Local renderer workflow

- Renderer authoring happens outside this repo.
- The main repo does not build or ship render artifacts.
- Trainer consumes recognizer assets and metadata only.

## 3) Removed service model

- Remote renderer backends are removed.
- HTTP `/plan` and `/render` are removed from the active architecture.
- `CUBEANIM_RENDER_BACKEND=http`, `CUBEANIM_RENDER_API_URL`, and `CUBEANIM_RENDER_API_TIMEOUT_SEC` are no longer supported.
- `cards/*` no longer contain render queue, artifact, or worker logic.

## 4) Verification model

- Canonical domain fixtures live in `tests/fixtures/domain/formula_golden.json`.
- Python domain tests validate full `formula -> timeline -> states` parity.
- Trainer JS tests validate parser/beat parity against the same fixture set.
- Product-facing files are protected by architecture guardrail tests against direct renderer/Manim imports.
