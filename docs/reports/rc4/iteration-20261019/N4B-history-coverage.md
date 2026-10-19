# N4B history lookup coverage

Scope: **SYNTHETIC_ENGINEERING**. This report covers AC-N4-08 through AC-N4-14; the integration owner's execution ledger is the only acceptance status registry. These fixtures establish recovery and I/O behavior, not customer performance or professional content quality.

The source baseline is `a08bc68c1cbbbc806205104c2bb01f3f096305f0`. Measurements execute the shared working candidate; each generated `N4B-*.json` records Python/platform and SHA256 of the exact resolver, shared snapshot reader, cache module and test bytes. The integration owner records the committed candidate SHA/tree after committing the shared changes.

## Implemented boundary

`operations.resolve_operation` remains the sole I01 truth query and uses the unchanged N1 receipt decoder. `operation_coverage` only collects canonical ancestry metadata; it does not interpret receipts, produce business results, read hints, publish disk indexes, or authorize writes. `Store.operation_receipt` uses this same resolver. The snapshot evidence reader decodes actual bytes once and records their SHA256 plus device/inode/size/nanosecond mtime/ctime signature. A missing parent field cannot silently terminate traversal.

Complete in-process coverage includes every reachable revision, including revisions with no receipt. An explicit historical head must first be reached from safely captured current control. Parent cycles, foreign identity, missing/corrupt snapshots, symlinks and duplicate operation IDs produce unknown. A matching result is always read and validated by N1, including its original ID/project/base/revision/digest and immutable object hash. No old result copy is retained in the coverage table.

Same-head queries validate every covered path/signature. A valid negative needs no historical JSON decode; a positive rereads at most its matching Document. Append-only current advancement validates the prior coverage and parses only the new segment, plus the matching Document when needed. A changed signature, an incompatible/forked chain or a changed root discards/rebuilds coverage. Weak filesystem signatures cause canonical rereading on every query. Unknown results are not retained as negative coverage.

`operations.show` keeps `project_path`'s current-Document validation. Its one-request snapshot evidence scope retains at most that first Document after full schema validation and a SHA256 of actual bytes. Each reuse rechecks the canonical path/signature and returns an isolated copy; a fork or weak signature cannot reuse it, and the evidence is discarded at request exit. This avoids decoding the same current Document again in I01 while retaining current capture, ancestry, receipt/result and final pointer checks. It does not place full Documents in the process coverage cache.

Current advancement during a query permits one bounded retry under N4 §5.5. Each attempt captures one control head. A second change returns `unknown(current_changed)` / `operation_unavailable` (503). An explicit requested head stays fixed through retries and is revalidated as an ancestor of captured control. The returned head always names the actual validated query scope; it cannot authorize a write against a later current. Writer locks, legacy occupancy checks and CAS remain N1 responsibilities.

## Capacity and use

The process has at most **8 project roots and 4,096 total revision headers**. Root keys use resolved directory identity and device/inode, and headers include project identity. Eviction removes a complete project coverage, never a portion that could continue proving absence. A history larger than the capacity is read canonically and is not cached. Forked processes clear inherited coverage before their first query. No disk cache is required or implemented.

The final 1,000-revision synthetic build retained 711,181 bytes under tracemalloc, including instrumentation's per-revision read/decode traces and return-object allocations; its observed peak was 765,717 bytes. The 4,096-header limit is a modest bounded metadata budget (roughly a few MB, not a strict byte limit). Full Documents and results are not kept in the process coverage cache; one public request may hold its validated current evidence until return. Large histories can require temporary canonical traversal memory.

- Force canonical mode for the same I01 interface: `resolve_operation(store, id, use_cache=False)`.
- Disable optimization process-wide, including service callers: `DECK_MASTER_OPERATION_CACHE=0`.
- Rebuild from canonical bytes: `operation_coverage.clear()`; the next query is cold.
- These switches never change stored operations logs, business history or current.

## Actual read counts

`test_real_cold_hot_incremental_counts` constructs 100/500/1,000 real committed synthetic revision chains. Each includes an atomic operation, commits without receipts, and absent IDs. It compares enabled/canonical states and original results. It then performs ten positive and ten distinct negative hot queries and appends Δ=1 and Δ=10 ordinary commits. The missing-receipt query also compares unknown results with caching disabled.

| Reachable revisions | Cold negative snapshot reads/decodes | Cold snapshot stats | Each hot negative reads/decodes | Each hot negative stats | Each hot positive reads/decodes | Each hot positive stats |
| --- | --- | --- | --- | --- | --- | --- |
| 100 | 100 | 600 | 0 | 200 | 1 | 206 |
| 500 | 500 | 3,000 | 0 | 1,000 | 1 | 1,006 |
| 1,000 | 1,000 | 6,000 | 0 | 2,000 | 1 | 2,006 |

For each chain, Δ=1 and Δ=10 positive queries read/decode exactly 2 and 11 snapshots respectively. Each hot positive invokes both original receipt/result readers and decodes each once. Filesystem receipt/result byte reads are reported separately because Store already has a signature-verified small-object byte cache. Counts instrument every `json.loads` call across modules and every actual `Path.read_bytes`/`Path.stat`, including symlink-check lstat calls; parsing moved into another helper remains counted. The Store wrapper has a separate one-cold-scan test.

These are reductions in historical JSON parsing and bytes read. Signature validation remains **O(H) stat**, with two stat/lstat calls per covered snapshot in these runs. The cold tracemalloc run includes tracing overhead; elapsed observations are not a calibrated latency comparison or a speedup claim.

Public-entry counts are separately recorded without excluding entry validation. Four `N4B-show-read-scopes-{0,4}-{cold,warm}.json` files cover a receipt at current and a receipt four revisions earlier. Cold complete `show` reads/decodes every canonical snapshot exactly once (2 or 6 total). Warm current receipt reads/decodes only current once; warm historical receipt reads current and the distinct matching snapshot once each (2 total). Each test asserts exactly one I01 invocation, the revision identity of every read/decode, and no duplicate snapshot. The old failing fixture used a historical receipt, so its original all-entry `1` assertion conflated two different Documents. The fix also removes the real current-Document duplication rather than hiding it outside the counters.

## Evidence and fault mapping

| AC | Current supporting evidence |
| --- | --- |
| 08 | `N4B-counts-{100,500,1000}.json`; canonical/enabled equality, exact cold reads/decodes, no-receipt unknown, Store wrapper one-scan test |
| 09 | Each counts file has all ten individual positive/negative observations, filesystem stats, receipt/result reader calls and decode counts |
| 10 | Each counts file has Δ=1/10 observations and canonical original-result comparison |
| 11 | `N4B-forged-hints.json`; empty, malformed, forged complete/checksum/mapping hints ignored; original legacy log and current hashes preserved; N1 postcommit cache-failure tests retain original successful result |
| 12 | `N4B-fault-*.json`; missing, malformed, foreign, symlink, cycle, missing-parent-field and result corruption; tests also cover unrelated orphan, orphan explicit-head refusal, hot inode replacement and duplicate ID |
| 13 | `N4B-process-cold.json` proves a fork builds its own six-revision coverage; `N4B-process-current-advance.json` proves an independent writer advances current during a cached read and the retry returns the new verified head; `N4B-process-target-commit.json` commits the previously absent exact target and the retry returns its original committed result; sustained change is unknown after two attempts; N1 real same-ID process races preserve single CAS winner |
| 14 | N1 input/Task/content regression suites, run with enabled and disabled cache by N1 owner; legacy log-only no-op checks execute after complete negative coverage, and cross-family occupancy, lost/corrupt logs, original digest/result, no source rereads, no new business side effects remain checked. The strict resolver test checks the entire project byte map and forbids persistent cache publication. |

Five `N4B-entry-safety-*.json` fixtures reject symlinked pointers/snapshots, missing/malformed bytes and malformed Document schema before any lookup or publication. Three `N4B-entry-race-*.json` fixtures replace/rewrite/symlink current after entry validation and prove stale evidence never returns committed. `N4B-entry-weak-signatures.json` records canonical rereads with weak signatures; no request evidence or process coverage is trusted.

`N4B-validation.txt` preserves the original **149 passed / 1 failed** stage and appends its resolution. `N4-validation-resumed.txt` records the final six-file **166 passed in 49.58s**, the shared-interface cache-disabled **101 passed in 22.19s**, N4A's **64 passed in 9.74s**, and Ruff/diff checks. The N1 owner's report supplies broader independent enabled/disabled integration runs. No optional disk-hint publishing path was added; publication failure is tested at N1's existing postcommit adapter boundary. No remaining N4B implementation blocker was found in this synthetic scope. Full candidate gates and the final SHA/tree are integration-owner work. Portable locator normalization and raw evidence hashes are documented in `N4-evidence-normalization.json`; measured hashes still identify original runtime bytes.
