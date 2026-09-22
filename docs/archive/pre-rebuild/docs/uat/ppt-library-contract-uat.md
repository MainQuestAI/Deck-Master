# PPT Library Contract UAT

## Scope
Verify that PPT Library candidate output is correctly consumed by Deck Master.

## Test Cases

### TC-L1: Candidate field completeness
- **Given**: A PPT Library search result with all required fields.
- **When**: `validate-ppt-library-result --input selection.json`
- **Then**: Result is `valid: true`.

### TC-L2: Missing required field
- **Given**: A candidate missing `slide_id`.
- **When**: Validated.
- **Then**: `valid: false`, error mentions `slide_id`.

### TC-L3: Confidence out of range
- **Given**: A candidate with `confidence: 1.5`.
- **When**: Validated.
- **Then**: `valid: false`, error mentions confidence range.

### TC-L4: Screenshot path warning
- **Given**: A candidate with missing `screenshot_path`.
- **When**: Validated.
- **Then**: `valid: true`, warning mentions `screenshot_path`.

### TC-L5: Real run integration
- **Given**: A real run with PPT Library selection.
- **When**: `decide-sourcing` is run.
- **Then**: Sourcing plan correctly references library candidates.

## Run Command

```bash
python3 scripts/deck_master.py validate-ppt-library-result --input library_results/selection.json
```

## v0.9.6 UAT Report

```bash
python3 scripts/deck_master.py uat-ppt-library \
  --run-dir runs/<run_id> \
  --input library_results/selection.json \
  --require-screenshot
```

Outputs:

- `runs/<run_id>/uat_reports/ppt_library_uat.json`
- `runs/<run_id>/uat_reports/ppt_library_uat.md`

## Selection v2

- Canonical input is `deck_master_ppt_library_selection.v2` using `selections[]`.
- Candidate identity requires `candidate_id`, `asset_key`, and `source_asset_id`.
- `source_file` and `source_path` are forbidden in v2 public artifacts.
- The full v2 payload must pass the canonical schema and recursive evidence
  safety scan, including `by_beat` and unknown nested objects.
- `page_task_id` and `query_trace_id` are checked at selection level and against
  candidate values when candidates carry them.
- `screenshot_ref` must remain run-relative. Missing or degraded previews are a
  warning by default and an error with `--require-screenshot`.
- v1 continues to require `source_file` and uses `canonical_slide_id` coverage.
