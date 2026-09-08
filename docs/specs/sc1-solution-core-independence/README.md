> **历史规格适用范围更新（SC-1.1 superseded）**：下文保留 SC-1 历史正文。默认外部 PPT Master 后端及标准／高密度双引擎要求，已由 [SC-1.1 正式替换裁决](../sc1.1-native-deck-core/specs/00-decisions-and-supersession.md#02-正式替换旧裁决)替换为默认内置 `deck_native`，旧运行按明确兼容／迁移规则处理；并非废弃整份 SC-1。研究、公共内容、真实编译／渲染／回读、质量、数据保护与当前批准等未冲突要求继续有效。逐项工程范围见 [SC-1 验收替换映射](../sc1.1-native-deck-core/acceptance/SC1_SUPERSESSION_MAP.json)；映射不代表验收通过。

# Deck Master SC-1 开发 Spec Pack
## 独立运行与 Solution Deck 质量升级

| 项目 | 内容 |
|---|---|
| 规格版本 | SC-1 Spec v1.0，开发输入稿 |
| 编制日期 | 2026-09-07 |
| 仓库 | MainQuestAI/Deck-Master |
| 已读取远端基线 | `4199a6a8cc17ac522e074fee95bc114d4e274849`，main，包含 PR #29 |
| 本轮业务目标 | 单一 Deck Master 安装与入口，直接从原始材料形成有依据、可审查、可编辑的客户 Solution Deck，减少用户补写 |
| 交付组织 | 一个业务迭代，三个工作包，八个顺序合并的建议 PR |
| 产品发布版本 | 本包不预先指定；SC-1 不是包版本，也不是正式 1.0 已就绪声明 |
| 事实边界 | 远端文件已阅读；本地安装、调用、测试、产物及可用性需要 Codex 核验 |

## 必须先读

按顺序阅读 [范围与裁决](specs/00-scope.md)、[基线与代码复用](specs/01-baseline-and-reuse.md)、[目标架构](specs/02-architecture.md)、[PR 与任务计划](tasks/00-delivery-plan.md) 和 [Codex 开工说明](agent/START_HERE.md)。

连续阅读使用 [完整开发说明书](DEVELOPMENT_SPEC.md)；查找单项文件使用 [目录](CONTENTS.md)。

本包所有“必须 / MUST”是本轮目标约束，不是当前已具备能力。“拟新增”“目标接口”均未在本次交付中实现。
`contracts/` 中的 JSON Schema 是目标契约草案，尚未安装进仓库；`examples/` 是人工编写的合成契约样例，不能用来证明真实生成或交付效果。

## 三个工作包

| 工作包 | 要完成的业务变化 | 主规格 |
|---|---|---|
| WP-A 单产品独立性 | 用户不用自己维护配套仓库、重复 Skill 和后端路径；无历史库也可真实生成 | `03-managed-installation.md`、`08-workflow-and-decisions.md`、`10-migration.md` |
| WP-B 公共方案内容内核 | 系统承担材料理解、缺口研究、方案设计、叙事和架构表达，不把这些工作反推给用户 | `04-intake-and-research.md`、`05-solution-and-narrative.md`、`06-diagrams-and-production.md` |
| WP-C 质量修订与实证 | 专业审查形成具体返修，当前版本审批有效，真实样本证明效果而非只证明流程 | `07-quality-and-repair.md`、`11-benchmark.md` |

## 文件导航

- `specs/`：产品范围、代码复用、架构、各模块行为、契约、迁移与验收。
- `tasks/`：建议 PR 顺序、任务卡、文件所有权、依赖和逐包完成标准。
- `contracts/`：七份目标 JSON Schema；既有对象的扩展约束见 `specs/09-contracts-and-cli.md`。
- `methods/`：五份可内置到现有 Skill 的具体专业方法参考稿，不新增公开入口。
- `examples/`：七份有效契约样例与合成原始材料；全部标记为合成数据。
- `acceptance/`：可追踪验收案例（91 项，含 spec_ref 回指治理章节）、评分量规和真实 UAT 操作规程。
- `agent/`：总控、实现、评审 Agent 的执行说明。
- `sources/`：固定提交来源清单，明确源码事实、设计决策与待核验项。
- `tools/validate_spec_pack.py`：只校验本规格包，不是 Deck Master 产品测试。
- `AMENDMENTS.md`：落库后的审查修订记录；与原件差异以该文件为准。

## 最终完成定义

必须同时满足：A 的隔离安装与依赖验收、B 的真实内容生产验收、C 的人工效果对照验收，以及回归与迁移验收。不得以某个 PR 合并、Schema 样例通过、Fixture 成功或 Gate 为绿，替代整轮完成。

有真实素材或宿主工具缺失时，可以报告 `engineering_complete / outcome_pending`，不得将整轮标为完成。不要扩大实现范围，也不要用虚构数据补齐真实证据。

## 建议落库位置

将整个目录提交到 `docs/specs/sc1-solution-core-independence/`。该位置是建议的新目录，需要 Codex 核验仓库约定后落地。本次未修改 GitHub 或用户本机仓库。
