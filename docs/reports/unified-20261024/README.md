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

`git ls-remote --heads origin` confirmed these heads and no existing integration branch. PR185 and PR187 diverge at `601f5ec6`; PR188 descends from PR184 and does not contain their full increments. The integration starts at PR188, merges PR185 (`a308be5a`), then PR187 (`c4e925d3`), retaining both parents and all source history. Integration fixes/consumer migration are `1ea3ad22`; new-finding recovery and action priority repair are `b8e6ec4f`; pending-current navigation and combined-contract fixture repairs are `b7523c99`. No source branch was rewritten or merged to main.

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
- Render doctor returned `needs_tool`: `rsvg-convert` absent. No render pass or final image/PPT semantics is claimed.
- Browser download was denied (`403 Domain forbidden`); existing `/usr/bin/chromium` is used through explicit test configuration. Browser assertions and skip-failure rules remain intact.
- Actual Host execution, user visual judgment, final image/PPT semantics, external-report real repair and outstanding CPU evidence remain separate gates. No real customer deck, paid model batch, monitoring installation, credential change, publication, issue closure or merge was performed.
- Source/wheel validation is recorded separately in the final validation manifest. First failures and reruns are retained under `/tmp/deck-integration-evidence`; the final evidence manifest identifies exact source/tree/wheel and results. Do not use earlier source-branch CI as final validation.

## Pro review handoff

Review the full main-to-head diff and source ancestry, then use [PRO-REVIEW.md](PRO-REVIEW.md). The user-selected ChatGPT Pro review must occur on the final fixed SHA after regression corrections. This integration task does not substitute an internal agent for Pro or authorize final merge.

Final compatibility repair `83cdfecb` preserves legacy v1 clean-review receipts while keeping v2 final-stage refusal, failed-prior and finding-closure checks. Final runtime `75551e7d` combines PR188 method preparation recovery context with PR185 fixed manifest/preview endpoint contracts. It does not add Humanizer. See [validation](VALIDATION.md), [reproduction](REPRODUCE.md), [prepared PR body](PR-BODY.md), and [consumer inventory](receipt-consumers.json).

Raw evidence and wheel archive: [manifest and archive hash](EVIDENCE.md). Final test-only follow-up `1c9d9231` verifies the automatic-save state and real refresh restoration; corrected installed module: 4 passed. Broad-suite service startup stability remains unproven.
