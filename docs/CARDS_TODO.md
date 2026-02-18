# Cards UI/Backend TODO

## Snapshot (2026-02-18)

### Done (intermediate results saved)
- FastAPI backend scaffolded: `/api/algorithms`, `/api/progress`, `/api/queue`, `/api/queue/status`, static and media mounts.
- SQLite schema and runtime DB bootstrap added.
- Render worker loop added (`scripts/cards_worker.py`) with `PENDING -> RUNNING -> DONE/FAILED` transitions.
- Draft/HD reuse logic integrated in service layer.
- Recognizer asset generation wired for OLL/PLL/F2L placeholders.
- Vanilla frontend bridge added in `static/cards/app.js` and connected from `index.html`.
- Test coverage added for DB/API/queue/worker; current suite is green on local setup.
- PLL source-of-truth moved to `pll.txt` with strict parsing and seeded case metadata (name/group/probability/formula).
- Runtime reset flow added for local dev: full DB+recognizer rebuild endpoint (`POST /api/admin/reset-runtime`).

## Updated Product Direction (from `index2.html` + latest feedback)
- `ALL` category is removed from primary UX. Entry point is grouped by selected set (`F2L`, `OLL`, `PLL`).
- Catalog entity is **Case**, not flat algorithm item.
- Each case card must show:
  - case number
  - probability
  - recognizer preview
  - currently selected algorithm (active formula)
- Selected algorithm lives “on top” for the case (persisted active selection).
- Card click opens focus/modal and allows:
  - switch to known alternative algorithm
  - set custom algorithm formula
- Permanent full-screen player is not required; render/video should be contextual (modal/focus view).

## TODO (implementation)

### 1) Data model and DB
- [x] Add case metadata columns for subgroup, case number, probability.
- [x] Add persisted selected algorithm pointer on case (`selected_algorithm_id`).
- [x] Seed OLL subgroups and probabilities (from extracted reference PDF).
- [x] Keep backwards compatibility with existing algorithm-based endpoints.

### 2) Repository/service layer
- [x] Add case-centric queries: list cases by group, case details with alternatives.
- [x] Add mutation to activate alternative algorithm for a case.
- [x] Add mutation to create custom algorithm as alternative inside a case.
- [x] Route queue/progress operations through active algorithm in case-centric flow.

### 3) API
- [x] Add `GET /api/cases?group=F2L|OLL|PLL`.
- [x] Add `GET /api/cases/{case_id}` with alternatives + active algorithm + artifacts/jobs.
- [x] Add `POST /api/cases/{case_id}/activate`.
- [x] Add `POST /api/cases/{case_id}/custom`.
- [x] Keep `/api/queue`, `/api/progress` compatible for existing scripts/tests.
- [x] Add `POST /api/cases/{case_id}/queue`.

### 4) Frontend (`index.html` + `static/cards/app.js`)
- [x] Move to `index2`-style grouped catalog layout.
- [x] Remove `ALL` filter from UI.
- [x] Render subgroup sections and case cards with probability/number.
- [x] Implement modal flow with on-demand video and queue state overlay.
- [x] Add alternatives radio-list + custom formula input with activation.
- [x] Keep polling every 5 seconds and refresh active case media state.

### 5) Validation
- [x] Update/add tests for new case endpoints and activation/custom flow.
- [x] Re-run unit/API/worker tests.
- [ ] Smoke-check run: API + worker + manual UI flow (select case -> draft -> HD -> polling update).

## Remaining short plan
- [ ] Manual browser smoke check of `index.html` against running API+worker to verify modal UX and queue transitions visually.
- [ ] Final recognizer polish pass for PLL top-card visual proportions on mobile and desktop.
- [ ] Mobile spacing pass for PLL cards in `index.html` after real-device smoke check.
- [x] Add static reference tables for PLL sets/probabilities/DoD and expose via API.
