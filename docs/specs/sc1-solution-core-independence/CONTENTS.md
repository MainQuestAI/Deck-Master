> **历史规格适用范围更新（SC-1.1 superseded）**：下文保留 SC-1 历史正文。默认外部 PPT Master 后端及标准／高密度双引擎要求，已由 [SC-1.1 正式替换裁决](../sc1.1-native-deck-core/specs/00-decisions-and-supersession.md#02-正式替换旧裁决)替换为默认内置 `deck_native`，旧运行按明确兼容／迁移规则处理；并非废弃整份 SC-1。研究、公共内容、真实编译／渲染／回读、质量、数据保护与当前批准等未冲突要求继续有效。逐项工程范围见 [SC-1 验收替换映射](../sc1.1-native-deck-core/acceptance/SC1_SUPERSESSION_MAP.json)；映射不代表验收通过。

# 文件目录

[完整开发说明书](DEVELOPMENT_SPEC.md)｜[入口说明](README.md)

## 产品与工程规格

- [specs/00-scope.md](specs/00-scope.md)
- [specs/01-baseline-and-reuse.md](specs/01-baseline-and-reuse.md)
- [specs/02-architecture.md](specs/02-architecture.md)
- [specs/03-managed-installation.md](specs/03-managed-installation.md)
- [specs/04-intake-and-research.md](specs/04-intake-and-research.md)
- [specs/05-solution-and-narrative.md](specs/05-solution-and-narrative.md)
- [specs/06-diagrams-and-production.md](specs/06-diagrams-and-production.md)
- [specs/07-quality-and-repair.md](specs/07-quality-and-repair.md)
- [specs/08-workflow-and-decisions.md](specs/08-workflow-and-decisions.md)
- [specs/09-contracts-and-cli.md](specs/09-contracts-and-cli.md)
- [specs/10-migration.md](specs/10-migration.md)
- [specs/11-benchmark.md](specs/11-benchmark.md)

## 交付计划与任务卡

- [tasks/00-delivery-plan.md](tasks/00-delivery-plan.md)
- [tasks/WP-A.md](tasks/WP-A.md)
- [tasks/WP-B.md](tasks/WP-B.md)
- [tasks/WP-C.md](tasks/WP-C.md)

## 既有对象契约增量

- [contracts/README.md](contracts/README.md)
- [contracts/EXTENSION_DELTAS.md](contracts/EXTENSION_DELTAS.md)

## 可内置的专业方法参考稿

- [methods/README.md](methods/README.md)
- [methods/brief-and-research.md](methods/brief-and-research.md)
- [methods/solution-design.md](methods/solution-design.md)
- [methods/storyline-and-pages.md](methods/storyline-and-pages.md)
- [methods/architecture-views.md](methods/architecture-views.md)
- [methods/semantic-review-and-repair.md](methods/semantic-review-and-repair.md)

## 验收矩阵与真实效果规程

- [acceptance/MATRIX.md](acceptance/MATRIX.md)
- [acceptance/rubric.md](acceptance/rubric.md)
- [acceptance/UAT_PROTOCOL.md](acceptance/UAT_PROTOCOL.md)

## Agent 执行与评审

- [agent/DEVIATION_LOG_TEMPLATE.md](agent/DEVIATION_LOG_TEMPLATE.md)
- [agent/REVIEW_PR.md](agent/REVIEW_PR.md)
- [agent/START_HERE.md](agent/START_HERE.md)

## 来源与本地核验边界

- [sources/README.md](sources/README.md)
- [sources/LOCAL_VERIFICATION_REQUIRED.md](sources/LOCAL_VERIFICATION_REQUIRED.md)

## 目标 JSON Schema

- [contracts/capability-execution-plan.v1.schema.json](contracts/capability-execution-plan.v1.schema.json)
- [contracts/context-pack.v2.schema.json](contracts/context-pack.v2.schema.json)
- [contracts/diagram-view.v1.schema.json](contracts/diagram-view.v1.schema.json)
- [contracts/external-quality-review.v2.schema.json](contracts/external-quality-review.v2.schema.json)
- [contracts/narrative-plan.v3.schema.json](contracts/narrative-plan.v3.schema.json)
- [contracts/research-task.v1.schema.json](contracts/research-task.v1.schema.json)
- [contracts/solution-model.v1.schema.json](contracts/solution-model.v1.schema.json)

## 合成协议样例

- [examples/capability_execution_plan.json](examples/capability_execution_plan.json)
- [examples/context_pack.json](examples/context_pack.json)
- [examples/diagram_view.json](examples/diagram_view.json)
- [examples/external_quality_review.json](examples/external_quality_review.json)
- [examples/narrative_plan.json](examples/narrative_plan.json)
- [examples/request.json](examples/request.json)
- [examples/research_task.json](examples/research_task.json)
- [examples/solution_model.json](examples/solution_model.json)

## 工具与计划验收JSON

- [tools/validate_spec_pack.py](tools/validate_spec_pack.py)

- [91 项计划验收 cases.json](acceptance/cases.json)
- [规格包自检结果（不是产品测试）](SPEC_SELF_CHECK.json)
- [落库修订记录](AMENDMENTS.md)
