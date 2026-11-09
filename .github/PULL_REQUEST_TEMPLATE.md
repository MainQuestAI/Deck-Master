# Pull Request Template

## Summary

<!-- One paragraph: what does this PR change and why. -->

## Issue / cause / scope

<!-- Link a real Issue when present; no placeholder Issue required. Use Refs #N
for partial work, Fixes #N only for a complete fix targeting the default branch.
Explain root cause (or unknown), affected users, scope and non-goals. -->

## Type

- [ ] feat (new capability)
- [ ] fix (bug)
- [ ] chore (docs / CI / governance)
- [ ] refactor
- [ ] test

## Verification

<!-- Commands you ran and their result. Do not claim production readiness. -->

- [ ] Relevant focused tests collected and executed; exact commands, results and missing prerequisites recorded
- [ ] Relevant [Rust core and deck-tools checks](workflows/rust.yml) verified; skipped checks and missing tools recorded
- [ ] Actual `deck doctor` results recorded where relevant
- [ ] No new absolute local paths, private customer names, tokens, or raw customer material in committed artifacts

## Contracts / schemas

<!-- Describe persistent-format changes and migrations when relevant; follow
AGENTS.md and the Rust rebuild plan. -->

## Compatibility / documentation / delivery

<!-- Note compatibility, migration and documentation effects, or explain N/A.
For content quality: link sanitized input, before/after, model/settings and
professional judgment; metrics do not establish user acceptance.
Merged is not released: record pending delivery until an actual release tag
and Issue/PR links are available. Do not invent a target date. -->

## Out of scope / follow-ups

<!-- What is deliberately NOT in this PR. -->
