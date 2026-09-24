# Deck Master Agent Recovery Playbook

Use this playbook when a rebuilt-core command returns a non-zero exit, a
`blocked`/`fail` status, or an unexpected state. Do not repair by editing
project objects by hand; every fix goes through the CLI/service layer.

Exit codes (spec 09.3): 0 action done (read `status` for deck state), 2 invalid
input, 3 awaiting host/tool, 4 execution failure, 5 conflict/late result with
current unchanged.

## Legacy Run Format

- Detect by: exit 2 with `error.code == "legacy_run_format"`.
- Meaning: the path is an old v0.9.x run (preview/run markers, no new
  Document pointer).
- Auto action: none in place. Read
  [docs/migration-to-rebuilt-core.md](migration-to-rebuilt-core.md); convert a
  full draft and `import-draft`, or pin the old release for that run.
- Stop when: the user has not chosen conversion vs pinning.

## Renderer Or Font Missing

- Detect by: `doctor --step render|compile` returns `status == "needs_tool"`,
  or `continue` returns `status == "needs_tool"`.
- Auto action: install the named tool (`soffice`, `pdftoppm`, `rsvg-convert`,
  `fc-match`) or point `DECK_MASTER_<TOOL>` at it, then re-run the same step.
- Never fall back to fixtures outside demo material.

## Conflict / Late Result

- Detect by: exit 5 or `error.code == "conflict"`.
- Auto action: re-read the current project (`view` / `continue`), rebase the
  payload (fresh `page_hash` / `produced_against`), retry with a new
  `operation_id` for changed content. The late payload never overwrites.
- Cancel-first wins: a result after `task cancel` is settled for call facts
  and refused for content (`late result after cancellation`).

## Review Blocked

- Detect by: `final-readiness` reports `review_status != "pass"`, or
  `export --purpose delivery` refuses with the unresolved dimensions list.
- A `continue` result with `next_action == "repair_page_visual"` addresses only
  the current page. Rebuild that Page/SVG, regenerate its preview, and submit a
  new page review with evidence closing the original finding. If it returns
  `repair_no_progress`, inspect the unchanged Page/SVG and the named finding
  before retrying. An unreviewed current page cannot dispatch the next page.
- Auto action: fix the named Page/SVG layer, then re-run the affected checks.
  Read findings from `deck-master view --project <dir>` (findings carry
  page/element addressing).
- A failing professional review blocks delivery even when all engineering
  checks pass; stopping a no-progress repair loop is not a pass.

## Schema Or Envelope Mismatch

- Detect by: exit 2 with a field path in `error.message`.
- Auto action: fix the named field; unknown envelope fields are rejected, not
  ignored. Page v2 normalization raises the exact pointer needing a decision.
- Stop when: a contract mismatch has no documented migration.

## Workbench Unavailable

- Detect by: `view_status == "unavailable"` or `review_url == null`.
- Auto action: the payload `findings` carry the real reason (no Document,
  service start failure, no browser). The local URL is still printed when a
  service is running; no browser does not lose the address.

## History And Restore

- Restore always creates a NEW revision; task call facts (consumed/unknown/
  cancelled) and the user stop state are never rolled back. Use
  `deck-master history list --project <dir>` to pick a revision, then
  `history restore` with the current base revision.
