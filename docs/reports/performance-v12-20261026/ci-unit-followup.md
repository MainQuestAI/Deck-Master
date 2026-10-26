# PR209 unit-gate follow-up

Review identity remains `2690e53deaba972a46a87af1c31366a963bd8f28`.
Run [40344766640](https://github.com/MainQuestAI/Deck-Master/actions/runs/40344766640)
checked merge `4252b82cf1b30af81e70031497176420ec744aa3`, whose tree equals
the review head (`85c906cfcfc4e66536a7118d32b836db9a8c5b67`).

Python 3.11 / Node 22 job 121648653764 ended with **4 failed, 4306 passed,
2 skipped, 899 deselected**. All four failures are the new assembly concurrency
test's `entered.wait(10)` assertion. The original log does not expose the
owner Future's underlying exception, so it alone cannot prove its exception type.

The test replaced the compiler but left the preceding renderer-tool lookup
real. Unit jobs intentionally do not install the separate rendering toolchain.
Locally forcing `soffice` unavailable reproduced the original wait failure.
A separate production-entry probe confirmed that a nonexistent configured
soffice raises `NeedsTool` before the compiler, clears the active assembly,
and leaves the Document unchanged. The probe passed; its three marker warnings
come from running the scratch diagnostic outside the repository pytest config.

The narrow fix controls only `soffice`/`pdftoppm` discovery in this synthetic
unit test. Actual font resolution, eligibility, recovery, request coordination,
waiter timeout and conflict checks remain. The compiler still blocks on an
Event and fails deliberately; no renderer is launched or fabricated. An added
assertion checks those two lookups and an early owner exception is now reported
instead of being hidden by a wait assertion. No product code, timeout, skip,
workflow selector or real rendering assertion changes.

Validation with both renderer overrides set to nonexistent paths:

```sh
DECK_MASTER_SOFFICE=/nonexistent/performance-unit-soffice \
DECK_MASTER_PDFTOPPM=/nonexistent/performance-unit-pdftoppm \
.venv/bin/python -m pytest -q tests/rebuild/test_performance_execution_paths.py \
  tests/rebuild/test_pipeline_preview_reuse.py -m 'not render and not browser'
```

Result: **18 passed, 3 deselected in 6.45s**, local Python 3.12.14. Ruff passed.
The first patch verification exposed an overly broad lookup counter including
`fc-match`; that failed attempt is retained as `ci-unit-targeted-after.log`.
The final patch delegates non-renderer lookups to the real resolver.
These are targeted results, not a new complete unit matrix.

The old run's separate real-rendering job 121648653352 passed **138 tests,
1 skipped, 5072 deselected**. This is remote renderer evidence, not installation
of the missing local rsvg tool. Clear-storage publication races, the unexplained
installed style-navigation failure and other ledger evidence gaps remain open.
