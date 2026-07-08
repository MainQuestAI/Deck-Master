# Deck Master Agent Task Index

This index routes user intent to the safest Agent command path. Prefer these
entries over guessing file locations or reading historical specs.

## Source Checkout Command Form

Use `python3 scripts/deck_master.py ...` before installation. For test and
editable-install work, use Python 3.12 by default. Python 3.11 and 3.12 are
supported for preview commands; real PPT Library v2 integration requires
Python 3.12+. After installing with `python -m pip install -e ".[dev]"`,
`deck-master ...` is equivalent.

## New Public Preview Run

- Intent: generate the public fixture demo or verify v0.9.14-preview.2.
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
