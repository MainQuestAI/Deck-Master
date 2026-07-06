# P4 — Real Benchmark Execution Closure

## 1. 目标

用 3 个真实 benchmark case 生成真实报告，让 aggregate 进入 `report_ready`。

## 2. In Scope

- 私有 benchmark 目录准备
- real benchmark run
- benchmark report
- benchmark RC report
- aggregate report 重跑

## 3. Out Of Scope

- 新增 benchmark case 类型
- raw source 入库
- UI 大改

## 4. 允许修改路径

仓库内：

- `benchmarks/cases/`
- `benchmarks/README.md`
- `scripts/benchmark/`
- `tests/test_benchmark_case.py`
- `tests/test_benchmark_report.py`
- `tests/test_benchmark_aggregate.py`

本机私有目录：

- `~/deck-master-local-benchmarks/<case_id>/`

注意：

- `raw/`、`workspace/` 不进入 git
- 仓库中只允许更新 metadata、说明文档和最终 report 引用逻辑

## 5. 必须实现

1. 建立三个私有目录：
   - `real_retail_growth`
   - `real_manufacturing_geo`
   - `real_healthcare_enablement`
2. 每个 case 具备：
   - `context_pack.json`
   - `raw/`
   - `workspace/`
3. 每个 case 生成：
   - `benchmark_report.json`
   - `benchmark_rc_report.json`
4. 重跑 aggregate report

## 6. 测试与验证

至少验证：

1. `validate-benchmark-case` 通过
2. 每个 case 的 benchmark run 能生成 report
3. aggregate 状态从 `metadata_ready` 进入 `report_ready`
4. aggregate 至少发现 3 个 real report

## 7. 成功标准

1. real benchmark 不再停留在 metadata 层
2. Deck Master 有真实生产质量报告
3. RC gate 有真实 benchmark 证据可消费

## 8. 依赖与并发

依赖 `P1`、`P2`、`P3`。
未满足前置条件时，不启动正式执行。

## 9. Agent 交付报告

必须输出：

1. 三个 case 的执行结果
2. 每个 case 的 report 路径
3. aggregate 结果
4. 仍缺的外部依赖或资产
5. 风险与建议下一步
