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
- On macOS, `renderer_fontconfig` checks the full host Fontconfig root with
  `fc-conflist` (override: `DECK_MASTER_FC_CONFLIST`). The renderer passes that
  configuration only to its child processes: a bundled LibreOffice may otherwise
  use a different default prefix and silently lose glyphs or substitute fonts.
  If discovery fails, provide `FONTCONFIG_FILE` for the existing full host
  configuration and re-run doctor. Explicit `FONTCONFIG_FILE` or
  `FONTCONFIG_PATH` settings are preserved; do not replace the configuration
  with a partial font list or change global/Homebrew application wrappers.
- Never fall back to fixtures outside demo material.

## Conflict / Late Result

- Detect by: exit 5 or `error.code == "conflict"`.
- Auto action: re-read the current project (`view` / `continue`), rebase the
  payload (fresh `page_hash` / `produced_against`), retry with a new
  `operation_id` for changed content. The late payload never overwrites.
- Cancel-first wins: a result after `task cancel` is settled for call facts
  and refused for content (`late result after cancellation`).

## Task Accept Response Lost

Retry the exact same task_id, operation_id, produced_against and result envelope.
For new successful adoptions, the request digest and stable result are stored
in the same Document commit as the completed Task and result_refs. A missing
or damaged operations cache is rebuilt from committed history; orphan revision
files never count as applied operations.

`already_applied.revision_id` names the original adoption, while
`current_revision_id` names the current project version. These may differ after
later work. `operation_result` is the original core result. Replay does not
restore the old version or dispatch historical pending tasks.

If `journal_warning.code == receipt_cache_unavailable`, adoption is committed
but the derived cache could not be saved. Keep the same payload and operation
ID when retrying after storage is writable. Changed payloads or dependency
bindings conflict. Old completed tasks without a receipt and without their
journal remain unresolved; do not invent a digest or edit storage by hand.

## Generation Protocol

New `generation.v1` blueprint tasks require explicit Host protocol/capability
declarations, an immutable request and a begun attempt. These are enabled only
for new projects created with `--project-format workbench.v3`; no old project
is migrated in place. New projects use `deckmaster-current.v2` so old writers
refuse them before changing current. Use the matching core to read or continue;
an older UI may be used with that core, but do not downgrade the writer.

- `host_protocol_unsupported` (CLI 2 / HTTP 422): read the current public Skill
  and declare the required capabilities. A Host name alone is not support.
- `generation_request_required` / `generation_attempt_required` (2 / 422):
  use the IDs returned by requests freeze and the same call begin.
- `generation_binding_conflict` / `generation_input_mismatch` (5 / 409):
  inspect frozen and actual input. New input needs a new request; the same
  allowance cannot be resent or relabeled. Consumed facts are retained.
- `generation_evidence_incomplete` / `tool_observation_unavailable` (2 / 422):
  inspect the real tool completion and its exposed fields. The current Codex
  adapter verifies native prompt/PNG/transparent-background fields. Its narrow
  direct literal-call profile also proves reference arguments were omitted.
  Nonempty references require a direct literal referenced_image_paths call,
  same-project immutable object files unchanged since call start, and the
  same-call PNG return. Other wrappers, semantic roles besides reference,
  model/seed and unrecorded parameters remain unverified. Never fill them from defaults or a self-reported observer label.
- `generation_object_not_found` (2 / 404): select a request/attempt referenced
  by the task in the chosen committed revision; orphan objects are not history.
- `operation_payload_conflict` (5 / 409): reuse the original freeze payload
  or use a new operation ID for genuinely different input.

An attempt's call state comes from Task.call_allowances. Unknown blocks new
calls; it is not not_sent. Native receipts may enrich a consumed Host report
without creating a second allowance or erasing the earlier observation.

## Review Blocked

For a full-deck/edit manuscript waiting for independent content review, use the
same installation's `deck-master review native --project <dir>` or Studio's
“独立审阅当前内容”. It runs a fresh read-only native Codex session using an
existing ChatGPT login, supplies the frozen complete packet and methods, then
accepts only the directly observed completion through the standard bound
receipt receiver. No API key, imported JSON, permanent issuer permission, or
policy downgrade is created. Read the actual findings before continuing.
The command's success means the review was recorded, not that it passed.
Committed receipts remain usable by a later ordinary `continue` process.

`needs_reviewer` still means the native client/login/transport is unavailable.
An interrupted `running` Task is not retried automatically: inspect it, then
explicitly cancel that Task before a new run. A failed Task preserves failure;
only a new explicit run calls the model again. `basis_changed`/stale inputs
require normal `continue` retirement/reissue. Missing professional/human review
is a separate policy requirement and is not satisfied by native content review.

- Detect by: `final-readiness` reports `review_status != "pass"`, or
  `export --purpose delivery` refuses with the unresolved dimensions list.
- A `continue` result with `next_action == "repair_page_visual"` addresses only
  the current page. Rebuild that Page/SVG, regenerate its preview, and submit a
  new page review with evidence closing the original finding. If it returns
  `repair_no_progress`, inspect the unchanged Page/SVG and the named finding
  before retrying. An unreviewed current page cannot dispatch the next page.
- Auto action: fix the named Page/SVG layer, then re-run the affected checks.
  Read findings from `deck-master view --project <dir> --revision <id>` (findings carry
  page/element addressing).
- A failing professional review blocks delivery even when all engineering
  checks pass; stopping a no-progress repair loop is not a pass.

## Required Text And Stale Review Recovery

`unverifiable_text_mapping` identifies a required atom whose native text cannot
be safely assigned or whose effective fill cannot be verified. Preserve the
SVG and report; bind the named SVG text objects with `data-atom-id` to the
reported content atom, or replace unsupported/inherited paint with explicit
native paint, then regenerate the checks. Do not choose a visible duplicate
as evidence for a hidden body. `unreadable_text` means a determined carrier is
under 6pt or has no effective visible fill.

Artifact adoption atomically supersedes obsolete non-trial review/repair tasks
after all selected pages change. For older pending tasks left behind by a
previous writer, run `continue`: it retires stale reviews before returning
pending work, then follows page review, compilation and new final review.
Current trial tasks, unaffected page reviews, historical results and call facts
remain recorded. A late result from a superseded task cannot be adopted; never
revive it or edit object storage. Repeated recovery does not duplicate work.

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

## Launcher And Personal Draft Recovery

`deck-master workbench` checks role, instance, project/registry identity and
loaded code version before service reuse. `port_conflict` never takes over
another listener: choose `--port 0` or explicitly stop the matching service.
`--stop` affects only the selected launcher/project and keeps business data.
`core_ready_ui_unavailable` means the core runs but the v2 UI is not installed;
use the matching complete package or the CLI and report the missing UI.

A `local_state_conflict` is a personal draft ETag/target conflict. Retain the
local buffer, read the saved draft, and keep an independent draft when needed.
Only a project ACK promises automatic recovery on a new port. A recovery file
is validated data and never a command to adopt or replay a pending operation.
Do not delete the journal to resolve a business conflict; it does not change
Document revision, content identity, or call facts.

## History And Restore

- Restore always creates a NEW revision; task call facts (consumed/unknown/
  cancelled) and the user stop state are never rolled back. Use
  `deck-master history list --project <dir>` to pick a revision, then
  `history restore` with the current base revision.

## Workbench Snapshot Reads

`view --content-plan` and `GET /api/content-plan` follow the same fixed revision
rules. `recorded` means the plan was saved, not that its claims passed review;
`derived` is a Page-title outline and is never persisted as a historical plan.
`basis_changed` retains the original Page/source links for comparison.
`content_plan_invalid` rejects compose adoption for missing goals, invalid
source versions/locators or missing basis. Re-read the work order's source
contract and use explicit unresolved facts where material is missing.
`content_plan_unreadable` is local to that detail; other pages remain readable.

New workbench projects require the `content-plan.v1` writer boundary and
`compose.v1` Host capabilities. Existing old-protocol tasks remain compatible;
never make an old project new-format by editing its pointer. History restore
restores the selected plan reference while keeping the current writer boundary.

`view --summary` and `view --page-id <id> --lineage` read current by default.
Add `--revision <id>` to pin the Document, page slots, tasks and stored prompts.
Get valid IDs with `deck-master history list --project <dir>`. Reads never
restore a revision, start Host work or save project changes. Read options
cannot combine with `--open`; `--lineage` requires `--page-id`.

- `invalid_revision` (HTTP 400 / CLI 2): provide one valid identifier, not a
  path. Empty or repeated HTTP revision arguments are rejected.
- `revision_not_found` / `revision_unavailable` (HTTP 404 / CLI 2): the
  snapshot must be readable, belong to this project and be reachable through
  the committed parent chain. Copied files, orphans and symlinks do not count.
  Read the project's available history. Never silently fall back to current.
- `page_not_found` (HTTP 404 / CLI 2): choose a page present in that snapshot.
- `project_unavailable` (HTTP 404 or 422 / CLI 2): check the selected project
  and restore missing/corrupt storage from a verified copy; do not rewrite
  current.json or content-addressed objects by hand.
- `object_unreadable` within a successful response: other pages/layers remain
  usable. Select an earlier readable snapshot or recover the affected object
  from a verified copy. An unreadable quality record cannot make the view pass.

The summary's `quality.status=detail_required` is not a quality verdict. Use
`final-readiness` for the current delivery gate. Artifact metadata is hash
checked on read; large image/PPT bytes are checked when `/api/file` serves
them. Historical applicability means relative to the selected snapshot.

## Workbench Operations

New `annotations save` and `changes commit` operations require a client-generated
canonical UUIDv4 saved with the complete request before transmission. Saving
opinions changes only their history; it does not dispatch tasks or invalidate
production outputs. `changes plan` stores an immutable derived preview without
changing the business revision. Commit requires that exact plan and base.

- `conflict` (CLI 5 / HTTP 409): read current state and preview a new plan. Do not
  silently widen its page/layer scope or reuse a stale target slot.
- `operation_payload_conflict` (5 / 409): an ID already names a different
  committed request. Recover the original request or use a new ID for genuinely
  new input. Whitespace and Unicode are not normalized.
- A missing response is unknown, not a failed save. Keep the original payload
  separate from later draft edits. Run `deck-master operations show --project
  <dir> --operation-id <UUID>` before another business submission.
- `operation_not_found` (2 / 404): no matching committed fact was found. Replay
  only the exact original payload and ID. A query timeout is not `not_found`;
  keep the pending operation and verify again without creating a new ID.
- `receipt_cache_unavailable`: business state is committed. The operations
  directory is a derived index and is rebuilt from committed parent history.
  Do not delete or rewrite immutable objects/current.json to repair it.
- `operation_unavailable` (4 / 503): storage or verification could not complete.
  Preserve the pending request and inspect the project before retrying.

Exact committed `icons confirm`, `candidates decide`, and `stages assemble`
requests remain recoverable while the current request is paused. Retain the
original project, operation ID, base revision and complete payload. Recovery
verifies committed ancestry and the request digest before returning the original
result; it does not grant permission for a new confirmation, decision or compile.
For `task call begin`, repeating the same in-flight task/allowance/execution and
frozen request returns its existing Attempt. This is receipt recovery only: do
not resend the external tool call. Wrong identity/request, missing Attempt,
settled/unknown calls and terminal tasks remain rejected. Resume only when new
work is actually authorized, never just to retrieve a committed response.

Read `changes handoff --change-id <id>` to obtain the core-generated plan,
tasks, required protocols and safely quoted CLI entry. Copying does not start
work. Only an actual `task start` with an execution reference records a claim.
A task older than 30 minutes needs verification; the service never automatically
repeats its call. Confirm cancellation before creating a replacement handoff.
Late results keep call facts but cannot overwrite the cancelled task's targets.
New `changes.v1` records require the matching writer; older cores refuse that
boundary. Existing projects are not migrated in place.

## Run Desk Recovery

`deck-master task list --project <dir> --limit 30 --offset 0 --revision <id>`
and `GET /api/tasks?limit=30&offset=0&revision=<id>` share a bounded projection.
Pin the returned revision for later pages. Optional status/change_id/attention
filters never start work. Existing `/api/tasks` without paging filters retains
its old response. `task status --details --revision <id>` and
`GET /api/tasks/<task_id>?revision=<id>` share detail, call facts and links to the
existing requests/attempts queries. Normal awaiting_host is HTTP 200 / CLI 0;
`continue` still uses exit 3 when it is waiting for a Host.

- `invalid_run_query`: CLI 2 / HTTP 400. Use limit 1–100, a nonnegative offset,
  one filter value and a committed revision. Do not fall back to a new snapshot.
- `task_not_found` / `change_not_found`: CLI 2 / HTTP 404. Read IDs from the
  selected project's committed run list; do not substitute another task.
- `run_object_unreadable`: local row/detail error. Other rows remain readable;
  use available history or restore that object from a verified project copy.
- `run_unavailable`: CLI 2 / HTTP 503. Preserve the current UI and saved operation;
  retry the same read. It is not permission to dispatch a replacement call.

New real claims on workbench.v3 record `execution_started_at` in the same Task
commit as execution_ref/status, and advance the pointer to `run-desk.v1`.
Use the matching core; older cores refuse the new writer before changing the
project. No existing HOME, installation or project is migrated by a read.
Legacy claims without this field remain "not recorded". Fixed-revision reads
do not acquire a live timeout merely because wall-clock time passes. Their last task update
may establish at least 30 minutes of waiting, but is never labeled claim time.

A 30-minute waiting warning only requests verification. Inspect the original
Task, request, Attempt and call allowance. Unknown is not not_sent; never
allocate or replay an external call automatically. After confirmed cancellation,
return to the affected page and explicitly preview a new scoped plan. Preserve
successful results and calls, and exclude those pages from the replacement.
The normal late-result protection remains in force after cancellation.

## Style calibration

`style_invalid` (CLI 2 / HTTP 422) means the chosen reference, recipe, dimensions or expansion gate is invalid. Preserve the draft, inspect `styles show`, and select explicit targets. `style_conflict` (CLI 5 / HTTP 409) includes per-page `items`; unresolved density constraints need explicit keep_target/use_reference before confirmation. Changed target bases need a new version/plan, never silently overwrite. Unreadable or unknown fixed snapshots use the shared `operation_unavailable` (CLI 4 / HTTP 503); read available history rather than treating it as the current version.

Confirmation recovery uses the original UUID and proposal through `operations show`; pointer-committed facts survive receipt-cache loss. A confirmed recipe does not dispatch or spend calls. Expansion requires an adopted, still-current candidate of the same immutable recipe. Unknown calls, cancellation and late results use the existing generation recovery procedure.

## Content operations

`content_basis_changed`: retain the body/outline draft and fixed sources. Read the current Document, Page refs and ContentPlan ref, compare the changed basis, then explicitly form a new content plan. Do not rebase an old payload silently. `content_invalid` identifies an invalid action/scope or provenance request. Unknown `content.commit` / `content.inputs` saves use the original UUID with `operations show`; committed requests replay their original result, not_found permits the original saved request after legacy checks, and unknown requires investigation. Merge/split preserve old annotations on their original identity, and never reuse an old page ID.

`content-ops.v1` is a forward writer boundary for manual ContentPlan versions, derived-page records and bounded compose requests. Older cores must refuse writes; use the current core to continue or read a committed earlier snapshot. No in-place downgrade or actual HOME migration is performed by these operations.

## Ordinary input update recovery

Keep the exact parsed patch, original base, operation ID and relative-path
context. `operations show` distinguishes verified committed facts, absence and
unknown history. An exact committed replay returns the original revision/result
plus the current revision without rereading missing material or dispatching
tasks. Its pending_tasks are historical; run `continue` for current work.
`operation_payload_conflict` requires the original binding for a retry; a
genuinely changed request is a separate operation after current state is known.
`operation_unverified` / `operation_unavailable` mean unknown, so never work
around them with a new ID/base. Cache failure after commit is only
`receipt_cache_unavailable` and does not undo the business change.

New `status=unchanged` ordinary input updates can commit a receipt-only
revision, preserving Page/input basis, tasks and calls. Ordinary safe IDs and
`content.inputs` UUIDv4 requests remain different families/digest domains.
Legacy logs retain their original contract: `legacy_recorded` no-op IDs stay
occupied; damaged or unverifiable old bindings are not upgraded to atomic
receipts. A completely lost old log-only no-op cannot be distinguished from
an unused ID. The exact limitations and retry steps live in
[input-update](../skills/deck-master/references/input-update.md#并发恢复与等待).

## Frozen Task methods and reading context

For `basis_changed`, retain the original Task, result draft and method hashes.
Read its ordered frozen manifest through `methods --project … --task-id …
--read`; do not replace it with current role defaults. Old Tasks without a
manifest use their provable frozen RC3 selector/digest, or report
`not_recorded`; they do not acquire new Review rules. Missing/hash-mismatched
files remain explicit. Run `continue` to formally retire/reissue an active
execution contract after outstanding/unknown calls are settled. This preserves
the actual scope and authorization; upgrading methods does not expand either.

New manifest/policy writes atomically require `rc4-content.v1` and
`argument-connectivity.v1` where applicable. A structural argument failure
reports concrete unreachable nodes/fields before object/Task adoption; retain
and revise the proposal at its actual scope. Structure does not prove source
adequacy, reasoning or approval. Historical reads, exact old result replay and
proved committed RC3 proposal adoption retain their historical semantics;
orphan or rewritten proposals cannot claim that exception. Old writers refuse
new persistent facts, and installation rollback cannot lower the project floor.

Check `capabilities.read_protocols` before v2. Unsupported explicit protocols
return `read_protocol_unsupported`; omit options for v1 on an older runtime.
`methods`, `create` and `continue` accept `--read-protocol work_context.v2
--body-mode full`; full is the default and always permits re-fetch. Manifest
has `context_ready=false`. A missing method/source/image also leaves precise
gaps. Delta needs an actually observed Host session/context generation with
retrievable exact bytes; CLI cache offers alone remain cold/full. Preserve
complete sources, notes, qualifications, images and physical constraints.
Returned or deduplicated bytes do not prove reading, application, review or
authorization. Read-only negotiation does not persist a new Task protocol or
writer floor.

## Versioned exports

- `delivery_blocked` / `input_reconciliation_pending` (exit 3, HTTP 409): read the
  returned `revision_id` and `gaps`. Complete the named page/layer or reconcile
  inputs; select the resulting new snapshot explicitly. `review` can export an
  unfinished readable copy without claiming delivery approval.
- `export_privacy_blocked`: inspect the named public artifact. The export has no
  downloadable half-package. Fix visible private content or an unsupported
  embedded/external resource in a new revision; original files remain intact.
- `export_id_conflict`: the ID already names another frozen purpose/revision.
  Reuse its original request to retry; a changed request needs a new export ID.
- `export_file_changed`: a stored package failed its hash or whitelist check.
  Keep it for diagnosis; create a new export ID from the intended revision.
- `restore_basis_changed` (exit 5, HTTP 409): current advanced after the plan.
  Keep both versions, read current history, and create a new plan and operation ID.
  Do not silently change the base of the old confirmed request.
- `operation_not_found` after an interrupted restoration: replay the saved plan,
  base and operation ID; durable ancestry determines whether it committed. A
  missing disposable receipt file does not authorize a second business change.

Engineering packages are internal. Recover only their `project/` directory into
an isolated location and use a compatible writer. They include source materials
and prompts, but exclude runtime authentication and personal drafts. They do not
install software, migrate HOME, or change another running project.


## RC3 role and installation recovery

If an `input_revision` result is refused because it would adopt an initial
argument direction, retain the Task, original proposal and reconciliation facts.
Reconcile a substantive framing result first, then follow `continue` through the
current framing/argument Tasks. The ordinary argument stays proposal-only until
a covering direction decision names that exact proposal and `adopt_proposal`
adopts it. An existing argument can still be updated through input reconciliation;
neither a broad Narrative layer nor `within_scope` selects the initial direction.

Reload the actual loaded Host entry after activate/rollback, resolve its managed
release and use that release's Python. Do not borrow PATH/HOME methods. All four
managed links share current; a foreign/occupied path aborts the switch before
any pointer change. Preserve the canonical UUIDv4 transaction ID and original
request; matching pending work resumes, while different requests report
`installation_transaction_pending` or `installation_transaction_conflict`.
Explicit completed replay returns historical `cli_active`/`host_skill`, with
independent current installation observations. A no-ID rollback after completion
is a new toggle, not a retry of the frozen old target.

`preparing` records the frozen request and preparation intents before creating
temporary files or inode witnesses. Resume its original ID/request; unproven
residual preparations remain preserved while that transaction prepares in a
separate recorded namespace. A symlink Host Skill directory uses its verified
real directory for locking and actions, retains access-chain checks, and keeps
logical CLI paths.

Ctrl-C (exit 130) reports transaction state; `compensating` resumes reverse
recovery and a terminal `rolled_back` ID returns the original failure.
`installation_recovery_conflict` retains external paths and backup/preparation
artifacts; do not delete them or claim restoration. Unverifiable journals and
persistence problems without a verifiable phase retain unknown state. Prefix then shared Host locks
coordinate managed switches. `--no-host-registration` never resolves, locks,
scans, reads or writes Host, including migration recovery. Rollback can retire
managed links absent from an older release; it does not downgrade project
writer floors or call facts. Exact command and journal details live in
[installation](../skills/deck-master/references/installation.md#durable-transaction-recovery).

Use `install transaction status --prefix … [--transaction-id …]` for read-only
phase, conflict, action and cleanup evidence. `install transaction recover
--prefix … --transaction-id … --action resume` uses the frozen original request;
`--action rollback` reverses only that interrupted plan. Retry the same ID and
direction after another interruption. If safe ownership cannot be proved, a
valid journal may be terminated with `--action abandon --reason …`: this persists
an explicit v2 abandoned receipt before clearing only its own pending pointer.
All managed/external paths, backups, preparations and journal evidence remain;
current health stays `conflict` with `installation_requires_attention=true`.
New installs still check path ownership. Corrupt or foreign journals cannot be
abandoned or force-unlocked. Confirmed temporary inode cleanup is limited to
new transactions after durable completion/verified rollback; earlier namespaces,
unconfirmed objects, replaced paths and backups remain preserved.

Installation status collects readable journals and per-path unreadable
diagnostics separately. A corrupt neighbour does not hide a readable selected
ID; selecting the corrupt/missing record returns `verification=unverifiable`
with its reason. Check `discovery_complete`, `recovery_blocked`, and
`pending.state` before interpreting the old nullable `pending_transaction_id`.
Unknown pending is not absence. Global uncertainty or multiple unfinished IDs
removes every recovery choice; actual activation and recovery still require
strict complete discovery. Action `phase` uses the recovery engine's pure
parent/witness/backup/prepared observation, including legitimate `backed_up`
and compensation windows. Old terminal actions remain historical after a later
valid install. Reading status never repairs pointers or modifies the scene.

Read the current request, scope, decisions, pause/revoke and completion before
resuming Content/Design/Review. Do not restart an already completed sub-intent,
refresh budget under a new operation ID, or restore old permissions with old
content. `completion.state=completed` returns the requested content outputs;
`needs_reviewer` returns readable artifacts plus the actual missing review.
Review-only is strict external report persistence=none; recovery does not create
a project or write a report into the source. A scope rejection is not success.

For a historical draft, use migration describe/apply and preserve unknown facts.
A confirmed imported manuscript can use imported_mapping without rebuilding
Narrative. For an old variant's narrow edit, use start_request variant_transition
with its exact revision/export and current CAS, not global history restore.
Actual historical files still use current-control delivery eligibility.

## Completed Image From A Different Execution

Read the existing attempt without transferring or adopting anything:

```sh
deck-master attempts show --project <dir> --attempt-id <id> --explain-reassociation
```

The opt-in `cross_execution_diagnostic` adds only derived read facts. Its
`status` is `unsupported`; `association_ready` and `adoption_ready` are always
false. `facts` retains the selected snapshot's task status, actual execution,
request, allowance, call state, registered invocation and observation/output
counts. `proof_obligations` distinguishes `not_established`, `not_evaluated` and
`unsupported`: none claims another execution's evidence is absent or verified.
No event selector/file path is accepted and no collector/provider is invoked.
Default `attempts show` output is unchanged.

`--revision` reads historical facts and labels `fact_scope=historical_snapshot`.
Even without that flag these are selected snapshot facts, never a current
adoption permission or budget check (`current_authority_checked=false`,
`current_budget_checked=false`). Exit 0 means this read succeeded, not that
reassociation is supported. Cancelled, unknown, consumed and released call facts
remain unchanged. Do not infer controller-fenced not-sent evidence from an empty
observation list or a Host-reported release, or use a matched image/input to
rename another execution's event. The unresolved choices and exact missing
proofs are recorded in [RP-24 evidence model](reports/issue-repair-20261023/RP-24-cross-execution-evidence.md).


## Explicit preproduction re-review

Default review remains incremental and returns `already_reviewed` when the current
required units pass. If an actual user request calls for checking an unchanged
unit again, `deck-master review native --project <dir> --force-unit page_copy`
selects that currently required unit explicitly (repeat the flag for additional
units). The existing HTTP entry accepts `force_units` as a nonempty unique list.
Do not combine this with a frozen `task_id`; execute that Task by its own identity.
This is a real native review command, not a read-only diagnostic: it still requires
the applicable authorization and live reviewer capability. Never invoke it merely
for environment readiness or substitute a synthetic receipt for actual review.

Explicit selection adds to missing/blocked units; it never drops them or bypasses
current scope, identity, cancellation, review-owner or acceptance checks. A
completed earlier pass is not permission to ignore a newly accepted failing
review. Only semantically unchanged policy bookkeeping can preserve applicability;
changed sources, actual requirements or authority still invalidate their basis.

## Native reviewer startup diagnostics

`review channels --check-native` checks executable/login prerequisites only. A
`prerequisites_ready` response has `session_verified=false`; it does not prove an
app-server session, model turn, review or receipt succeeded.

After an authorized `review native` fails before entering its session, read
`review channels --project <dir>`. `native_startup_failures` contains local
historical diagnostics: fixed category/phase, timestamp, selected revision,
CLI exit code and observed process exit code (null when not observed). This is
separate from `native_executions`, which describes actual Task history. A later
successful execution does not delete earlier startup failures, and old failures
do not override current prerequisite observations.

The private sidecar `.deckmaster/native-review-startup-history.json` is diagnostic
history, not a Task, checkpoint, authenticated receipt or permission. It never
stores raw stderr, login output, configuration or exception strings. Startup
errors expose `error.details.startup_history_saved`; false means the original
failure remains but its history could not be saved. Discovery reports
`native_startup_history.status=unavailable` for unreadable/corrupt history;
preserve it for diagnosis rather than treating it as an empty history.

Inspect the named phase and the existing native client locally. Do not change
credentials/security settings or automatically retry a model call. Retry only
when the review is authorized and the startup issue is resolved. This diagnostic
entry does not repair native client databases or establish professional approval.
