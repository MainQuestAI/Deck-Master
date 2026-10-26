# Performance iteration v1.2 — implementation and evidence

This is an implemented, partially validated iteration, not an issue-closeout or release approval. All 21 cards have code changes or their explicitly scoped maintenance disposition. The required final render/offline acceptance and original w01 gate are not complete.

## Identity and inputs

- Branch: `codex/performance-v12-20261026`.
- Exact parent: `b688c300dbb612bea9af8cf63a1743fb8136ae2c` (PR189); main and the PR189 branch were not modified.
- Product implementation: `84a3a60efb9721491fd0845ca766caa1244df7d0`.
- Old reported measurements remain attributed to `555497cb97ba2bec0c62192ec68412ce3c31287f`.
- Six original input texts in `inputs/` match the supplied SHA256 values; 21 cards, 66 source mappings, 53 maintenance candidates. All 21 GitHub issue bodies and comments were read. The ZIP was not downloaded successfully in this executor; no claim of local ZIP or original HTML verification.
- `issue-ledger.json` maps requirements, actual files, commit, evidence and remaining work. `maintenance-dispositions.json` records the bounded symbol decisions; its original inspection identity is retained separately from the implementation commit.

## Changes

Request-scoped facts now flow through the existing readers and review context. Successful OperationReader scans publish existing coverage; PPTX status reuses bounded metadata without retaining whole files. v2 summaries reuse the existing bounded cache with actual dependency guards, runtime-human-evidence bypass and owner-controlled single-flight. History/control/reading/time and final CAS checks remain.

Task successors use an ordered per-key index with the original adoption predicate. Ordinary task pagination builds only page members; attention filtering retains the necessary all-candidate judgment and reuses it for rows. Candidate status/file/freeze share verification with different byte retention, commit classification reuses local JSON, review import indexes unique refs, and export copy validates one manifest while still hashing each file. Explicit assemble coordinates by project/operation; only its owner removes the active entry.

Overview owns and releases image leases as groups/viewports change. Hidden panels stop repeated reads; unchanged rows/current-work panels retain DOM, evidence JSON formats on expansion, and candidate preview has one parent-owned state flow. Thumbnail retry uses a finite active-wait budget. Draft persistence serializes once for two synchronous writes. The latest PR189 clear ownership/scope invalidation is preserved.

The local heavy-test wrapper serializes opted-in batches only. Fixtures clean up services they actually own, including a controlled lost-response case. CLI `--version` avoids business imports. Seven private unused entries and 18 unused constants were removed within the supplied list; public compatibility and core dependencies remain.

## Validation

- Non-browser/non-render suite: initial 4291 passed, 2 failed, 3 setup errors, 2 existing skips. The five unsuccessful installation tests failed dependency setup; unchanged selectors then passed offline from an official-package wheelhouse. Aggregate **4296 passed, 2 skipped**; this is not a second full-suite run.
- Targeted source regression runs and corrections are retained in `evidence/verification-summary.json`. Independent review found and corrected historical cache dependency capture, coverage failure fallback, large-viewport lease starvation, lost-response cleanup and a miss-to-owner cache race. Frontend review corrected preview selection/timer races.
- Q2 subprocess checks: 70/70 passed, zero skips, original assertions/timeouts retained.
- Independent wheel built from clean implementation commit; wheel SHA256 `8ddbc13da88e9c05e718198e7475b1367a20139a0fc6bdd363234910b2badcef`; sdist SHA256 `e15e38b2fc7c85379bdc1c5a81a8eb0eddfde74000ff054ffdc44f89c30bb1b8`. Installed into a separate venv from local official dependencies. Module-origin auditing verifies actual `site-packages` code and static resources, rather than source imports.
- Installed aggregate: **78 passed** (61 initial + 10 retry + 7 corrected setup retry); results and exact retries are recorded in the evidence summary. System Chromium is the actual browser; the unavailable Playwright download is not claimed as installed.
- The four PR189 browser test files now select a system Chromium when present, otherwise the default Playwright browser. Assertions are unchanged. An initially missing `shutil` import was caught by lint/review and corrected before the final seven-selector retry.

## Same-machine observations

Measurements use the exact b688c300 baseline and the same immutable fixture on this executor. Probes and timing samples are separate; no heavy test was run concurrently with timing samples. JSON records preserve raw samples and output identities.

| Scenario | Before | After | Scope |
|---|---:|---:|---|
| 300-page no-task v2 HTTP, median of 3 warm samples | 1122.47 ms | 41.36 ms | Not p95; identical response hashes |
| Same personal v2 HTTP | 1131.32 ms | 79.16 ms | Not p95 |
| Same v1 HTTP | 16.57 ms | 20.76 ms | Small regression retained, not hidden |
| v2 artifact builder, cold/warm | 3 / 3 | 1 / 0 | Separate counted run |
| CLI version, five fresh-process pairs, CPU | 140–159 ms | 34–35 ms | Identical output; total modules 242→87 |
| Ordinary 200-task list, limits 1/30/100, full rows | 200 each | 1/30/100 | Same outputs; legacy-shaped background tasks |
| Attention list, necessary relationships | 200 | 200 | Required accurate totals retained |

The 200-task fixture is not evidence for 200 valid active bound tasks. Store byte counters omit direct cached-reader I/O and must not be read as total physical I/O. HTTP timing CPU includes the in-process client and service. No new p95, large-PPTX 24s/60s CPU or universal CPU-percentage target is claimed. The 524-version regression verifies warm full-JSON decodes fall to zero while O(H) signature checking remains. Real browser regressions cover all 100 overview pages in both entries, lease release and large viewports.

## Remaining blockers and evidence

1. **Render/offline/full compiler chain blocked:** `rsvg-convert` is missing. Formally approved `apt-get update && apt-get install -y librsvg2-bin` failed with permission denied under `/var/lib/apt/lists/partial`. An approved user-directory APT attempt reached the configured official snapshot source but got proxy HTTP 403; no package was installed. This was execution failure, not approval rejection. Exact commands/targets are in `evidence/renderer-blocker.json`. No permissions, TLS, security settings or product checks were changed.
2. **Original w01 gate fails on both baseline and candidate:** its background tasks have no collaboration binding, so `tasks.start` raises `EligibilityBlocked` and background updates stay zero. The original 100 warm samples, 250ms threshold and background assertion remain. A legitimate bound task fixture must be agreed/implemented through existing production semantics before claiming this gate. The new optional factory background count defaults to 150 and only supports the separately labelled 200-task read measurement.
3. **Official Playwright download failed:** CDN responded `403 Domain forbidden`. Existing system Chromium was used through its supported launch argument; no alternate-host or fake browser-cache workaround.
4. Required render/offline acceptance, one real concurrent assemble/compiler chain and the unmeasured scenario observations remain explicit in the per-issue ledger. No issue is closed and no full-green/release claim is made.

All fixtures are synthetic; there were no model invocations or real customer paid generations. No merge, release, push or issue closure was performed. The draft PR text is prepared separately for review.

Final lint: affected source/tests and the changed runner/benchmark pass Ruff. A broader `ruff check src tests tools` additionally reports two pre-existing parser errors at line 556 in `tools/rc3_campaign/q2_later_300{,_v2}.py`; both files are byte-identical to b688c300 and outside this iteration. They were not changed to obtain a green full-tree lint claim.
