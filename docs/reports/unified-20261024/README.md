# Unified repair integration — 2026-10-24

Status: **draft integration, not accepted, not merge-ready**. No Pro review or final merge has run. Humanizer is explicitly deferred by the user; its source branch remains untouched.

## Locked sources

| Role | Exact source |
| --- | --- |
| main base | `afcc23d1654a6ce24583677c4de9d4a80f0f89bd` |
| PR184 plan | `7bbf204658dfc39f53fa34352543168e7eee1e65` (original plan `55adc97c5bb5f16ae7fcff7c33c43969fae9ce97`) |
| PR185 repairs | `bf4f661bfec4aa28db2869aaf43494d6cf0f4b8d` |
| PR187 workflow | `870db06e7067c935b2331ade7f39e6bc20b8393d` |
| PR188 UI | `159cfd63e9bcf71c10d98dad45a1a2567eb52136` |

The initial `git ls-remote --heads origin` confirmed these heads and no existing integration branch. A later readback found all source heads and main unchanged; the integration branch then pointed to the earlier 8dc30210 candidate. PR185 and PR187 diverge at `601f5ec6`; PR188 descends from PR184 and does not contain their full increments. The integration starts at PR188, merges PR185 (`a308be5a`), then PR187 (`c4e925d3`), retaining both parents and all source history. Integration fixes/consumer migration are `1ea3ad22`; new-finding recovery and action priority repair are `b8e6ec4f`; pending-current navigation and combined-contract fixture repairs are `b7523c99`. No source branch was rewritten or merged to main.

## Conflict decisions

- Keep PR188 manuscript reading, tools drawer, compact controls, mobile interactions, originating workspace, candidate decisions, adopted-compose identity and unread result visibility. Merge PR185 queued-navigation intent and PR187 current_work/outline entry points into that UI.
- Use PR188 snapshot-scoped CurrentRelationships as the active UI relationship projection, retaining its adopted-content receipt verification. Add PR185 changed-dependency replan, full-scope successor proof and unknown-call-only recovery. Preserve source task status and immutable candidate history. `pending_count` retains undecided history; `historical_count`/`actionable_count` distinguish current work. `stale_count` is a compatibility count of historical candidates. Source RP08 assertions were ported to this explicit combined contract, retaining the 22-record/one-action and two-distinct-basis checks.
- Keep action-target display facts from PR185 plus PR188 current relation and kind/creation fields. Keep exact original recipe/reference bytes and all v1/v2/v3 design records; preserve feasibility and production eligibility boundaries.
- Combine PR188 poll cancellation/control-light compatibility with PR187 exact summary reuse. Preserve modal content ownership, removed-trigger fallback and queued-close focus protection.
- Keep PR187 scoped original-finding/source repair and external-report handoff. Extend PR188 clean-prior replacement handling to retain genuinely new findings on a later recheck, as required by PR187 recovery; no invented findings or dropping failed findings. The synthetic clean-pass and multi-owner regressions now explicitly request rechecking clean units/owners; separate failed-prior/drop/disjoint/empty-observation/final-stage rejection cases remain.
- Keep full review-owner, outline, source, authorization/adoption, asynchronous recovery and writer boundaries. These require integrated tests, not trust in a clean textual merge.

## #183 consumer migration

Native review claim/checkpoint/recovery/accept paths and current repository workbench examples explicitly request `task_receipt.v1`. Browser cancellation negotiates the advertised `task_receipt.v1` UI capability, then verifies the actual Task through the existing recovery read. Managed Host instructions require capability discovery and the explicit flag, followed by full `work_context.v2` reading. CLI/service omission remains the legacy compatibility path for external clients; no claim can be made about unowned external consumers.

Historical campaign executables are hash-bound evidence and remain byte-for-byte intact. New `controller_v3.py`, `supplementary_recorder_v3.py`, `q2_later_300_v3.py` carry compact mutation calls with distinct sibling hashes and control/registration identity. Active 70-case carrier points to v3; all 70 identities, assertions, 180-second deadline and isolated-interpreter requirements remain. V1/v2 checks remain present; the differential identity suite also covers v3. Existing campaign controls are not silently migrated or authorized for new execution.

## Acceptance and blockers

See [reproduction and installation notes](REPRODUCE.md), [consumer inventory](receipt-consumers.json), [issue index](ISSUES.md) and [machine-readable mapping](issue-matrix.json). The original 51 plus #186 are mapped separately, with source commits, final paths, tests and historical evidence. This does not convert the historical 30 bounded/22 partial assessment into 22 bugs or integrated acceptance.

- GitHub open-PR enumeration and direct issue #183 read returned `Forbidden`. These operations stopped; no alternate identity/channel was used. The reported second new issue remains unidentified. PR187 current CI remains unverified; PR188 success is not substituted. User-provided historical observations were PR188 push run `40075042367` success and PR run `40075046021` attempt 3 success (09:56 UTC); they were not independently queried in this task. Their first Q2 timeout/browser failures remain historical evidence and are not asserted to share PR187's cause.
- Render doctor returned `needs_tool`: `rsvg-convert` is absent. The available actual PPT → PDF → PNG path passed with synthetic foreground checks; missing SVG paths and final image/PPT meaning remain unverified.
- Browser download was denied (`403 Domain forbidden`); existing `/usr/bin/chromium` is used through explicit test configuration. Browser assertions and skip-failure rules remain intact.
- Actual Host execution, user visual judgment, final image/PPT semantics, external-report real repair and outstanding CPU evidence remain separate gates. No real customer deck, paid model batch, monitoring installation, credential change, publication, issue closure or merge was performed.
- Source/wheel validation is recorded separately in the final validation manifest. First failures and reruns are retained under `/tmp/deck-integration-evidence`; the final evidence manifest identifies exact source/tree/wheel and results. Do not use earlier source-branch CI as final validation.

## Pro review handoff

Review the full main-to-head diff and source ancestry, then use [PRO-REVIEW.md](PRO-REVIEW.md). The user-selected ChatGPT Pro review must occur on the final fixed SHA after regression corrections. This integration task does not substitute an internal agent for Pro or authorize final merge.

Compatibility repair `83cdfecb` preserves legacy v1 clean-review receipts while keeping v2 final-stage refusal, failed-prior and finding-closure checks. `75551e7d` combines PR188 method recovery context with PR185 fixed manifest/preview contracts. `6c822e2d` and `2040ca6d` repair legacy optional-handoff projection and exact source/wheel test identity. Both complete frozen non-browser sweeps at 2040ca6d passed (4062 passed, two external Frozen A skips), replacing the earlier unresolved startup diagnosis with a reproduced BUILD_ID mismatch and full-suite evidence.

Packaged runtime `b66cec18` restores trial permission wording and the original first-row viewport requirement without losing current-work UI. Browser test follow-ups preserve native popover focus destinations, exact summary reuse, production refusal, draft recovery and fixed-download assertions. CI ownership keeps renderer-dependent browser cases in the job with both toolchains. See [validation](VALIDATION.md), [original failure attribution](failure-attribution.json), [browser failure attribution](browser-failure-attribution.json), [reproduction](REPRODUCE.md), [prepared PR body](PR-BODY.md), and [consumer inventory](receipt-consumers.json).

The old 8dc30210 remote CI failed (689 browser passes / 21 failures); it is historical, not a result for the repaired candidate. The exact log request was denied and stopped. Current suite completion and remaining gates are recorded in VALIDATION.md. Raw evidence and both archive identities are in [EVIDENCE.md](EVIDENCE.md). No source branch, Humanizer branch or main was changed.

The [30-owner acceptance focus](acceptance-focus.json) supplements each of the 52 issue rows with the specific engineering assertion and remaining real-evidence boundary. PR187 current-work/outline/focus/summary tests and the integrated speech-method clipboard tests are explicitly mapped. #186 retains all six requirements from its source follow-up report; this does not imply a fresh issue read or real external-report repair.

The stability archive includes the complete binary main-to-code-candidate patch and commit graph, with SHA256 in review-diff-identity.json. Commit 7947b25a fixes three test merge omissions without changing runtime: nested overview disclosure, RP10 mapping-label semantics, and visible opinion-composer entry. The prior complete browser attempt and the unresolved one-time method reload startup delay remain documented in VALIDATION.md.

[Remaining gates](remaining-gates.json) individually lists unexecuted cases, original unit skips and the attempted installation refusal. [Contract mirrors](contract-mirrors.json) records byte identity for the 14 changed runtime schemas.

Read-only refresh follow-up: [method reload investigation](METHOD-RELOAD-INVESTIGATION.md) narrows the failure to the post-initial-read, pre-mount phase, corrects response-header timing limits, and specifies the missing evidence and next capture. Root cause remains unresolved; no new test or code change. This supplement postdates the unchanged evidence archive.

Authorized renderer follow-up: [installation permission block](RENDERER-INSTALL-BLOCK.md). Official package index update was denied by OS filesystem permissions despite require_escalated execution. No installation or dependent rerun occurred; user consent is already present.
