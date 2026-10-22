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

Remote original head terminal unit evidence (2026-10-22):
Python 3.11/Node22 job 120014697231: 73 failed, 3679 passed, 2 skipped,
733 deselected in 1137.37s. Python 3.11/Node24 job 120014697826: identical
73 failing test IDs and totals in 1329.85s. The failure list is tracked locally
in /tmp/deck-ci-39833146156-unit-failures.json. Most mapped to the fixes above;
the isolated Q2 child exposed one additional frozen-owner fixture requiring
explicit replacement with original open findings retained (under correction).
Other remote jobs remain in progress; these are honest failed gate results.

The later local unit diagnostic segment stopped after 15 failures with
930 passed, 56 deselected in 193.69s. This also ran during source integration,
so its two local-runtime health failures were rechecked on a fixed candidate:
launcher, port-restart recovery and JSON polling receipt all passed (3 in 1.53s).
No runtime health timeout was changed. The trailing unit files passed separately:
221 passed, 41 deselected in 59.35s; /tmp/deck-ci-tail-unit-repro.log.

Final code candidate for the first CI-followup push:
`c9cc33a21b5643be22b3cdd763ffd96c61757187`. Exact git archive wheel, temporary
installation and canonical Skill inventory matched (278 package files);
CI-followup-installation.json contains wheel SHA256 and actual import path.
Installed module was asserted before running archived native review/recovery,
explicit re-review, RP24 diagnosis, scoped review gate, policy semantic identity,
original-image review and real preview-poll browser checks:
**88 passed in 30.31s**, `/tmp/deck-followup-c9cc33a2/installed-tests.log`.
The corresponding source selection for remaining known contract failures passed
71 tests in 16.86s. The isolated Q2 wrapper passed8 tests in138.84s, including
actual `-I -B` child70/70 passed0skip; no HOME or real model call involved.

Python3.12/Node24 original CI job120014696823 also ended with the same73 failed
IDs,3679 passed,2 skipped in1490.15s. Original browser and final matrix still run.
Followup is pushed separately as codex/issue-repair-20261023-ci-followup so the
original requested CI can reach its own terminal state without concurrency
cancellation. No PR creation or merge is performed.

## Terminal original run and next exact candidate

Run 39833146156 on 59f4c0fdf6901db15ec1bfb7d8fc749459340e16
completed **failure**. All four unit configurations had the same 73 failures;
render had 3 failures. Browser job 120014697184 ended with **40 failed,
556 passed, 3891 deselected in 3032.19s**. Installed UI stages were not reached.
The browser failures are being reproduced in independent groups; two deep-quality
navigation failures were already repaired in 3260c3de. No final gate pass claimed.

Followup source 3b809d3e9d073972dce21f618218f39ca76e3d14 is pushed to
codex/issue-repair-20261023-ci-followup. Run 39838599321 render job120034119366
passed **136 tests, 1 skipped, 4385 deselected in 198.13s**. Official runner
librsvg2-bin installation succeeded; this does not resolve local apt permissions.
The prior followup run39837132490 was superseded by branch concurrency after
its render result of 1 failed/135 passed/1 skipped. The remaining fixture wrongly
requested image regeneration for an unused-asset change: it now checks unchanged
original/SVG and production tasks, with a new current page-visual review.

The exact 3b809d3e archive wheel matches all278 package files and canonical Skill
inventory; wheel SHA256 e48e246b2657ae40215233b65a7ea80ca7008a42c760768fb9ca554837df2bff.
Actual installed import: /tmp/deck-followup-3b809d3e/site/deck_master/__init__.py.
Installed scoped-owner/gate, explicit-unit re-review and RP24 diagnosis checks:
**41 passed in7.52s**. The new cross-page deck-finding owner regression retains
exact frozen identity without permitting partial review to close a deck defect.

Full local unit command on that fixed source:
`.venv/bin/python -m pytest -q -p no:cacheprovider tests/rebuild -m 'not render and not browser'`.
Result **2 failed,3782 passed,2 skipped,733 deselected,3 errors in1025.95s**.
All five failed/setup outcomes belong to test_install.py temporary wheel/sdist
venvs: pip install setuptools>=77/wheel encounters DNS Errno-3 before installing
the project. Isolated reproduction:1 failed/7 passed/3 deselected in38.06s.
Normal dependency-source resolution must recover before rerunning those checks;
no source override, credential/security change or assertion relaxation was used.
Logs: /tmp/deck-followup-3b809d3e/full-unit.log and /tmp/rp02-install-diagnosis.log.
