# Integrate repair baseline, workflows and finalized UI; migrate compact receipts

Draft integration of PR184, PR185, PR187 and PR188 onto main, preserving all four source histories. Humanizer is explicitly deferred. #183 now has migrated native/Web/active SDK consumers, with explicit legacy compatibility and preserved historical campaign executable identities.

Review the complete main-to-head change. Entry: [source/conflict report](https://github.com/MainQuestAI/Deck-Master/blob/codex/unified-repair-20261024/docs/reports/unified-20261024/README.md), [52-issue map](https://github.com/MainQuestAI/Deck-Master/blob/codex/unified-repair-20261024/docs/reports/unified-20261024/issue-matrix.json), [validation](https://github.com/MainQuestAI/Deck-Master/blob/codex/unified-repair-20261024/docs/reports/unified-20261024/VALIDATION.md), [Pro handoff](https://github.com/MainQuestAI/Deck-Master/blob/codex/unified-repair-20261024/docs/reports/unified-20261024/PRO-REVIEW.md).

Runtime candidate: `75551e7d06dd3c7a78e05e9188ac032bbd064da0`; base: `afcc23d1654a6ce24583677c4de9d4a80f0f89bd`. Later evidence-only commits do not change the packaged runtime. Final wheel SHA256: `1059ddce8ce3f51622eae72a18d1e40833c591e22aea45a67632bdc421a1b7d9`; 369 wheel files and 292 tracked runtime source files match their installed bytes. Prior installed candidate b7523c99: 190 passed, 94 runtime modules audited; final expanded wheel selection: 261 passed / 1 autosave-test race; four-case rerun passed and test-only 1c9d9231 removes the redundant saved-button click. Final Q2: 43 outer / 70 inner passed. Details in VALIDATION.md and validation.json.

Important integration repairs: preserve adopted-compose/current request identity; new findings after a prior clean pass remain recoverable; pending-current sidebar navigation cannot fall back to an old revision; combine current_work/outline with the finalized UI; retain exact summary reuse and modal focus ownership. Complete failure/rerun chronology is in validation materials.

Not merge-ready: the second reported new issue is unidentified; current remote CI is unverified; rsvg-convert is unavailable; actual Host/final visual/PPT/external-report/remaining CPU acceptance is incomplete. No user-selected Pro review or merge has run. No issue-closing directives are included.

PR creation from the integration environment was denied (`POST /repos/MainQuestAI/Deck-Master/pulls: Forbidden`). This text is prepared for an authorized creation step after API access is restored; it is not evidence that a PR already exists.
