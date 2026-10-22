# Integrated CI follow-up

Baseline PR184: 55adc97c5bb5f16ae7fcff7c33c43969fae9ce97. Initial CI head:
59f4c0fdf6901db15ec1bfb7d8fc749459340e16, run 39833146156.

The render job 120014697159 completed with 3 failed, 133 passed, 1 skipped
in 200.33s. These are not cloud renderer installation results. The runner
installed official librsvg/LibreOffice/Poppler successfully. Local installation
remains blocked by filesystem permissions. RP19 report records exact writer
promotion and retired-task invariants behind the three corrected expectations.

A targeted local reproduction selected six files from earlier CI progress:
candidates, eligibility enforcement/entry coverage/resolver, production and
RC3 gate repair. Result: 51 failed, 133 passed, 3 deselected in 36.62s.
This is diagnostic evidence, not a passing candidate. Further scope tests
exposed a real all-manuscript vs page-target review deadlock under a narrowed
request; separate runtime repair is in progress.

Four isolated fixture updates preserve the intended checks:

- Explicit assembly of old format is refused by pipeline's precise
  stage_format_required/project error before mutation; current pointer unchanged.
- New blueprint method selection uses visual-reference, while reconstruction
  and the historical RC3 selector retain blueprint-svg. Exact tuples checked.
- The asset attachment positive now explicitly selects a genuine PNG original
  and verifies exact bytes. Merely permitting an asset is not consumption;
  existing RP19 negative tests cover no selection and unsupported SVG attachment.
- Pause refusal is tested against a genuinely allocated second allowance under
  an explicit two-call grant, rather than a nonexistent call-2. The old call
  remains in flight and can settle; the reserved call cannot begin while paused,
  with current pointer and reserved state unchanged.

Command: PYTHONPATH=src:tests/rebuild .venv/bin/python -m pytest -q
 tests/rebuild/test_candidates.py tests/rebuild/test_production.py
 tests/rebuild/test_flow_quality.py tests/rebuild/test_late_results_and_stops.py
 -m 'not render and not browser'

Result: **108 passed, 7 deselected in 17.72s**. No production assertions removed,
no source capability downgrade, no model invocation. CI matrix and browser job
remain in progress; no final gate pass claimed.

The narrowed-request deadlock is confirmed and repaired in `9d08f79e`:
actual valid nonempty page-action targets select review coverage; compile/PPT,
assembly, missing, empty and unknown targets retain full-manuscript coverage.
Independent scope/authority guards and unresolved deck/target findings remain.
The two authorization fixtures now review after narrowing the request, preserving
RP14's requirement freshness rather than reusing an old request's review.
Integrated enforcement/scoped/entry-coverage/read-only-diagnostic suite:
**65 passed in 5.39s**. New regression first reproduced the real failure before
runtime editing, and includes full-deck, empty/unknown targets and open findings.

After scoped runtime repair, current effective-policy comparison and frozen-owner
fixture repairs, the combined 13-file diagnostic selection passed:
**312 passed, 7 deselected in 64.28s** (`/tmp/deck-ci-integrated-contracts.log`).
Selection: candidates, eligibility enforcement/entry coverage/resolver,
production, rc3_01_gate_repair, flow_quality, late_results_and_stops,
rc3_preproduction_semantics, rc3_restyle_workflows, rc3_review_policy_ready,
review_policy_semantic_identity, scoped_preproduction_eligibility; pytest -q
-p no:cacheprovider -m 'not render and not browser'. Full src/tests Ruff and
`git diff --check` passed. This is distinct from the still-running remote full gate.
