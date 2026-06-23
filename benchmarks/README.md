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

python3 scripts/deck_master.py benchmark-aggregate-report \
  --benchmark-dir benchmarks \
  --force
```

## Data Policy

- Keep raw sensitive customer material outside this directory unless it has been
  explicitly approved for local benchmark use.
- Benchmark reports store artifact paths and summaries, not copied source text.
- Generated reports are local files under `benchmarks/results/`.
- Real benchmark cases committed here must use `case_type=real_metadata`.
- Real benchmark cases must set `source_material.raw_source_policy` to
  `local_path_only` and only reference local private source paths.
- Do not commit raw source documents, customer excerpts, caches, generated
  benchmark runs, or generated benchmark reports.

## Real Metadata Cases

This repository includes three sanitized real-case metadata entries:

- `real_retail_growth`
- `real_manufacturing_geo`
- `real_healthcare_enablement`

Their raw source material is expected under a local private path such as
`~/DeckMasterPrivateBenchmarks/<case_id>/`. These paths are references only;
the referenced files are not part of the repository.
