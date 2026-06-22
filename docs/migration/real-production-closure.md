# Real Production Closure Migration Guide

This guide explains how to move an existing Deck Master local setup onto the Real Production Closure flow.

## 1. Update The Suite Release

```bash
python3 scripts/deck_master.py suite-install --target codex
python3 scripts/deck_master.py release-smoke
```

What changes:

- Deck Master builds into a staging release first.
- The staged release is verified before activation.
- The prior release is retained as `~/.deck-master/previous`.
- `release-rollback` can restore the previous release.

Rollback:

```bash
python3 scripts/deck_master.py release-rollback
```

## 2. Update Production Generation Flow

Production generation now waits for an external Agent result.

Old compatible read state:

```text
dispatched
```

Current production state:

```text
awaiting_agent_execution
```

Action:

```bash
python3 scripts/deck_master.py run-generation --run-dir <run_dir> --no-execute
```

Then send `generation_dispatch/dispatch_package.json` to the external Agent and import `deck_generation_result.v2`.

## 3. Update Build And Render Flow

Use build commands before final readiness:

```bash
python3 scripts/deck_master.py build prepare --run-dir <run_dir>
python3 scripts/deck_master.py build run --run-dir <run_dir>
python3 scripts/deck_master.py final-readiness --run-dir <run_dir>
```

The build writes artifact manifests and render result v2. Final readiness reads those outputs.

## 4. Update Export Rules

Client export now reads final readiness.

```bash
python3 scripts/deck_master.py export --run-dir <run_dir>
```

If final readiness is blocked, client export is blocked. Internal export can be used only when degraded output is acceptable and clearly marked.

## 5. Update Benchmark Cases

Real benchmark metadata must use:

```json
{
  "case_type": "real_metadata",
  "source_material": {
    "raw_source_policy": "local_path_only",
    "local_source_paths": ["~/DeckMasterPrivateBenchmarks/<case_id>/raw"],
    "excluded_from_repo": true
  }
}
```

Do not commit raw source files. Commit only sanitized metadata.

## 6. Update Release Candidate Checks

Use:

```bash
python3 scripts/deck_master.py rc-gate --output-dir <out_dir> --benchmark-dir benchmarks --skip-browser-smoke --force
```

If browser validation is required:

```bash
python3 scripts/deck_master.py rc-gate --output-dir <out_dir> --benchmark-dir benchmarks --require-browser-smoke --force
```

## Compatibility Notes

- Legacy `dispatched` generation-session state remains readable.
- Existing `suite-build-release-tree` remains available.
- `release-build` is the clearer command for self-contained release output.
- Fixture mode remains available for tests and local smoke, but fixture fallback is blocked for production and benchmark paths.
