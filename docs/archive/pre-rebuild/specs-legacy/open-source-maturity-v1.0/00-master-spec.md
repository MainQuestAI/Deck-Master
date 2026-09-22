# 00 — Open Source Maturity Master Spec

## 1. 这份 Spec 解决什么问题

Deck Master 已具备可开源的产品基础，但当前仓库还缺少公开发布所需的治理文件、标准安装、首跑 demo、能力边界、设计一致性和 release 证据。本 Spec 把这些缺口拆成开发任务，目标是先拿到 M1 public Technical Preview，再推进 M2 正式开源 RC。

## 2. 成功标准

M1 成功标准：

1. 外部用户能 clone 仓库、安装 dev 依赖、跑通 fixture demo、打开 Review Desk。
2. README 首屏能说明产品价值、技术预览状态、能力边界、License 和运行路径。
3. 未配置 production backend 时，系统不会误报 ready。
4. 公开 fixture demo 有 10-12 页，且无 placeholder、本机绝对路径、客户敏感信息。
5. Review Desk 完成 M1 最小设计合规。
6. `preview-gate` 通过。

M2 成功标准：

1. M1 全部通过。
2. production 所需外部独立仓已同步开源、替换为本仓能力，或明确移出正式候选范围。
3. `rc-gate --skip-browser-smoke` 和 `rc-gate --require-browser-smoke` 通过。
4. 本地写操作有 token 或 origin 校验。
5. release tree 可独立安装、验证、回滚。
6. GitHub 社区入口、路线图、维护承诺齐备。

## 3. 关键决策

| ID | 决策 | 已定口径 |
|---|---|---|
| D0 | 发布可见性 | M1 public Technical Preview |
| D1 | License | Apache-2.0 |
| D2 | 开源范围 | 当前 Deck Master 仓库全仓开源 |
| D2.1 | 产品独立性 | M1 用 Review Desk + 公开 fixture demo 证明独立可体验 |
| D3 | UI 门槛 | M1 最小 DESIGN.md 合规，M2 全量收口 |
| D4 | 文档语言 | 外部入口英文优先，内部 agent 指引保留中文 |
| D5 | 版本真相源 | `pyproject.toml` 为包版本真相源，manifest 记录 suite/version |
| D6 | 维护承诺 | M1 Best-effort technical preview，M2 定义安全响应和 issue SLA |
| D7 | 贡献授权 | DCO，暂不引入复杂 CLA |

## 4. 开发包总览

| 任务 | 名称 | 里程碑 | 阻断 |
|---|---|---|---|
| T1 | Release Governance | M1 | P0 |
| T2 | Packaging And CI | M1 | P0 |
| T3 | Backend Truth And Preview Gate | M1 | P0 |
| T4 | Docs First Run Demo | M1 | P0 |
| T5 | Public Fixture Seed | M1 | P0 |
| T6 | Repo Hygiene And Release Tree | M1 | P0 |
| T7 | Review Desk Design Minimum | M1 | P0 |
| T8 | M2 RC Hardening | M2 | P1 |

## 5. 依赖图

```text
T1 -> T2
T1 -> T4
T2 -> T3
T3 -> T4
T4 -> T5
T1 + T2 + T3 -> T6
T4 + T5 -> T7
T1..T7 -> M1 acceptance -> T8
```

## 6. 不在本 Spec 范围

1. 不重写 Deck Master 核心编排架构。
2. 不把 Review Desk 扩展成完整编辑器。
3. 不引入云端服务、账号系统、SaaS 托管或远程协作。
4. 不清理所有历史归档文档，只处理公开入口和 release 路径会暴露的问题。

## 7. Agent 交付报告格式

每个任务包交付时必须包含：

1. 修改文件清单。
2. 实现摘要。
3. 验证命令和真实结果。
4. 未完成事项。
5. 对 M1 / M2 Go 条件的影响。
