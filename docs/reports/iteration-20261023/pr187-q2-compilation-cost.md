# Q2 cumulative work and bounded compilation reuse

Investigated fixed head 03c38c3d5574a88590be743289ee01460788fe9e, push run 39959259053, failed Python 3.12 / Node 22 job 120432797932. Read these explicit URLs; did not retry the denied Actions enumeration. This head's PR-triggered CI remains unknown; bb's earlier PR success is not evidence for 03.

## New failure evidence

The 170-second snapshot is at case 68, process CPU 140.432 seconds. Case 68 finishes at 170.716945, case 69 at 174.704151; case 70 setup passes at 174.705243 before the parent kills the whole suite at its original 180-second deadline. First 69 call phases total 173.457191 seconds, setup 0.055993 and teardown 0.925794. The snapshot in controller.installation/read_bytes is not a stuck-read diagnosis. Compared with the previously captured local run, 67/69 matching call phases are slower; cumulative local matched calls were 133.121438 seconds. Environments differ, so this establishes distributed elapsed cost, not runner contention or a specific product regression.

The same push's Python 3.12 / Node 24 job 120432797998 succeeds with 3927 passed / 2 skipped. Successful captured child telemetry is not present in its console log; therefore per-case remote success timing cannot be compared. Other matrix/browser/render jobs succeeded according to the specific run jobs endpoint. No CI reruns were requested.

## Measured repeat work

Serial local profiling on current and real 601 sources retains real SDK and all case assertions. Aggregate cProfile.getstats by filename/line/name: repeated dynamic imports create multiple code objects, which a naive pstats mapping can undercount. In case 69, both revisions perform 23 complete installation validations and 24 helper loads. Current installation cumulative 2.370758 seconds, 601 2.271506; current helpers 0.696941, 601 0.596099. These are local profiler measurements, not historical CI CPU attribution.

A specific redundant cost is compiling the same SHA-pinned supplementary source for every helper load. Cache only one immutable compiled code object keyed by raw bytes and canonical filename. Every call still revalidates both pinned files and the actual scoped bytes about to execute. Every call creates fresh scoped and controller modules; no module, installation result, inventory, hash, mtime, authorization, journal or task state is cached. No package-byte check is removed. The fixed controller and supplementary files and their SHA constants remain byte-identical.

After change, same-case helper calls remain 24 but compiled scoped code runs once; total compile calls 143 to 120 (23 eliminated). Helpers cumulative 0.327505 seconds; installation still 23 calls, 2.382643 seconds. Case call 5.2193 to 4.8103 seconds under profiling. This proves a narrow repeated-work reduction, not that it alone resolves every 180-second timeout. The original gate and all 70 substantive cases remain unchanged.

## Identity and validation boundaries

q2_later_300.py itself changes bytes. Old control.scope.tool references therefore continue to reject changed tool bytes; do not rewrite old controls or claim old Root approval applies. This optimization has a new commit identity and is not a migration of historical admitted runs. Real native/model/customer effects remain not_run.

Focused regressions prove fresh mutable namespaces/controller state, one compile across two loads, original pins, and rejection of same-size/same-mtime tampering after cache warmup for both pinned files. The actual 70-case wrapper provides unchanged byte/inventory/identity/outcome checks. Independent review is recorded separately.

Lint: the added test passes ruff. Explicitly linting the historical tool reports an existing parser error at `...; match(manuscript)`, independently reproduced from fixed 03c38c3d source. The CI's normal core/tests lint scope does not include this tool. No assertion or unrelated historical statement was changed to hide that result.

Candidate regression completed: 14 passed in 126.83 seconds (the original wrapper and diagnostics plus three compilation regressions). Actual child output records 70 starts, 210 passed phases, 70 finishes and exit 0; elapsed 124.436617, process CPU 104.037638 seconds. Raw artifacts preserved in executor handoff/pr187-q2-cumulative. A single local elapsed sample is not a remote acceptance result or a statistically controlled performance claim.
