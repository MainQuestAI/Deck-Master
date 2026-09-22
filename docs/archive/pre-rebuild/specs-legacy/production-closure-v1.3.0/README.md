# Deck Master v1.3.0 Production Closure 开发包

状态：Current Implementation Sync  
日期：2026-07-03  
主 Spec：[`../deck-master-v1.3.0-production-closure-spec.md`](../deck-master-v1.3.0-production-closure-spec.md)

## 1. 本包定位

本包用于把 v1.3.0 Production Closure Spec 拆成可执行开发包，供 Codex、Claude Code 和后续 ChatGPT 协作时直接引用。

建议先读：[`00-development-package.md`](./00-development-package.md)。

本包原本重点解决四类问题，当前仓状态已经完成主线闭环：

1. `ppt-master` 已成为可认证的 production backend
2. Deck Master 已正式绑定和锁定外部依赖
3. `ppt-deck-pro-max` bridge 已进入 release truth
4. real benchmark 与 RC gate 已形成真实放行闭环

后续使用本包时，应把它当作 v1.3.0 Production Closure 的实现证据索引，而非继续补 P2/P3/P4/P5 功能的待办清单。

## 2. 交付结构

```text
production-closure-v1.3.0/
  00-development-package.md
  README.md
  implementation/
    development-plan.md
    P1-ppt-master-backend-certification-implementation.md
    P2-deck-master-backend-binding-and-lock-implementation.md
    P3-ppt-deck-pro-max-bridge-lock-and-smoke-implementation.md
    P4-real-benchmark-execution-closure-implementation.md
    P5-rc-gate-dogfood-release-closure-implementation.md
  tasks/
    P1-ppt-master-backend-certification.md
    P2-deck-master-backend-binding-and-lock.md
    P3-ppt-deck-pro-max-bridge-lock-and-smoke.md
    P4-real-benchmark-execution-closure.md
    P5-rc-gate-dogfood-release-closure.md
```

## 3. 开发顺序

原执行顺序如下：

1. `P1` `ppt-master` backend certification
2. `P2` Deck Master backend bind + external dependency lock
3. `P3` `ppt-deck-pro-max` bridge SHA 固定 + cross-repo smoke
4. `P4` real benchmark execution closure
5. `P5` RC gate / dogfood / release closure

当前状态：

1. `P2` 已让外部 backend 真相进入 capability lock 和状态输出；
2. `P3` 已让 bridge 固定 SHA 进入 release truth；
3. `P4` 已跑出 3 个 real benchmark report pair，aggregate 已为 `report_ready`；
4. `P5` 已让 `external_dependency_closure` 进入 RC gate，且 required failures 为 0。

## 4. 开发包索引

| 任务 | 名称 | 主对象 | 核心结果 |
|---|---|---|---|
| P1 | PPT Master Backend Certification | `hugohe3/ppt-master` | backend manifest、smoke、Deck Master 兼容文档 |
| P2 | Deck Master Backend Binding And Lock | Deck Master | `backend bind`、bindings registry、`external_dependencies[]`、状态真相扩展 |
| P3 | PPT Deck Pro Max Bridge Lock And Smoke | `PPT-Deck-Pro-Max` + Deck Master | 固定 SHA、cross-repo smoke、bridge 进入 capability lock |
| P4 | Real Benchmark Execution Closure | Deck Master + 私有 benchmark 目录 | 3 个 real report、aggregate=`report_ready` |
| P5 | RC Gate Dogfood Release Closure | Deck Master | external dependency closure、RC 全绿、clean install/dogfood |

当前证据口径：

1. `benchmarks/results/aggregate/benchmark_aggregate_report.json`：`status=report_ready`
2. `rc_reports/rc_gate_report.json`：`status=pass`、`required_failures=0`
3. `suite-status`：`production_backend_ready=true`、`client_delivery_ready=true`
4. `setup-status`：可透传 suite/client delivery readiness，但当前 active workspace repair 仍需单独判断
5. 当前 closure 证明的是系统级 readiness；每个真实 run 仍需等待外部 render/writeback 回写后，才能进入最终客户成片判断

## 5. 使用方式

建议按以下顺序阅读：

1. `00-development-package.md`
2. `implementation/development-plan.md`
3. 对应细化实现稿 `implementation/P*.md`
4. 对应任务包 `tasks/P*.md`
5. 主 Spec

每个任务包都应输出：

1. 修改文件
2. schema / 状态变化
3. 测试命令与真实结果
4. 跨仓库依赖
5. 未完成项
6. 风险与建议评审重点

后续重点应从“继续补功能”转成：

1. 固化 evidence pack 刷新方式；
2. 收敛 release note / RC report 的用户可读口径；
3. 明确 workspace repair、browser smoke、Review Desk 安全展示是否进入发布门禁；
4. 保持 raw benchmark source 不入 git。
5. 明确 run 级最终成片 readiness 与 suite/client delivery readiness 的边界。
