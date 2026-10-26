# Content edit handoff projection

Base: `8586d0258b52f69d7338fd8e8e225ee7f350b682`.
Scope: RP-24 / #134–135 controlled Host acceptance follow-up; no issue closure claim.

A bounded `edit` request with `page_copy/plan` scope could be refused by
`content.commit` for missing direction while its completion reported
`in_progress`, `missing=[]`, `next_action=null`. The content completion reader
only evaluated `full_deck/content_only`; the edit responsibility was absent.

Completion now reuses the existing `content.operation` eligibility judgement
for this content scope. Missing decisions, pause and revoked grants retain the
existing reasons, priority, next action and responsible role. The negotiated
current-work summary consumes that same result. Reads do not grant authority,
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
