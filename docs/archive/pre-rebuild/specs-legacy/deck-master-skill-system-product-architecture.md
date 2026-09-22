# Deck Master Skill System Product Architecture

日期：2026-06-17
状态：产品架构定义稿，供下一轮 spec / 评审使用。
适用范围：Deck Master 作为独立开源产品时的 Skill 体系、用户入口、管理边界和安装关系。

## Summary

Deck Master 应定义为 **完整可交付的 Solution Deck 产品系统 + Skill Suite**。

Deck Master 的产品目标是让用户从客户资料出发，完成一套可审查、可生产、可渲染、可交付、可沉淀的专业方案 Deck。它不能只停留在“编排外部工具”的位置，也不能把关键产出能力长期留在产品之外。

因此，Deck Master 需要直接内化 PPT Master、PPT Library、PPT Deck Pro Max、PPT Quality Gate 等既有开源项目或本地资产，把它们重建、引用、改造为 Deck Master 的产品能力。它们可以保留独立使用方式，但在 Deck Master 产品定义中应被视为内置能力栈。

Deck Master 的 Skill 体系应分三层：

1. **Deck Master Core Skills**：Deck Master 自己拥有的主链路入口。
2. **Deck Master Product Capability Skills**：被 Deck Master 内化的生产、检索、质检、渲染能力。
3. **Reference Packs / Assets**：Deck Master 使用的页型、视觉系统、模板、标准和 benchmark 资产。

## Design Principles

### 1. 按用户任务入口拆 Skill

Skill 不应按 CLI 命令或代码模块拆分。用户说出口的任务，才是 Skill 的拆分边界。

合理入口：

- “帮我从客户资料做一套方案 Deck。”
- “帮我规划这套 Deck 的主叙事和页面结构。”
- “帮我审一下这份 Deck 能不能交付。”
- “帮我从历史 PPT 里找类似页面。”
- “帮我把已有 brief 生产成高质量 PPT/HTML。”

不适合成为独立 Skill 的入口：

- `build-brief`
- `build-claim-map`
- `decide-sourcing`
- `import-generation-result`
- `summarize-run-metrics`

这些是 Deck Master 内部步骤，应由 Core Skill 调用。

### 2. Deck Master 必须作为完整产品成立

Deck Master 的开源项目应能独立安装、独立 setup、独立完成一条从材料到可交付产物的主链路。PPT Master、PPT Library、PPT Deck Pro Max、PPT Quality Gate 必须进入 Deck Master 的内置能力栈。

Deck Master 必须覆盖：

- Setup / workspace / run state
- context intake
- brief / claim / narrative planning
- page tasks
- historical asset retrieval
- source decision
- deck production
- default build / render
- quality gate
- Review Cockpit
- export queue
- feedback / metrics / benchmark

硬决策：

- PPT Master 进入 Deck Master 默认 build / render 引擎；完整 build 默认通过 PPT Master 路径产出。
- PPT Library 进入 Deck Master asset intelligence；作为历史页检索、索引健康、候选页、使用反馈的内置能力。
- PPT Deck Pro Max 进入 Deck Master production intelligence；作为主叙事、逐页稿、视觉系统和生成任务的内置生产能力。
- PPT Quality Gate 进入 Deck Master quality governance；作为 Draft / Render / Delivery Gate 的独立入口和内置审查能力。

实现上可以复用、迁移或重建这些开源项目的代码；产品表达上它们属于 Deck Master 的能力组成。

### 3. 内置能力的产物必须回写 run

只要内置能力在 active Deck Master run 内被使用，产物就必须通过 Deck Master import / state update 进入 run。

Deck Master run 是唯一交付状态源。单独 PPTX、单独 HTML、单独 quality report、单独历史页选择结果只能作为 evidence 或 input，不能直接替代 run state。

### 4. Setup 是 Agent 行为，不能退化成用户命令清单

用户点名 Deck Master 后，Agent 应该：

1. 检查 setup status 和 suite status。
2. 用自然语言说明缺什么。
3. 确认 workspace。
4. 代执行 setup / suite repair / migration。
5. 再次验证 readiness。

Agent 不应只把 next command 原样抛给用户。

## Proposed Skill Taxonomy

### Layer 1: Deck Master Core Skills

这些 Skill 属于 Deck Master 产品本体，应随 Deck Master release 一起发布。

| Skill | 定位 | 用户入口 | 主要职责 |
|---|---|---|---|
| `deck-master` | 顶层编排器 | “用 Deck Master 做一套方案 / 继续一个 run / 看现在卡在哪里” | Setup 引导、workspace 绑定、run state、next step、suite readiness、Review Cockpit、handoff / handback 路由 |
| `deck-planner` | 方案规划入口 | “帮我规划这套 Deck / 从材料整理主叙事 / 生成页面结构” | context intake、brief、claim map、judgment、narrative plan、page tasks、sourcing plan |
| `deck-review` | 审查与交付入口 | “帮我审一下这套 Deck / 看能不能交付 / 输出修改清单” | quality gates、review cockpit、finding summary、delivery readiness、export queue、repair loop |
| `deck-learning` | 沉淀与复利入口 | “把这次经验沉淀下来 / 记录反馈 / 形成 benchmark” | feedback queue、run metrics、benchmark、workspace learning pack、asset reuse signals |

#### `deck-master`

最小职责：

- First-run setup ceremony。
- 判断当前任务需要哪个 Core Skill 或 Product Capability Skill。
- 确保所有真实 production run 进入 Deck Master run state。
- 告诉用户下一步，不直接跳到外部工具完成交付。

它是 suite 的 router 和 runtime owner，不承担所有内容生产细节。

#### `deck-planner`

最小职责：

- 从客户材料构建方案意图。
- 生成可审查的主叙事、章节结构和页面任务。
- 明确每页需要哪些证据、历史资产或新生成内容。

它解决“这套 Deck 应该怎么讲”。

#### `deck-review`

最小职责：

- 独立读取 Deck Master run。
- 输出页面级问题、交付阻断、修复建议。
- 统一查看 internal gates、quality findings、review cockpit decisions 和 export queue。

它解决“这套 Deck 能不能交付”。

#### `deck-learning`

最小职责：

- 记录项目反馈、页面使用结果、成交或未成交原因。
- 生成 run metrics 和 benchmark evidence。
- 更新 workspace learning pack。

它解决“这次交付能否转化成下一次更好的默认经验”。

`deck-learning` 可以后置实现，但产品架构中应保留位置，避免反馈能力混入主控入口。

### Layer 2: Deck Master Product Capability Skills

这些 Skill 属于 Deck Master 产品能力。它们可以保留独立安装和独立使用方式，但在安装 Deck Master 时必须作为内置能力进入 release tree、setup、suite status 和用户路由。

| Skill | Deck Master 内化定位 | 独立使用场景 | 在 run 内使用时的规则 |
|---|---|---|---|
| `ppt-master` | 默认 build / render 引擎 | 生成 SVG/PPTX/PDF/HTML | render result 必须导入 preview / export state |
| `ppt-library` | asset intelligence | 搜历史页、建库、查索引、看候选 | selection 必须进入 sourcing state，feedback 默认写 run-local queue |
| `ppt-deck-pro-max` | production intelligence | 从 brief 生产高质量 PPT/HTML | generation result 必须携带 run_id + session_id 并导回 generation session |
| `ppt-quality-gate` | quality governance | 审 PPT/HTML/PDF 是否能交付 | findings 必须进入 Deck Master quality report |

这些能力是 Deck Master 达成产品目标所需的内置能力栈。实现可以采用 fork、wrapper、subtree、vendored package、CLI bridge 或重建模块；产品定义统一归入 Deck Master。

### Layer 3: Reference Packs / Assets

这些资产应作为 package、workspace resource 或 reference pack 管理，不急着做成 Skill。

| Asset | 用途 |
|---|---|
| `ppt-structure-assets` | 页型、结构模板、密度标准 |
| visual system packs | 色彩、字体、布局、品牌约束 |
| page archetypes | 不同行业 / 场景的页面原型 |
| quality rubrics | draft / render / delivery gate 的评分规则 |
| benchmark cases | 真实案例 smoke 和质量回归 |
| prompt packs | 给 Product Capability agent 的任务提示 |

这些资产由 Core Skills 和 Product Capability Skills 引用，不应成为用户主要入口。

## User Routing Model

| 用户意图 | 首选 Skill | 后续可能调用 |
|---|---|---|
| 从客户材料做完整方案 Deck | `deck-master` | `deck-planner`、`ppt-library`、`ppt-deck-pro-max`、`ppt-master`、`deck-review` |
| 只规划方案结构和主叙事 | `deck-planner` | `ppt-library` |
| 已有 brief，要生成高质量 PPT/HTML | `ppt-deck-pro-max` | `deck-review` 或 `deck-master` run import |
| 检索历史 PPT 页面 | `ppt-library` | `deck-planner` 或 `deck-master` sourcing |
| 审查已有 PPT/HTML/PDF | `ppt-quality-gate` 或 `deck-review` | `deck-master` import-quality-findings |
| 检查一个 Deck Master run 是否能交付 | `deck-review` | `deck-master` export |
| build / render SVG/PPTX/PDF | `ppt-master` | `deck-master` import-render-result |
| 记录交付反馈和经验沉淀 | `deck-learning` | `ppt-library` feedback adapter |

## Installation Model

### Release Tree

Deck Master release 应形成：

```text
~/.deck-master/current/
  skills/
    deck-master/
    deck-planner/
    deck-review/
    deck-learning/              # optional / later
    ppt-master/
    ppt-library/
    ppt-deck-pro-max/
    ppt-quality-gate/
  product-capability-manifest.json
```

### Agent Links

Codex / Claude Code / other agent 目录只保留 symlink：

```text
~/.codex/skills/deck-master -> ~/.deck-master/current/skills/deck-master
~/.codex/skills/deck-planner -> ~/.deck-master/current/skills/deck-planner
~/.codex/skills/deck-review -> ~/.deck-master/current/skills/deck-review
~/.codex/skills/ppt-master -> ~/.deck-master/current/skills/ppt-master
~/.codex/skills/ppt-library -> ~/.deck-master/current/skills/ppt-library
~/.codex/skills/ppt-deck-pro-max -> ~/.deck-master/current/skills/ppt-deck-pro-max
~/.codex/skills/ppt-quality-gate -> ~/.deck-master/current/skills/ppt-quality-gate
```

Claude Code 同理。

### Migration Rule

如果目标位置已有历史实体目录：

1. 不静默覆盖。
2. 先识别是否是已知 legacy skill。
3. 生成 migration plan。
4. 备份到可回滚目录。
5. 再替换为 symlink。
6. 迁移后重新跑 `suite-status`。

## Product Boundary

Deck Master Core Skills 负责：

- run state
- planning state
- quality state
- review state
- handoff / handback contracts
- setup / workspace / suite readiness
- feedback / metrics / benchmark state

Product Capability Skills 负责：

- build / render / export
- 历史资产检索
- 新页生产
- 深度视觉 / 内容质量审查

Reference Packs 负责：

- 页型知识
- 视觉标准
- 质量标准
- benchmark evidence

这个边界确保 Deck Master 可以作为独立开源项目成立。PPT Master、PPT Library、PPT Deck Pro Max、PPT Quality Gate 可以继续保持各自历史来源和独立入口，但在 Deck Master 产品中必须被内化为产品能力。

## Implementation Path

### Phase 1: Product Definition

- 落本文档。
- 明确 Core Skills、Product Capability Skills、Reference Packs。
- 在 specs 索引中把本文档作为 v0.9.13+ 的产品架构前置。

### Phase 2: Packaging & Migration Spec

- 定义 release tree。
- 定义 product capability source package。
- 定义 legacy real directory migration。
- 定义 install / setup / suite repair 的用户可见流程。
- 定义失败和回滚策略。

### Phase 3: Core Skill Split

最小拆分顺序：

1. `deck-master` 保留 router / setup / run owner。
2. 新增 `deck-planner`，先从现有 deck-master playbooks / prompts 提取 planning 入口。
3. 新增 `deck-review`，先从 quality / review / export 文档提取交付审查入口。
4. `deck-learning` 等反馈链路稳定后再拆。

拆分后不必马上拆代码模块；先拆 Agent 入口和人机交互。

### Phase 4: Product Capability Packaging

- 将 `ppt-master` 纳入默认 build / render package。
- 将 `ppt-quality-gate` draft 晋升为 release package。
- 将 `ppt-library` 内化为 asset intelligence package；数据库和索引生命周期可保留独立配置。
- 将 `ppt-deck-pro-max` 内化为 production intelligence package；可参考或迁移现有仓库能力。
- 所有 capability package 都必须进入 Deck Master release tree。

### Phase 5: Acceptance

验收标准：

- `~/.deck-master/current/skills/` 可见 Core Skills 和 required Product Capability Skills。
- Codex / Claude Code 目录对应入口都是 symlink。
- `suite-status` 能区分 Core readiness、Product Capability readiness、Task readiness。
- 用户点名 Deck Master 时，Agent 能先进入 router / setup / workspace / run state，不直接跳到生产器。
- 用户点名 `deck-planner`、`deck-review`、`ppt-quality-gate`、`ppt-library` 时，Agent 能进入对应任务入口。
- product capability output 进入 active run 前必须 import 或 state update。

## Open Questions

1. `deck-planner` 和 `deck-master` 的边界是否按“规划入口 vs 顶层运行时”拆分。
2. `deck-review` 是否覆盖内建 quality gates 和外部 `ppt-quality-gate` findings 的统一查看。
3. `deck-learning` 是否放入 v0.9.13，还是等真实 feedback 数据成熟后再拆。
4. `ppt-library`、`ppt-deck-pro-max`、`ppt-master` 在 release tree 中采用 curated wrapper package、subtree、fork，还是重建模块。
5. 历史实体目录迁移是否需要显式 `--migrate-legacy-skills` 开关。

## Recommended Decision

建议下一轮先做 **v0.9.13 Deck Master Product Capability Packaging & Migration Spec**。

该 spec 不应继续扩大 generation / quality / sourcing adapter。它只解决：

- Deck Master Core Skill 拆分。
- Product Capability skill package 的来源和安装。
- 历史实体目录迁移。
- Codex / Claude 软链接统一。
- First-run setup 与 suite setup 的统一引导。

这样可以先把“用户到底能点名哪些 skill、这些 skill 装在哪里、谁管理谁”定清楚，再继续推进真实生产链路。
