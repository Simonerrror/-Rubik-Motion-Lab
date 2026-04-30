---
schema: agentcompanies/v1
kind: task-index
---

# Paperclip Tasks

This directory stores reviewable task briefs for Paperclip agents.

Task briefs are repository planning artifacts only. Canonical algorithm content,
runtime data, generated assets, and tests must still live in the repository
proper and pass the project validation flow before deployment.

Default routing:

- Product Lead owns milestone boundaries and source approval decisions.
- Content Engineer owns manifests, seed/runtime wiring, and parser validation.
- QA Reviewer owns regression, smoke, generated asset, and deployment checks.
