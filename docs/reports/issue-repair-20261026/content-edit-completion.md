# Content edit handoff projection

Base: `8586d0258b52f69d7338fd8e8e225ee7f350b682`.
Scope: RP-24 / #134–135 controlled Host acceptance follow-up; no issue closure claim.

A bounded `edit` request with `page_copy/plan` scope could be refused by
`content.commit` for missing direction while its completion reported
`in_progress`, `missing=[]`, `next_action=null`. The content completion reader
only evaluated `full_deck/content_only`; the edit responsibility was absent.

The first candidate (superseded by the PR212 correction below) reused the existing `content.operation` eligibility judgement
for this content scope. It projected missing decisions, pause and revoked grants with the
existing reasons, priority, next action and responsible role. The negotiated
current-work summary consumed that same result. Reads do not grant authority,
change a Page, dispatch a Task or spend budget. Commit eligibility is unchanged.

An allowed edit returns `inspect_requested_content`, not a new production step.
An `edited` operation proves that operation committed; request scope is an upper
permission bound, not a complete list of required edits. Consequently this fix
does **not** infer whole edit-request completion from one commit or the presence
of Pages. Requested-content checks remain `not_evaluated`. Existing
`content_only/write_only` completion still returns its manuscript without
starting visual production, independently of project-wide delivery readiness.
Review packet `needs_reviewer` and input-failure handling remain separate facts.

Regression evidence: the first four public-API tests on unmodified main yielded
3 failures (missing direction, authorized next step, pause) and 1 pass (completed
write-only). After the fix, the nine focused tests pass, including read-only
method/summary agreement, actual edit commit, revoke, needs_reviewer, source
failure, missing write-only direction and non-content scope isolation. The
adjacent 156-test run passed (the initial seven focused cases plus content ops,
entry transactions, design completion, current work, external review and read
performance). These are synthetic engineering regressions, not independent
professional/model-quality approval. Raw runs and controlled Host originals are
retained outside the repository under the task evidence directory.

## PR212 review correction

Independent review exposed three false blockers in the first candidate: a legal
`page.edit` with page_copy-only scope; a p1-only grant/edit inside a p1/p2 request;
and a copy edit whose request allowed membership changes but whose grant did
not. All three committed successfully but the generic reader invented a broader
content.operation. The three regression cases fail on 9a95402c; earlier green
runs did not cover them.

The corrected projection never interprets a request ceiling as an operation.
A generic completion/method/current-work read retains only request-control
reasons (migration, closed, paused, input reconciliation); otherwise it returns
`inspect_requested_content`. Action-specific direction, authority and scope
judgements are returned with the existing content-plan response, using the
validated plan's exact context shared with the unchanged commit guard. A
rejected commit retains its original exact diagnostic. This also means a generic
read cannot report a missing direction or revoked grant for an unspecified next
operation: the caller must use the concrete preview/error for that diagnosis.
No orphan plan scan, permission inference, durable state or approval layer was
added. A real page_copy-only content.operation still reports its extra plan-layer
violation; the separate legal page.edit is not mislabeled as that operation.

The regression suite now explicitly checks both real violations and legal narrow
edits through plan/commit, completion, method reader and current-work summary.
Build/install results are retained with the follow-up evidence, separately from
the original runs above. Neither set establishes model-quality acceptance.
