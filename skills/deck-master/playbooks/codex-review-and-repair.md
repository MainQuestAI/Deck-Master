# Playbook — Review and Repair Loop

Use when quality gates block export or when you want to systematically address
findings before delivery.

For a selected-page edit without a delivery request, use [local edits](local-edits.md).
Reuse confirmed direction and current checks. Only request external review when
the finding requires it and the configured review policy calls for it.

## Steps

### 1. Identify Blocking Findings

```bash
python3 scripts/deck_master.py next-step --run-id <run_id>
```

Look for `fix_quality_finding`, `fix_evidence_gap`, and `repair_page` actions.

### 2. Request External Quality Review

For semantic or evidence alignment issues that need deeper reasoning:

```bash
python3 scripts/deck_master.py prepare-quality-review \
  --run-id <run_id> --scope semantic,evidence
```

Execute the review tasks in `quality_review_tasks/`, write results, then:

```bash
python3 scripts/deck_master.py import-quality-review \
  --run-id <run_id> --input external_quality_review.json
```

### 3. Repair Pages

For each P1 finding:

1. Read the `repair_instruction` field.
2. Update the relevant page task, claim, or evidence.
3. If a page needs regeneration:
   ```bash
   python3 scripts/deck_master.py prepare-generation-handoff --run-id <run_id>
   ```
4. Re-run the relevant quality gate:
   ```bash
   python3 scripts/deck_master.py quality-gate --run-id <run_id> draft_v2
   ```

### 4. Override When Justified

If a P1 finding is a false positive or acceptable risk:

```bash
python3 scripts/deck_master.py override create \
  --run-id <run_id> \
  --finding-id <finding_id> \
  --severity P1 \
  --reason "Business justification" \
  --approver "user"
```

### 5. Re-check Readiness

```bash
python3 scripts/deck_master.py next-step --run-id <run_id>
```

Repair within the authorized scope until the affected checks pass. Export only
when requested and approved for the current version; otherwise return the
corrected artifacts and remaining findings.
