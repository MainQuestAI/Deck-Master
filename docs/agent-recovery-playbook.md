# Deck Master Agent Recovery Playbook

Use this playbook when a JSON command returns `blocked`, `fail`, or an
unexpected runtime stage. Do not repair by editing random artifacts.

## Backend Missing

- First read the persisted build route. Only `legacy_ppt_master` requires the
  `ppt-master` dependency to be `bound_verified` with a verified git SHA.
- For that legacy route, detect missing dependencies with `agent-doctor` or
  `suite-status.external_dependency_status`; stop that route until repaired.
- For `deck_native`, inspect actual compiler/renderer/font and host task
  readiness instead. An unbound optional legacy backend does not block native.
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
- Scene waiting: the Agent must write a semantic `page_scene.v2` with locked
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

## Native Build and Research Recovery

Use `next-step --run-dir <run>` and `build status --run-dir <run>` first.
The persisted route and immutable current revision take precedence over legacy
compatibility projections. Do not repair a native run by editing fixed SVG or
Scene projections: submit both files using its Runtime-issued action.

- `awaiting_agent_imagegen`: execute the issued host image task and submit the
  real image plus observation receipt. A missing provider request ID stays null.
- `awaiting_agent_reconstruct` / `awaiting_svg_authoring`: return SVG and Scene
  for the same Lock and input fingerprint. Explicit page repair uses
  `build retry --page-id <page> --stage svg`; valid other pages are retained.
- Exhausted action budget: preserve the run and report its used/remaining budget.
  Do not create a different action ID or run merely to evade the limit.
- `migration_required`: keep historical files read-only; create a specific
  `build migrate --dry-run --output <plan>` and apply only that unchanged plan.
  `--verify` and `--rollback` require the returned migration ID.
- Interrupted commit: recover projections from the authoritative revision and
  replay the original action. A published revision includes its durable receipt;
  a complete orphan snapshot before pointer publication can be safely reused.
- Pending research: follow the returned `research dispatch` command. Restart
  reuses its pending action. `inconclusive` and `capability_unavailable` retain
  the affected decisions and open questions; they do not establish customer facts.

Native file quality checks use the current artifact without requiring a legacy
backend setup. Recompile/render and rerun affected gates after changes; a new
PPTX always needs its own final artifact approval.

### Native cancellation and incomplete source reading

- `stopped`: preserve the cancellation receipt and any completed page outputs.
  A stopped issued action is one consumed attempt, not a way to reset the budget.
  Use `build cancel --run-dir <run> --action-id <issued-action> --reason "<reason>"`
  to stop current host work. Only explicit `build retry --run-dir <run>
  --page-id <page> --stage <cancelled-stage>` resumes. Late output for the cancelled
  action is rejected; cancellation cannot revoke an already committed revision.
- `blocked_context_reading`: execute the returned extraction task for missing
  source ranges. Import the version-bound result with `import-context-pack
  --run-dir <run> --input <pack.json> --merge`. A full extraction must identify the
  actual source SHA, preserved extraction snapshot and complete coverage; never
  turn a partial read into full by changing a status label. Changed source bytes
  require registration of that version. Exact result replay is idempotent.
- `needs_agent_analysis` from `build-judgments`: author a source-referenced public
  problem and solution mechanism through the existing content handoff. Existing
  Narrative proposals remain unscored proposals. Preserve working assumptions,
  risk and recheck conditions; a general source reference is not factual support.

Quality overrides bind the actual selected artifact or public draft inputs and
scope. Changed bytes require a new explicit decision. Page output actions cannot
replace quality reports, build evidence or final approval files. Workspace learning
keeps raw customer feedback and finding details in their source runs; reusable
cards require an explicitly authored abstraction with source and scope limits.
