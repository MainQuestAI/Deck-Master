# R2 independent review command record

All Python commands use `/workspace/work/rc3/reviews/env-04-snapshot-573a46a/bin/python`; its imported `deck_master` is the fixed snapshot. Environment for every shell:

```bash
export PIP_NO_INDEX=1 PIP_FIND_LINKS=/workspace/work/rc3/wheelhouse
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR=/workspace/work/rc3/reviews/rc3-04-code-review-round2-573a46a/tmp
```

The original five R1 probe files were copied into this review directory and rerun separately using the absolute Python above. Their raw stdout is retained in `probe_*-rerun.log`, and complete result JSON/project facts are retained beside each script. These are the per-process commands (independent calls were orchestrated concurrently):

```bash
/workspace/work/rc3/reviews/env-04-snapshot-573a46a/bin/python /workspace/work/rc3/reviews/rc3-04-code-review-round2-573a46a/probe_import_scope.py
/workspace/work/rc3/reviews/env-04-snapshot-573a46a/bin/python /workspace/work/rc3/reviews/rc3-04-code-review-round2-573a46a/probe_request_source_replay.py
/workspace/work/rc3/reviews/env-04-snapshot-573a46a/bin/python /workspace/work/rc3/reviews/rc3-04-code-review-round2-573a46a/probe_input_revision_sources.py
/workspace/work/rc3/reviews/env-04-snapshot-573a46a/bin/python /workspace/work/rc3/reviews/rc3-04-code-review-round2-573a46a/probe_external_gap_status.py
/workspace/work/rc3/reviews/env-04-snapshot-573a46a/bin/python /workspace/work/rc3/reviews/rc3-04-code-review-round2-573a46a/probe_delivery_pause_race.py
```

The first four scripts are byte-identical to the R1 scripts. The race script changes only its fixed snapshot helper path from `7a8578b` to `573a46a`. Its `_passing_deck` helper is explicit L1 synthetic test setup from `tests/rebuild/test_export.py`, SHA256 `1aaeae0cc3c9cc7158cbc9dfa2b868643edbbec76ad7e52863d7eee281fcc53e`. Neither this helper nor passing fixture tests demonstrate real native rendering, model usage, professional review, or human acceptance. No product monkeypatch is used by the race probe.

The following finite positive/control selections ran from `/workspace/work/rc3/reviews/rc3-04-code-snapshot-573a46a`. Logs are `targeted-positive.log` (36 passed) and `targeted-recovery.log` (4 passed). These are separate runs, not a broad-suite result:

```bash
/workspace/work/rc3/reviews/env-04-snapshot-573a46a/bin/python -m pytest -q --basetemp=/workspace/work/rc3/reviews/rc3-04-code-review-round2-573a46a/tmp/targeted-positive \
  tests/rebuild/test_rc3_import_scope.py::test_complete_manuscript_can_change_one_page_and_retain_the_unselected_original \
  tests/rebuild/test_rc3_import_scope.py::test_explicit_full_scope_can_replace_membership_notes_and_order_atomically \
  tests/rebuild/test_rc3_import_scope.py::test_provided_outline_cannot_relax_the_actual_document_hard_page_limit \
  tests/rebuild/test_rc3_request_source_identity.py::test_closed_same_source_stays_closed_but_new_explicit_instruction_at_same_locator_can_start \
  tests/rebuild/test_rc3_request_source_identity.py::test_same_source_retry_does_not_resume_a_paused_request \
  tests/rebuild/test_rc3_reconciliation_sources.py::test_null_narrative_import_can_revise_copy_with_no_claimed_source_or_role \
  tests/rebuild/test_content_plan.py::test_plan_page_source_navigation_survives_lost_ack_and_later_edits \
  tests/rebuild/test_content_plan.py::test_explicit_imported_plan_is_adopted_and_restore_does_not_keep_the_wrong_plan \
  tests/rebuild/test_content_ops.py::test_direct_edit_supports_recursive_bullets_and_tables \
  tests/rebuild/test_content_ops.py::test_host_result_scope_and_new_identity_lineage \
  tests/rebuild/test_rc3_generation_settlement.py \
  tests/rebuild/test_generation_protocol.py::test_native_roundtrip_links_one_ledger_and_replays_without_new_attempt \
  tests/rebuild/test_visual_styles.py::test_current_analysis_claim_survives_unrelated_page_edit_and_is_idempotent \
  tests/rebuild/test_visual_styles.py::test_analysis_claim_rejects_changed_inputs_without_writes_or_calls \
  tests/rebuild/test_rc3_selected_delivery.py::test_selected_old_policy_true_uses_current_false_without_claiming_human

/workspace/work/rc3/reviews/env-04-snapshot-573a46a/bin/python -m pytest -q --basetemp=/workspace/work/rc3/reviews/rc3-04-code-review-round2-573a46a/tmp/targeted-recovery \
  tests/rebuild/test_flow_quality.py::test_cancelled_revision_recovers_once_and_refuses_late_result \
  tests/rebuild/test_flow_quality.py::test_resume_keeps_retired_task_history_and_original_change_reason \
  tests/rebuild/test_content_ops.py::test_changed_body_marks_retained_original_basis_stale \
  'tests/rebuild/test_rc3_delivery_serialization.py::test_waiting_delivery_rechecks_committed_control_before_publishing_any_bundle[revoke]'
```

Read-only F9 confirmation used the same absolute Python to import `deck_master.method_resources.route_request`, call it once with the exact original Master instruction recorded in `F9-readonly-router-confirmation.json`, and save its result plus actual module path/hash. It does not create a project or claim an installed Host execution. The complete R1→R2 product diff is `product-delta.patch` with its 22-path selection in `product-delta-files.json`.

Final identity command:

```bash
/workspace/work/rc3/reviews/env-04-snapshot-573a46a/bin/python /workspace/work/rc3/reviews/rc3-04-code-review-round2-573a46a/capture_identity.py
```
