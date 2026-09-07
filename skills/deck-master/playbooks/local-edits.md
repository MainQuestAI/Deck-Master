# Selected-Page Edits

Use for a specified page, visual correction, or wording update in an existing
Deck Master run. Keep the existing profile, audience, structure, and approved
style unless the user changes them.

1. Identify the requested page IDs and inspect their current source/package,
   build status, and relevant finding. Reuse known state; do not restart setup,
   whole-deck brief, or storyline/style selection for an unchanged direction.
2. Change only the selected page's source. Preserve other page files and their
   valid approvals. Retain evidence for business numbers and explicit claims;
   ordinary structural text does not require new evidence registration.
3. For high-density SVG/layout repairs, use the existing page-scoped retry
   command below. It invalidates that page from SVG onward. Complete its exact
   waiting refs, then resume. Content changes require the relevant package and
   content-lock validation; resolve stale bindings through the runtime, never
   forge approval or copy stale receipts. Reuse the user's existing direction
   when recording a refreshed selection.
4. For standard pages, import the revised generation result in its existing
   session, refresh the preview, and rebuild. Inspect affected previews and
   ensure unrelated page sources/approved design remain unchanged.
5. Run gates whose inputs changed. Final artifact binding means a rebuilt PPTX
   needs fresh artifact gates, even if only one page changed. Run final-readiness
   for a requested client delivery and honor its current-version approval.
   For an edit-only request, finish with the corrected artifact and verification.

```bash
deck-master build retry --run-dir <run_dir> --profile high-density --page-id P001 --stage svg
deck-master build run --run-dir <run_dir> --profile high-density
```

If a contract reports an actual missing decision, first look for the answer in
the user's request and current run decisions. Ask once only when the missing
answer would change scope, content, style, or delivery. Do not add role
announcements, mandatory interviews, or unrelated benchmark/release checks.
