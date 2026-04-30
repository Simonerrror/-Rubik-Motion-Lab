---
schema: agentcompanies/v1
kind: task
id: RUB-10
title: Full ZBLL import and remaining advanced-set tails
status: in_review
owner: product-lead
agents:
  - product-lead
  - content-engineer
  - qa-reviewer
created_at: 2026-04-30
updated_at: 2026-04-30
---

# RUB-10: Full ZBLL Import And Remaining Advanced-Set Tails

## Current Result

Full ZBLL is now imported into the Trainer pipeline.

- Source: SpeedCubeDB public ZBLL aggregate pages.
- Review note: `docs/reviews/2026-04-30-zbll-speedcubedb-source-review.md`.
- Canonical manifest: `data/manifests/zbll_speedcubedb.json`.
- Scope imported: 472 ZBLL cases across U, L, T, H, Pi, S, AS.
- Runtime/catalog total after import: 646 cases.
- ZBLL recognizers: formula-based isometric SVG, marker `recognizer:v1-zbll`.
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

## Verification

- `PYTHONPATH=packages/cubeanim/src uv run pytest -q`
  - Result: 137 passed, 1 skipped.
- `PYTHONPATH=packages/cubeanim/src uv run pytest -q tests/test_algorithm_manifest.py tests/test_trainer_preview_assets.py tests/test_trainer_asset_prune.py tests/e2e/test_cards_trainer_smoke.py -s`
  - Result: 18 passed, 1 skipped.
- `git diff --check`
  - Result: clean.

## Remaining Tails

- ZBLS is still a 2-case pilot. Full ZBLS needs an approved full source or an internal authored manifest.
- ZBLL recognizers are formula-based isometric cards, not a dedicated top-pattern ZBLL recognizer. This is acceptable for shipping bulk data, but a dedicated recognizer can be a later visual-quality task.
- Hosted GitHub Pages verification must be done after push with cache-busted URLs:
  - `data/catalog-v2.json`
  - `assets/recognizers/zbll/svg/zbll_zbll_t1.svg`

## QA Notes

Manual QA should check:

- Open Trainer and switch to ZBLL.
- Confirm ZBLL case count is 472.
- Open `ZBLL T #1`.
- Confirm top-right recognizer renders and is not the fallback placeholder.
- Play/pause/scrub the algorithm.
- Regression spot-check F2L, OLL, ZBLS, and PLL tabs.
