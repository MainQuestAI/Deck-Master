# PR #189 concurrent personal-clear recovery repairs

Baseline: `555497cb97ba2bec0c62192ec68412ce3c31287f`. Keep the PR Draft;
no merge, release, real HOME migration or real model acceptance is performed.
These R1/R2 labels belong to the latest concurrency review, not the earlier
capacity R1 or original-image N1 findings.

## Behavior

- R1 (`6a2e3672`): commit/inspect/end responses release only the preserved
  project, operation ID and canonical complete request they actually sent.
  Browser Web Locks serialize the short local-storage check/write/delete;
  network calls never hold that lock. Another operation's record is retained
  and re-read. Storage/lock errors never acknowledge completion or send a new
  clear without a durable local request. The stored request format is unchanged.
- R2 (`035ba9e6`): validate a shared manifest backup before classifying its
  owner. A valid other-operation backup is related evidence, not an error and
  not proof that the requested operation succeeded or never ran. Its digest
  participates in end confirmation; its original file/receipt is not changed.
  End still fences late commits, uses the v2 small marker and full immutable
  evidence, and does not delete, restore or change business state.

The optional inspection `backup.related_operation` describes the other owner,
manifest/backup digests and count. `backup.available` still refers only to the
requested operation. Existing HTTP/CLI arguments, status enums, old v1 closures
and ordinary state size limits remain compatible.

## Permanent regression coverage

- Five real two-tab response orders: delayed first CAS conflict, commit success,
  inspect success, inspect unresolved result and end success, each followed by
  the next operation losing its successful response and refreshing to recover.
- Local read/write/delete and missing/rejected-lock failures, plus two initial
  submissions waiting on the same local lock. Network recovery stays available
  to the other tab while the first response is withheld.
- Other-owner completed/interrupted backups, malformed JSON, wrong manifest,
  duplicate/changed/foreign records and symlinks; changed evidence or live
  state rejects stale confirmation; an own success receipt stays authoritative.
- Actual public CLI clear combined with real UI inspection/end/download/replan,
  including lost end response. Backup/receipt bytes, later drafts and the
  business Document are asserted unchanged.

New tests are included in the separate installed-wheel runner. Existing N1,
N2, F1–F4, near-limit capacity and legacy closure tests remain in their gates.
No existing assertion, skip, timeout or workflow gate is weakened.

## Evidence boundaries

Before product changes, the two main regressions produced four failures and
three passing adjacent cases on the fixed baseline. Earlier new-test harness
failures (waiting for the plan/held response, modal lifecycle and native-function
return serialization) are retained separately and are not product findings.

At this report commit, engineering validation is in progress. Final counts,
source/checkout identity, red/green logs, separate QA observations and CI results
must be reported for the final candidate, not copied from an earlier Head.
The original Q2 failure is retained; its job is retried once with all 70 cases,
real `-I -B`, and the unchanged 180-second deadline. Recurrence remains a
separate performance diagnosis, never a reason to weaken the gate.

Independent QA is limited to changed and adjacent recovery behavior. Visual
checks cover the affected controls and messages; the existing missing-source
design acceptance remains blocked and is not reclassified by functional success.
