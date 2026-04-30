# ZBLS CubeZone Source Review

Date: 2026-04-30
Category: ZBLS
Source: https://www.cubezone.be/zbf2l.html

## Decision

Import the full visible CubeZone ZB First Two Layers set into the canonical trainer manifest as ZBLS.

## Basis

- Product owner explicitly directed the full ZBLS import on 2026-04-30.
- CubeZone publicly lists ZB First Two Layers as 306 cases across the individual subgroup pages.
- The imported data preserves CubeZone/Lars Vandenbergh attribution in the canonical manifest metadata.
- The importer stores source URL, retrieval date, subgroup provenance, and source sticker id per case.

## Scope

- Included subgroups: ConU, SepU, InsertE, InsertC, and ConF2L pages linked from the CubeZone ZB F2L overview.
- Included algorithms: visible algorithm cells from the individual subgroup pages.
- Source quirk: `ConF2L_1 #06` has a visible case image but a blank formula cell. It is retained as a case with neutral identity placeholder `U U'` so runtime trainer records remain non-empty.

## Follow-Up

- If a stricter redistribution policy is needed later, replace this source manifest with an internally-authored or explicitly licensed manifest and regenerate the seed/runtime/catalog artifacts.
