# UI implementation status · 2026-10-24

User authorized continuous product implementation, isolated branch/worktree, push and PR on 2026-10-24. This supersedes the planning-only boundary in the archived plan; it does not authorize modifying customer projects or merging the resulting PR.

## Baseline

- Parent PR: https://github.com/MainQuestAI/Deck-Master/pull/184 (open, unmerged at start).
- Parent head: `7bbf204658dfc39f53fa34352543168e7eee1e65`.
- Parent remote main: `afcc23d1654a6ce24583677c4de9d4a80f0f89bd`.
- Implementation branch: `codex/ui-refactor-20261024`; PR will initially target the parent branch if still unmerged.
- Original dirty checkout is untouched. Development environment is isolated in the new worktree.
- Actual UI: `/studio/`, native v2 ES modules; 9 initial sheets plus dynamic comparison sheet. No new framework or polling owner.

## Phase ledger

| Phase | Status | Evidence / remaining work |
| --- | --- | --- |
| E0 | IMPLEMENTED | PR184 remote head rechecked unchanged; isolated managed worktree and codex branch, original checkout untouched. |
| E1 | IMPLEMENTED | 99 semantic tokens; 172 button and 33 field/status appearance rules consolidated. Object menus, project recovery menu and 0/1/30-project launcher geometry verified. |
| E2 | IMPLEMENTED | Current relationship shared by summary/task/candidate reads; object identity metadata; three content areas; stable selection, contextual movement and selection-first production. |
| E3 | IMPLEMENTED | Six reading layers; bounded long copy; nonmodal source inspection; 440/880 editor retaining drafts, validation, exact range and keyboard boundary. |
| E4 | IMPLEMENTED | Selection-first gallery; existing pinned candidate comparison and adoption retained; decision controls fit desktop viewports; shared candidate identities preserved. |
| E5 | IMPLEMENTED_WITH_DEPENDENCIES | V1/V2/V3 recipe reading, existing two-source/four-phase flow, task subareas and fixed exports; narrow exact-replay fixes and finding-set continuity. RP-18 and external #186 closure remain explicitly outside this UI slice. |
| E6 | VERIFIED_WITH_LIMITS | Source/installed regression and 30 screenshots are recorded in VERIFICATION.md. Six ACs remain PARTIAL; final full browser sweep and remote CI tracked below. |

## Dependencies and ownership

- RP-00: retrieved original Git objects and cherry-picked narrow patches 84a63131 / f1ac7a71 as 1ff3195b / 67c15930, retaining attribution. PR147 lightweight reads and single-flight polling integrated as 6d2023dc.
- RP-04: annotations.save and styles.references.import now recover the exact committed receipt before new-write eligibility. Changed payloads and new operations remain blocked after pause; other RP-04 scope is not declared closed.
- RP-08 / #182 owns current relationship projection before UI issue #132 can close.
- RP-09 / #181 owns mixed style schema reading before #141 closes.
- #186: this implementation owns investigation and the minimum finding-continuity dependency; it must not close findings from a generic new pass.
- The UI plan does not claim closure of all 51 repair issues. Original RP owners and evidence boundaries remain.

## Verification

Product ACs link concrete tests in acceptance-matrix.json. A PARTIAL status identifies a still-unverified dependency or evidence layer; prototype passes are not product passes. No actual Host generation, customer export, default installation activation or user acceptance has been run.

### E1 initial verification

- Isolated environment imports this worktree via editable install; Playwright 1.61.0 matches the available Chromium cache. No global activation.
- First attempt: 10 passed, 6 environment failures (new Playwright browser executable absent). Corrected isolated dependency to existing browser version.
- After initial control migration: 16 passed (font tokens, Studio integration including lost-response upload/drafts, overview).
- Follow-up: 13 passed (overview, UI design, font tokens, static modules).
- Native popover regression included: 9 passed in UI design suite; narrow scroll containment, keyboard Escape focus return and correct page/layer navigation.
- A discovered screen-reader label escaped table clipping on narrow screens; positioned its icon trigger locally and reran geometry tests.
- Token generator --check, CSS parse and git diff --check pass. These are incremental source/browser checks, not the final same-commit AC ledger.

### Required repair dependencies

- 45 passed: native review, transport, RC3 style workflows, original candidate references and summary polling. Narrow patches are retrievable in this branch.
- Exact replay regression first failed on both affected operations. Fix preserves the original committed receipt and immutable operation payload. New writes and changed-payload replays remain rejected.
- 97 passed: exact replay after pause, annotations, visual styles, eligibility entry coverage, content preproduction review and UI journal.

### E3 single-page editor

- 440px drawer expands to 880px, becomes full width on narrow screens. Same mounted form and DraftEditor keep close/reopen drafts and exact-range dialogs. Inline title validation prevents invalid planning requests.
- Source inspection and its material reader remain nonmodal and bound to the selected revision. Reader requests abort on replacement or disposal.
- 24 existing browser cases passed after migrating to the named dialog trigger and explicit close before navigation. New keyboard regression found Tab escaping to browser chrome; explicit boundary handling fixed it.
- Follow-up 14 passed: exact range, draft retention, narrow/editor geometry, long-copy diff/impact visibility, and UI geometry/keyboard suite.
- Synthetic screenshots: evidence/single-page-editor/. No customer content or Host generation.

### E2 current relationship (RP-08 slice)

- Summary, run desk and candidate selection consume the same request/basis relationship. Historical failures remain failed, stale candidates remain undecided; neither is promoted into the current action queue. Unknown calls remain verification obligations.
- Candidate basis comparison is extracted from the existing candidate reader, preserving visual-equivalence and adopted target semantics. This is not a new permission gate or a replacement for adoption planning.
- All referenced historical snapshot signatures join the summary cache guard. Corruption invalidates warm results; repairing the snapshot restores eligibility projection without rewriting business state.
- Current task cards and action targets expose stage, scope, timestamp, identity and current relationship. Object counts and affected-page counts are distinct. Unreadable/unknown actions follow enabled actions.
- 90 passed across shared-currentness, overview, task/candidate service and action-target Chromium navigation tests. Follow-up 5 passed includes explicit request replacement and retained background scope.
- Existing navigation fixtures now carry real current-request bindings. Old unbound synthetic tasks no longer silently qualify as current handoffs.
- Initial pressure samples: 24 pages / 120 candidates, 99.0ms first read and 6.9/6.2ms warm; 100 pages / 500 candidates, 365.5ms first and 18.4/17.7ms warm. This local read sample is not a before/after CPU benchmark or full #142/#182 closure.
- RP-03/RP-06 and unresolved finding continuity remain separate dependencies. No issue is declared closed by this slice.

### E1/E2/E4 presentation and E5 mixed recipes

- Three content areas: manuscript, chapters/plan, materials/sources. Notes, arguments and methods remain accessible in the auxiliary menu and existing deep links. Page movement is contextual; batch editing appears only after selection.
- Thirty-page selection test retains pages 2/28 through filtering, counts outside-filter selections, adds only visible objects with select-all, and restores exact stable IDs after reload. Alt-arrow reorder retains the same focused object.
- Global project menu owns personal-state recovery; project-list removal uses a named object menu. Existing create/open recovery remains unchanged.
- Field/status appearance migrated from 33 legacy rules to the shared control recipes; migration inventory is field-status-migration.json. Stack flow now provides real spacing. Gallery production tools are hidden with zero selection.
- 20 passed initial content/navigation/recovery checks; 9 passed style checks including V3 without original images and mixed V1/V2/V3 immutable records; 50 passed subsequent cross-surface browser checks; 18 passed launcher/intake/recovery checks. These incremental runs precede final E6 evidence.
- All recipe versions are readable in the confirmed catalog. V3 exposes seven typed dimensions and planning coverage; feasibility stays zero-call. Selected recipe does not claim applied current design. Candidate lists bind the exact recipe ref.
- Added FINDING-CONTINUITY.md: existing fixed-review handoff preserves the whole finding set; external professional report normalization and unbound repair-ledger continuity remain #186 work. No closure claimed.
- Full-suite collection initially failed when invoking the pytest executable (repository tools namespace absent). Retried with the CI-equivalent python -m pytest entry. Ruff also found an undefined snapshot callback in the earlier currentness patch's unrelated visual-basis function; restored its original snapshot reader before rerunning.


### Final regression findings and evidence boundaries

- Read context initialization now accepts the minimal document used by pinned-directory integrity checks; runtime/spec schema mirrors are byte-identical again.
- Reading evidence and design parameters are collapsed by default. Deep links to a fixed review/atom expand their bound source inspection; opening the editor closes source inspection and resets annotation mode.
- Candidate metadata is compact without dropping stage, stable page identity, return time or request relationship. Both 1440×900 and 1280×800 keep the image and decision actions together.
- Product screenshots cover five workspaces, page reading and its editor at 1440/1280/390. Launcher screenshots cover 0/1/30 registered synthetic projects, long titles and a missing location. [Screenshot browser](evidence/product-screens/index.html).
- The initial broad unit run used macOS `/private` temporary paths, triggering the campaign recorder's existing path refusal. The final run uses an isolated non-private basetemp without changing those rules. Source edits during an earlier run also invalidated the captured service BUILD_ID; final service verification uses a frozen product tree.
- Local native render run: 125 passed, 8 failed, 1 skipped. All 8 failures reproduce on the untouched PR184 head under the same macOS renderer/font environment (parent comparison: 8 failed, 1 passed). They are not relabelled passing or treated as UI regression fixes. Linux CI rendering is recorded separately.
- Minimal native `<select>` control probe in local macOS Chromium also fails ArrowDown→Enter with no application handlers; the full keyboard-path test remains enabled. Its Linux CI outcome and local limitation are tracked separately; no product key handler or test skip was added to mask it.

- Full source unit regression on frozen 750e19d7: **3526 passed, 2 skipped**. The two skips require the external frozen A installation used by historical-writer compatibility checks; they are not counted as passes. Subsequent final changes are limited to explicit historical-candidate preview eligibility, task empty-state text and secondary-action disclosure; their impacted suites and final installed resources are rechecked separately.
- Broad browser testing caught a real recommendation/permission conflation. A historical request no longer hides an explicit preview of a still-current candidate. Automatic recommendations still exclude it; adoption remains subject to unchanged request, basis and authorization checks. Stale generation basis remains unselectable.
- Screenshot regression caught a native DOM append coercing a conditional to the text `false`; the optional legacy panel is now appended conditionally. The seven-surface evidence test rejects standalone booleans/object strings in the rendered work area.
- Overview initially exposes two secondary matters; the remaining named group is keyboard-expandable. All underlying action targets remain available, while the first matrix row fits the desktop screen.

- Independent installed-wheel recovery suite: **257 passed**. The final subsequent overview-only change is additionally checked against the rebuilt wheel with installed-module path auditing, including natural summary polling, object menus, seven workspaces and launcher geometry.
- Real timer polling now preserves an open row menu and focus only when its fixed action identity is unchanged. Changed result membership closes the old action instead of transferring Enter to another operation. The focused regression suite passed 16 cases.

### Frozen product delivery

- Product commit: `6d1a6ff0787640a59628f56c0b6a055bc01af20c`. Parent PR184 remains open at its original `7bbf2046` head; the implementation PR targets `codex/repair-plan-baseline-20261023`.
- Final source service/current-relationship sweep: **83 passed**. This covers every service failure from the run interrupted by a product BUILD_ID change; its other 3512 passes are retained as incremental evidence, not mislabeled a clean final full-suite pass.
- Final installed-wheel supplemental suite: **62 passed**, all 79 runtime modules loaded from site-packages. Final offline export/resource check: **9 verified**. The 243 shared source/package files match byte-for-byte; the wheel contains nine additional build-hook method files. Evidence: [installed-release.json](evidence/installed-release.json).
- Candidate permission/material-state follow-up: **20 passed**. Method initialization, stable-checkbox identity, narrow image geometry and version-change editing: **5 passed**.
- Thirty actual product screenshots regenerated from the final wheel; all 30 views load in the artifact viewer and the 390px viewer has no horizontal overflow.
- AC ledger: **24 PASS_AUTOMATED / 6 PARTIAL**. These are synthetic product checks, not customer, native OS or professional approval.
- Final complete local browser sweep: RUNNING. Final remote workflow for product commit: [40010957909](https://github.com/MainQuestAI/Deck-Master/actions/runs/40010957909), RUNNING at this record. The earlier product commit had four Linux unit jobs and Linux render pass; its outdated browser job was cancelled when superseded.
- Nothing was merged or activated in the default installation. Original checkout and user projects remain untouched.
