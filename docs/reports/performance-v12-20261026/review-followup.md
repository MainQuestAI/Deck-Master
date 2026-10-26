# Independent review follow-up (reviewed head 99a59a58)

This is a partial correction, not acceptance or closure of the three findings.

## Candidate preview: corrected

When selecting B fails, the UI retains A but has already invalidated A's
in-flight status epoch. The failure branch now asks the existing single reader
to resume A. If GET or explicit POST is still active, the existing pending flag
defers that one read until completion. Hidden/disposed guards remain unchanged;
no second timer, state owner, or automatic POST is introduced.

Six new browser cases cover GET/POST in flight and visible/hidden/disposed
completion. Together with the existing performance frontend file: **12 passed
in 63.87s**. The parent-transferred independent reproducer also passed: reads
continued **2 to 5** across its 4.5-second window, retained A, **1 passed in
11.71s**. This count is not a performance target; the former double-reader
baseline's higher count is not reproduced as desired behavior.

## Clear recovery: click-boundary correction only

The handler now captures the displayed pending request/plan before re-reading
storage. A newly discovered request or changed end confirmation stops the
click instead of silently turning first confirmation into a retry. Same-request
and end-binding ownership checks remain. Seven ownership browser cases passed
(31.72s), including a new two-window scenario. Serving the exact old 99a59a58
personal-maintenance.js in that scenario failed: A's first-confirmation click
retried B and actually cleared the synthetic personal state. No old runtime
files were changed for that counterexample.

**The two-null publication race remains unresolved.** Serialized Web Locks do
not make the two renderer-local localStorage views current. Freezing the click
does not create atomic reserve-if-empty. Server receipts/CAS cannot recover a
request overwritten before it reaches the server. Single successful reruns of
the existing race test are not evidence of repair.

The smallest concrete proposal identified is one IndexedDB transaction record
per project containing the full request and end binding. Reserve, compare/update
and release would be short local transactions, never held across network calls.
An explicit initialized/empty state must prevent stale legacy localStorage
re-import after release. Existing retained localStorage records would migrate
without silently overwriting conflicts; storage failure must stop new clearing.
The server, read-only plan, existing CAS/receipts and new-operation-after-end
semantics would remain unchanged. This requires a new persistent browser
object/storage contract, outside v1.2's no-new-database constraint, so it is
proposed for a scope decision and **not implemented**. The alternative server
reservation adds a write endpoint and still needs offline retention; messaging
requires crash/suspension-aware membership and is not an established smaller
correct solution.

Existing end/reload/transport/storage/recovery selectors passed **28 tests in
50.95s** with system Chromium explicitly configured. The earlier invocation
omitted that argument and failed ten browser startups (18 passed); its log is
retained separately. The single two-null test pass in this batch does not close
the known intermittent root race.

## Installed style navigation: still under investigation

The original 628-pass/1-fail installed result remains a failure. Its empty
recipe selection/pager/list indicate recipe hydration had not completed; the
old capture lacks response completion and timing. Existing ten diagnostic greens
do not establish a fix. No speculative style patch or assertion relaxation is
included. A new stable installed run with richer request lifecycle evidence is
needed to distinguish pending transport, editor initialization and discarded
responses. Full acceptance remains blocked while this finding is unresolved.

The diagnostic plugin's preflight ran the unchanged original two parameters:
**2 passed in 9.59s**. Its default mode does not replace product JS; it records
request start/response/finish/failure, held-route registration/release, draft
lifecycle and final DOM. No claim of style repair follows from that preflight.
