# ZBLL SpeedCubeDB Source Review

Date: 2026-04-30
Category: ZBLL
Source: https://speedcubedb.com/a/3x3/ZBLL

## Decision

Import the full visible ZBLL aggregate-page set from SpeedCubeDB into the canonical trainer manifest.

## Basis

- Product owner explicitly directed the full ZBLL import on 2026-04-30.
- The imported data preserves SpeedCubeDB attribution in the canonical manifest metadata.
- The importer stores source URL, retrieval date, subset provenance, and source subgroup per case.

## Scope

- Included subsets: U, L, T, H, Pi, S, AS.
- Included algorithms: visible algorithms rendered on each subset aggregate page.
- Excluded data: interactive "More Algorithms" expansion content that is not present in the initial aggregate-page HTML.

## Follow-Up

- If a stricter redistribution policy is needed later, replace this source manifest with an internally-authored or explicitly licensed manifest and regenerate the seed/runtime/catalog artifacts.
