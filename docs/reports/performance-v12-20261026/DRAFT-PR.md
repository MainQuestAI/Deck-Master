# perf: reduce repeated reads and bound workbench resource lifetimes

Stacked on PR189 (`codex/integration-closeout-20261025`, exact `b688c300`). This PR contains the separate v1.2 performance iteration; do not merge before its dependency and independent review are resolved.

Repeated reads now share request facts and existing bounded caches. Overview releases image leases; ordinary pagination builds only page details; bulk verification avoids repeated object/manifest reads; assembly merges in-flight work by project/operation. Current authorization, recovery ownership, professional judgment and CAS remain required. All 21 cards and finite maintenance decisions are mapped in `docs/reports/performance-v12-20261026/issue-ledger.json`.

Validation (synthetic fixtures, no model/customer generation):
- Final runtime `17a2d032`: full unit 4309 passed/1 failed/2 existing Frozen A skips. The failure was W01→W10 fixture design scope, fixed only in the fixture at `072c88e4`; exact original selector passed. Aggregate4310 passed, not a second full run.
- Original full installed gate:628 passed/1 failed;106 loaded product modules audited as site-packages. Exact failed two-parameter retry and5 diagnostic trials passed, but no repair is claimed.
- Original installed offline entry:9/9; three fixed downloads verified, zero external requests/page errors.
- Earlier full source browser:752 passed/8 failed. Five view/DOM expectations corrected and targeted checks passed; two rsvg-dependent cases blocked; one original clear-storage race remains. Product source was unchanged during that batch, but W01 script changed; this is not a final17 whole-tree pass.
- Final legal W01 factory retains300 pages/1500 candidates/1650 tasks/4500 attempts, original100 warm samples/250ms: baseline p95 88.30ms, candidate98.03ms, both pass. Each completed one start/zero cancel; no v1 speedup or sustained-transition claim.
- Legal25/200-task fixture:12 complete responses identical. At200/limit1 ordinary rows200→1; attention retains200 necessary relationships. Candidate ordinary-check allocation≈32→8MiB; export14/44/104-file record validation15/45/105→2/2/2. Measurements are scoped observations, not new gates.

**Keep Draft — unresolved:**
1. Clear-storage cross-renderer publication race: exact b688c300 also reproduces2 POSTs under serialized Web Locks. This is not an exemption. Existing receipt/CAS cannot recover an overwritten request never received by server. Concrete alternatives and traces are recorded; no new storage/protocol or timeout masking applied.
2. Installed style-navigation recipe card absent once. Exact/diagnostic retries pass; cause remains unresolved. Original failure retained.
3. Missing rsvg-convert: approved system installation failed permission checks; official user-directory APT route hit proxy403. No bypass. Full renderer-dependent/formal assemble acceptance remains incomplete; offline9/9 does not replace it.

Runtime wheel SHA256:`9c6812918c57fafe6807500e8d2a03bc3a6dbfacad5145e7f5d0e2e0d5296544`. Runtime files after17 are unchanged;072 only adjusts the synthetic request scope. Full unit/installed batches have identical before/after fingerprints. See README, closeout-status.json and evidence in the report directory for exact scope, failed first attempts, per-card gaps and independent in-thread review. Parent will arrange the separately requested Astra xhigh cloud review. No merge, release or issue closure performed.
