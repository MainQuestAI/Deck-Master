# Fixed integration validation

This is engineering evidence, **not acceptance of all 52 issues or merge approval**. Humanizer is deferred by the user. No user-selected ChatGPT Pro review or final merge has run. PR creation was denied; this report describes a branch, not an existing PR.

The packaged runtime is `b66cec184e20bbfb34a133980e9ca92bbeb7e9bf` (tree `31b45fa320d0e9f0fa6acadd0233a2c4c3f61016`). Subsequent commits change browser test interactions/assertions and CI test ownership only. The final test/CI candidate is recorded in sources.json; report-only commits may follow. Main remains `afcc23d1654a6ce24583677c4de9d4a80f0f89bd` and all four source heads remain unchanged ancestors.

Wheel SHA256: `fbe010395aa53f5c1e69bb86b55ed47c40fa2cd92541eb5195ab2b9e20b4b2dd`. Python 3.12.14, distribution 1.0.0. All 369 packaged files match the installed wheel; all 292 tracked runtime files match Git blobs. Test runners preload the installed package, audit every imported runtime module, check bundled static resources and compare package bytes before/after. The checked-in `verify-installed.py` also protects multiprocessing children from pytest's source-path insertion.

## Complete suite results

The final full sweeps are complete. Each result retains its exact source/test/runtime identity; earlier narrow selections and interrupted attempts do not substitute for these sweeps.

| Candidate / execution | Result | Evidence |
| --- | --- | --- |
| 2040ca6d full source non-browser/non-render | 4062 passed, 2 skipped, 849 deselected; 1569.02s | source-stable.log/xml |
| 2040ca6d full installed non-browser/non-render | 4062 passed, 2 skipped, 849 deselected; 1550.17s | installed-stable-unit.log/xml and identity |
| b66cec18 full installed non-browser/non-render | 4062 passed, 2 skipped, 849 deselected; 1696.73s | installed-final-unit.log/xml and identity |
| dbd7133b final source non-browser/non-render | 4062 passed, 2 skipped, 849 deselected; 1921.46s | source-final-frozen.log/xml; code/test fingerprints unchanged |
| dbd7133b complete installed browser attempt | 704 passed / 4 failed; all 708 completed; 4535.86s | installed-final3-browser.log/xml and identity |
| 7947b25a final installed browser without missing renderer | 708 passed, zero failures/errors/skips; 4336.99s; original maxfail=15 | installed-final4-browser.log/xml and identity |
| 7947b25a five complete affected modules | 77 passed; 262.90s | final-affected-modules.log/xml and identity |
| 7947b25a unchanged method-scope diagnostic module | 4 passed; 14.29s; 532 successful observed responses, no request/page errors | method-reload-diagnostic.xml; method-reload-network.json |
| b66cec18 production/layout/version complete modules | 14 passed; 91.06s | production-layout-corrected.log/xml |
| a811d828 complete upload/recovery module | 35 passed; 247.47s | reference-full-final.log/xml |
| b66cec18 actual installed PPT render | 1 passed; 6.24s | installed-available-ppt-render.log/xml, actual PPT/PDF/PNG |
| dbd7133b available native/PPT/notes and installation checks | 74 passed / 1 environment-blocked failure, 5 deliberately unselected rsvg cases; 108.32s | installed-available-render-extended.log/xml; renderer-boundaries.json |
| 7947b25a actual PPT assembly / paused exact replay | 3 passed; 13.90s; actual compiled/rendered/readback artifacts retained | installed-assembly-replay.log/xml and identity |
| 7947b25a missing-renderer refusal contract | 1 passed; 2.69s; next page remains blocked | installed-missing-renderer-contract.log/xml and identity |
| Remote integration CI | Old 8dc30210 FAILED; new candidate UNVERIFIED | Exact supplied run below |
| User-selected Pro | NOT_RUN | Parent coordinates |

The installed unit sweep retains its b66cec18 start identity: during that run only browser tests, CI ownership and reports changed; packaged runtime and non-browser test files did not. The exact Git diff is retained in unaffected-unit-reuse.json. This is explicitly reused evidence at its original SHA; the final source sweep uses dbd7133b. The subsequent 7947b25a changes only three browser test functions; AST comparison verifies every other statement, import and fixture is unchanged (final-test-only-reuse.json). Non-browser evidence remains explicitly attributed to its original SHA; the final browser sweep runs 7947b25a.

The two unit skips are unchanged guards for an unavailable external Frozen A installation. They are not passes. Q2 retains all 70 cases, the 180-second inner deadline, isolated interpreter identities and its zero-failure/error/skip rule; child results are retained separately. The final source sweep completed Q2 in 165.902 seconds and the final wheel sweep in 167.069 seconds: 70/70 passed, no failures/errors/skips and 61 actual runtime identity observations.

## Original 12 failures / 3 errors and autosave race

[failure-attribution.json](failure-attribution.json) records every original failed/error node, its trace, classification, fix and complete frozen-suite evidence. The initial broad run began at b8e6ec4f and crossed source edits. Seven startup failures plus three setup errors were caused by parent/child BUILD_ID disagreement, not proven to be random load: an isolated temporary-package reproduction starts healthy, changes one Python file, observes the unchanged parent's cached identity disagree with the child and fail the unchanged 8-second health gate, then restores bytes and becomes healthy again. Setup failures in the first reproducer are retained. Both frozen 2040ca6d full sweeps pass these cases.

The other five failures were: one invalid synthetic clean-owner fixture, two projection-order assumptions, one legacy v1 clean-review compatibility regression, and one lost method-handoff context. Their repairs retain finding identity/closure, v2 final-stage rejection, exact owner counts, disabled unknown candidates, and both fixed manifest and UI recovery context. No service timeout or negative permission assertion was removed.

The earlier installed autosave failure clicked an already-saved disabled button after a 600ms automatic save. The test now checks saved state, disabled save control and refresh restoration; the initial 261/1 result and four-case reruns remain historical, not rewritten as a full pass.

The first expanded installed sweep was interrupted after 1040 passed / 7 failed. [installed-failure-attribution.json](installed-failure-attribution.json) separately maps its topbar product regression, four repository-path assumptions in installed tests, one missing real-render dependency and one hidden-composer interaction. The canonical/installed resource checks were strengthened to exact roots and equal Skill bytes; none were skipped. A separate unguarded test runner also re-entered pytest in multiprocessing children; its two failures are retained, the guarded runner's complete module probe passed 51 cases, and the final full installed run uses the guarded runner.

## Browser failures and integration repairs

[browser-failure-attribution.json](browser-failure-attribution.json) preserves the 2040ca6d full-wheel failure traces and separate focus reproduction. That sweep stopped at the unchanged maxfail=15 with **504 passed / 15 failed**, 3074.83s. The remaining browser cases were not run in that attempt. Focus/journey complete modules independently yielded **13 passed / 5 failed**.

Product repairs retain the current UI: unknown legacy scope exposes optional handoff reads without current production actions; trial details explicitly distinguish a selected fixed basis from full-deck direction or production permission; toolbar and stacked-card whitespace leave the first page visible at the original viewport sizes. The original viewport sizes and geometry thresholds remain; trial permission text is asserted explicitly. Test expectation changes are identified below against their source behavior.

Test corrections follow actual UI entry points, scope nested details selectors, and synchronize dependent summary/control reads while retaining exactly three summary reads at 16 seconds and exactly three control reads. Native popover cancellation restores the visible Project actions button; the removed-trigger title fallback and late-close new-form focus assertions remain unchanged, as does PR187's modal implementation.

The continuous journey now probes a **real visual changes.commit** after a manuscript edit: it must raise `preproduction_blocked` and leave the document unchanged. PR185 intentionally permits zero-call page-copy corrections. After a fresh explicit synthetic review, authorization refs and call facts must remain unchanged; the original candidate/adoption/fixed ZIP checks continue. The UI-created `full_deck` fixture already has its explicitly selected bounded template; the test does not invent an absent-authority premise or issue image calls.

An additional upload continuation race appeared during the affected-module run. A committed upload may retain its result while a private draft is pending; its recovery button may then disappear because a draft-save receipt automatically completes navigation. The test uses the real retained-result action and accepts a timed-out pointer attempt **only** when that button is gone and the actual preview is ready. Original image-alpha, request-identity, single-reference and reload assertions remain. The pointer timeout is 5 seconds, below the previous Playwright default. Initial failures, the insufficient first correction, interrupted broad starts and the final full-module result are all retained.

The complete dbd7133b installed-browser attempt reached all 708 cases: 704 passed / 4 failed. Three failures exposed remaining test merge omissions: closing an outer disclosure with a descendant selector, retaining the pre-RP10 narrative/mapping label, and checking an opinion save button before opening the real composer. Commit 7947b25a repairs those entries, restores the exact RP10 meaning, adds two unmapped-atom and closed-disclosure assertions, and retains the original invalid-atom, disabled-save, annotation, focus, pagination and offline-recovery checks. Five complete affected modules passed all 77 cases; that is separately recorded and does not replace the final full browser sweep.

The fourth failure is **not classified as fixed**: at 1280px a method-preparation refresh remained in the bootstrap shell beyond the unchanged 5-second field assertion. The complete unchanged four-case module passed with read-only network observation (532 requests/responses, zero request or page errors, slowest observed response 0.196s), and again in the 77-case affected run. No wait was relaxed, no retry added and no runtime change made. The original cause remains unestablished; the observation of PID1-owned Chromium zombies is environmental context, not proof of causality. Preserve this intermittent startup risk for Pro review and evaluate it alongside the final full sweep, which passed all 708 selected cases without a failure or skip. Passing reruns do not establish the original cause.

The additional available assembly tests execute actual PPT compilation, rendering and readback from existing synthetic SVG previews. They verify paused exact replay performs no compilation/render/readback/artifact writes and still refuses changed requests, new operations and corrupt receipts. This adds concrete RP-04/RP-05 engineering evidence without claiming actual SVG regeneration or professional visual acceptance.

## CI and tool boundaries

Parent-supplied exact historical CI: push run [40087360087](https://github.com/MainQuestAI/Deck-Master/actions/runs/40087360087) on `8dc3021053495633ed6d85444b81a70721224d24` failed at 11:33:06 UTC. Its [browser job 120853007419](https://github.com/MainQuestAI/Deck-Master/actions/runs/40087360087/job/120853007419) had 689 passed / 21 failed; four unit jobs and render succeeded; wheel/offline/installed recovery stages were skipped. A request for this precise job log returned Forbidden and stopped. Full node traces for all 21 remote failures are unavailable; do not equate those results with local 2040ca6d or later code. Only four static UI files and workbench.py changed in the runtime after that run; compiler/pipeline/quality implementation is unchanged. The old render success is retained as historical implementation evidence, not promoted to final CI or individual browser-render case results.

CI collection proof covers **4913 tests exactly once** across 4064 unit, 139 pure-render and 710 browser cases. The two browser+render cases stay in the required browser job, which installs both toolchains. The pure-render job has no Chromium and now selects `render and not browser`. No case leaves CI. The first auxiliary collection attempt lacked the source-only tools import path; that error is retained and the corrected collection requires zero errors before emitting its proof.

Local `rsvg-convert` is absent. The two actual-render browser cases and other unavailable renderer-dependent cases remain NOT_RUN; marking their real dependency does not make them pass. Existing soffice/pdftoppm completed the real PPT chain with synthetic foreground checks, which is narrower than final customer-facing visual or PPT semantic acceptance. An additional dependency audit identified executable long-notes, native table geometry/path/text-slack, native design and error-contract checks: 74 passed. One temporary candidate-install test failed at install_candidate's mandatory render preflight; the exact child doctor returned exit3/needs_tool solely for rsvg-convert, with Python/resources/soffice/pdftoppm ready. The temporary current activation does not exist. That attempted failure is preserved as blocked, not recast as a pass; no retry or guard bypass occurred. [renderer-boundaries.json](renderer-boundaries.json) distinguishes this test-built candidate from the primary wheel. No renderer download or system change was attempted.

## Remaining gates

- PR creation `POST /repos/MainQuestAI/Deck-Master/pulls` was **denied, Forbidden**. No PR was created, no retry or alternate channel was used. Prepared text: [PR-BODY.md](PR-BODY.md).
- Open PR enumeration, issue #183 read and the exact old browser job-log read were also denied and stopped. PR187's latest CI and new integration CI remain unverified; PR188's prior success is not substituted.
- The starting 51 issues plus #186 are mapped. The second reported new issue remains unidentified. No number, closure or acceptance was guessed.
- One earlier method refresh exceeded the unchanged5s bootstrap assertion; its cause remains unestablished despite complete affected-module and final full-browser passes. This is retained as a stability risk for Pro review, not silently waived.
- Actual Host execution, real external-report repair, user visual judgment, final image/PPT meaning and remaining end-to-end CPU evidence are not established by synthetic tests. No customer production, paid-model batch, monitoring installation, credential change, publication or issue closure occurred.
- Only Humanizer was explicitly deferred. Other missing evidence remains a gate, not a waiver or declared postponement.

Earlier evidence, including first failures, is preserved in [HISTORICAL-VALIDATION.md](HISTORICAL-VALIDATION.md), the old archive and the new stability archive. Use each result only with its recorded SHA and scope.

The final artifact capture includes six viewport PNGs, complete overview/offline-recovery screenshots and results, and the continuous same-project trace plus actual fixed-version review ZIP. The trace records zero model calls and no browser errors; it does not assert professional or user visual acceptance. See final4-browser-artifacts/manifest.json in the stability archive.


Final installed-wheel measurements at test candidate 7947b25a (runtime b66cec18) passed 3/3 in 1.74s. Six synthetic sources each contain 17754 characters; one warm-up and three raw samples per protocol are retained. For 1/13/30 pending tasks, legacy responses were 230759/2993372/6907112 bytes and compact responses were 1226 bytes; JSON object reads were 9/105/241 versus zero. Legacy CPU medians were 3.738627/36.811266/75.847958ms versus 0.056237/0.048177/0.190684ms. All raw samples, including the 1.121228ms compact30 outlier, remain in installed-receipt-measurements.log and final-receipt-measurements/. This measures response construction only, not end-to-end Host latency, temperature or final CPU acceptance.


The 61 NOT_RUN cases classify as **60 requiring real rsvg-convert** (including two browser-render cases) and **one requiring the original immutable external Frozen A installation**. The two additional unit skips also require Frozen A. The attempted failure is exactly `tests/rebuild/test_install.py::test_candidate_install_activate_and_run_doctor`: its temporary child doctor exits3/needs_tool solely for rsvg-convert; current activation does not exist. This demonstrates the required refusal, not a product/script defect to suppress. Minimum completion requires a supported real rsvg-convert in an authorized validation environment and the unchanged test/candidate; Frozen A cases additionally require the original external installation, not a reconstructed substitute. Existing AGENTS.md Stop And Report applies to needs_tool, so no system renderer installation or preflight bypass was attempted. All independent available checks were completed.
