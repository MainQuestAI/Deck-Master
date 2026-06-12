# Real Case Benchmark Template

Use this folder as a starting point for real workflow validation.

1. Copy this folder to `benchmarks/cases/<your_case_id>/`.
2. Update `benchmark_case.json` with the real case name, industry, workspace,
   baseline hours, and target pages.
3. Place a matching `context_pack.json` in the copied folder, or point
   `inputs.context_pack` to an approved local path.
4. Run `benchmark-run` for a semi-automated local pass, or run your normal Deck
   Master workflow and then run `benchmark-report` against the existing run.
5. Record manual checkpoints during review:

```bash
python3 scripts/deck_master.py benchmark-checkpoint \
  --run-dir benchmark_runs/<run_id> \
  --checkpoint human_review_started
```

6. Import narrative advice, external quality review, generation results, and
   render results when those companion steps are available.

Keep sensitive source material in the approved project workspace. Benchmark
reports should reference artifact paths and summarize status only.

