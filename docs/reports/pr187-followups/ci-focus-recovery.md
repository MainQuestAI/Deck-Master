# PR187 launcher focus recovery

The parent supplied pull_request run 40004477594 attempt 1, job 120588965651:
checkout bba649b (e4b1d151 merged with bf4f661), browser 645 passed / 1 failed
at the original five-second heading-focus assertion. Installed checks were skipped.
The old payload base 601 is not treated as checkout identity. Direct access to this
specific job log returned Forbidden locally; no alternate channel was attempted.

The original test passed locally once. Delaying the subsequent project-list
response by 250ms reproduced its unchanged focus assertion: 1 passed / 1 failed.
The removal handler closed the modal while its trigger remained connected; the
native close event restored that trigger, then the list refresh removed it.
launcher-ui.js and dom.js are identical at e4b1d151 and bf4f661. A local merge-tree
comparison changes only the inherited clipboard test and its report, not product
code. This is an inherited timing defect, not evidence of a new Q2 problem.

After the remove POST succeeds, the launcher removes that confirmed entry before
closing its confirmation, then performs the original fresh list read. Cancellation
and rejected deletion retain the entry and trigger. A failed refresh cannot undo
confirmed removal. No shared-modal focus rules or five-second assertions change.

Independent review additionally reproduced an inherited late-response defect:
closing removal, opening a new creation form, then receiving the old response
closed the new form. The callback now checks the original dialog content owner
before closing. It neither cancels nor retries the already issued removal. Tests
hold the actual request and cover both successful and rejected late responses,
retaining the new form's text and focus.

Validation evidence is recorded separately against the final commit/wheel.
The first late-response test used a timing sleep; it was replaced by an explicit
pending signal. Its initial string wait expression violated existing CSP; the
corrected function expression changes no CSP, timeout or product behavior.
Historical CI failure and these test-development failures remain in the handoff.
No model, customer production, desktop/render quality, or full-issue acceptance is
claimed. PR185, PR188 and Humanizer branches are not modified.
