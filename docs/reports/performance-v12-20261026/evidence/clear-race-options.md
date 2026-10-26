# Clear recovery publication race: investigation, not an implemented repair

Exact b688c300 source/test reproduced the original assertion on trial 3 (trials 1–2 passed): two commit-clear POSTs, distinct operation IDs. Only Chromium's supported executable_path was supplied externally. Candidate trace records serial Web Lock callbacks, each observing null, followed by the delayed storage event. No tracked baseline changes.

## Existing boundaries inspected

- personal-maintenance lockedPending owns only short local read/compare/write. Holding that lock across server waits would prevent the other window recovering an uncertain operation, violating the existing rule.
- requireOwner compares the full preserved request and end-inspection binding. It does not establish that a renderer's initial localStorage read is current.
- plan_clear is explicitly read-only. Adding a claim there would introduce a state-changing planning step.
- commit_clear uses clear_lock, exact operation/request replay, current-manifest CAS and original backup ownership. These protect server writes but cannot prevent the second POST or recover a request that never reached the server and was overwritten locally.
- Ended operations remain fenced. test_pr189_clear_recovery allows a NEW operation on the SAME manifest after ending before deletion. A manifest-derived operation ID breaks this case and, even with a closure epoch, does not suppress duplicate POSTs.

## Concrete alternatives requiring a scope decision

A. One browser-origin durable transaction record keyed by project identity (IndexedDB): make compare/reserve/replace/remove atomic, import the existing localStorage preserved request without overwriting a conflicting record, keep the full request/end binding and existing server receipt/CAS. Transaction failure must fail closed. LocalStorage compatibility/migration and storage-failure tests must be defined, not removed. This introduces a new persistent browser object and changes the local recovery storage contract; not authorized implicitly by the performance cards.

B. An explicit server pending-request reservation under the existing clear_lock: keep plan read-only, reserve after user confirmation, compare exact request, make late/failed reservation recoverable, and leave deletion to existing commit_clear. This needs a new write/endpoint and durable pending identity; before-server/offline local recovery still needs a defined rule. Larger business/protocol change than A.

C. Component-scoped live-window handoff/acknowledgment using messaging and the existing lock: no database, but membership, suspended/crashed windows, reconnect and timeout behavior must be defined. Neither a sleep nor receipt from one live window proves that all relevant storage views are current. No bounded, complete implementation of this alternative is established by current evidence; it is not claimed impossible or equivalent to A.

Independent additional click-boundary issue: commit currently reads storage before choosing recovering/expected, so a newly visible other-window record can turn a button labelled first confirmation into an implicit retry. Capturing the visible pending/plan before reread, then returning on ownership change, can use existing sameRequest without a new object. That narrow change alone does not fix the proven two-null-read race and has not been applied or counted as a solution.

No sleep, timeout relaxation, deterministic-operation shortcut, fake receipt, new database, new endpoint, security change, or assertion removal has been applied. Continue unaffected verification; full acceptance remains blocked by the reproduced race until a repair satisfies all original recovery checks.
