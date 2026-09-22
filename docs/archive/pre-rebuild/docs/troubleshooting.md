# Deck Master Troubleshooting

## Suite Status Is Degraded

Run:

```bash
python3 scripts/deck_master.py setup-status --include-suite --output json
python3 scripts/deck_master.py suite-status --output json
```

Repair:

```bash
python3 scripts/deck_master.py suite-install --target codex
```

If a real directory already exists where a skill symlink should be, create a migration plan:

```bash
python3 scripts/deck_master.py suite-migrate-legacy-skills --target codex --plan-file /tmp/deck-master-migration.json
```

## Release Smoke Fails

Run:

```bash
python3 scripts/deck_master.py release-smoke
```

Common causes:

- `bin/deck-master` is missing or not executable.
- `scripts/deck_master.py` is missing from the release tree.
- `SHA256SUMS` does not match release files.
- Required skills, capabilities, or contracts are missing.

Rollback:

```bash
python3 scripts/deck_master.py release-rollback
```

## Generation Is Waiting

If run-state shows `awaiting_agent_execution`, Deck Master is waiting for an external generation result.

Check:

```bash
ls <run_dir>/generation_dispatch
```

Then import:

```bash
python3 scripts/deck_master.py generation-session import-results --run-dir <run_dir> --input <result_or_dir>
```

Import blockers usually mean one of these:

- `run_id` mismatch.
- `session_id` mismatch.
- source fingerprint mismatch.
- absolute path or path traversal.
- checksum mismatch.
- placeholder content in production output.

## Build Or Render Is Blocked

Check:

```bash
python3 scripts/deck_master.py build status --run-dir <run_dir>
python3 scripts/deck_master.py final-readiness --run-dir <run_dir>
```

Typical blockers:

- missing preview assets.
- invalid artifact signature.
- checksum mismatch.
- stale source fingerprint.
- missing render result.
- page count mismatch.

## Client Export Is Blocked

Client export requires final readiness.

```bash
python3 scripts/deck_master.py final-readiness --run-dir <run_dir>
python3 scripts/deck_master.py export --run-dir <run_dir>
```

Use the readiness JSON to identify the blocking reason:

```text
<run_dir>/delivery/final_readiness.json
```

## RC Gate Fails

Run:

```bash
python3 scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc --benchmark-dir benchmarks --skip-browser-smoke --force
```

Read:

```text
/tmp/deck-master-rc/rc_gate_report.json
/tmp/deck-master-rc/rc_gate_report.md
```

Common failed checks:

- `schema_json_parse`: invalid JSON in contract or benchmark metadata.
- `artifact_validator`: artifact descriptor, checksum, signature, or path safety issue.
- `release_smoke`: self-contained release package issue.
- `fixture_e2e`: fixture autoplan smoke did not produce required run files.
- `benchmark_aggregate`: fewer than 3 real metadata benchmark cases.
- `browser_smoke`: Playwright/browser runtime missing when `--require-browser-smoke` is used.

## Benchmark Metadata Is Rejected

Real benchmark cases must not include private text.

Allowed:

```json
{
  "raw_source_policy": "local_path_only",
  "local_source_paths": ["~/deck-master-local-benchmarks/<case_id>/raw"]
}
```

Blocked fields include:

- `raw_content`
- `raw_source_text`
- `source_excerpt`
- `embedded_text`
- `content`
