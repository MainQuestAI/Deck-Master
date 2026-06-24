# Deck Master Skill OS 改造规划稿

日期：2026-06-24  
状态：规划稿，用于后续与 ChatGPT 讨论正式 Spec  
范围：Deck Master Skill 体系、CLI、Run State、Artifact、Review Cockpit、安装与验证链路  

## 1. 本文定位

本文不是正式实现 Spec。它用于记录本轮讨论中暴露的真实问题、阶段判断和后续 Spec 应覆盖的方向。

后续正式 Spec 可以基于本文展开，但需要进一步细化为命令、schema、测试、迁移和验收标准。

本文面向两个读者：

1. ChatGPT：用于高层产品与系统设计讨论。
2. Codex / Claude Code：用于后续拆解成可执行开发任务。

## 2. 背景

Deck Master 已经从早期的单一 PPT 流程，演进成一个具备 run state、workspace、planning、sourcing、generation、render、quality、review、export 的本地 Deck 生产系统。

当前仓库里已经有一份 v1.0 Skill Suite 方向的文档：

- `docs/specs/deck-master-v1.0-skill-suite-interaction-spec.md`

这份文档已经提出了较完整的 skill 名称体系：

- `deck-master`
- `deck-setup`
- `deck-upgrade`
- `deck-doctor`
- `deck-init`
- `deck-brief`
- `deck-planner`
- `deck-sourcing`
- `deck-producer`
- `deck-builder`
- `deck-quality`
- `deck-review`
- `deck-learn`
- `deck-autopilot`

本轮讨论的关键变化是：问题不再停留在“是否要新增一个访谈 skill”，而是 Deck Master 整个 skill suite 是否要按 GStack 的工作流系统逻辑重做。

## 3. 本轮暴露的具体问题

### 3.1 访谈深度不足只是表层问题

最开始的问题集中在 `deck-planner` 和 `ppt-deck-pro-max` 的访谈体验不够好。

深入看后，根因不在某一个 skill；整个 Deck Master 缺少类似 GStack 的强流程结构：

- 阶段入口不够明确。
- 阶段完成后没有可靠的下一步提示。
- 阶段产物没有成为下游 skill 的硬依赖。
- 用户确认、自动推进、阻断条件没有形成统一规则。
- Agent 容易把 CLI 命令当成流程，把命令跑完当成任务完成。

### 3.2 当前 Skill 名字基本可用，但功能太薄

本轮确认：之前这组 `deck-*` 名字整体方向是对的，不需要大幅改名。

问题在于每个 skill 的内部能力太薄，缺少 GStack 那种工作流 discipline：

- `Use When`
- `Do Not Use When`
- `First Checks`
- `Forcing Questions`
- `Exit Artifacts`
- `Next Skill`
- `Handoff Prompt`
- `Stop Conditions`

也就是说，名字像产品体系，行为还像命令索引。

### 3.3 `deck-sourcing / deck-producer / deck-builder` 边界不清

本轮重点澄清了三者边界：

| Skill | 核心职责 | 不承担的职责 | 产物 |
|---|---|---|---|
| `deck-sourcing` | 决定每页用什么材料、证据和来源 | 不写最终页文案，不排版，不构建文件 | `sourcing_plan.json` |
| `deck-producer` | 把页面任务和材料来源变成页面内容包 | 不装配整套文件，不判断最终交付 | `page_package.json` / `deck_generation_result.v2` |
| `deck-builder` | 把页面内容包构建成 HTML / PPTX / PDF / PNG | 不新增业务主张，不补写页面内容 | `build_manifest.json` / artifact manifest |

一句话：

- `deck-sourcing` 管材料来源。
- `deck-producer` 管页面内容包。
- `deck-builder` 管文件构建。

这个边界应成为正式 Spec 的基础。

### 3.4 当前 CLI 是命令集合，还没有完全成为阶段运行时

当前 CLI 已经有很多基础命令：

- `route-skill`
- `next-step`
- `run-state`
- `workflow-autopilot`
- `init-project`
- `build-brief`
- `build-claim-map`
- `decide-sourcing`
- `generation-session`
- `run-generation`
- `build`
- `render`
- `quality-gate`
- `final-readiness`
- `export`

这些命令说明底层能力已经不少。

但它们现在更像一组可调用命令，还没有形成“阶段完成 -> 产物写入 -> 下游验证 -> 用户确认或自动推进”的统一 runtime。

这也是为什么只改 SKILL.md 无法根治问题。

### 3.5 `workflow-autopilot` 需要更强的审批与停顿机制

当前 `workflow-autopilot` 已能连续推进，但需要补上两类规则：

1. 高影响阶段必须停下来问用户。
2. 机械门禁可以自动继续，但必须记录 evidence。

建议高影响阶段包括：

- `deck-brief -> deck-planner`
- `deck-planner -> deck-sourcing`
- `deck-sourcing -> deck-producer`
- `deck-review -> export`

建议自动阶段包括：

- `deck-builder -> deck-quality`
- `deck-quality -> deck-review`

### 3.6 Review Cockpit 需要展示 skill 阶段

Review Cockpit 当前已有 run / review / readiness 能力。

但如果 Deck Master 要升级成 Skill OS，UI 需要让用户看懂：

- 当前处于哪个 skill 阶段。
- 当前阶段产物是否齐。
- 下一步推荐哪个 skill。
- 哪些条件阻断了下游。
- 哪些动作需要用户确认。

否则用户仍然会看到大量技术状态，却不知道下一步该干什么。

## 4. 参考对象：GStack 的有效机制

本轮重点参考 GStack，目标是吸收它的工作流机制，而非复制具体技能名称。

### 4.1 GStack 的有效点

GStack 的强项包括：

1. 每个 skill 有明确场景。
2. 每个 skill 有强制问题或审查步骤。
3. 每个 skill 输出可被下游读取的产物。
4. 阶段之间会主动推荐下一步。
5. 关键选择会通过用户确认卡住。
6. 自动流程有 stop condition。
7. review / qa / ship 等阶段会读取前置结果，并判断是否过期或缺失。

### 4.2 对 Deck Master 的启发

Deck Master 应吸收的是这套“阶段交接纪律”，具体创业问题、代码评审问题和 ship 流程只作为参考样本。

对应到 Deck Master：

- `deck-brief` 完成后，应主动询问是否进入 `deck-planner`。
- `deck-planner` 完成后，应主动询问是否进入 `deck-sourcing`。
- `deck-sourcing` 完成后，应主动询问是否进入 `deck-producer`。
- `deck-builder` 完成后，应自动进入 `deck-quality`。
- `deck-quality` 完成后，应自动进入 `deck-review`。
- `deck-review` 准备导出客户版前，必须确认。

## 5. 核心判断

### 5.1 Deck Master 应升级为 Skill OS

Deck Master 不应只是一组 PPT 相关工具的包装。

更合适的定位是：

> Deck Master 是面向解决方案型 Deck 的本地生产工作流系统，负责把客户上下文、业务判断、历史素材、页面生产、文件构建、质量门禁和交付审查串成可追踪闭环。

这个定位下，skill 是用户入口，CLI 是执行层，run state 是状态层，artifact 是交接层，Review Cockpit 是可视化层。

### 5.2 Skill 文档不能单独解决问题

只改 skill 文档，会带来一个风险：Agent 的话术更像流程，但底层系统仍然无法验证阶段条件。

因此需要同步升级：

- CLI 命令
- runtime state
- artifact schema
- route resolver
- workflow autopilot
- Review Cockpit
- test gate
- installer / manifest

### 5.3 正式 Spec 应先定义“阶段契约”

正式 Spec 不应从 UI 或单个命令开始。

更稳的起点是定义全链路阶段契约：

```text
skill input
-> first checks
-> required artifacts
-> exit criteria
-> handoff record
-> next skill recommendation
-> approval policy
-> downstream entry validation
```

一旦阶段契约稳定，CLI、UI、测试和 Skill 文档都可以围绕它实现。

## 6. 建议的分层架构

### 6.1 用户入口层：Skill

Skill 面向用户自然语言输入。

职责：

- 判断当前请求归属哪个阶段。
- 用业务语言解释当前阶段。
- 调用 CLI 检查真实状态。
- 指导用户确认关键选择。
- 把执行结果回写到 run state。

### 6.2 执行层：CLI

CLI 负责真实动作。

建议新增或升级这些能力：

| CLI 能力 | 用途 |
|---|---|
| `skill-handoff` | 生成当前 skill 完成后的交接记录 |
| `validate-stage` | 校验某个 skill 是否可以进入 |
| `accept-handoff` | 记录用户确认进入下一阶段 |
| `workflow-status` | 用产品语言展示全链路阶段状态 |
| `route-skill` 升级 | 返回推荐 skill、原因、缺失产物、是否需要确认 |
| `next-step` 升级 | 返回面向 skill 的下一步，而非只返回命令 |
| `workflow-autopilot` 升级 | 支持审批策略和阶段 evidence |

### 6.3 状态层：Run State

Run State 需要表达当前 skill 阶段。

建议至少包含：

- current_skill_stage
- completed_skills
- required_next_skill
- recommended_next_skill
- blocked_next_skills
- missing_artifacts
- approval_required
- approval_status
- final_readiness_status

### 6.4 交接层：Artifacts

建议新增或升级这些文件：

- `skill_handoff.json`
- `stage_status.json`
- `approval_log.jsonl`
- `sourcing_plan.v2.json`
- `page_package.json`
- `build_manifest.json`
- `final_readiness.json`

其中最关键的是 `skill_handoff.json`。它负责把“这个阶段做完了，下一步该做什么”变成机器可读状态。

### 6.5 可视化层：Review Cockpit

Review Cockpit 需要增加 Skill OS 视图。

建议展示：

- 当前阶段
- 已完成阶段
- 当前阶段产物
- 阻断项
- 推荐下一步
- 需要用户确认的动作
- 自动执行的门禁
- 可导出状态

### 6.6 安装与发布层

安装和 suite readiness 也要同步升级。

需要确认：

- 新 skill 是否都能被安装。
- 旧 `ppt-*` 入口是否保留兼容。
- CLI capability 是否被 manifest 登记。
- 本机 release tree 是否含完整 skill 文档。
- Codex / Claude Code 链接是否一致。

## 7. 建议的工作流闭环

### 7.1 标准生产链路

```text
deck-init
-> deck-brief
-> deck-planner
-> deck-sourcing
-> deck-producer
-> deck-builder
-> deck-quality
-> deck-review
-> deck-learn
```

### 7.2 每段职责

| 阶段 | 业务问题 | 产物 | 下一步 |
|---|---|---|---|
| `deck-init` | 这个项目的资料、边界、目录是否准备好 | project metadata / material inventory | `deck-brief` |
| `deck-brief` | 客户问题、目标、证据、主张是什么 | deck brief / claim seed | `deck-planner` |
| `deck-planner` | 这套 Deck 怎么讲，分几页，每页承担什么任务 | narrative plan / page tasks | `deck-sourcing` |
| `deck-sourcing` | 每页用什么材料和证据支撑 | sourcing plan | `deck-producer` |
| `deck-producer` | 每页具体怎么写、怎么表达 | page package / generation result | `deck-builder` |
| `deck-builder` | 如何构建成可检查文件 | build manifest / artifacts | `deck-quality` |
| `deck-quality` | 文件是否存在客户可见风险 | quality report | `deck-review` |
| `deck-review` | 是否可交付，是否可导出客户版 | final readiness / export queue | export / repair / learn |
| `deck-learn` | 哪些经验进入下一次复用 | learning pack | next run |

## 8. 关键设计原则

### 8.1 高影响阶段必须确认

涉及方向、结构、生产成本、素材授权、客户交付的动作，必须让用户确认。

典型场景：

- 从 brief 进入 planner。
- 从 planner 进入 sourcing。
- 从 sourcing 进入 producer。
- 从 review 进入 client export。

### 8.2 机械门禁应自动运行

质量扫描、最终 readiness 汇总、构建后验证等不应频繁打断用户。

只要前置条件满足，就应自动执行并记录证据。

### 8.3 客户可见内容必须结构化隔离

页面生产阶段必须区分：

- 客户可见标题
- 客户可见正文
- 讲者备注
- 视觉说明
- 内部制作说明

builder 只能读取允许进入客户可见文件的字段。

### 8.4 旧名兼容，新名对外

`ppt-library`、`ppt-deck-pro-max`、`ppt-master`、`ppt-quality-gate` 继续保留兼容。

普通用户入口推荐统一使用：

- `deck-sourcing`
- `deck-producer`
- `deck-builder`
- `deck-quality`

### 8.5 CLI 是事实源

Skill 文档里的流程必须由 CLI 验证。

Agent 不能只靠自然语言判断“阶段完成”。  
必须读取 artifacts、run state 或 CLI 返回结果。

## 9. 实施优先级建议

### Phase A：冻结阶段契约

目标：

- 定义每个 skill 的进入条件。
- 定义每个 skill 的退出产物。
- 定义 handoff record。
- 定义 approval policy。

这一阶段应先出正式 Spec。

### Phase B：补 CLI 运行时

目标：

- 新增 `skill-handoff`。
- 新增 `validate-stage`。
- 新增 `accept-handoff`。
- 升级 `route-skill` / `next-step` / `run-state`。

这是最关键的实现阶段。

### Phase C：升级 workflow-autopilot

目标：

- 支持 `quick / production / repair / review-only` 的阶段审批策略。
- 高影响阶段停问。
- 机械门禁自动执行。
- 每段写 evidence。

### Phase D：升级三段生产边界

目标：

- `deck-sourcing` 输出稳定 `sourcing_plan.v2`。
- `deck-producer` 输出 `page_package`。
- `deck-builder` 只构建 artifact，不写业务新内容。

### Phase E：Review Cockpit 展示

目标：

- UI 展示当前 skill 阶段。
- UI 展示下一步推荐。
- UI 展示缺失产物。
- UI 展示需要确认的动作。

### Phase F：安装与验证

目标：

- suite manifest 登记所有新能力。
- skill 安装树完整。
- legacy wrapper 可用。
- 测试覆盖 routing / handoff / stage validation / autopilot。

## 10. 风险和反模式

### 10.1 只写 Skill 文档

风险：

- Agent 话术变好，但系统仍无法验证阶段完成。
- 自动推进仍会跳阶段。
- 用户确认无法追溯。

### 10.2 只改 CLI 命令名

风险：

- CLI 看起来更产品化，但工作流行为不变。
- 阶段交接仍依赖 Agent 自觉。

### 10.3 过早进入 UI

风险：

- UI 只能展示已有状态。
- 如果 runtime 没有 handoff / approval / stage validation，UI 会继续展示不完整状态。

### 10.4 生产阶段混写内容和文件构建

风险：

- builder 为了解决版式问题顺手改业务文案。
- 内部制作说明进入客户文件。
- 质量门禁无法追踪内容来源。

### 10.5 旧 `ppt-*` 名称直接删除

风险：

- 破坏已有用户路径。
- 打断现有 Agent skill 调用。
- 让迁移成本变高。

建议保留 wrapper，逐步引导到 `deck-*`。

## 11. 给 ChatGPT 的讨论问题

后续和 ChatGPT 讨论正式 Spec 时，建议围绕这些问题展开：

1. Deck Master 的 Skill OS 是否应以 `skill_handoff.json` 作为核心交接对象？
2. `deck-brief -> deck-planner -> deck-sourcing` 哪些环节必须用户确认？
3. `deck-autopilot production` 是否允许预授权连续推进？如果允许，哪些阶段仍必须停？
4. `deck-producer` 的页面内容包字段应该如何拆分，才能避免客户可见内容污染？
5. `deck-builder` 是否只能消费 `page_package`，是否允许读取旧 `preview_manifest`？
6. `deck-quality` 和 `deck-review` 的边界如何避免重叠？
7. Review Cockpit 的 Skill OS 视图应该展示哪些最少信息？
8. CLI 新增 `skill-handoff / validate-stage / accept-handoff` 是否足够，还是需要统一 `workflow` 子命令组？
9. 旧 `ppt-*` skill 的兼容期和 wrapper 策略如何设计？
10. 第一轮实现应选哪条最小闭环验证？

## 12. 建议的 ChatGPT 输出要求

请 ChatGPT 基于本文输出以下内容：

1. 一版 Deck Master Skill OS 总体架构建议。
2. 一版阶段契约模型。
3. 一版 CLI 能力清单。
4. 一版 artifact 清单。
5. 一版最小实现路线。
6. 一版风险清单。
7. 一版正式 Spec 目录结构建议。

要求：

- 不写代码。
- 不直接展开到字段级 schema。
- 优先判断系统边界和阶段依赖。
- 明确哪些阶段必须用户确认。
- 明确哪些阶段可以自动继续。
- 保留现有 skill 名称体系。
- 保留旧 `ppt-*` 入口兼容。

## 13. 当前建议结论

Deck Master 下一阶段应按“Skill OS”方向推进。

最小正确路线：

1. 先冻结阶段契约。
2. 再补 CLI handoff runtime。
3. 再升级 route / next-step / run-state。
4. 再改 autopilot。
5. 再补 sourcing / producer / builder 三段产物边界。
6. 最后升级 Review Cockpit 和安装验证。

如果只改 Skill 文档，系统体验会改善有限。

真正要解决的问题是：每个阶段完成后，系统必须知道“下一步是谁、能不能进、缺什么、要不要问用户、问完如何记录”。

这就是 Deck Master 从 PPT 工具集合升级为专业 Solution Deck 工作流系统的关键。
