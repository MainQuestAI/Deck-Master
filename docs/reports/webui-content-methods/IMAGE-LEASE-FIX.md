# Full breakdown image dismissal lease fix

The PR run [39513027174](https://github.com/MainQuestAI/Deck-Master/actions/runs/39513027174), head `4582238c50c012b4d1f052235dc5e1b553d5d79f`, failed at the 1280×800 full-breakdown close assertion: dialog hidden and trigger focused, but large-image pins remained 1. Source browser: 554 passed / 1 failed; wheel/offline/installed steps skipped. Its successful parallel push run does not erase this failure. This is separate from the historical mobile-gallery scrolling timeout.

Root cause: native dialog dismissal hides the dialog and restores focus before dispatching the queued `close` event. The full breakdown image released its lease only in that event. Therefore the UI could look closed and be interactive while still owning a large-image lease. This is a resource-lifecycle ordering defect, not evidence of a permanently leaked bitmap or an infrastructure failure.

A real-browser regression records pins synchronously in the trigger's focus handler. On the old implementation, all three viewports (1440×900, 1280×800, 390×844) fail with 1 pin. Existing geometry, focus, screenshot and zero-pin assertions are retained. The repaired regression covers both Escape and the Close button at all three sizes.

The modal helper accepts an optional idempotent `beforeClose` cleanup. For resource-owning dialogs, Escape and the Close button run cleanup before native close/focus restoration; the close event retains fallback cleanup for programmatic dismissal. Only the full-breakdown caller opts in, using the existing image.dispose operation. Cached decoded images remain bounded and reusable. No wait, retry, force-click or relaxed assertion was added.

Product and clean package source: `7730a3dac39fe1023cf15e10fdebb585c551e18e`, based on main `40bbc2851eec3932174c6202305fbc2ce5aede49`. Package identity is in [image-lease-package.json](evidence/image-lease-package.json). Subsequent evidence edits do not change product bytes.

Validation:
- Old implementation: 3 failed / 6 deselected, 7.88s, at the new synchronous focus assertion.
- Source style + common dialog suites: 18 passed, 42.37s.
- Source queued-dialog cases: 4 passed / 17 deselected, 7.63s.
- Full source Ruff and diff checks passed.
- Clean wheel and sdist built; both changed installed JavaScript files match the wheel manifest. Installed style/common/queued dialog browser suites: **22 passed in 46.60s**, using Python3.12, Playwright1.64 and system Chromium151 from a separate test copy without src. Log: [image-lease-installed.log](evidence/image-lease-installed.log). CI uses its own browser installation; local results do not replace it.

Original CI failure excerpt and old-implementation regression are preserved under evidence/image-lease-*.log. New exact-head remote CI is required; this report does not claim a new full local unit/render/browser run. Actual Host, professional review and human acceptance are not evaluated by this repair. No merge, tag or publication performed.
