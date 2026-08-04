# Deck Master Agent Recovery Playbook

Use this playbook when a JSON command returns `blocked`, `fail`, or an
unexpected runtime stage. Do not repair by editing random artifacts.

## Backend Missing

- Detect by: `agent-doctor --mode production` check `production_backend` or
  `suite-status.external_dependency_status` for `ppt-master`.
- Auto action: none for production. Fixture preview may continue.
- Stop when the `ppt-master` production backend is not `bound_verified` with a
  verified git SHA.
- Verify with:

```bash
python3 scripts/deck_master.py agent-doctor --mode production --output json
```

## Preview Missing

- Detect by: `preview-gate.required_files.status == "fail"` or
  `next-step.runtime_stage == "needs_preview"`.
- Auto action: rebuild preview only when upstream artifacts exist.

```bash
python3 scripts/deck_master.py build-preview --run-dir <run_dir>
python3 scripts/deck_master.py preview-gate --run-dir <run_dir> --expect-unconfigured-backend-ok
```

- Stop when: request, narrative plan, page tasks, or sourcing plan is missing.

## Schema Mismatch

- Detect by: validation error mentioning a schema version or a contract in
  `docs/contracts/`.
- Auto action: run a documented migration command only when one exists.
- Stop when: no migration path is documented.
- Verify with the same command that reported the schema mismatch.

## Stale Generation Result

- Detect by: import or generation session output mentions stale source
  fingerprint, checksum mismatch, or session mismatch.
- Auto action: recreate or redispatch the generation session.

```bash
python3 scripts/deck_master.py generation-session status --run-dir <run_dir>
python3 scripts/deck_master.py generation-session dispatch --run-dir <run_dir>
```

- Stop when: external Agent execution is required.

## P0 Quality Finding

- Detect by: quality gate output with severity `P0` or final readiness blocker.
- Auto action: repair the source artifact or rerun the matching quality gate.
- Stop when: an override would be required. P0 cannot be overridden for client
  export.
- Verify with:

```bash
python3 scripts/deck_master.py final-readiness --run-dir <run_dir> --no-write
```

## Final Readiness Blocked

- Detect by: `final-readiness` has blockers or `agent-doctor` check
  `final_readiness` is blocked.
- Auto action: fix blocker codes in order: render, artifact path, delivery
  validation, lineage, quality gates, customer-visible safety.
- Stop when: production backend, external artifact, or human approval is
  missing.
- Verify with:

```bash
python3 scripts/deck_master.py final-readiness --run-dir <run_dir> --no-write
```

## Release Smoke Failed

- Detect by: `release-smoke.status != "passed"` or verification errors.
- Auto action: rebuild release tree once.

```bash
python3 scripts/deck_master.py release-build --output /tmp/deck-master-0.9.14-preview-release --force
python3 scripts/deck_master.py release-smoke --release-root /tmp/deck-master-0.9.14-preview-release
```

- Stop when: checksum, missing contract, or missing capability errors remain.

## High-Density Builder

- Detect by: `build status --profile high-density` returns `blocked`, or a
  high-density command returns a structured error with an `HD_*` code.
- Read the persisted failure before changing artifacts:

```bash
python3 scripts/deck_master.py build status --run-dir <run_dir> --profile high-density
python3 scripts/deck_master.py next-step --run-dir <run_dir>
```

- Auto action: follow the returned `next_command`. A page-scoped failure uses
  `build retry --profile high-density --page-id <page_id> --stage <stage>` and
  invalidates that stage and all downstream artifacts.
- Blueprint waiting: the Agent must generate or approve the blueprint at the
  recorded `output_ref`, then rerun the recorded resume command.
- Scene waiting: the Agent must write a semantic `page_scene.v1` with locked
  text references and in-canvas geometry, then resume the run.
- Visual review waiting: the Agent must write a passing visual review tied to
  the current SVG and blueprint hashes, then resume the run.
- Stop when: the error is `HIGH_DENSITY_CAPABILITY_MISSING`, a production run
  lacks the required Agent/ImageGen capability, or the error remains after one
  targeted retry. Do not mark the canonical build manifest completed while
  high-density status is blocked or awaiting Agent work.
- Verify after repair:

```bash
python3 scripts/deck_master.py build run --run-dir <run_dir> --profile high-density
python3 scripts/deck_master.py build status --run-dir <run_dir> --profile high-density
python3 scripts/deck_master.py final-readiness --run-dir <run_dir> --no-write
```
