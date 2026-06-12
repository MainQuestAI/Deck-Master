# PPT Master Contract UAT

## Scope
Verify that render results from PPT Master are correctly consumed by Deck Master.

## Test Cases

### TC-R1: Completed render
- **Given**: A render result with `status: completed` and `artifact_path`.
- **When**: `validate-render-result --input render_result.json`
- **Then**: `valid: true`.

### TC-R2: Failed render
- **Given**: A render result with `status: failed` and `errors`.
- **When**: Validated.
- **Then**: `valid: true` (if schema correct), errors visible.

### TC-R3: Missing artifact path
- **Given**: A completed result without `artifact_path`.
- **When**: Validated.
- **Then**: `valid: false`.

### TC-R4: Delivery gate integration
- **Given**: A completed render result.
- **When**: `quality-gate delivery --artifact <path>` is run.
- **Then**: Delivery gate reads the render artifact.

## Run Command

```bash
python3 scripts/deck_master.py validate-render-result --input render_result.json
```
