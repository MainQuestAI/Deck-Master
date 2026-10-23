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
| E0 | IN_PROGRESS | Live remote baseline recorded; actual code differs from the earlier local inventory. |
| E1 | IN_PROGRESS | 99 semantic tokens now feed generated CSS; 172 overlapping button rules migrated to controls.css; bounded actions, neutral selected navigation, native row popovers. Forms/status and global menus still pending. |
| E2 | IN_PROGRESS | Overview priority, selection-first batch actions, shared current relationship and task identity metadata implemented. Content/sequence/materials refinements still pending. |
| E3 | IN_PROGRESS | Single page reading width; nonmodal source inspection; 440/880 modal editor with retained drafts, title validation and keyboard focus loop. Annotation/mode and complete lifecycle checks still pending. |
| E4 | NOT_RUN | Gallery, pinned candidate comparison, adoption/keep. |
| E5 | NOT_RUN | Style phases, task/version/export, exact replay and finding continuity. |
| E6 | NOT_RUN | Full functional inventory, same-candidate regressions, browser evidence and isolated package checks. |

## Dependencies and ownership

- RP-00: retrieved original Git objects and cherry-picked narrow patches 84a63131 / f1ac7a71 as 1ff3195b / 67c15930, retaining attribution. PR147 lightweight reads and single-flight polling integrated as 6d2023dc.
- RP-04: annotations.save and styles.references.import now recover the exact committed receipt before new-write eligibility. Changed payloads and new operations remain blocked after pause; other RP-04 scope is not declared closed.
- RP-08 / #182 owns current relationship projection before UI issue #132 can close.
- RP-09 / #181 owns mixed style schema reading before #141 closes.
- #186: this implementation owns investigation and the minimum finding-continuity dependency; it must not close findings from a generic new pass.
- The UI plan does not claim closure of all 51 repair issues. Original RP owners and evidence boundaries remain.

## Verification

All product ACs remain NOT_RUN until a concrete test or browser observation is linked. Prototype passes are not product passes. No actual Host generation, customer export, default installation activation or user acceptance has been run.

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
