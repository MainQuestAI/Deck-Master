# Fixed candidate validation

This report is **bounded engineering evidence, not acceptance of all 52 issues and not merge approval**. No Pro review has run. The runtime candidate is `75551e7d06dd3c7a78e05e9188ac032bbd064da0`, tree `8ba3825cb84994da9905064674317300bbd1f6e1`, based on main `afcc23d1654a6ce24583677c4de9d4a80f0f89bd`. Report-only commits may follow; the runtime payload remains the candidate recorded here.

## Results

| Check | Exact scope / source | Result |
| --- | --- | --- |
| Installed candidate | b7523c99; actual wheel and audited module paths | **190 passed**, 94 imported runtime modules entirely within site-packages |
| Wheel byte identity | b7523c99 | 369 wheel files match installed bytes; 292 tracked runtime files match Git blob bytes |
| Q2 full gate | active v3; final carrier unchanged after 1ea3ad22 | **70/70 passed**, 0 failures/errors/skips, 61 isolated runtime identity observations; 118.873 seconds, unchanged 180-second deadline |
| Q2 wrapper + v3 differential suite | 1ea3ad22 (helper bytes unchanged in b7523c99) | **43 outer tests passed**; wrapper independently requires all 70 inner cases |
| Critical conflict browser rerun | final b7523c99 UI/test payload | **14 passed**, 9 unselected; real Chromium, required-browser gate |
| Clean-prior / cancellation | b8e6ec4f runtime and corresponding test change | **8 passed**, 31 unselected; retains negative finding and late-result assertions |
| Native review and recovery | b7523c99 test payload, runtime same as b8e6ec4f | **30 passed**; also included in final installed selection |
| Poll lifecycle | b7523c99 | passed with deferred route/stop/hide-show/control cancellation checks |
| Ruff | b7523c99 | passed on src/deck_master and tests/rebuild |
| Full source unit suite | began at b8e6ec4f; final navigation/test-only follow-up explicitly reverified at b7523c99 | Final counts recorded in validation.json; original failures retained below |
| Full browser suite | initial broad run | interrupted after 34 passed; **not a full-suite pass**. Final installed and conflict selections cover their named cases only |
| Render | final installed candidate | **BLOCKED / needs_tool**: missing rsvg-convert; no rendering or image/PPT semantics pass |
| Remote CI | integration / source PR187 | **UNVERIFIED**; no substitution from PR188's reported prior successes |
| User-selected ChatGPT Pro | whole integration | **NOT_RUN**, parent coordinates after blockers/candidate freeze |

Final wheel: `deck_master-1.0.0-py3-none-any.whl`, SHA256 `1059ddce8ce3f51622eae72a18d1e40833c591e22aea45a67632bdc421a1b7d9`. Python 3.12.14, distribution 1.0.0; actual module `/workspace/deck-wheel-venv/lib/python3.12/site-packages/deck_master/__init__.py`. No real HOME activation or release was performed.

## Failure and rerun chronology

1. First merge probe named a nonexistent test path; no tests ran. The command was corrected, not counted as a pass.
2. First core selection: 6 failures / 32 passes. It exposed merged candidate count/display and changed-dependency contracts, and an old browser label expectation. Resolve shared current relationships while retaining PR188 adopted-content identity and PR185 replan/unknown-call boundaries.
3. Integrated core selection: 3 failures / 122 passes / 18 unselected. One was a true isolated-child source mismatch caused by the original workspace's editable environment; one outline fixture assumed an action list existed when no current action was valid; one clean-pass fixture did not explicitly request its unit under frozen-owner review. Separate environment and exact scoped fixtures replaced those assumptions.
4. Clean-pass fixture retries initially failed frozen-owner checks; those logs remain. Final test explicitly rechecks a clean progression owner. Separate failed-prior, dropped/disjoint finding, blank-observation and final-stage refusals remain unchanged.
5. First installed wheel selection: **1 failure / 161 passes**. The failure was real: a new defect replacing a clean prior pass was refused for lack of an old finding ID. Integration fix b8e6ec4f retains the new finding instead of masking it with an old pass, while preserving continuity/closure for every existing finding. Matching installed rerun: **162 passed**.
6. Broad source first run: **2 failed / 1235 passed / 3 errors / 849 unselected**, then explicitly interrupted. Nested wheel/sdist pip could not resolve its host after the loopback-safe test fixture removed proxy variables. Cached actual dependency wheels were supplied via PIP_NO_INDEX/PIP_FIND_LINKS for the retry; no installation assertion was removed. Broad browser run was interrupted to freeze the repaired candidate, retaining 34 passes and shutdown diagnostics.
7. Conflict browser first run: **3 failed / 5 passed / 15 unselected**. Two tests tried a method action hidden in PR188's explicit More menu; they now open the visible menu. One genuine product failure lost the pending current-version route during a sidebar click. b7523c99 carries that intended route while committed reading/writes stay on their original basis. Final browser rerun: **14 passed**.
8. Full source run found an additional synthetic multiple-clean-owner fixture that assigned `fail` without findings merely to provoke a recheck. It now starts with actual clean owners and explicitly forces the original units. The exact eight owners, sixteen records and per-owner identity assertions remain; final native selection 30 passed and installed selection 190 passed include this fix. An empty failed prior still cannot silently become passing.

All named first logs, retries, Q2 child logs/JUnit/identity observations, screenshots, exact commands, installed probes, wheel hashes and dependency hashes are preserved in the evidence archive, with a hash manifest. Earlier source-branch counts and images remain labeled by their original SHA; they are not promoted to final candidate proof.

## Remaining acceptance gates

- `GET .../pulls?state=open&per_page=100`, `GET .../issues/183` and `POST .../pulls` returned **Forbidden**. Each stopped without an alternate identity/channel or uncertain-write retry. The integration branch push succeeded, but **no unified PR URL was obtained**. Use prepared PR-BODY.md only after authorized API access is restored.
- Known starting scope is 51 recorded issues plus #186. The second reported new issue is still unidentified; no number was invented. Individual criterion closure remains separate from mapped engineering tests.
- Two original old-core compatibility cases require an absent external Frozen A installation and were skipped by their unchanged guard; they are not passes.
- No final full browser sweep or remote CI completion is asserted. Required browser selections did execute; there was no skip-as-pass fallback.
- Actual Host, real external-report repair, user visual judgment, final image/PPT meaning, and applicable end-to-end CPU/temperature claims remain unverified. The response-construction CPU measurements are explicitly narrower.
- Humanizer is deferred by explicit user decision. All other unmet acceptance remains unmet, not waived or silently postponed.

## Final broad-run findings and bounded repairs

The broad source run finished at **4032 passed, 12 failed, 3 errors, 2 skipped, 849 deselected**, 1522.35 seconds; it stopped at the unchanged maxfail=15 limit. It started at b8e6ec4f, so it is historical integration evidence, not a fixed-final-SHA sweep.

- 83cdfecb preserves v1 clean-review compatibility while rejecting failed empty priors and blank observations; v2 final-stage rejection stays intact. Candidate ancestry assertions now select the candidate action by kind instead of assuming it sorts first. All 98 review/freshness/native cases passed. The new negative fixture initially referenced an unsaved subject, then a nonexistent narrative; those setup failures are recorded, and the final fixture stores its own real subject.
- 75551e7d restores PR188 method handoff context, recovery surface, selected resources and digests alongside PR185 structured preview and manifest. Eight source/browser cases passed, including real clipboard/CLI/resource hashes at three viewport sizes.
- Seven service/launcher failures and three setup errors occurred during the broad run (8-second health deadline or absent review URL). Studio launch, journal restart, three Web launch cases, service reuse and all 19 workbench-service cases passed separate reruns. The deadline is unchanged. Full-run service stability remains **unresolved**, not waived as a flaky test.
- The late browser-required invocation selected only unmarked contract tests and correctly refused to run; the corrected named contract selection ran. No such zero-test invocation is counted as passing.

The b7523c99 wheel result above is prior evidence. The final 75551e7d wheel has SHA256 `1059ddce8ce3f51622eae72a18d1e40833c591e22aea45a67632bdc421a1b7d9`; 369 installed files and 292 Git-tracked runtime files match byte-for-byte. Final installed/Q2 results are recorded in validation.json.

## Final installed expanded selection

The actual 75551e7d wheel produced **261 passed, 1 failed** in 318.44 seconds. All 98 imported runtime modules were audited inside site-packages. The failure was the 1440px method preparation test clicking an already-saved disabled button after its clipboard and CLI checks; DraftEditor automatically saves 600ms after changes. The unchanged four-case module independently reran **4 passed**. Test-only commit `1c9d9231` now asserts the real saved status, disabled save button and refresh restoration rather than racing a redundant click. The corrected module result is recorded in validation.json. No timeout was enlarged and no persistence/resource/scope assertion was removed. The expanded run is retained as **261/1**, not rewritten as a clean 262-test run.

Final Q2 rerun at 75551e7d: **43 outer tests passed in 165.06 seconds**, including **70 inner cases, zero failures/errors/skips, 61 isolated runtime identity observations**. The inner 180-second limit remains unchanged.
