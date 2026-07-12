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

- [ ] `python -m unittest discover -s tests` passes
- [ ] `python scripts/deck_master.py rc-gate --tier ci --skip-browser-smoke --force` passes (CI tier)
- [ ] `python scripts/deck_master.py agent-doctor --mode preview --output json` not blocked by this change
- [ ] No new absolute local paths, private customer names, tokens, or raw customer material in committed artifacts

## Contracts / schemas

<!-- If you changed a runtime contract or schema under docs/contracts/ or
skills/deck-master/schemas/, name it and whether a migration is documented. -->

## Out of scope / follow-ups

<!-- What is deliberately NOT in this PR. -->
