# Integrate repair workflows and finalized UI; migrate owned compact-receipt callers

## Summary

Integrate PR184, PR185, PR187 and PR188 into one main-targeted change while retaining all source histories. #183 now migrates owned native/SDK/Web/Host consumers, negotiates compact receipts and retains explicit legacy-client compatibility. Historical campaign executables remain frozen; the active v3 carrier has its own identity. Humanizer is explicitly deferred.

## Issue / cause / scope

Refs #183, #138, #186, #133, #142; the full52-item mapping is linked below. Repairs and finalized UI diverged across source branches; integration must preserve both business boundaries and actual interactions. No issue is claimed closed.

Preserve PR188's complete UI and adopted-compose/unread-result behavior, PR185's dependency/scope/unknown-call recovery, and PR187's current_work/outline/source-finding/external-report/diff/summary/focus fixes. Integration follow-ups restore method handoff context, legacy v1 clean-review compatibility, optional historical handoff reads, trial permission wording and usable first-screen layout. Review the entire main-to-head diff, including the shared business conflict decisions and browser synchronization changes.

Base: `afcc23d1654a6ce24583677c4de9d4a80f0f89bd`. Packaged runtime: `b66cec184e20bbfb34a133980e9ca92bbeb7e9bf`. Test/CI candidate and source ancestry are fixed in [sources.json](https://github.com/MainQuestAI/Deck-Master/blob/codex/unified-repair-20261024/docs/reports/unified-20261024/sources.json); later report-only commits do not change runtime/test payloads. Wheel SHA256: `fbe010395aa53f5c1e69bb86b55ed47c40fa2cd92541eb5195ab2b9e20b4b2dd`; 369 installed package files and 292 tracked runtime files match byte-for-byte.

## Type

- [x] feat
- [x] fix
- [x] chore
- [x] refactor
- [x] test

## Verification

Validation: final source and actual-wheel non-browser/non-render sweeps each passed **4062 tests with two unchanged external Frozen A skips**; the complete installed browser sweep passed **708/708, no failures/errors/skips** (4336.99s). Q2 retained all 70 cases and the 180-second limit: source165.902s / wheel167.069s, all70 passed with61 actual runtime observations each. Available rendering added one actual PPT-chain pass, 74 native/PPT/notes passes, three actual assembly/paused-replay passes and one missing-renderer refusal pass. One temporary installation preflight failed solely because rsvg-convert is absent; it was not bypassed or called a pass. Missing dependency cases remain individually listed in the [validation matrix](https://github.com/MainQuestAI/Deck-Master/blob/codex/unified-repair-20261024/docs/reports/unified-20261024/VALIDATION.md).

First failures and all reruns remain recorded: original source12fail/3error, old8dc30210 remote browser689pass/21fail, intermediate local504pass/15fail, and dbd7133b complete704pass/4fail. Three final test merge omissions were repaired at7947b25a and five complete affected modules passed77/77. One earlier method-page reload stayed in the startup shell beyond the original5s assertion; unchanged diagnostic/module/full reruns pass, but its original cause remains unresolved and is explicitly carried to Pro review.

Review entry points: [source/conflict report](https://github.com/MainQuestAI/Deck-Master/blob/codex/unified-repair-20261024/docs/reports/unified-20261024/README.md), [52-issue mapping](https://github.com/MainQuestAI/Deck-Master/blob/codex/unified-repair-20261024/docs/reports/unified-20261024/issue-matrix.json), [failure attribution](https://github.com/MainQuestAI/Deck-Master/blob/codex/unified-repair-20261024/docs/reports/unified-20261024/browser-failure-attribution.json), [reproduction](https://github.com/MainQuestAI/Deck-Master/blob/codex/unified-repair-20261024/docs/reports/unified-20261024/REPRODUCE.md), and [user-selected Pro review prompt](https://github.com/MainQuestAI/Deck-Master/blob/codex/unified-repair-20261024/docs/reports/unified-20261024/PRO-REVIEW.md).

- [x] Relevant focused tests and full available suites executed; exact commands, results and missing prerequisites are in REPRODUCE.md / VALIDATION.md.
- [x] `python -m ruff check src/deck_master tests/rebuild` passes on7947b25a.
- [ ] Final candidate Rebuilt Core Gate verified (unit matrix, real rendering, required browser, installed wheel/offline UI and recovery): new remote CI is not verified.
- [x] Actual render-doctor and installed `deck-master capabilities` observations recorded. Render doctor reports needs_tool; capability readiness does not establish independent review or Host execution.
- [ ] No new absolute local paths, private customer names, tokens, or raw customer material in committed artifacts.

The last checkbox is not attested as written: the requested technical audit intentionally retains isolated sandbox installation/evidence paths. No private customer materials or credentials were introduced. These are review reports, not customer-facing deliverables.

## Contracts / schemas

Runtime truth remains `src/deck_master/resources/contracts/`. [contract-mirrors.json](https://github.com/MainQuestAI/Deck-Master/blob/codex/unified-repair-20261024/docs/reports/unified-20261024/contract-mirrors.json) enumerates all14 changed schemas and their sole byte-identical spec mirrors, including task/review/document/asset/content-requirement and workbench summary/target/lineage contracts. Complete source and installed package-boundary checks pass. Existing writer floors, fixed historical Tasks, scope and authorization boundaries remain; compact reads/receipts do not grant production authority or lower compatibility floors.

## Compatibility / documentation / delivery

Owned callers explicitly migrate to task_receipt.v1 and still read full work_context.v2. Omitted protocol remains the external legacy-client compatibility path; historical hash-bound campaign executables remain intact and activev3 has distinct identity. See receipt-consumers.json and the52-issue mapping. Real Host, image/PPT meaning and user approval are separate from engineering metrics. Delivery remains pending: no release tag, publication or merge was performed.

## Out of scope / follow-ups

Humanizer is explicitly deferred and its independent branch is untouched. No customer production, paid-model batch, monitoring installation, credential change or issue closure was performed.

These are unmet acceptance gates, not approved deferrals.

Not merge-ready: the second reported new issue remains unidentified; latest integration/source-187 CI is unverified; the earlier intermittent startup cause is unresolved; rsvg-convert and external Frozen A evidence are unavailable; actual Host, external-report real repair, final visual/PPT meaning, user judgment and remaining CPU acceptance are incomplete. No user-selected ChatGPT Pro review or final merge has run, and no issue-closing directives are included.

PR creation was denied (`POST /repos/MainQuestAI/Deck-Master/pulls: Forbidden`) and was not retried or bypassed. This is prepared creation text, not evidence that a PR exists. The final pushed branch can be opened in the repository's existing comparison page by the authorized user.
