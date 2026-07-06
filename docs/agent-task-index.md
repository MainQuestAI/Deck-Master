# Deck Master Agent Task Index

This index routes user intent to the safest Agent command path. Prefer these
entries over guessing file locations or reading historical specs.

## New Public Preview Run

- Intent: generate the public fixture demo or verify Technical Preview.
- Command:

```bash
bash scripts/demo.sh
deck-master preview-gate --run-dir /tmp/deck-master-demo/oss-demo --expect-unconfigured-backend-ok
```

- Expected artifacts: `request.json`, `narrative_plan.json`, `page_tasks.json`,
  `sourcing_plan.json`, `preview_manifest.json`.
- Success state: `preview-gate.status == "pass"`.
- If blocked: read `docs/agent-recovery-playbook.md#preview-missing`.

## Continue Existing Run

- Intent: resume a run without guessing the next file to write.
- Command:

```bash
deck-master next-step --run-dir <run_dir>
```

- Expected artifacts: no write by default; returns `next_command`,
  `runtime_stage`, `recommended_skill`, and `next_agent_action`.
- Success state: execute only the returned `next_command`.
- If blocked: route by `runtime_stage` in the recovery playbook.

## Check Agent Readiness

- Intent: decide whether the current repo can be handled by an Agent.
- Commands:

```bash
deck-master agent-doctor --mode preview --output json
deck-master suite-status --output json
deck-master agent-doctor --mode production --output json
```

- Success state: `agent-doctor.status == "ready"` and suite output explains any
  non-production capability limits.
- If production is blocked: do not run production commands; follow
  `next_agent_action`.

## Check Client Delivery

- Intent: decide whether a run can be exported to a client-facing artifact.
- Command:

```bash
deck-master final-readiness --run-dir <run_dir> --no-write
```

- Expected artifacts checked: render result, final artifact, lineage, quality
  gates, customer-visible safety.
- Success state: final readiness has no blockers.
- If blocked: fix the blocker code before export.

## Repair Blocked Run

- Intent: convert a blocked JSON state into a safe next action.
- Commands:

```bash
deck-master next-step --run-dir <run_dir>
deck-master agent-doctor --mode production --run-dir <run_dir> --output json
```

- Expected output: `runtime_stage`, `blocking_issues`, `errors`,
  `next_agent_action`.
- If the next action needs external backend or handoff output, stop and report.

## Build And Verify Release

- Intent: create a self-contained release tree and verify it.
- Commands:

```bash
deck-master release-build --output /tmp/deck-master-agent-ready-release --force
deck-master release-smoke --release-root /tmp/deck-master-agent-ready-release
```

- Success state: release smoke `status == "passed"`.
- If blocked: follow `docs/agent-recovery-playbook.md#release-smoke-failed`.

## QA

- Intent: verify this repository after changes.
- Commands:

```bash
python3 -m unittest discover -s tests
python3 -m pytest -q
deck-master agent-doctor --mode preview --output json
```

- Success state: all tests pass and `agent-doctor` returns `ready` or explains
  only expected preview warnings.
