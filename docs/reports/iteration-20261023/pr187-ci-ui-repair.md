# PR187 original-head browser CI follow-up

The published review head remains 258fc33a3b63504b5652b846c686457024cd42dd,
originally based on 601f5ec68ae994fb42d933f672f0f495eb6d557b. Its PR workflow
39933601045 browser job 120347616813 ended with 27 failed / 604 passed;
subsequent installed UI steps did not execute. This is separate evidence from
the d626ec87 follow-up's 672 source and 672 installed focused checks.

## Confirmed causes and bounded repair

- The unified current-work component had removed the existing primary/secondary
  action presentation, counted secondary titles and expandable object navigation.
  Restore that presentation around the backend-selected primary and ordered
  action facts. Share the old presentation helpers with v1; do not restore a
  second frontend priority or eligibility policy. Optional records are explicitly
  readable without becoming current mandatory work. Both frontends still use
  exactly the same component and server targets.
- Within one backend priority, sorting by opaque action_id could reorder missing
  production layers. Preserve the existing fact assembly order as the stable
  tie-breaker; retain recovery/review priority and all write guards.
- The result-reading test assumed unread results were buried in a secondary
  list. Assert the v2 backend now selects review_results, then click its primary
  action. Keep all target membership, read-receipt, reload, identity, no-write
  and CSP assertions.
- The late-content-poll test intercepted only the old exact v1 query. Match the
  actual explicit v2 negotiation URL; preserve late-success/late-error cases,
  original timeouts and newer-revision/content-plan assertions.

The 27 original failed node IDs were rerun against the repair, all passed.
A viewport regression encountered while restoring the layout was corrected by
keeping expandable evidence with the secondary actions; original 1280/1440/1024
matrix visibility checks remain unchanged. A new backend regression fixes the
within-priority production-layer order rather than relying on hash luck.

The local bundled Playwright browser was absent. Its normal download returned
403 Domain forbidden; it was not retried through another URL or identity.
A test-only launcher adapter outside the repository selects existing real
/usr/bin/chromium via executable_path for tests using the default launcher.
It changes no product, assertion, timeout, receipt or browser data; no fabricated
browser-cache identity is used. This environment difference remains explicit.

## Identity and limits

This work is a separate local increment after d626ec87, with a new wheel and
installed identity required before delivery. No push, merge, release, Library
retry, credentials or security settings change is authorized here.

PR185's newer bf4f661 adds only its clipboard test synchronization and diagnosis
report. A separate prospective merge-tree check was conflict-free; those 8 tests
passed against the exact d626ec87 installed package. This does not silently add
bf4f661 to the local repair branch or relabel original 258fc/601 evidence.

Real Host/model review, S3 effect/human evaluation and customer visual quality
remain not_run; this is engineering navigation and contract evidence only.
