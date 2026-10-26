# Separate 724 branch CI failure: initial position / clear-plan ordering

Run 40360544880, job 121704795712, checked out exact 7244477a240002ba5365e0283713e8096778c72f. It is not PR run40360555531 and not d609 run40370430109.

The required source browser step ended at 2026-10-26T17:21:55Z with **1 failed, 772 passed, 4452 deselected in2673.20s**. The failed test was `test_pr189_clear_capacity_browser.py::test_large_interrupted_clear_ends_refreshes_downloads_and_replans[True]`, line39. It expected `清理结果待核实`, but displayed `个人状态已变化，本次清理被拒绝；请重新生成计划。`. This is the first-attempt manifest CAS refusal branch. Failure preceded the `lost_response=True` end-clear fault injection. Wheel build, offline and installed steps were skipped; this is not an installed-suite failure. Four unit jobs and renderer passed. The upload step found no artifact directory.

Raw fetched log: `/workspace/scratch/performance-input/ci-40360544880-job121704795712.log`, SHA256 `56e30d431d9ba511666866742c7ee15e4816f4c924130295fe8e10fb0eb4ea30`.

The capacity test, server clear/CAS code and personal-maintenance CAS branch are unchanged between724 andd609. d609's fresh-control GET replacement does not await or cancel the independent initial savePosition POST. Thus the test-order vulnerability still applies; an old failed run is not relabelled as a new-head test result.

A controlled d609 browser probe held the initial POST /api/ui-state, obtained plan-clear200, then released the position write200 before commit-clear. Commit returned409 with `code=local_state_conflict`, `field=manifest_digest`, and message `personal state changed since the plan; nothing was cleared, plan again`. Both drafts remained. This reproduces the observed refusal through a real ordering boundary; the original CI log lacks response payload/timing to prove that this exact interleaving caused its failure. Do not claim an exact historical trace that was not collected.

Minimal test correction waits for the initial actual reading-position response before creating the capacity scenario. It also asserts that the injected draft-001 unlink failure was actually reached. No sleep, timeout increase, weakened assertion, CAS bypass or product-code change. The capacity scenario's two variants and the existing real changed-state CAS refusal test pass: **3 passed in10.95s**. Controlled ordering probe: **1 passed in2.85s**. Logs/runs remain under `/workspace/scratch/performance-input/capacity-order*`.

This test-only correction is kept local for integration coordination; no rerun or push was requested to interrupt the current d609 CI. No new product fix or entire-CI success is claimed.
