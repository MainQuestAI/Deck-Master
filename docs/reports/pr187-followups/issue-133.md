# #133 / RP10 field-level plan preview

Cross-PR follow-up in PR187; PR185 and original RP10 evidence remain unchanged.

Both frontends now display the actual formal-plan → proposed-plan differences alongside the existing impact statistics: chapter names/membership, page goals, source identity/version/locator and editable legacy summary/unknown facts. The baseline is the fixed formal Plan, never a restored draft. Preview freezes its differences with the request generation; subsequent edits/cancellation remove the pending preview, while confirmation retains existing CAS and draft behavior. Plan-only changes still correctly report zero changed Page objects; that count is not used as a substitute for field differences.

Actual Chromium coverage includes both 24-page editors changing chapter name and the last page's goal, invalidating/repreviewing/confirming and concurrency rejection. The source association case checks actual source names, locations and extract versions through cancel/reload/commit. Independent read-only UI review found no confirmed blocker; combined #133/#142 targeted suite: 12 passed. Fixed-HEAD installation evidence is separate.
