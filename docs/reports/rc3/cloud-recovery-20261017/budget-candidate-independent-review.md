# RC3 budget, candidate and adoption engineering review

Result: **LIMITED_ENGINEERING_PASS** for the reviewed changes at `f9ebfbf98ee704d8784da72eae0ffece600d1562`.

The final independent R6 process completed **114 passed in 46.61s**, with no failures or skips. The 26 source/test files recorded before and after the run have identical SHA-256 values. The run began at `8490c8ff` with the pending test/entry-inventory changes; committing those same bytes as `f9ebfbf9` during the run did not change the tested files. No remaining P1/P2 was identified within this review's scope.

## Scope and independence

This reviewer independently examined Root's candidate-slot accounting, shared authority selection, atomic batch binding, current ancestor ceilings, numeric-root preservation, planning-zero exception and adoption-authority fixes. The reviewer originally implemented portions of the budget template/API/UI integration; Root separately reviewed those portions, found concrete defects and required their repairs. The final run is an independent execution of the integrated public SDK/HTTP/browser regressions, not a claim that the reviewer independently authored and reviewed every budget line.

Only existing authorization, Task, candidate and allowance facts are used. No paid model/image calls, new credentials, old experiment recovery, user Mac operations, merge or release occurred in this review. Synthetic ledger tests use real SDK claim/freeze/begin/settle transitions with explicitly synthetic observations; they do not establish actual image/model effects or external spend.

## Confirmed behavior

- `eligibility.py:575` and `:644`: calls and trial slots share their original numeric root; current ceilings of every local ancestor constrain descendants. Already-held calls can finish, cancellation before a candidate result releases that trial slot, and produced candidates retain their use after adoption/restore. Same-identity replacement cannot move historical consumption to another root.
- `eligibility.py:445`: planning-zero is limited to a never-numeric delegation lineage. Historical/current `budget_parent_ref`, `parent_authorization_ref` and `replaces` facts are considered. Explicit numeric zero and a former positive ceiling reduced to zero cannot mint a fresh computed root. Both current and stale parent refs were exercised; safe zero materialization must actually record zero, not merely be rejected later by the execution gate. Original pure-zero future-page and manifest-fixed positive cases still pass.
- `eligibility.py:970`, `changes.py:166`, `content_ops.py:205`: the gate and binding use the same usable, sufficiently funded authority. Whole-batch call/candidate requirements choose one authority under the project lock, which is passed unchanged into every Task. Existing bound Tasks cannot borrow a later larger grant. Equally funded explicit `within_scope` authority remains selectable when an older `candidate_only` grant exists.
- `collaboration_binding.py:121` and `eligibility.py:657`: a `candidate_only` authorization cannot dispatch a `within_scope` auto-adoption Task. Current control also blocks a previously claimed auto Task after its authorization is tightened. Real zero-call SVG trial acceptance returns a candidate without changing current manuscript/Plan/Page/output pointers; explicit `within_scope` auto acceptance changes only the selected SVG.
- Budget preview uses current parent facts, displays a smaller existing numeric ceiling and retains the computed upper bound separately. Explicit numeric templates remain usable. Empty fixed scopes, manifest expansion, stale Plans and consumed per-page credits remain refused.
- Browser/HTTP coverage exercises desktop/mobile full-deck preview/grant and edit preview → immutable ChangePlan handoff → budget grant → current-version re-preview → real commit. Full-deck/auto budget forms explicitly describe and grant bounded current-artifact adoption; trial budgets remain `candidate_only`.
- The new budget CLI, adapter and HTTP preview entries are registered as read analysis. The unrelated dependency fixture now requests zero external calls for its `task.start` operation; the export-invalidation test explicitly authorizes one SVG trial slot. Their original scope, dependency and delivery-invalidation assertions remain intact.

## Final executable evidence

Method: independent ordinary tests over the following files/case, with separate R6 results and JUnit evidence.

1. `test_rc3_budget_workflow.py`
2. `test_rc3_budget_selection.py`
3. `test_rc3_candidate_quota.py`
4. `test_rc3_budget_browser.py`
5. `test_budget_templates.py`
6. `test_scope_and_delegation.py`
7. `test_rc3_budget_ancestors.py`
8. `test_collaboration_service.py`
9. `test_rc3_adoption_authority.py`
10. `test_eligibility_entry_coverage.py`
11. `test_dependency_slices.py`
12. `test_export.py::test_adopting_an_existing_svg_candidate_invalidates_delivery_with_named_gaps`

Evidence:

- R6 log（证据 ID `evidence-budget-candidate-independent-r6.log-a7fb54ee`，未入仓）: `114 passed in 46.61s`.
- R6 JUnit（证据 ID `evidence-budget-candidate-independent-r6.xml-fb7c6616`，未入仓）.
- R6 before hashes（证据 ID `evidence-budget-candidate-independent-r6-before.json-63333f98`，未入仓） and after hashes（证据 ID `evidence-budget-candidate-independent-r6-after.json-71026ffd`，未入仓）: 26 files, no changed hashes.
- Python lint check of the two new boundary-regression files and diff whitespace check: PASS.

## Retained earlier observations

These are separate rounds and are not combined into the R6 result.

| Evidence | Original outcome | Interpretation |
| --- | --- | --- |
| `budget-candidate-independent.log/xml` | 61 PASS | Earlier integration run; predates final fixes. |
| `budget-candidate-independent-final.log/xml` | 76 PASS | Earlier coherent source snapshot; predates zero-lineage/adoption repairs. |
| `budget-ancestor-repro.log/xml` | 2 FAIL | Actual P1: superseded larger intermediate parent was used for calls/candidates. Fixed, retested in R6. |
| `budget-fresh-root-repro.log/xml` | 1 FAIL | Actual P1: lowered numeric zero parent minted a new computed root. Fixed, retested in R6. |
| `budget-zero-lineage-independent.log/xml` | 8 PASS | Intermediate zero-lineage regression run; not the final review snapshot. |
| `evidence-adoption-authority-before.log-409777cd` | 1 FAIL | Actual P1: candidate-only auto SVG acceptance changed current Page. Fixed, retested in R6. |
| `budget-candidate-independent-r4.log/xml` | 112 PASS / 2 FAIL | New reviewer tests expected internal ModelError instead of the public OperationError wrapper, and a specific policy reason instead of the earlier current-region rejection. Both product operations already rejected safely. Raw failures retained. |
| `adoption-authority-independent-r5.log/xml` | 5 PASS | Corrected public-interface assertions, preserving dispatch/accept rejection and full Document/pointer invariants. No product bytes changed. |

The earlier budget implementation rounds and their failures remain recorded in the implementation handoff（证据 ID `evidence-budget-implementation-handoff.md-ab23909a`，未入仓）. Nothing was reset or relabeled as a same-round pass.

## Limits and remaining delivery checks

This is a bounded software-mechanism review. It does not certify the entire RC3 requirement set, real model/image quality, the original M02/S12 experiment, Owner/audience approval, finished-deck effects or PowerPoint manual acceptance. Missing historical experiment material was not used as a gate on ordinary development.

The final full unit/install runs and all seven CI jobs must retain their own final-head results. Root reported earlier full-unit diagnostic failures and installation attempts blocked by PyPI DNS; these remain original observations, not passes replaced by R6. Root subsequently reported resolving dependency downloads through official PyPI and a real install run of 13 PASS / 1 FAIL: the remaining source-manifest check detected the concurrent HEAD move from `8490c8ff` to `f9ebfbf9`. That check needs its own frozen-head rerun without changing its expected value. These install outcomes are Root-reported, not independently rerun here. Final packaging, PR120 state, CI and release status remain the main thread's responsibility. No merge/release approval is implied.
