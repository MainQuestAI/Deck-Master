# Deck Master Benchmarks

This directory stores local benchmark cases and generated benchmark reports.

Deck Master benchmark runs are designed for local workflow validation. They do
not call external LLMs, do not upload customer data, and do not claim v1.0.0
10x readiness by themselves.

## Commands

```bash
python3 scripts/deck_master.py validate-benchmark-case \
  --case benchmarks/cases/retail_fixture/benchmark_case.json

python3 scripts/deck_master.py benchmark-run \
  --case benchmarks/cases/retail_fixture/benchmark_case.json \
  --benchmark-dir benchmarks \
  --mode semi-auto

python3 scripts/deck_master.py benchmark-report \
  --case benchmarks/cases/retail_fixture/benchmark_case.json \
  --run-dir benchmark_runs/<run_id>

python3 scripts/deck_master.py benchmark-checkpoint \
  --run-dir benchmark_runs/<run_id> \
  --checkpoint human_review_started

python3 scripts/deck_master.py benchmark-list \
  --benchmark-dir benchmarks
```

## Data Policy

- Keep raw sensitive customer material outside this directory unless it has been
  explicitly approved for local benchmark use.
- Benchmark reports store artifact paths and summaries, not copied source text.
- Generated reports are local files under `benchmarks/results/`.
