---
schema: agentcompanies/v1
kind: task
id: RUB-10
title: Bulk algorithm import pipeline for ZBLL and ZBLS
status: draft
owner: product-lead
agents:
  - product-lead
  - content-engineer
  - qa-reviewer
created_at: 2026-04-30
---

# RUB-10: Bulk Algorithm Import Pipeline For ZBLL And ZBLS

## Short Answer

Do not import "all 800 algorithms" in one step. Build a governed bulk-import
pipeline and ship category subsets in small, reviewable batches.

The goal is to scale from the current 2-case ZBLS pilot to full ZBLL/ZBLS
coverage without losing source provenance, formula validity, recognizer
correctness, UI performance, or rollback ability.

## Current State

- F2L, OLL, PLL are live in the static Trainer.
- ZBLS is live as a 2-case pilot:
  - `ZBLS_U01`
  - `ZBLS_U02`
- Trainer category tabs are now data-driven from `catalog.categories`.
- ZBLS recognizers are now formula-based isometric SVGs, not fallback hash cards.
- ZBLL is not live. `data/manifests/zbll_t_fixture.json` is quarantine-only
  because source reuse terms are not approved.
- Manifest governance blocks ZBLL/ZBLS imports when provenance or license basis
  is missing, unknown, unspecified, or pending review.

## Problem

The product needs large algorithm coverage, roughly "800 algos" across advanced
sets, but bulk importing raw algorithm lists is unsafe.

Main risks:

- unclear source licensing or attribution;
- formula parser/timeline failures;
- wrong recognizer state versus playback state;
- unstable generated catalog diffs from runtime DB ids;
- UI/search/performance regressions after a large case count increase;
- deployment cache confusion on GitHub Pages;
- agent-generated content entering runtime without human review.

## Scope

In scope:

- Create a repeatable import workflow for ZBLL and ZBLS subsets.
- Keep canonical source data in `data/manifests/*.json`.
- Generate/refresh `db/cards/seed.sql`, runtime recognizers, and
  `apps/trainer/data/catalog-v2.json` only through existing tools.
- Add tests that stop fallback recognizers and invalid formulas from shipping.
- Validate UI behavior and performance with static Trainer smoke checks.
- Document source review decisions per imported source/subset.

Out of scope:

- Scraping or copying third-party algorithm lists without explicit reuse basis.
- Adding new npm/pip dependencies for import convenience.
- Shipping full ZBLL before source governance is resolved.
- Making Paperclip a runtime dependency of the Trainer.
- Hand-editing generated catalog IDs to force stability.

## Milestone Plan

### M0: Source Governance Gate

Owner: Product Lead

Deliverables:

- Identify approved sources for each target set:
  - ZBLS subsets;
  - ZBLL subsets;
  - any future COLL/ELL/VLS-like expansion.
- For each source, create a review note under `docs/reviews/`.
- Record:
  - source title;
  - URL or internal source path;
  - retrieval date;
  - explicit license/reuse basis;
  - human approval note;
  - allowed categories/subsets.

Acceptance criteria:

- No source has `unknown`, `unspecified`, or `pending legal review` license text.
- ZBLL remains quarantine-only until this gate passes.
- Content Engineer has exact approved source list before writing manifests.

### M1: Manifest Batch Format

Owner: Content Engineer

Deliverables:

- Extend canonical manifests only if needed; prefer current
  `manifest_version: 1`.
- Define stable case codes:
  - ZBLS: `ZBLS_<subset><index>`; example `ZBLS_U01`.
  - ZBLL: `ZBLL_<subset><index>`; exact subset names require Product Lead
    approval before runtime import.
- Keep batches small:
  - first real batch: 10-25 cases;
  - normal batch: 25-75 cases;
  - never one unreviewable 800-case diff.
- Keep one manifest per category/subset/source boundary.

Acceptance criteria:

- Every case has stable `case_code`, `display_title`, `subset`, `sort_order`,
  `recognition_notes`, `probability_notes`, and at least one primary algorithm.
- Formulas are parser-safe repository notation.
- Manifest validation runs before seed/runtime sync.

### M2: Import Tooling Hardening

Owner: Content Engineer

Deliverables:

- Reuse `tools/algorithm_manifest.py` and `tools/import_f2l_pdf.py` patterns.
- Add a category-neutral manifest sync command if current F2L importer naming
  becomes misleading.
- Keep governance validation mandatory for ZBLL/ZBLS.
- Add deterministic output checks where practical.

Acceptance criteria:

- New import flow can generate seed SQL blocks from approved manifests.
- Invalid formulas fail before touching runtime assets.
- Missing source governance fails before touching runtime assets.
- No dependency installation is required.

### M3: Runtime And Recognizers

Owner: Content Engineer

Deliverables:

- Rebuild cards runtime using existing `uv` command path.
- Ensure recognizer assets are generated only for active catalog cases.
- ZBLS must continue using formula-based isometric recognizers.
- ZBLL recognizer strategy must be decided before runtime import:
  - either PLL-like top permutation renderer;
  - or a dedicated ZBLL top/side renderer;
  - or isometric formula renderer if Product Lead accepts that visual language.

Acceptance criteria:

- No new ZBLL/ZBLS runtime recognizer uses `recognizer:v4-fallback`.
- Recognizer preview and playback start state agree for representative cases.
- Asset pruner keeps only catalog-referenced recognizers.

### M4: Static Trainer UX

Owner: Product Lead + Content Engineer

Deliverables:

- Verify category tabs and labels remain data-driven.
- Add grouping for large sets so 800 algorithms are browsable:
  - subset sections;
  - stable sort;
  - progress sort compatibility;
  - search/filter if card count becomes hard to scan.
- Keep first screen usable on desktop and mobile.

Acceptance criteria:

- Trainer can open with all imported categories without console errors.
- Category switching remains responsive.
- Existing F2L/OLL/PLL flows are unchanged.
- ZBLS/ZBLL categories are not hidden behind hardcoded UI lists.

### M5: QA And Deployment

Owner: QA Reviewer

Required commands:

- `PYTHONPATH=packages/cubeanim/src uv run pytest -q`
- `SMOKE_STRICT=1 PYTHONPATH=packages/cubeanim/src uv run pytest -q tests/e2e/test_cards_trainer_smoke.py -s`
- `git diff --check`

Additional checks:

- Use Playwright against local static Trainer for at least:
  - first imported ZBLS case;
  - last imported ZBLS case;
  - first imported ZBLL case once ZBLL is approved;
  - one F2L, one OLL, one PLL regression case.
- After push, verify GitHub Pages:
  - deployment succeeded;
  - hosted `catalog-v2.json` contains expected categories;
  - hosted recognizer SVG marker is not fallback;
  - cache-busted URL loads the latest asset.

Acceptance criteria:

- Tests pass.
- Smoke passes.
- Pages deploy succeeds.
- QA Reviewer records any screenshot/log artifact paths in the final report.

## Agent Work Split

### Product Lead

- Approve exact source list and category taxonomy.
- Decide ZBLL subset naming before import.
- Decide whether ZBLL recognizer should be top-card or isometric.
- Keep batches reviewable; reject one-shot 800-case diffs.

### Content Engineer

- Convert approved sources into canonical manifests.
- Run manifest governance validation.
- Generate seed/runtime/catalog/assets through repository tools.
- Add or update tests when renderer/import behavior changes.
- Do not introduce new dependencies.

### QA Reviewer

- Review generated diffs for unexpected churn.
- Confirm no fallback recognizers in newly imported advanced categories.
- Run full test and smoke commands.
- Verify Pages after deployment.
- Flag cache, performance, grouping, and mobile regressions.

## Current Tails To Clean Before Bulk Import

- ZBLL source governance is unresolved. Keep ZBLL quarantined.
- ZBLL recognizer design is undecided. Do not import ZBLL into runtime until
  Product Lead chooses renderer strategy.
- `apps/trainer/data/catalog-v2.json` can churn if runtime DB ids are reset.
  Avoid committing unrelated catalog id churn in small fixes.
- Existing Paperclip structure had agents only. This task introduces
  `paperclip-company/tasks/` as the task intake location.
- Hosted GitHub Pages uses `cache-control: max-age=600`; QA should use
  cache-busted URLs during post-deploy verification.
- ZBLS pilot has only two internally authored cases. Bulk import needs approved
  source coverage, not extrapolation from placeholders.

## Definition Of Done

- Approved source review docs exist for every imported batch.
- Canonical manifests exist for every imported batch.
- Seed/runtime/catalog/assets are generated through repository tools.
- New advanced categories have no fallback recognizers.
- Full tests and strict Trainer smoke pass.
- Pages deploy succeeds and hosted assets are verified.
- Product Lead signs off on the next batch before agents continue.

## Explicit Agent Instruction

If an agent is asked to "add all 800 algorithms", it must stop and split the
work into governed batches. The first deliverable is a source-reviewed manifest
batch, not a runtime import.
