# Canonical Algorithm Manifest

Repository-native manifests define canonical algorithm content before SQL seed generation.

## File shape (`manifest_version: 1`)

- Top-level:
  - `manifest_version` (int, required)
  - `category` (string, required)
  - `subset` (string, required)
  - `source` (object, required): `title`, optional `url`, `retrieved_at`, `license`, `notes`
  - `cases` (non-empty list, required)
- Per case:
  - `case_code` (string, required)
  - `display_title` (string, required)
  - `subset` (string, optional; defaults to top-level subset)
  - `sort_order` (int > 0, optional)
  - `recognition_notes` (string, optional)
  - `probability_notes` (string, optional)
  - `algorithms` (non-empty list, required)
- Per algorithm:
  - `name` (string, required)
  - `formula` (string, required)
  - `primary` (bool, exactly one `true` per case)

## Validation contract

- Formulas are validated with:
  - parser (`FormulaConverter.convert_steps`)
  - timeline builder (`build_sandbox_timeline`)
- SQL generation is deterministic from sorted case/algorithm order.
- Seed/import flows call the pilot source-governance validator before formula validation.

## Source Governance (Pilot Gate)

- For ZBLL/ZBLS pilot imports, `source.license` must record an explicit reuse basis:
  - published license text/identifier, or
  - written owner permission with date captured in `source.license` and details in `source.notes`.
- Do not import canonical pilot content when `source.license` is missing or uncertain (`unknown`, `unspecified`, `pending legal review`).
- Keep full provenance fields populated for every pilot manifest:
  - `source.title`
  - `source.url`
  - `source.retrieved_at`
  - `source.license`
  - `source.notes`

## Current fixture

- `data/manifests/zbll_t_fixture.json` is a quarantined ZBLL T fixture (2 cases) used for parser/timeline checks only; it must not be imported into seed/runtime output until source reuse is explicit.
- `data/manifests/zbls_u_pilot.json` is the first bounded ZBLS U pilot slice (2 cases) used for manifest-to-runtime wiring validation.

## Legacy compatibility

- `tools/import_f2l_pdf.py` still accepts legacy `version: 1` F2L payloads in `data/f2l/best_f2l_from_pdf.yaml`.
- New extractions from `tools/import_f2l_pdf.py --extract-yaml` now emit canonical manifest format.
