# D1-D15 硬决策追踪表

日期：2026-06-24

## 1. 用途

本文件补充 `00-master-spec.md` 中的 D1-D15 硬决策追踪，确保每个关键决策都能落到任务、验收和风险控制上。

## 2. 决策追踪

| 决策 | 内容摘要 | 主任务 | 关键验收 | 风险控制 |
|---|---|---|---|---|
| D1 | 保留现有 Skill 名称，不新增独立访谈 Skill | A1, B1, C2, C3 | Skill manifest 和 Skill docs conformance 通过 | 防止通过改名掩盖行为薄弱问题 |
| D2 | 生产阶段固定为 9 个 | A1, A2, C1 | 9 个 Stage Contract 全部可加载，Review Desk 展示 9 阶段 | 防止各入口各自定义阶段 |
| D3 | Stage Contract 是行为真源 | A1, A2, A5 | route / next-step / run-state / workflow status 一致 | 防止 CLI、Skill 文档和 UI 漂移 |
| D4 | `skills/manifest.json` 是 Skill identity 真源 | A1, C2, C3 | Manifest provenance report 通过 | 防止 installer、release tree、runtime 维护重复列表 |
| D5 | Artifact 和 Approval 是事实，Workflow State 是派生快照 | A2, A4 | 修改 artifact 后 workflow state 可重建 | 防止把缓存状态当成事实 |
| D6 | Handoff 使用 append-only 记录 | A3, A5 | handoff prepare / accept / reject 幂等，历史可追溯 | 防止下游无法复核上游交付 |
| D7 | Approval 绑定 Transition 和 Fingerprint | A4, B5, C5 | 上游 fingerprint 变化后旧 approval stale | 防止旧确认错误复用 |
| D8 | 高影响 Transition 必须确认 | A4, A5, B5 | brief、planner、sourcing、export 关键跳转均能阻断 | 防止方向、来源、成本和最终导出被自动跨越 |
| D9 | 机械门禁自动运行 | A5, B5 | producer -> builder、builder -> quality、quality -> review 可自动推进 | 减少无价值确认，保留 evidence |
| D10 | 允许显式预授权，但限制模糊授权 | A4, B5 | preauthorization 有 actor、scope、expiry、cost ceiling、fingerprint boundary | 防止一句“继续做”变成长期无限授权 |
| D11 | Sourcing、Producer、Builder 边界固定 | B2, B3, B4 | sourcing plan、page package、build manifest 各自通过 schema 和负向测试 | 防止来源判断、内容生产、构建职责混写 |
| D12 | Page Package 是 Producer 与 Builder 的正式边界 | B3, B4 | Builder 默认读取 `deck_page_package.v1` | 防止旧 preview manifest 成为正式生产输入 |
| D13 | Quality 与 Review 分离 | A1, A2, C1 | quality gate 和 review desk 状态可区分 | 防止机器质量检查替代人工审查 |
| D14 | Review Desk 只展示派生业务状态 | A2, C1 | 前端不自行推导 Stage，API projection 测试通过 | 防止 UI 和 runtime 状态分裂 |
| D15 | 兼容优先，不删除 `ppt-*` | C2, C3, C4 | 旧入口可映射到公开 Stage，legacy bootstrap 通过 | 防止历史入口和外部工具链断裂 |

## 3. 必须补齐的测试映射

现有 `acceptance/requirements-traceability.csv` 已有 `SO-001` 到 `SO-020`。正式开工前建议补一版机器可读追踪表，增加以下列：

- `decision_id`
- `requirement_id`
- `task`
- `test`
- `negative_test`
- `evidence`
- `release_gate`

本目录已补充：

`acceptance/decision-requirements-traceability.csv`

建议补充的负向测试：

| 决策 | 负向测试 |
|---|---|
| D3 | 人为制造 route / run-state 不一致，必须失败 |
| D6 | 重复 prepare handoff，同 fingerprint 必须复用或幂等 |
| D7 | 修改上游 artifact 后，旧 approval 必须 stale |
| D8 | 无审批执行 `review -> client export` 必须阻断 |
| D10 | 自然语言“继续做”不得生成长期 preauthorization |
| D11 | Producer 尝试写 build-only 字段，必须被 schema 或 validator 拦截 |
| D12 | Builder 直接读取 legacy preview manifest，必须走 adapter 或失败 |
| D14 | 前端自行推导 stage 的测试 fixture 必须失败 |
| D15 | 旧 `ppt-deck-pro-max` 入口调用后必须回写 canonical stage 信息 |

## 4. 开发报告要求

每个任务交付报告必须回答：

1. 本任务关闭了哪些 `D*` 决策。
2. 本任务新增或修改了哪些 schema。
3. 本任务新增了哪些正向测试和负向测试。
4. 本任务是否影响旧 run、旧 `ppt-*` 入口、release tree 或 Review Desk。
5. 如有偏离，deviation log 是否已记录。
