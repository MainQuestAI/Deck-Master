# Draft: reduce repeated read work and bound workbench resource lifetimes

Proposed base: PR189 head `b688c300dbb612bea9af8cf63a1743fb8136ae2c` / `codex/integration-closeout-20261025`. Keep this iteration separate from PR189 closeout; do not describe the full main-to-head diff as performance-only.

Repeated v2 reads rebuilt the same artifact facts, overview navigation retained image pins past the active page group, and several bulk paths repeated full object/manifest work. This change reuses existing request readers and bounded caches, releases consumer-owned image and panel resources, limits ordinary pagination detail work, and coordinates identical in-flight assemble operations without changing recovery, control, permission or CAS predicates.

The 21 v1.2 cards and bounded maintenance dispositions are mapped in [issue-ledger.json](issue-ledger.json) and [maintenance-dispositions.json](maintenance-dispositions.json). No automatic closing keywords are included: acceptance remains incomplete.

Validation: 4296 non-browser/non-render cases passed across the full run and five exact offline setup retries, with two existing skips; Q2 70/70; 78 selected independently installed-wheel cases passed across documented exact retries using real system Chromium. Five fresh-process CLI pairs and same-machine fixed-fixture HTTP/list comparisons are recorded in [README.md](README.md). New latency observations are not new release gates.

Remain Draft: render/offline and one real compiler chain require unavailable rsvg-convert. Official package retrieval failed permission/proxy restrictions. The original w01 gate also fails unchanged on the baseline because its background task lacks collaboration binding; its assertions and 100-read/250ms contract were not relaxed. Large-PPTX CPU and unmeasured p95 observations are not claimed. Details and initial failed runs are preserved.

No push, merge, release, issue closure or real customer generation was performed by this task. This file prepares the review description; it is not evidence of a remote PR being created.
