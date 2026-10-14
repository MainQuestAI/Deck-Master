---
name: deck-review
description: Review fixed deck content and artifacts or produce a strictly read-only external report, preserving the real reviewer identity and assurance.
---

# Deck Review

Read the shared [review and repair](../deck-master/references/review-and-repair.md), [content methods](../deck-master/references/content-methods.md) and [paired calibration examples](../deck-master/references/content-calibration.md). Use the installed runtime's review work order and exact subject refs.

For an existing project inspect `deck-master capabilities`, `continue --project … --json` and `task status`. Cover only the requested stage and actual missing dimensions. Preserve the first Owner-visible draft separately from repaired content. A new execution or a renamed Skill does not establish independence; when the trusted review channel is unavailable report `needs_reviewer`. Self-review remains `host_self`, and extraction remains `tool`. Never claim human, professional or desktop acceptance without its actual evidence.

For external files use `deck-master review evaluate SOURCE --persistence none`; any report output must be outside the source directory. This extracts actual bytes and notes but does not initialize or mutate the source project, grant permissions or certify semantic quality. Import is a separate explicit scoped transaction bound to exact source hashes and current Page refs. Imported unverified reports remain tool/needs_review. Retrying a write uses the original operation ID and payload; content repair is routed back to content work, conversion errors to the affected artifact layer.
