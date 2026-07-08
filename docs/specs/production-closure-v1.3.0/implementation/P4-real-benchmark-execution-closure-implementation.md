# P4 细化实现稿 — Real Benchmark Execution Closure

日期：2026-07-03
状态：Completed / Current Evidence Synced
对应任务包：[`../tasks/P4-real-benchmark-execution-closure.md`](../tasks/P4-real-benchmark-execution-closure.md)

## 1. 目标

把 benchmark 从“只有 metadata”推进到“有真实运行报告”。当前仓状态已经完成本轮最小闭环：

1. 3 个 real case 都已有可用于运行的本地素材引用
2. 3 个 real case 都已生成 `benchmark_report.json`
3. 3 个 real case 都已生成 `benchmark_rc_report.json`
4. aggregate 状态已从 `metadata_ready` 进入 `report_ready`

## 2. 当前事实

### 2.1 仓里已经有 3 个 sanitized real case

当前已提交的 real metadata case：

1. `real_retail_growth`
2. `real_manufacturing_geo`
3. `real_healthcare_enablement`

它们的 metadata 已经写在：

```text
benchmarks/cases/<case_id>/benchmark_case.json
```

并且都遵守：

1. `case_type=real_metadata`
2. `raw_source_policy=local_path_only`
3. raw source 只引用 `~/deck-master-local-benchmarks/<case_id>/...`

### 2.2 当前 aggregate 已进入 report 层

当前仓里的 aggregate 报告是：

```text
benchmarks/results/aggregate/benchmark_aggregate_report.json
```

当前状态：

1. `status=report_ready`
2. `real_metadata=3`
3. `benchmark_report=3`
4. `benchmark_rc_report=3`
5. `complete_real_case_pairs=3`

这说明 P4 的主线目标已经完成：metadata、真实运行报告、RC benchmark report 和 aggregate 已经闭环。

当前完整 report pair：

1. `real_healthcare_enablement/bench-real_healthcare_enablement-20260703043930`
2. `real_manufacturing_geo/bench-real_manufacturing_geo-20260703043930`
3. `real_retail_growth/bench-real_retail_growth-20260703043652`

### 2.3 benchmark 命令链已经具备

当前仓里已经有以下命令：

1. `validate-benchmark-case`
2. `benchmark-run`
3. `benchmark-report`
4. `benchmark-rc-report`
5. `benchmark-aggregate-report`

这些命令已经用于产出当前证据链。后续 P4 相关工作应聚焦证据刷新、敏感素材隔离和回归保护。

### 2.4 P4 闭环不等于每个 real run 已最终成片

当前 P4 已证明：

1. 3 个 real case 都有真实 `benchmark_report.json`
2. 3 个 real case 都有真实 `benchmark_rc_report.json`
3. aggregate 已为 `report_ready`

但当前 benchmark 报告仍显示：

1. `readiness.final_ready=false`
2. `export_ready=false`
3. `quality_blocked=true`

因此，P4 当前闭环证明的是“真实 benchmark 证据链已经形成”，并不直接等于每个 case 的最终客户交付产物已经 ready。

## 3. 本轮实现范围与当前边界

### 3.1 仓库内

允许修改：

1. `benchmarks/README.md`
2. `scripts/benchmark/`
3. `tests/test_benchmark_case.py`
4. `tests/test_benchmark_report.py`
5. `tests/test_benchmark_aggregate.py`
6. 必要的 benchmark 说明文档

### 3.2 本机私有目录

当前已按以下结构保留本地私有素材引用：

```text
~/deck-master-local-benchmarks/real_retail_growth/
~/deck-master-local-benchmarks/real_manufacturing_geo/
~/deck-master-local-benchmarks/real_healthcare_enablement/
```

每个 case 的最低要求仍为：

1. `context_pack.json`
2. `raw/`
3. `workspace/`

### 3.3 本轮不做

1. 不新增第 4 个 real case
2. 不把 raw source 放进 git
3. 不改 benchmark case 类型
4. 不对 benchmark UI 做大改

## 4. 设计方案

## 4.1 私有 benchmark 资产准备清单

每个 case 的最低准备要求已经作为后续刷新前检查项保留：

1. `context_pack.json` 可被 Deck Master 读入
2. `raw/` 内存在真实原始材料
3. `workspace/` 是可写目录
4. metadata 里引用的本机路径都真实存在

后续重新刷新 P4 证据前，建议先做统一检查：

1. 路径存在
2. 文件可读
3. 不含需入库的敏感原文
4. case id 和私有目录一一对应

## 4.2 每个 case 的执行顺序

当前已按以下顺序生成证据，后续刷新继续沿用：

1. `validate-benchmark-case`
2. `benchmark-run`
3. `benchmark-report`
4. `benchmark-rc-report`

标准产物路径：

```text
benchmarks/results/<case_id>/<run_id>/benchmark_report.json
benchmarks/results/<case_id>/<run_id>/benchmark_rc_report.json
```

P4 当前已经满足每个 case 至少产出这两个文件。

## 4.3 aggregate 收口规则

aggregate 重跑前，最低前置条件仍是：

1. 3 个 real case 都有 `benchmark_report.json`
2. 3 个 real case 都有 `benchmark_rc_report.json`

当前 aggregate 已反映：

1. `report_counts.total >= 6`
2. `benchmark_report >= 3`
3. `benchmark_rc_report >= 3`
4. `status=report_ready`

## 4.4 结果治理

P4 只把以下内容留在仓库可见层：

1. metadata
2. report 路径
3. aggregate 结果
4. 运行说明

raw source、客户原文、缓存、运行中间产物继续只保留在私有目录。

## 5. 测试设计

### 5.1 仓内回归

后续改动至少执行：

```bash
python3 -m unittest tests.test_benchmark_case tests.test_benchmark_report tests.test_benchmark_aggregate
```

### 5.2 三个 real case 验证

后续刷新 real case 证据时至少执行：

```bash
python3 scripts/deck_master.py validate-benchmark-case --case benchmarks/cases/real_retail_growth/benchmark_case.json --benchmark-dir benchmarks
python3 scripts/deck_master.py validate-benchmark-case --case benchmarks/cases/real_manufacturing_geo/benchmark_case.json --benchmark-dir benchmarks
python3 scripts/deck_master.py validate-benchmark-case --case benchmarks/cases/real_healthcare_enablement/benchmark_case.json --benchmark-dir benchmarks
```

### 5.3 aggregate 验证

后续刷新 aggregate 时至少执行：

```bash
python3 scripts/deck_master.py benchmark-aggregate-report --benchmark-dir benchmarks --force
```

当前验收点已满足：

1. aggregate 从 `metadata_ready` 进入 `report_ready`
2. `reports[]` 不再为空
3. 3 个 real case 都被计入统计
4. run 级最终成片状态仍需后续 render/writeback 证据单列判断

## 6. 风险

### 风险 1：私有资产后续漂移

影响：

1. case metadata 可以通过
2. 正式 benchmark run 仍可能中途失败

处理方式：

1. P4 先做素材盘点
2. 未满足最小目录要求的 case 不进入正式 run

### 风险 2：敏感原文误进入仓库

影响：

1. benchmark 闭环完成的同时带来数据治理风险

处理方式：

1. 仓库只放 metadata 和 report
2. raw source 坚持本地私有目录
3. 报告中只写路径和摘要，不复制原文

### 风险 3：benchmark 结果缺少后续人工检查证据

影响：

1. `benchmark_rc_report.json` 可能无法稳定反映真实 readiness

处理方式：

1. 每个 case 的运行记录必须包含关键 checkpoint
2. `benchmark-report` 与 `benchmark-rc-report` 都要落地

## 7. 完成定义

按当前仓状态，P4 已满足以下完成条件：

1. 3 个 real case 的私有目录准备完成
2. 3 个 real case 都生成了 `benchmark_report.json`
3. 3 个 real case 都生成了 `benchmark_rc_report.json`
4. `benchmark_aggregate_report.json` 进入 `report_ready`
5. 仓库中没有引入 raw source 或客户敏感原文
