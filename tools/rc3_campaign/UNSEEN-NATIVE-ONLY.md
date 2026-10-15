# Standalone unseen C recorder

`unseen_native_only.py` records the exact native C text for **U-LIVE-01** and
**U-READ-01**, and the shared six-original barrier. It never imports Deck Master,
calls a model, reads an oracle, generates content/feedback, or infers quality from
an SDK gate. Old `native_only.py` stays unchanged; a U case cannot be renamed Q1.
Source engineering tests are not actual native, transfer, human or RC3 admission.

The only imported utility is sibling `controller.py`, SHA
`d0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261`, checked
**before import**. Only its hash/ref/immutable-file/Journal/time utilities are
called. No d0 registration, SDK adapter or d9 validator is used. No key is read.

## Registration and one run per case

Registration format is `rc3-unseen-native-registration.v1`, arm `E1-C`.
Accepted status is explicitly `ENGINEERING_ONLY_NOT_ADMITTED` or an actually
Root-admitted `ADMITTED` registration. A draft is refused. Required exact keys:

- `campaign_id`, `recorder_sha256`, `common_utils_sha256`, `format`, `status`, `arm`.
- `budget`: `initial_writer=5, feedback=1, repair_cycles=1, repair_writer=3,
  verification=1`. No per-stage/run alias refreshes this budget.
- Exact refs `protocol`, `admission_review`, `exposure_registry`; the exposure
  registry is frozen and includes actual preparer/author/answer exclusions.
- `cases`: both exact U IDs, each with only a legal `brief` ref and nonempty
  `materials` ref list. No source/answer discovery or implicit extra files.
- `role_instructions`: nonempty refs for initial_writer, feedback, repair_writer,
  verification, extra_writer, extra_review. The last two mean separately declared
  extra **recorded** work, never equal-budget allowance or automatic permission.
- `cyberppt`: fixed commit `980e5576565f0673c67ee41b01d20ed66cb8417c`, `files`
  with six refs and `relative_path`: complete source-analysis, storyline,
  visual-system, ppt-production, quality-assurance and original MIT LICENSE.
  The production constants pin all original lengths/SHA, 121367 method bytes
  plus1078 MIT bytes. No excerpt or DM schema is substituted.
- `barrier_methods`: exact six-slot method-identity refs, one per case/arm.
  Each C identity JSON equals its exact `cyberppt` bundle. A/B identity refs
  identify their own actual installed Task-specific method evidence; no claim
  that every A/B Task has five methods.
- `observable_configuration`: model, seed, tokens, price, invocation_parameters;
  actual unknowns stay null.

Unknown registration keys, including installation/project/task_id/sdk_gate or
oracle fields, are rejected. Input/method/role refs are rechecked. The campaign
registers only one C run per exact case. A copied run cannot change its canonical
run_root or registration identity. This is a local host accounting boundary,
not an OS sandbox against a malicious same-account Host.

CLI operations (run with the actual reviewed source's absolute Python `-I -B`):

```text
freeze-campaign --registration FILE --out NEW_CAMPAIGN
init --campaign CAMPAIGN --out NEW_RUN --case U-LIVE-01|U-READ-01
prepare --run RUN --stage NEW --role ROLE
begin-native --run RUN --stage STAGE --invocation ROOT_OBSERVATION
read-methods --run RUN --ordinal N --executor ACTUAL_CANONICAL_ID
observe --run RUN --ordinal N --result RAW --result-sha256 SHA \
  --observation ROOT_COMPLETION --observation-sha256 SHA
snapshot --run RUN --name original_complete|repaired_complete|equal_budget_evaluated --ordinal N
deliver-feedback --run RUN --ordinal N
repair-begin --run RUN --evidence NECESSITY
declare-extra --run RUN --evidence ACTUAL_SEPARATE_EXTRA_RECORD
status --run RUN
bind-original-slot --campaign CAMPAIGN --slot CASE-A|CASE-B|CASE-C --proof FILE
inspect-initial-barrier --campaign CAMPAIGN
open-private-evaluation --campaign CAMPAIGN --Root-observation FILE --independent-audit FILE
```

`freeze-campaign` is a tool operation for a future authorized registration, not
an action taken by this source implementation or its tests on formal data.

## Actual native observations and exact original bytes

Invocation and completion records carry `observation_kind` equal to d0's
`root_controller_transcription_of_actual_native_tool_response`,
`assurance=host_attested`, a fresh `observed_at_utc`, and evidence_kind
`ROOT_ACTUAL_NATIVE` for admitted work or `SYNTHETIC_ENGINEERING_ONLY` for neutral
fixtures. They are Root transcriptions, not platform signatures or human proof.

Invocation binds `packet_sha256` and `spawn`: actual tool name
collaboration.spawn_agent/followup_task, canonical_task_name, returned_task_name,
actual `native_turn_id`, fork_turns, inherited_identities and lineage_known.
Fresh spawn uses fork none and empty inheritance. Known followups remain within
the same run and author/reviewer responsibility; feedback reviewer may later
perform readonly verification. Unknown/excluded lineage and cross-case actors
cannot qualify. Every actual reported turn is globally charged once by its
actual turn ID, including excluded or over-cap turns. They can still retain raw
originals but never gain equal-budget credit. Prospective cap exhaustion refuses
another packet. An interrupted global/local journal append remains unknown and
blocks resend/reset, rather than creating fresh allowance.

`read-methods` returns all six exact files and saves a mechanical read record.
That response does not prove the model read/applied them. The actual Root
completion separately binds its hash, packet hash, model_output_bytes_sha256,
all_method_bytes_read and `completion`: sender, FINAL_ANSWER, list_agents
completed observation and observed_completed_agents. Its full raw_final_message
UTF-8 bytes must exactly equal RAW, preserving prefixes, fences, CR/LF and terminal
LF. Metadata is separate. Unknown or refused turns still count; unknown is not a
complete draft. All supplied RAW/completion bytes are exclusively frozen before
JSON metadata validation. Hash/format/observation refusal never edits the raw or
allows replacement of its ordinal.

The first original is the **earliest actual observed complete declaration**,
not an SDK acceptance or preferred text. After that declaration no new initial
Writer is eligible. Blind views are exact byte copies with one identity-offset
mapping and possible native format identifiability disclosed. Completeness is
Root's observed declaration; no content/schema quality decision is automated.

Feedback is one actual independent review, after the local original is frozen.
It is public legal feedback, never a private answer. Repair needs exact byte
locators into that feedback, an actual defect declaration and1–3 necessary layers
(argument/page_copy/speech). No defect means no manufactured repair. Repair is
one cycle with at most three actual Writer turns, including refusals/retries.
The first actual complete repair ends that single cycle, preventing a preferred
later full draft; partial necessary-layer work and actual refusals still count.
The repaired raw and byte diff are frozen. One actual readonly verification is
required after repair; it cannot be delivered as a second feedback or initiate
another Writer repair. Without repair the evaluated view keeps the same original
invocation/bytes. Extra/over-budget/excluded execution is preserved and cannot be
relabeled an equal-budget result. A Writer packet includes only this case's
legal inputs, pinned methods, exact own author history, and the one feedback
when needed; no verification text, other arms/cases or private metadata enters it.

## Six original slots, without importing A/B SDK

The fixed barrier slots are U-LIVE-01-A/B/C and U-READ-01-A/B/C. Each proof has
only observation fields plus `slot`, `input_identity`, `method_identity`,
`original_snapshot`, `lineage_read_execution`. Input identity is SHA256 of the
canonical encoded ordered `[sha256,bytes]` brief/material rows for that case.
Methods match its preregistered slot identity. The snapshot timepoint must be
original_complete, never first_sdk_complete/qualified/equalbudget/later work.

C snapshot must be this campaign's unique actual C run and earliest native
original, with a known eligible within-budget initial prefix. A/B snapshot is
the existing `rc3-campaign-original-native-snapshot.v1`, containing the actual
`rc3-native-complete-draft-manifest.v1`, selected raw_stage_ordinals, all selected
raw/observation refs and completeness_source_observation. SDK outcomes can be
failures; they cannot replace raw originals or imply quality.

The lineage sidecar is a separate Root observation with slot, lineage_known,
author_identities, earliest_complete_snapshot_sha256 and
earlier_complete_snapshot_refs=[]; invocation/method_read/completion refs bind
the actual completeness execution. For A/B, `stage_receipts` lists every selected
ordinal and its own invocation/method_read/completion refs in manifest order.
Completion hashes/read-record hashes/actual senders must match. Same actual
invocation cannot fill a different slot; excluded authors are refused. These are
host-attested actual chronology/read/execution observations, not a content judge
or platform attestation. All transitive refs are rechecked at barrier inspection.

Only when all six complete originals exist and are fixed does the barrier become
ready; missing/refusal never triggers a waiver or resample. `open-private` also
checks an actual independent nonauthor audit (the JSON field is
`independent_nonauthor`), exact original_proof_sha256s in binding order, reviewer,
barrier_slots and all_originals_checked. Its native_invocation/native_completion/
audit_raw refs bind a fresh fork-none independent actual fullFINAL/completed
source, excluding authors/feedback/controller-preparers. No reviewer boolean
alone passes. Its actual native audit and unknown cost are recorded separately,
without adding or resetting C Writer/feedback allowance. Actual evaluation reported before the barrier permanently marks
contamination; later originals do not wash it. An ordinary failed preflight does
not pretend private judgment already happened. A later report can explicitly
record private_evaluation_before_initial_barrier=true, preserving contamination.

The recorder never accepts an oracle argument, opens the private/oracle tree,
or dispatches private judges. Root separately releases the private evaluation
packet only after the gate, using actual fresh eligible judges. Undisclosed
same-account context/history cannot be detected cryptographically; fresh/exposure
records remain honest host_attested observations, not a sandbox claim.

## Focused validation and remaining admission

`tests/rebuild/test_rc3_unseen_native_only.py` uses only fresh temporary neutral
texts. Its six tiny method fixtures explicitly monkeypatch expected hashes only
inside pytest, not a production fallback or evidence of full Cyber read. Tests
cover raw-first exactness/refusal/immutability, counters and replay, first-draft
and no-repair identity, necessary repair/readonly closure, no run reset, unknown
lineage/cross-case actors, six slots/SDK snapshot rejection, transitive ref tamper,
early private contamination, and crash accounting. A clean isolated import
asserts no deck_master or old native_only module was loaded.

Fixed old d0/d9/bf bytes, existing actual native fullFINAL/read primitives and
Cyber method identities may support precise unchanged-dependency reuse. New case
validation/counters/lineage/barrier differences still need independent source
review and Root's bounded actual admission. This file creates no actual final05
identity, installed candidate, production authorization, ledger, formal native
run or private evaluation. Those future bindings remain pending.
