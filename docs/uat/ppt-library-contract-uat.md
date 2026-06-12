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
