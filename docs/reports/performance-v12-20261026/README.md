# Performance iteration v1.2 — implementation and remaining acceptance

The performance changes are implemented through `17a2d032ed2cf128c672ee6e568ddd52f6aeab20`. Keep this work Draft: an actual clear-storage cross-renderer publication race remains unresolved, the required renderer is unavailable, and the completed installed gate retains one unexplained style-navigation failure. No issue is closed.

## Identity and scope

- Branch: `codex/performance-v12-20261026`; exact parent: PR189 head `b688c300dbb612bea9af8cf63a1743fb8136ae2c`. The PR189 branch and main were not modified.
- Implementation commits: `84a3a60e` and `17a2d032`; `756d69d0` records earlier validation/docs. Old measurements remain attributed to `555497cb97ba2bec0c62192ec68412ce3c31287f`.
- Six original text inputs match their supplied SHA256 values: 21 cards, 66 source mappings and 53 maintenance candidates. All corresponding GitHub bodies/comments were read. The Library ZIP did not materialize and the original HTML transfer was truncated; neither is claimed locally verified.
- [issue-ledger.json](issue-ledger.json) separates implemented subitems from missing evidence. [closeout-status.json](closeout-status.json) records the current gate snapshot. [maintenance-dispositions.json](maintenance-dispositions.json) retains the finite symbol decisions.

## Implemented behavior

Existing request readers now share snapshots, completion, input freshness, page digests and review facts within the same basis. Verified operation scans publish bounded metadata; PPTX status reuses bounded projection metadata before full-byte reads. The existing four-entry summary cache validates actual dependencies and complete historical signatures, bypasses runtime-human-evidence responses, and coordinates same-key owners. Current controls, professional judgment and final CAS remain live.

Failed-task lookup uses an ordered per-key index with the original adoption predicate. Ordinary pagination expands only current-page details; attention still evaluates all necessary candidate facts for accurate totals. Candidate verification retains bytes only as required by status/download/freeze. Commit classification shares local JSON; review binding indexes unique refs; copy reuses a manifest while checking each file. Assembly coordinates by project/operation and only its owner removes an active item.

Overview releases image leases when visible windows/groups change. Hidden panels stop repeated reads; stable rows/current-work panels retain DOM, folded evidence formats lazily, and availability updates preserve frozen method content. Candidate status is parent-owned; thumbnail polling has a finite active-wait budget. Draft persistence serializes once for two synchronous writes. CLI business imports follow parsing, with an exact version fast path. Scoped test ownership/cleanup, top-level heavy-batch locking, shared active helpers and finite compatibility-safe cleanup are included.

## Verification snapshot

| Check | Actual outcome | Boundary |
|---|---|---|
| Earlier source unit run | 4291 passed, 2 failed, 3 setup errors, 2 skipped; five unchanged setup cases later passed offline | Earlier candidate aggregate 4296; not the final run |
| Full source browser | 752 passed, 8 failed | Five obsolete view/DOM/lazy-evidence expectations corrected and targeted tests passed; two failures require rsvg-convert; one actual recovery race unresolved |
| Post-patch targeted run | 71 passed, 1 failed; corrected PPTX fixture selector then passed | Initial failure was invalid Plan/Page mapping in the new test; `closeout-two` separately records 2 passed; that clear-storage retry does not fix the intermittent race |
| Final full unit at 17a2d032 | 4309 passed, 1 failed, 2 existing skips | W10 fixture request lacked design scope; fixture-only 072c88e repair and exact selector passed. Aggregate4310, not a second full run |
| Original installed full gate at 17a2d032 | 628 passed, 1 failed, 106 installed modules audited | Style-navigation recipe card missing once; exact2-parameter retry and5 diagnostic trials passed, cause unresolved |
| Original w01 gate, legal bound fixture | Both baseline and candidate passed, 100 warm reads, threshold 250ms, real background action | Final design-scope factory: baseline p95 88.303111ms; candidate98.030074ms; slowdown retained |
| Final wheel/sdist build | Completed at 17a2d032 | Build success is not install/render/offline acceptance |

The final wheel SHA256 is `9c6812918c57fafe6807500e8d2a03bc3a6dbfacad5145e7f5d0e2e0d5296544`; sdist SHA256 is `2c32ef6b34aa9bc841e836bbe273f220d1cfe8309aadfe82e639d01157b21725`. The106-module installed origin audit is in evidence/installed-full-final-origins.json. The original offline entry passed9/9 with zero external requests/errors and three fixed downloads verified. Earlier wheel hashes and 78-case retries remain earlier evidence and must not be relabelled.

Independent reviews prompted fixes for coverage fallback, actual historical cache dependencies, owner-registration races, image-window starvation, response-loss service cleanup, preview selection/resume and repeated request facts. Proposed patches were statically reviewed before application; static review is not a test pass.

## Same-machine observations

The corrected w01 fixture retains 300 pages, 1,500 candidates, 1,650 tasks and 4,500 attempts. Its background task is dispatched through the existing legitimate collaboration path. Both sources execute the same shape with real background progress; the 100-sample/250ms rule and background assertion are unchanged. Prior unbound-fixture failures remain in `w01-gate-status.json` as superseded diagnostic evidence, not the current gate result. See [final w01 identities](evidence/w01-final-identities.json). Earlier narrower-scope measurements remain separately recorded. The final factory explicitly includes the W10 synthetic design extension. Each large run completed one start and zero cancel; no sustained-transition claim.

For PERF-200, the new fixture has exactly 25 or 200 formally dispatched/bound tasks, a running task and two returned synthetic SVG candidates. The baseline and 17a2d032 read the same immutable fixture at the same explicit clock. All 12 full responses match without dropping fields; current pointers and fixture contents stay unchanged. Three uninstrumented warm samples are observations, **not p95**. Work counters run separately.

| 200 tasks: attention | Limit | Before median ms | After median ms | After full rows | After task relations | After candidate basis | After snapshot requests |
|---|---:|---:|---:|---:|---:|---:|---:|
| no | 1 | 1543.58 | 64.37 | 1 | 1 | 1 | 1 |
| no | 30 | 1499.03 | 94.47 | 30 | 30 | 2 | 2 |
| no | 100 | 1504.08 | 125.39 | 100 | 100 | 2 | 2 |
| yes | 1 | 1550.49 | 168.40 | 1 | 200 | 2 | 3 |
| yes | 30 | 1515.67 | 165.53 | 30 | 200 | 2 | 3 |
| yes | 100 | 1510.35 | 167.31 | 100 | 200 | 2 | 3 |

Before this change each condition assembled 200 rows and evaluated 200 task relationships. Attention correctly retains 200 relationship evaluations after the change. At ordinary limit 1, candidate-basis evaluations fall from 2 to 1 and snapshot requests from 3 to 1; full snapshot-evidence reads fall from 219 to 2, while 219 signature checks remain. This includes coverage reuse, so it is not attributed solely to pagination. The other counters and raw samples are in [runs-legal-comparison.json](evidence/runs-legal-comparison.json). Copied heavy scopes remain unmeasured. Store-returned byte counters are not total physical I/O.

Additional matched-shape synthetic probes compare b688c300 with 17a2d032:

| Path | Before | After | Measurement boundary |
|---|---:|---:|---|
| 4×8MiB ordinary candidate check, Python allocation peak | 33,565,898 B | 8,399,858 B | Separate tracemalloc probe; not RSS/font/renderer cost |
| Target download reads / total verified file bytes | Target 2 / 40MiB | Target 1 / 32MiB | All four files still checked; target bytes reused |
| Freeze allocation peak | 41,959,778 B | 41,959,781 B | Whole verified bytes intentionally retained |
| Low-writer 20/100KiB Task classification reads | 3 each | 1 each | asset-inputs branch remains 0 before/after |
| 14/44/104-file export record validations | 15 / 45 / 105 | 2 / 2 / 2 | Existing-export check plus one copy context |
| Same export manifest entry visits | 372 / 3,822 / 21,522 | 60 / 210 / 510 | Includes validation/serialization; synthetic filler files |

See [baseline costs](evidence/cost-baseline-final/measurements.json) and [candidate costs](evidence/cost-candidate-final/measurements.json). Timing, counts and memory probes are separate. Commit timing covers the whole locked commit body, not only classification; export timings cover existing-export reuse and copying. No broad hardware/temperature/CPU claim follows from these narrow measurements.

Earlier 300-page no-task v2/personal HTTP observations and five version-only fresh-process pairs remain separately identified in their original records. They are not new 17a2d032 measurements and do not prove unmeasured 200-task summary p95, help latency, or 16.93MB PPTX 24s/60s CPU targets. New suggested budgets remain observations, not new release gates.

## Remaining correctness and environment blockers

1. **Real recovery race:** `test_two_first_attempts_serialize_only_the_local_record` intermittently observes cross-renderer clear-storage publication mismatch. Three repeated passes followed by a failure demonstrate that a single retry is insufficient. Preserve the exact failure, request/storage trace and invariant; do not weaken the assertion or mark the race resolved. Exact unchanged b688c300 source/test reproduced2 POSTs on trial3; the tracked baseline diff is empty. See [investigation](evidence/clear-race-baseline-investigation.json) and [concrete options](evidence/clear-race-options.md). This does not prove a database is the only possible repair.
2. **Renderer unavailable:** `rsvg-convert` is missing. Approved system APT installation failed with permission denied under `/var/lib/apt/lists/partial`; an approved local-directory APT attempt hit proxy HTTP 403 at the configured Debian snapshot source. No package was installed, security setting changed, or substitute environment created. The original installed offline entry passed9/9, including actual native compilation/rendering for its fixture. Full renderer-dependent acceptance and the required formal assemble chain remain incomplete. This was execution failure, not an automatic-approval rejection.
3. **Installed style navigation:** one full-batch failure remains unexplained. Exact two-parameter retry and five diagnostic two-parameter trials passed; no product repair is claimed. Preserve screenshot/request evidence and investigate in independent review. Two rsvg-dependent browser cases remain blocked, not passed.
4. **Remaining observation gaps:** large-PPTX CPU, actual cold/warm thumbnail request/ready breakdown, full import S×R work, complete process-tree lifetime accounting and the remaining multi-state cache matrix are explicit per-card gaps. They are not automatically new code scope or release thresholds.

All fixtures are synthetic; no model or real customer paid-generation calls were made. PR189 recovery scope invalidation and original permission/CAS semantics remain required. Push and Draft PR creation were authorized after this test round; no merge, release or issue closure is authorized here. The parent will arrange separate Astra xhigh cloud review.

Source-identity caveat: `full-browser-run.json` records HEAD `756d69d0`, different before/after worktree fingerprints and `source_changed_during_run=true`. Root confirmed the only changed file was `examples/workbench/w01_pressure.py`; all product `src` files remained at84a3a60e until the browser batch ended, and17a2d032 product patches were applied afterward. The752/8 result therefore applies to that unchanged product code, while the whole worktree was not stable and it is not a final17a2d032 gate. The17a2d032 wheel has since been independently installed; the original installed full regression completed628/1 with106 modules audited, and offline9/9. Its single failure remains open.

Final unit and installed batches both retained identical before/after worktree fingerprints. Runtime files in072c88e are identical to17a2d032;072c88e changes only the synthetic W01/W10 request scope. Renderer repair requires the environment administrator to provision official librsvg2-bin matching the installed2.60.0+dfsg-1 libraries in an allowed path, then configure DECK_MASTER_RSVG_CONVERT if needed and rerun doctor/render gates; no chmod/sudo/proxy bypass is proposed.
