# Deck Master v1.1 Skill OS Runtime 本地接入说明

日期：2026-06-24

## 1. 接入结论

本目录已吸收 `/Users/dingcheng/Downloads/deck-master-skill-os-runtime-spec-pack.zip` 返回的完整 Spec Pack，作为 Deck Master v1.1 Skill OS Runtime 的候选实施基线。

当前建议：

- 保留原包文件结构，便于和 `package-manifest.json` 追溯。
- 本地补充文件只记录接入判断、验收结果和硬决策追踪。
- 后续正式开发从 `tasks/A0-baseline-version-freeze.md` 开始。
- A0 完成前不把本目录内容视为已发布规范。

## 2. 本地吸收路径

原始包：

`/Users/dingcheng/Downloads/deck-master-skill-os-runtime-spec-pack.zip`

仓库接入目录：

`docs/specs/skill-os-runtime-v1.1/`

核心入口：

- `README.md`
- `00-master-spec.md`
- `iteration-plan.json`
- `stacks/`
- `tasks/`
- `schemas/`
- `examples/`
- `acceptance/`
- `LOCAL_ADOPTION.md`
- `acceptance/decision-traceability.md`

## 3. 本地验收记录

已完成的只读验收：

| 检查项 | 结果 |
|---|---|
| ZIP 文件结构 | 57 个文件 |
| JSON 可解析性 | 19 个 JSON 全部可解析 |
| `package-manifest.json` 文件数 | 56 个受管文件 |
| manifest hash | 全部匹配 |
| 基线 SHA | 与当前本地 `HEAD` 和 `origin/main` 一致 |
| 禁用句式扫描 | 未命中 |
| 包内 validation report | `errors: []` |

基线 SHA：

`4605213f1ee3ba937e4658855582c7517b5af027`

本地限制：

- 当前 Python 环境没有现成 `jsonschema` 依赖。
- 本轮未独立二次执行完整 JSON Schema validation。
- Schema validation 结论以包内 `validation-report.json` 为准，本地只完成了解析、hash、结构和字段级抽查。

## 4. 与前置规划文档的关系

前置规划文档：

`docs/planning/2026-06-24-deck-master-skill-os-planning.md`

关系说明：

- 前置规划文档保留为问题诊断和方向判断。
- 本目录作为 v1.1 Runtime 候选实施基线。
- 发生冲突时，正式开发应优先看本目录的 `00-master-spec.md`、`iteration-plan.json` 和 `tasks/`。
- 如需偏离本目录，先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md` 或后续实际采用的 deviation log。

## 5. 当前仓库状态提醒

接入时工作区已有未提交文档改动：

- `docs/specs/deck-master-v1.0-skill-suite-interaction-spec.md`
- `docs/planning/`

这些文件来自本轮 Deck Master Skill OS 规划讨论。后续提交时建议把它们和本目录一起作为“文档吸收与规划基线”提交。

## 6. 开工顺序

建议严格按以下顺序推进：

1. A0：冻结基线、建立 deviation log、确认版本口径。
2. A1：建立 canonical manifest 和 stage contract registry。
3. A2：实现 workflow state resolver。
4. A3：实现 handoff runtime。
5. A4：实现 approval / preauthorization runtime。
6. A5：统一 CLI workflow、route、next-step、run-state。
7. B1-B5：补强访谈、sourcing、producer、builder、autopilot。
8. C1-C5：Review Desk、兼容迁移、安装发布、dogfood 验收。

## 7. 非绕行规则

以下规则建议作为 v1.1 开发红线：

- A1 完成前，不新增独立 route / next-step 真源。
- A3 完成前，不让下游阶段直接消费上游产物。
- A4 完成前，不改造 Autopilot 跨越高影响阶段。
- B3 完成前，不让 Builder 把 `page_package.v1` 当正式输入。
- B4 完成前，不允许 Builder 读取 `internal_only` 字段进入客户文件。
- C4 完成前，不宣称 v1.1 ready。
- `review -> client export` 永远需要显式确认。

## 8. 建议补充给 ChatGPT 的问题

如果继续和 ChatGPT 讨论 Spec，建议聚焦以下问题：

1. `D1-D15` 的硬决策是否全部可接受。
2. `deck-sourcing / deck-producer / deck-builder` 的边界是否足够清楚。
3. `page_package.v1` 的客户可见字段是否覆盖真实 solution deck 生产需要。
4. `approval + fingerprint` 的失效策略是否足够严格。
5. Autopilot 的 `interactive / preauthorized / quick / repair / review-only` 五种模式是否足够。
6. Review Desk 的最小可见状态是否能让非技术用户理解当前阻断点。
7. 旧 `ppt-*` 入口映射到公开 Stage 的兼容策略是否会造成误导。
