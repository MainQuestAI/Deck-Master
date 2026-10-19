# N3 content structure and method dispatch evidence

This is mechanical engineering evidence on the shared RC4 candidate tree. The
starting commit was `a08bc68c1cbbbc806205104c2bb01f3f096305f0` on
`codex/rc4-iteration-20261019`. The integration Owner supplies the final candidate
commit, wheel identity and the sole execution ledger. These tests use explicitly
synthetic projects and no paid model or image calls. They do not demonstrate
professional quality or independent model review.

## Implemented boundaries

- `models.validate_narrative_semantics(..., policy=...)` adds the explicit
  `argument-connectivity.v1` write policy. All nodes participate in weak
  connectivity from the central node. Explicit edges and qualification-node
  references contribute adjacency; source sharing, issues and alternatives do
  not. The input graph is never rewritten. Historical no-policy reads retain
  their original structural semantics.
- `NarrativeDisconnected` uses the existing error envelopes, code
  `narrative_disconnected`, path `payload.narrative.nodes`, and structured central,
  unreachable-node and policy details. Failed acceptance leaves the current
  Narrative/Plan/Page and Task completion unchanged. Existing call-fact
  settlement still happens before adoption checks.
- New Task producers freeze ordered `{id, relative_path, sha256}` entries in
  `method_manifest`; the aggregate digest uses that same order. Applicable
  argument and narrative-writing input revisions also freeze the policy. Task
  schema additions remain optional solely for historical reads. Runtime schemas
  and their single registered rebuild-spec mirrors match byte for byte.
- `Store._commit_locked` raises the writer floor in the same pointer swap that
  first publishes a Task manifest. It also covers initial create. New direct
  Narrative adoption that applies the new policy raises the floor in its own
  transaction. No read or exact replay adds fields or raises a floor.
- Writer rank and the explicit `collaboration_required` list include
  `rc4-content.v1`. It inherits the existing collaboration, independent-review,
  trusted-receipt and Host protocol requirements. Writer registry consumers
  derive their lists from `WRITER_RANK`/`SUPPORTED_WRITERS`; the remaining
  `rc3.v1` equality in `workbench_protocol_required` identifies the historical
  notes-only protocol boundary and is intentionally unchanged.

## Producer audit

The literal Task object is constructed only by `tasks.new_task`. Its real callers
are `service._input_compose_task`, `service.open_compose_task`,
`service.open_blueprint_task`, `service.open_host_task`,
`content_production.build_phase_task`, `changes._new_task`, and
`visual_styles.analyze` (the function that opens the visual analysis Task).

`new_task` freezes the initial manifest. `build_phase_task` freezes again after
its compose.v2 phase/scope is complete; `collaboration_binding.stamp_task`
finalizes only an already-new Task's manifest after binding the real phase.
Existing Tasks without a manifest are never upgraded by stamping. The
preproduction Review producer passes its actual `required_units` into the Task.
`continue` and input-update recovery reuse these producers. Existing pending
Tasks and read-only work orders retain their original objects.

Tests exercise actual public create, continue, open-phase, input-update,
preproduction Review and committed change-action paths. No acceptance test relies
only on manually adding manifest or policy fields to a fixture.

## Review selection

New Review methods are the required union, filtered in this order:
`source-reading → content-methods → content-examples → content-calibration →
review-and-repair → physical-units`.

| Actual review scope | Methods |
|---|---|
| Preproduction argument or fidelity | source-reading, content-methods, content-examples, content-calibration, review-and-repair |
| Final content / argument / page_copy / progression | source-reading, content-methods, content-calibration, review-and-repair |
| Speech only | content-methods, review-and-repair |
| Page visual, visual/conversion/privacy only | review-and-repair, physical-units |
| Mixed content and visual, or ordinary unconstrained review | source-reading, content-methods, content-calibration, review-and-repair, physical-units |

Explicit invalid/contradictory unit lists return a located contract error.
Omitted units use the Runtime stage default. Non-Review ordering stays unchanged.
`collaboration-routing` remains separate entry guidance. No-Task Skill reads,
CLI `methods --review-unit`, and external read-only handoff obtain the applicable
methods without creating a Task. External report provenance still says no
reviewer executed and records no method application.

## I05 and historical compatibility

`resolve_task_methods(task, *, reader=None)` is the authoritative read interface:

```text
methods                  ordered entries with this installation's path
method_manifest          ordered {id, relative_path, sha256} entries
basis_status             current | basis_changed | not_recorded
current_method_release   actual readable-byte aggregate, or null if unavailable
historical_selector      whether the fixed RC3 mapping was used
issues                   located expected/actual hash or missing-byte gaps
```

The optional request-level byte reader is consumed by N4. The resolver never
creates Tasks, grants authority or changes professional status.

The final independent source review found two producer/recovery defects and
reproduced both through actual public Runtime paths before repairing them:

- `open_host_task` previously reused an active Review with the same instruction
  even when the requested units changed from visual-only to content. Reuse now
  compares actual unit/page scope. Omitted units use existing Runtime stage
  definitions; unit/page ordering and grouping do not create another Task.
  Invalid explicit units are rejected before an existing Task can be returned.
  Existing Task objects remain unchanged.
- Method reissue of a fixed-budget blueprint used a broader target projection
  than its real producer, tried to acquire the original already-held page
  credit, and dropped its `budget_key`. Reissue now checks the original dispatch
  layers/pages against a prospective Document that releases the old unspent
  reservations, then transfers those same reservations to the replacement.
  The old Task retains released/consumed history and the replacement retains
  the exact page credit. This neither grants authority nor adds a call slot.
  Already-consumed and unknown fixed credits remain unavailable. For a committed
  bounded change action, the replacement's immutable change record deducts prior
  settled slots from that action's call ceiling; it does not refresh the original
  per-action upper bound even when the unchanged project authorization has spare
  budget. The old immutable change record is preserved.

| Existing fact | Result |
|---|---|
| Legacy Task, RC3 selector bytes match its recorded digest | Return exactly that RC3 ordered set, without current Review additions |
| Missing/changed original bytes or unrecorded basis | Report the precise basis gap; readable content remains available |
| New manifest hash drift | Preserve the frozen manifest and refuse v1 method-body consumption; v2 reports unavailable/mismatched context and retains readable content |
| Old active applicable argument Task or changed methods | New submission returns `basis_changed`; continue supersedes and creates a new Task with a fresh manifest/policy |
| Replacement of a committed change-action Task | Preserve the old immutable Task/change record and register the replacement under a new immutable change record with a valid action binding |
| Historical accepted operation replay | Return the committed receipt before applying new method/structure checks |
| Unchanged pre-RC4 accepted proposal, current request/input/scope/CAS still valid | Permit first adoption under original semantics, without claiming the new policy or raising the content floor |
| Rewritten proposal, replaced request, orphan object, forged old completed marker | No historical exemption; new argument rules or basis replacement apply |

The historical exemption requires a pre-floor committed acceptance receipt plus
its completed compose.v2 Task and exact result Ref. An object or marker alone is
insufficient. A fixed-baseline subprocess actually creates the disconnected RC3
proposal used in these tests; the same baseline code attempts a public write to
an upgraded project and is refused with project bytes unchanged.

## Validation

- `N3-focused-tests.log`: 18 affected files, **377 passed / 4 deselected**. The
  complete literal command is preserved in the log. This includes N3/N4 transport
  equivalence, independent-review admission, argument phases, input revisions,
  Task receipt recovery, eligibility, candidate/change paths and schema/package
  boundary tests.
- `N3-incremental-tests.log` and `N3-incremental-tests.xml`: the final dedicated
  N3 module, **41 passed**. These overlap the focused run and must not be added
  to its count as distinct tests. The last three tests add explicit real-RC3
  rewritten/replaced-request negatives and real change-action reissue coverage.
- `N3-final-review-tests.log` and `.xml`: after the independent source review's
  narrow fixes, five affected modules, **118 passed**. The dedicated N3 module
  now includes ten additional cases for real changed Review scope, equivalent
  default/reordered scopes across all three stages, fixed-credit transfer and
  no fixed or per-action credit refresh after consumed/unknown observations. The positive transfer
  case executes real claim/freeze/begin/settle with explicitly synthetic evidence
  and zero external calls. These cases overlap previous runs; counts are not
  additive.
- `python -m compileall -q src/deck_master` and `git diff --check`: passed.
- `N3-method-inventory.json`: exhaustive source inventory, 23 canonical mapped
  resources, plus the actual default final Review manifest and aggregate digest.
  It is source inventory evidence; final installed-wheel verification belongs
  to the integration build and is not inferred from it.

The four deselected render cases were also attempted before the final focused
run. Each stopped at the actual missing `rsvg-convert` executable:
`test_flow_quality.py::test_revised_deck_recompiles_real_slide_order` with
`reorder`, `remove`, `add`, and `edit`. Two earlier `test_tasks` render cases
stopped for the same missing executable. No renderer fallback or successful
render claim is made. This does not block the N3 synthetic structural/method
checks. Required installed-wheel and wider candidate checks remain the
integration Owner's responsibility.

## Acceptance evidence mapping

| AC | Supporting tests / evidence |
|---|---|
| N3-01 | actual_create_continue_and_phase_producer_freeze_atomic_floor; input_revision_applies_policy_atomically_to_new_narrative; error_details_use_existing_cli_and_collaboration_envelopes |
| N3-02 | single_center_argument_formally_accepts_without_artificial_edges; existing compose.v2 framing acceptance; qualification_and_weak_mixed_direction_chain_preserve_input |
| N3-03 | qualification_and_weak_mixed_direction_chain_preserve_input; existing phased argument acceptance |
| N3-04 | disconnected_nodes_and_self_loops_do_not_pass; shared_sources_alternatives_and_issues_are_not_argument_edges; qualification chain |
| N3-05 | real_rc3_committed_disconnected_proposal_can_first_adopt_and_replay; real_rc3_acceptance_exemption_requires_unchanged_object_and_current_request; forged_old_completed_task_without_committed_receipt_is_no_exemption; missing_policy_cannot_bypass_acceptance_and_continue_reissues |
| N3-06 | seven review_scope_union_is_stable cases; actual preproduction producer/method read regressions; real_review_dispatch_reuses_only_the_same_scope; three real_review_dispatch_default_and_reordered_units_reuse_without_writes cases |
| N3-07 | visual selector cases; external_review_handoff_methods_are_readonly_and_not_application; N4 visual full-context tests |
| N3-08 | same_review_task_preserves_manifest_across_four_entry_modes; no_task_review_reads_scope_without_writes; external handoff cases |
| N3-09 | actual create/continue/phase/input revision/Review; new_and_legacy_stamp_finalization_have_distinct_contracts; real change-action reissue; single schema mirror guard |
| N3-10 | rc3_selector_does_not_inject_new_review_methods; fixed-baseline subprocess; strict changed/missing calibration tests; method_reissue_preserves_unspent_fixed_page_credit; spent/unknown fixed-credit and change-action-ceiling negatives |
| N3-11 | test_rc4_work_context.py full/delta/manifest, cold context, stale cache, drift/missing basis and complete visual/source body tests; I05 byte-reader integration |
| N3-12 | real_old_writer_refuses_before_any_project_bytes_change; first-floor pointer-failure test; true old receipt/adoption no-floor checks; existing collaboration/independent-review/trusted-receipt regressions; source inventory. Final wheel evidence supplied by integration Owner |

No merge, release, tag, deployment, actual-user HOME activation, authorization or
credential modification was performed by this workstream. The root Owner owns
commits/push and final candidate assembly. Four Skill wording is coordinated
with that Owner; canonical professional-method body changes belong to N6.
