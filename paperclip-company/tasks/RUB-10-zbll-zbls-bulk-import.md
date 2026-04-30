---
schema: agentcompanies/v1
kind: task
id: RUB-10
title: Full ZBLL and ZBLS imports
status: done
owner: product-lead
agents:
  - product-lead
  - content-engineer
  - qa-reviewer
created_at: 2026-04-30
updated_at: 2026-04-30
---

# RUB-10: Full ZBLL And ZBLS Imports

## Current Result

Full ZBLL and ZBLS are now imported into the Trainer pipeline.

- ZBLL source: SpeedCubeDB public ZBLL aggregate pages.
- ZBLL review note: `docs/reviews/2026-04-30-zbll-speedcubedb-source-review.md`.
- ZBLL manifest: `data/manifests/zbll_speedcubedb.json`.
- ZBLL scope imported: 472 cases across U, L, T, H, Pi, S, AS.
- ZBLS source: CubeZone ZB First Two Layers public subgroup pages.
- ZBLS review note: `docs/reviews/2026-04-30-zbls-cubezone-source-review.md`.
- ZBLS manifest: `data/manifests/zbls_cubezone.json`.
- ZBLS scope imported: 306 cases across ConU, SepU, InsertE, InsertC, ConF2L.
- Runtime/catalog total after import: 950 cases.
- ZBLL recognizers: formula-based isometric SVG, marker `recognizer:v1-zbll`.
- ZBLS recognizers: formula-based isometric SVG, marker `recognizer:v1-zbls`.
- Trainer category order: F2L, OLL, ZBLS, ZBLL, PLL.

## Implemented

- Added `tools/import_speedcubedb_zbll.py`.
- Added `tools/render_manifest_seed.py` for category-neutral manifest-to-seed sync.
- Added full ZBLL seed block to `db/cards/seed.sql`.
- Regenerated static catalog and ZBLL recognizer assets under `apps/trainer/`.
- Added ZBLL category wiring in Trainer constants, static HTML fallback tabs, sandbox preview assets, and catalog builder defaults.
- Added formula parser support for `3` move suffix notation, normalized as inverse turns.
- Added validation for double-prime source notation during manifest normalization.
- Added tests for importer parsing, full manifest validity, runtime counts, ZBLL service listing, catalog grouping, and non-fallback ZBLL recognizers.
- Added `tools/import_cubezone_zbls.py`.
- Added full ZBLS seed block to `db/cards/seed.sql`, replacing the two-case pilot runtime block.
- Regenerated static catalog and ZBLS recognizer assets under `apps/trainer/`.
- Added tests for CubeZone parsing, full ZBLS manifest validity, ZBLS service listing, catalog grouping, and non-fallback ZBLS recognizers.
- Adjusted non-F2L service ordering so data-driven categories use canonical case order instead of alphabetical subgroup order.

## Verification

- `PYTHONPATH=packages/cubeanim/src uv run pytest -q`
  - Result: 140 passed, 1 skipped.
- `PYTHONPATH=packages/cubeanim/src uv run pytest -q tests/test_cubezone_zbls_import.py tests/test_cards_db.py tests/test_cards_service.py tests/test_trainer_catalog_builder.py tests/e2e/test_cards_trainer_smoke.py -s`
  - Result: 40 passed, 1 skipped.
- `PYTHONPATH=packages/cubeanim/src uv run pytest -q tests/test_algorithm_manifest.py tests/test_trainer_preview_assets.py tests/test_trainer_asset_prune.py tests/e2e/test_cards_trainer_smoke.py -s`
  - Result: 18 passed, 1 skipped.
- `git diff --check`
  - Result: clean.

## Remaining Tails

- ZBLL/ZBLS recognizers are formula-based isometric cards, not dedicated last-layer/top-pattern recognizers. This is acceptable for shipping bulk data, but a dedicated recognizer can be a later visual-quality task.
- Hosted GitHub Pages verification must be done after push with cache-busted URLs:
  - `data/catalog-v2.json`
  - `assets/recognizers/zbls/svg/zbls_zbls_conu1a02.svg`
  - `assets/recognizers/zbll/svg/zbll_zbll_t1.svg`

## QA Notes

Manual QA should check:

- Open Trainer and switch to ZBLS.
- Confirm ZBLS case count is 306.
- Open `ZBLS ConU_1a #02`.
- Confirm top-right recognizer renders and is not the fallback placeholder.
- Play/pause/scrub the algorithm.
- Switch to ZBLL.
- Confirm ZBLL case count is 472.
- Open `ZBLL T #1`.
- Confirm top-right recognizer renders and is not the fallback placeholder.
- Play/pause/scrub the algorithm.
- Regression spot-check F2L, OLL, and PLL tabs.
