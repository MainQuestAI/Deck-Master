# Baseline & Gap Register

## 1. 已确认基线

| 项目 | 当前状态 |
|---|---|
| Main | `4605213f1ee3ba937e4658855582c7517b5af027` |
| PR #8 | 已合并，v1 Skill Suite Runtime |
| Review Desk | v0.3 已合入 main |
| Skill manifest | `1.0.0`，14 个公开 `deck-*` + 4 个兼容 `ppt-*` |
| Route Resolver | Runtime stage / input type → public skill |
| Run State | 输出 `recommended_skill` / `skill_stage` / `skill_route` |
| Autopilot | 可直接调用 brief、plan、generation、quality、build、export 命令 |
| Approval | Review Desk 存在 approval task，但不是 Stage Transition Contract |
| Builder | Production Backend Gate 已存在；contract-smoke 输出被标记 non-client-deliverable |
| Release | self-contained tree、stage/verify/activate/rollback 已存在 |

## 2. 问题注册表

| ID | 问题 | 影响 | 本轮处理 |
|---|---|---|---|
| G-01 | Skill 行为只是薄文档 | Agent 容易把命令跑完当成完成 | Stage Contract + Skill Doc Contract |
| G-02 | Manifest、Route、Installer metadata 重复 | 漂移和兼容风险 | 单一 Manifest 真源 |
| G-03 | Stage 完成由文件存在性推断 | 无法表达确认、过期和部分完成 | Workflow State Resolver |
| G-04 | 无跨 Stage Handoff | 下游无法验证上游交付 | Handoff Runtime |
| G-05 | Approval 未绑定 Transition / Fingerprint | 旧确认可能错误复用 | Approval Runtime |
| G-06 | Autopilot 直接跨高影响阶段 | 方向、成本、来源和导出可被绕过 | Autopilot v2 Policy |
| G-07 | 访谈机制散落且不阻断 | 关键业务信息不足 | Forcing Questions + Decision Log |
| G-08 | Sourcing / Producer / Builder 边界模糊 | 内容与构建责任混写 | 三段 Artifact Contract |
| G-09 | Builder 正式输入仍是 Preview | 内部字段和旧结构易泄漏 | Page Package + Build Manifest v2 |
| G-10 | UI 看不到 Stage Handoff | 用户不知道为什么不能继续 | Skill OS Stage View |
| G-11 | 旧 Run 没有 Handoff / Approval | 升级后状态不确定 | Legacy Bootstrap |
| G-12 | 外部完整 Skill Package 识别与采用不统一 | 可能覆盖或绕开高价值能力 | Generic external package contract |

## 3. 不应重复开发的能力

本轮不得重新实现以下已存在能力：

- Setup / Suite 安装基础。
- Production Builder Backend Gate。
- Generation Result v2 的 run/session/hash 绑定。
- Artifact Validator 基础。
- Final Readiness 基础。
- Review Desk 页面级审查。
- Release staging / verification / rollback。

本轮只在必要处接入 Workflow Contract。

## 4. 需要 Codex 开工前核验的本地事实

- 当前 main 的实际全量测试数和结果。
- 本机 `~/.deck-master/current` 是否指向 `4605213f1ee3ba937e4658855582c7517b5af027`。
- Codex / Claude Code skill links 状态。
- 完整 PPT Master / PPT Library / PPT Deck Pro Max 的安装路径和版本。
- 当前本地真实 Run 中是否存在可用于 Legacy Bootstrap 的代表样本。
- Review Desk v0.3 的截图基线是否仍可重放。

这些事实不得在开发报告中凭推测填写。
