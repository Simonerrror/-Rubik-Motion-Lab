# ZBLS U Pilot Source Review (RUB-9)

Date: 2026-04-30
Reviewer role: Content Engineer

## Scope

- Pilot-only ZBLS `U` subset import
- Keep subset bounded to 2 cases before broader rollout

## Reviewed source

- Internal authored content package for runtime-wiring validation:
  - `data/manifests/zbls_u_pilot.json`

## Selected cases for pilot

- `ZBLS_U01`
- `ZBLS_U02`

## Transformations applied

- Normalized spacing and prime notation to repository parser format.
- Preserved stable case keys in `ZBLS_<subset><index>` form.
- Marked one primary algorithm per case.

## Attribution and licensing notes

- Source attribution is preserved in the manifest source block.
- Reuse basis is explicit and repository-local:
  - `Copyright (c) 2026 Rubik Motion Lab`
  - Redistribution in this repository is approved by product owner decision dated `2026-04-30`.

## Manifest artifact

- `data/manifests/zbls_u_pilot.json`
