# RP-14 integration: same effective policy and current fidelity fixtures

Base `59b71b30`; verification completed 2026-10-22 18:51 UTC.
Plan PR #184 baseline `55adc97c5bb5f16ae7fcff7c33c43969fae9ce97`.

## Reproduction and diagnosis

`pytest tests/rebuild/test_rc3_restyle_workflows.py tests/rebuild/test_rc3_review_policy_ready.py -k 'consumed_font or effective_review_change'`:
**5 failed, 2 passed** before changes (`/tmp/rp26-integration-baseline.log`).

The three restyle failures occur AFTER the original task-freshness assertion
passes. The old local scenario called a helper that always demanded a newly
dispatched review. Unused-font and sibling-recipe mutations retain an applicable
fidelity review, so dispatch correctly returns already_reviewed. Unrelated-page
density requires an actual recheck, whose frozen historical owners the old
helper did not place in `replaces`. No visual freshness production fix is needed.

The two review-policy failures are runtime regressions: an equal accepted policy
replacement retained the running task but its next dispatch created a second
Task. Comparing frozen/current requirements showed only policy object ref and
`replaces` differences (created_at can also differ). These are audit identity,
not changed editorial requirements.

## Narrow repair

- `effective_requirements` compares review-policy requirements while excluding
  only outer object ref, record `replaces` and `created_at`. Decision ID, value,
  scope, request, evidence/source, authority, expiry and dependency basis remain
  compared, after the ordinary current/effective/accepted filtering. This is
  limited to `policy` / `content_review_requirement`; manuscript decisions keep
  exact existing semantics. Frozen packets and reader output retain all original
  provenance. The same comparison applies to historical imported review checks.
- Restyle tests use a local settling helper: retain already-applicable fidelity
  reviews; for an actual missing unit use existing `rc3_fixtures` owner-aware
  real dispatch/claim/accept machinery. Assert final pass, no missing units or
  blockers, and pure status-read nonmutation. Original task freshness, immutable
  prepared input, reservation, task-start and scope-refusal assertions remain.
  This also repairs the scope-replacement scenario's old fixture.
- Added regression with a deliberately different audit timestamp: the same
  policy reuses the Task and leaves frozen inputs unchanged. The current reader
  still exposes the new ref/replacement chain. A genuinely different instruction
  source makes the old task stale even with equal policy value.

## Evidence and boundaries

`python -m pytest -q -p no:cacheprovider tests/rebuild/test_review_policy_semantic_identity.py tests/rebuild/test_rc3_review_policy_ready.py tests/rebuild/test_rc3_restyle_workflows.py tests/rebuild/test_rp14_effective_requirements.py tests/rebuild/test_rc3_review_policy_workflow.py`

**51 passed, 14.95s**. Ruff and `git diff --check` PASS. No assertion removed or
weakened; existing policy-ready tests are unchanged. No edits to eligibility.py,
content_review.py, shared eligibility helpers or other agents' files.

Synthetic protocol/core evidence only. No model/production/native call, browser,
installation or customer acceptance claimed. Parent owns remaining integrated
scope-gate/allowance/method mapping failures and full CI validation.
