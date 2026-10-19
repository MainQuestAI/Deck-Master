# Pull Request Template

## Summary

<!-- One paragraph: what does this PR change and why. -->

## Type

- [ ] feat (new capability)
- [ ] fix (bug)
- [ ] chore (docs / CI / governance)
- [ ] refactor
- [ ] test

## Verification

<!-- Commands you ran and their result. Do not claim production readiness. -->

- [ ] Relevant focused tests collected and executed; exact commands, results and missing prerequisites recorded
- [ ] `python -m ruff check src/deck_master tests/rebuild` passes
- [ ] Final candidate [Rebuilt Core Gate](workflows/rebuild.yml) verified: unit matrix, real rendering, required browser, installed wheel/offline UI and recovery
- [ ] Actual `deck-master doctor --step <affected_step>` / `deck-master capabilities` results recorded where relevant
- [ ] No new absolute local paths, private customer names, tokens, or raw customer material in committed artifacts

## Contracts / schemas

<!-- Runtime schema truth is src/deck_master/resources/contracts/. Name changed
contracts, their sole registered spec mirrors and compatibility/writer-floor
behavior. Check tests/rebuild/test_package_boundary.py. -->

## Out of scope / follow-ups

<!-- What is deliberately NOT in this PR. -->
