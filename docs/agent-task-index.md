# Deck Master Agent Task Index

This index routes user intent to the safest Agent command path. Prefer these
entries over guessing file locations or reading historical specs.

## Task Scope

Choose the request before loading a production playbook. Existing directions,
page selections, and authorization remain usable; only ask about a missing
decision that affects this task.

| Intent | Routing command | Detail to read |
| --- | --- | --- |
| New deck from material | `route-skill --input-type new_deck` | `skills/deck-master/playbooks/codex-run-solution-deck.md` |
| Selected-page revision | `route-skill --input-type local_edit --run-dir <run_dir>` | `skills/deck-master/playbooks/local-edits.md` |
| Read-only diagnosis | `route-skill --input-type diagnosis --run-dir <run_dir>` | Reported error and deck-doctor |
| Client delivery | `route-skill --input-type client_delivery` | Current final-readiness and approval |
| Software installation/upgrade | `route-skill --input-type software_release` | `skills/deck-master/references/installation.md` |

Explicit task routes preserve the edit/diagnosis scope even when a run's
whole-deck workflow has upstream gaps. They report the applicable skill and
references without changing run state or granting stage/export approval.
Selected-page edits reuse confirmed design and valid unaffected artifacts.

## Project Skill Installation

After the central release is installed, attach Codex project entries with
`suite-install --target codex --scope project --project-root <project> --links-only --include-optional`.
Use the same project arguments with `suite-status` and `uninstall-skill --suite`.
From inside that project, default discovery uses the nearest suite entry;
`--scope global` explicitly selects global links. See
`skills/deck-master/references/installation.md` for upgrade/rollback and migration.

## Source Checkout Command Form

Use `python3 scripts/deck_master.py ...` before installation. For test and
editable-install work, use Python 3.12 by default. Python 3.11 and 3.12 are
supported for preview commands; real PPT Library v2 integration requires
Python 3.12+. After installing with `python -m pip install -e ".[dev]"`,
`deck-master ...` is equivalent.

## New Native Production Run

SC-1.1 supersedes the former unconditional PPT Master prerequisite. Preserve
all source authorization, evidence, revision and final approval requirements.
Start from materials with `start-conversation`, submit the Agent extraction to
`build-brief`, then follow `next-step`. Native `autoplan` dispatches a
`page-content` task: submit complete Agent-authored page content through
`page-content submit`, which atomically creates PagePackages and dispatches
ImageGen or SVG tasks. No HD fixture run or legacy generation artifact is a
prerequisite. See [content handoff](contracts/page-content-handoff.md).

Existing runs keep their persisted route. Use documented `build migrate`
operations for explicit conversion; an unidentified historical run remains
`migration_required`. Never change the run mode to weaken delivery gates.

## New Public Preview Run

- Intent: generate the public fixture demo or verify v0.9.14-preview.4.
- Command:

```bash
bash scripts/demo.sh
python3 scripts/deck_master.py preview-gate --run-dir /tmp/deck-master-demo/oss-demo --expect-unconfigured-backend-ok
```

- Expected artifacts: `request.json`, `narrative_plan.json`, `page_tasks.json`,
  `sourcing_plan.json`, `preview_manifest.json`.
- Success state: `preview-gate.status == "pass"`.
- If blocked: read `docs/agent-recovery-playbook.md#preview-missing`.

## Continue Existing Run

- Intent: resume a run without guessing the next file to write.
- Command:

```bash
python3 scripts/deck_master.py next-step --run-dir <run_dir>
```

- Expected artifacts: no write by default; returns `next_command`,
  `runtime_stage`, `recommended_skill`, and `next_agent_action`.
- Success state: execute only the returned `next_command`.
- If blocked: route by `runtime_stage` in the recovery playbook.

## Check Agent Readiness

- Intent: decide whether the current repo can be handled by an Agent.
- Commands:

```bash
python3 scripts/deck_master.py agent-doctor --mode preview --output json
python3 scripts/deck_master.py suite-status --output json
python3 scripts/deck_master.py agent-doctor --mode production --output json
```

- Success state: `agent-doctor.status == "ready"` and suite output explains any
  non-production capability limits.
- If production is blocked: do not run production commands; follow
  `next_agent_action`.

## Check Client Delivery

- Intent: decide whether a run can be exported to a client-facing artifact.
- Command:

```bash
python3 scripts/deck_master.py final-readiness --run-dir <run_dir> --no-write
```

- Expected artifacts checked: render result, final artifact, lineage, quality
  gates, customer-visible safety.
- Success state: final readiness has no blockers.
- If blocked: fix the blocker code before export.

## Repair Blocked Run

- Intent: convert a blocked JSON state into a safe next action.
- Commands:

```bash
python3 scripts/deck_master.py next-step --run-dir <run_dir>
python3 scripts/deck_master.py agent-doctor --mode production --run-dir <run_dir> --output json
```

- Expected output: `runtime_stage`, `blocking_issues`, `errors`,
  `next_agent_action`.
- If the next action needs external backend or handoff output, stop and report.
- Distinguish the two waiting states (SC-1 A5/F03): `awaiting_agent_execution`
  (e.g. `needs_generation_execution`) is executable by you in this session —
  do not stop; only states that genuinely need the user (approval, authorization)
  or an external backend are stop-and-report conditions.

## High-Density Build

- Intent: build the independent high-density deck route from locked Page
  Packages through Agent blueprint work, semantic scene reconstruction, native
  SVG, editable PPTX, readback, and canonical handback.
- Capability check:

```bash
python3 scripts/deck_master.py suite-status --capability deck_master.build.high_density.v1 --output json
```

- Prepare and run:

```bash
python3 scripts/deck_master.py build prepare --run-dir <run_dir> --profile high-density --output-profile production_pptx
python3 scripts/deck_master.py build run --run-dir <run_dir> --profile high-density
```

- Continue an Agent-owned stage with the exact command returned by:

```bash
python3 scripts/deck_master.py next-step --run-dir <run_dir>
```

- Check progress:

```bash
python3 scripts/deck_master.py build status --run-dir <run_dir> --profile high-density --watch
```

- Repair a page-scoped failure:

```bash
python3 scripts/deck_master.py build retry --run-dir <run_dir> --profile high-density --page-id <page_id> --stage <stage>
```

- Success state: `high_density_status.v2.status == "completed"`, the build
  manifest is completed with a high-density manifest reference, and canonical
  artifact/render handback validates.
- If blocked: read `docs/agent-recovery-playbook.md#high-density-builder`.

## Build And Verify Release

- Intent: create a self-contained release tree and verify it.
- Commands:

```bash
python3 scripts/deck_master.py release-build --output /tmp/deck-master-0.9.14-preview-release --force
python3 scripts/deck_master.py release-smoke --release-root /tmp/deck-master-0.9.14-preview-release
```

- Success state: release smoke `status == "passed"`.
- If checking the default `~/.deck-master/current` fails, treat it as an
  active-install smoke failure; build and smoke a fresh tree before reporting
  release readiness.
- If blocked: follow `docs/agent-recovery-playbook.md#release-smoke-failed`.

## QA

- Intent: verify this repository after changes.
- Commands:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python3 -m unittest discover -s tests
python3 -m pytest -q
python3 scripts/deck_master.py agent-doctor --mode preview --output json
```

If venv pip bootstrap is unavailable, use `uv venv --python 3.12 .venv` and
`uv pip install --python .venv/bin/python -e ".[dev]"`, then run the same
commands through `.venv/bin/python`.

For compatibility evidence, optionally repeat the same command set on Python
3.11 after the Python 3.12 release smoke is green.

- Success state: all tests pass and `agent-doctor` returns `ready` or explains
  only expected preview warnings.

## Bounded public research

Use `research prepare --run-dir <run> --input <task.json>` with the formal
`research-task.v1.schema.json` contract. Each task contains one concrete
question; create separate task IDs for independent questions. `based_on`
records the SHA-256 of each input and the canonical JSON fingerprint of that
reference list. The run-relative `authorization_ref` points to a record with
`scope: public_research`, an explicit `authorization_basis`, and exactly the
approved `public_query_context` and `allowed_sources` (HTTPS hostnames).
Internal questions and private context are not included in the dispatched
query. Raising the default two actions/two rounds/six sources requires matching
`limits` in that authorization record.

`research dispatch --run-dir <run> --task-id <id>` durably reserves one host
action before the tool call. On restart it returns the same pending action ID;
inspect the host's existing tool observation before deciding whether execution
is still needed. `research status` is read-only. The host executes the approved
query and calls `research submit --run-dir <run> --input <result.json>` with
`task_id`, the issued `action_id`, `status`, one `query_log` entry containing
`tool`, the exact `query`, and the actual `observation`, plus `sources`,
`result_summary`, `counter_evidence`, and `open_questions`.

Accepted terminal statuses are `executed`, `inconclusive`, and
`capability_unavailable`; `retryable_error` allows another action within the
remaining budget and becomes `inconclusive` at exhaustion. Executed results
require consulted HTTPS sources within the authorization, captured `excerpt`,
`applicability_bounds`, and a counter-evidence check. The runtime records host
observations; it does not independently attest that the external tool ran.
Terminal results atomically update the existing Context Manifest with affected
judgments, unresolved questions, and `externally_verified_candidate` sources.
They never establish unknown customer facts or approve delivery. Exact result
replay is idempotent; conflicting replay and unissued actions are rejected.
