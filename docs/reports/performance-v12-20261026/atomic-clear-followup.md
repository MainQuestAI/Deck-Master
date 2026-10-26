# Atomic personal-clear recovery follow-up

Parent authorized this bounded primitive replacement after independent review of e6d5a572. It replaces only the single project recovery slot; it does not add a business object, lease, server reservation or background synchronization.

`clear-recovery-store.js` uses one IndexedDB readwrite transaction for each read/claim/compare-update/compare-clear. A request is sent only after transaction completion. Web Locks remain short local-only protection; HTTP never runs inside either lock or transaction. Full original request and end-inspection identity remain the compare boundary. First-click losers display recovery and never implicitly retry the winner.

The initialized empty row is retained after clear so an old localStorage request cannot be resurrected. Initial migration validates the original request and saves its original bytes; the legacy key is read-only evidence. Corrupt data, transaction abort or a changed legacy key stop new clearing and preserve evidence. A legacy conflict is explicitly blocked, not automatically reconciled.

Only HTTP `commit-clear` now requires `X-Deck-Clear-Recovery: indexeddb.v1`; a stale page receives 409 `clear_recovery_upgrade_required`. Session/origin authorization runs first and stays unchanged. The new caller supplies this header explicitly; the shared API helper does not add it for old code. Inspect/end and CLI service contracts and request bodies are unchanged. New pages migrate and replay old complete requests. Ending an operation still permits a new operation ID for the same manifest.

## Validation before independent installation

- 36 affected browser/HTTP cases passed, including original late-response ownership, recovery, capacity and exact-one-first-POST assertions.
- Six migration/abort cases passed: legal migration and unavailable clear transport across reload, initialized empty marker, corrupt legacy, old/new page conflict and protocol refusal, aborted end intent, aborted initial migration and first claim.
- Original two-window first-attempt test passed 10 independent browser trials. Each retains the same request in both windows and sends exactly one first POST. These are product tests, not isolated IndexedDB probes.
- Ruff and JavaScript syntax checks passed. A local read-only review found no blocker; it does not substitute for the separate Astra xhigh review.
- Original installed e6d5a572 gate completed: 630 passed; supplemental installed candidate coverage 12 passed, 106 runtime modules audited inside independent site-packages. Both original style-navigation parameters passed with request/DOM diagnostics. The earlier style failure remains preserved and is not described as a proven product fix.

## Preserved failures and limits

The first new migration batch had 27 passes / 2 test failures: an assertion matched a pre-existing notice before the async request and reloaded too early, and a string wait predicate violated CSP. Corrected to await the actual request/completion and use a function predicate; no product assertion was removed. The first added migration-abort test injected only one abort, after which explicitly opening the panel successfully retried the local read; changed fault injection to remain unavailable for that page and verified recovery from a fresh working page. Its original failure is retained.

An attempted repeated pytest node selector was deduplicated to one test despite `--keep-duplicates`; it is not counted as ten trials. The retained `idb-contention-repeat.py` executes ten independent processes and checks every result.

Current-candidate build, independent wheel installation and the complete original installed selector (plus the seven new protocol/migration cases) are next. No final installed pass is claimed here. Local librsvg installation remains blocked by the previously documented permissions/official-source 403; no further workaround was attempted. e6d5a572 CI has all four unit jobs and real-rendering job green; browser/installed job was still in toolchain installation at the latest read.
