# Incremental review: last-allowance Task test setup

Result: **LIMITED_ENGINEERING_PASS** for the test-only delta to `tests/rebuild/test_tasks.py:638` on base `4ced68704df218ffa5eb76cd48a0b3907716f7ed`.

The old setup dispatched its Task before changing policy, then issued new authority and reused that old Task. The updated setup first verifies the old binding is refused with `basis_stale` and the whole Document remains unchanged. It then cancels that Task through the public service, dispatches a new rewrite through the normal content-operation path and asserts the new Task is bound to the current grant. This is consistent with the implemented rule that old Tasks cannot borrow later authority.

The original ownership/allowance assertions remain unchanged: `exec-a` claims the Task; `exec-b` cannot claim it; the one allowance begins for `exec-a`; `exec-b` cannot begin that allowance. The global one-call limit is unchanged. No core source, production policy, test expected value or prior failure record was altered by this review.

Independent execution:

- `test_tasks.py::test_two_executions_race_for_the_last_allowance`
- `test_rc3_budget_workflow.py::test_bound_task_cannot_borrow_new_larger_grant_but_its_last_held_call_can_finish`

Both passed: **2 PASS in 0.93s**. Log（证据 ID `evidence-last-allowance-independent.log-2ecf62e1`，未入仓）, JUnit（证据 ID `evidence-last-allowance-independent.xml-2266fb05`，未入仓）. Seven relevant source/helper/test files have identical before（证据 ID `evidence-last-allowance-independent-before.json-8b72d509`，未入仓） and after（证据 ID `evidence-last-allowance-independent-after.json-677c6cce`，未入仓） hashes. diff whitespace check: PASS. Root's separate original targeted run remains at `evidence-last-allowance-r1.log-c7ba301c` (1 PASS in 0.87s).

No new issue was found in this bounded test correction. This does not relabel the earlier full-unit R4 result (Root reported 2871 PASS / 2 SKIP / 2 FAIL) as a same-round pass, and does not replace final-head full CI, real Host, finished-deck or PowerPoint desktop acceptance. No model/image service was called and no repository file was modified by this reviewer.
