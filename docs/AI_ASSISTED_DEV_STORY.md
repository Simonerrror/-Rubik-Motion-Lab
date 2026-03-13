# AI-Assisted Development Story

This project was built as an iterative AI-assisted engineering process.

## Narrative

- Baseline: one-shot prototype from a single prompt.
- Stabilization: parser/render/UI foundation hardened with tests.
- Productization: behavior invariants, simultaneous move semantics, smooth motion.
- Polish: visual palette alignment and storage ergonomics.
- Cards phase: FastAPI + vanilla cards UI, case-centric PLL workflow, recognizers, and runtime consistency fixes.
- Split phase: trainer becomes fully JS for playback, cards runtime becomes service-only, and the Python renderer moves out into a sibling local mini-repo.

## Commit Map

| Commit | Request Focus | Main Change | Impact |
|---|---|---|---|
| `76a7b93` | bootstrap | repo init + ignore policy | project starts from clean git root |
| `f809d8e` | one-shot baseline | core cube pipeline | first end-to-end engine |
| `5f310ac` | render workflow | CLI + render planning/catalog | reproducible render operations |
| `e75015b` | usability | GUI renderer workflow | practical day-to-day usage |
| `2508d21` | scene invariants | overlay + layout + pre-state behavior | stable composition and readability |
| `ec044f3` | move semantics | simultaneous `+` moves and axis checks | richer algorithm notation support |
| `4ac62be` | motion quality | timing policy + easing + tests | smoother animations |
| `a81c2f7` | visual polish | softened internal dark faces | cohesive palette |
| `b464e4a` | storage contract | readable quality folders + compatibility | cleaner output structure |
| `HEAD` | local split | service-only cards runtime, JS trainer playback, renderer/domain extraction | cleaner product boundary and smaller active repo graph |

## Why This Matters

The value is not only the trainer/runtime product, but the transparent engineering trail:

- prompts -> code
- feedback -> targeted patch
- tests -> confidence
- polishing -> production readiness

## Session Lessons

- Keep domain logic shared and versioned before trying to split repositories.
- Trainer playback is safer when the browser computes timeline/state locally from canonical formula contracts.
- Recognizer assets are easier to operate when grouped by category directories.
