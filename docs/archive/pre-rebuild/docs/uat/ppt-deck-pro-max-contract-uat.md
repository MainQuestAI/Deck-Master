# PPT Deck Pro Max Contract UAT

## Scope
Verify that generation results from PPT Deck Pro Max are correctly consumed by Deck Master.

## Test Cases

### TC-G1: Completed result
- **Given**: A generation result with `status: completed`.
- **When**: `import-generation-result --input generation_result.json`
- **Then**: Generation task status is `completed`, preview manifest updated.

### TC-G2: Failed result
- **Given**: A generation result with `status: failed` and `errors`.
- **When**: Imported.
- **Then**: Task status is `failed`, Review Cockpit shows error.

### TC-G3: Locked page protection
- **Given**: A locked page and an import attempt.
- **When**: Imported without `--force`.
- **Then**: Error, page not overwritten.

### TC-G4: Rerun safety
- **Given**: A generation result for a previously completed task.
- **When**: Imported again.
- **Then**: New result replaces old, locked pages respected.

## Run Command

```bash
python3 scripts/deck_master.py import-generation-result --run-id <id> --input generation_result.json
python3 scripts/deck_master.py validate-generation-result --input generation_result.json
```

## v0.9.6 UAT Report

```bash
python3 scripts/deck_master.py uat-generation-tool \
  --run-dir runs/<run_id> \
  --tool ppt-deck-pro-max \
  --require-preview
```

Outputs:

- `runs/<run_id>/uat_reports/generation_tool_uat.json`
- `runs/<run_id>/uat_reports/generation_tool_uat.md`
