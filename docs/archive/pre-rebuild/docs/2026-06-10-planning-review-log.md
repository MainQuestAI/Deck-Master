# Deck Master 规划评审记录

日期：2026-06-10
状态：已完成

## 1. 文档目的

这份文档用于记录 Deck Master 下一轮开发前的完整评审过程。

当前规则已经明确：在 Office Hour、CEO Review、DevEx Review、Engineering Review、Design Review 完成并合并成确认版实现方案前，不进入下一轮产品开发。

当前评审已经收口。确认版实现方案见 `docs/2026-06-10-run-os-mvp-confirmed-implementation-plan.md`。

## 2. 评审流程状态

| 环节 | 状态 | 输出 | 备注 |
|---|---|---|---|
| Office Hour | 已完成 | `docs/2026-06-10-office-hour-run-os.md` | 确认 Professional Deck Run OS、第一用户、第一场景和 12 小时到 2 小时指标。 |
| CEO Review | 已完成 | `docs/deck-master-top-level-product-design-draft.md` 与会话结论 | 已确认方向，应用形态缺口已在后续评审补齐。 |
| 应用形态评审 | 已完成 | 本文档 | 确认 Agent 外挂运行时、CLI、localhost Web UI、Deck Workspace。 |
| DevEx Review | 已完成 | 本文档与 gstack 评审日志 | 实测发现运行时可用，但新手引导、根目录快速开始、错误提示仍弱。 |
| Engineering Review | 已完成 | 本文档 | 已确认下一轮工程边界、状态模型、Workspace、Build Skill 与测试矩阵。 |
| Design Review | 已完成 | `docs/2026-06-10-web-ui-design-spec.md` | 已确认 Web UI 职责、语言策略、信息架构与审查流程。 |
| 终局蓝图补充评审 | 已完成 | `docs/2026-06-11-deck-master-endgame-blueprint.md` | 将长期方向从单次 Run OS 扩展为专业方案叙事生产系统。 |
| MVP 方案压缩评审 | 已完成 | `docs/2026-06-10-run-os-mvp-confirmed-implementation-plan.md` | 将下一轮实现收敛为 P0 可审查闭环，Build Skill 自动执行和复杂 UI 操作进入增强层。 |
| 统一实现方案 | 已完成 | `docs/2026-06-10-run-os-mvp-confirmed-implementation-plan.md` | 作为 P0 实现主方案。 |

## 3. 已锁定的产品判断

- 第一用户：售前解决方案架构师。
- 第一场景：客户会议后的 Solution Deck 草案。
- 核心指标：从方案思路基本确认到第一版可审查草案，从约 12 小时压到约 2 小时。
- 产品方向：专业 Solution Deck 叙事生产系统，近期用 Professional Deck Run OS 跑通生产闭环。
- 应用形态：Agent 外挂运行时 + CLI 执行层 + localhost Web UI 审查面板 + 文件系统 Deck Workspace。
- Web UI 角色：由 Agent 或 CLI 唤起，用于预览、审查、审批、质量状态查看和产物确认。
- 持久化形态：用户指定 Deck Workspace 文件夹，每次任务形成独立 run 目录。
- 长期知识：LLAM wiki、OpenViking、飞书会议记录、项目记忆继续承担长期知识职责；Deck Master 在 run 内保存引用、摘要、决策和审查记录。
- 质量门禁：Quality Gate 是 Deck Master 内建子系统，吸收 `ppt-quality-gate` 的方法论和检查规则。
- 终局蓝图：Deck Master 的长期价值来自 Workspace 级资产复利、Claim-Evidence Graph、Asset Intelligence、Quality Governance 和 Delivery Feedback。
- 本轮 MVP：优先完成 Runtime、Events、`next_step`、Workspace-aware Planner、Sourcing、Draft Gate、Review UI 和 Quality-aware Export。
- P0 边界：Build Skill 自动执行、替换来源、转生成页、锁定历史页、完整反馈学习进入增强层，不作为 P0 阻断项。

## 4. 当前应用形态定义

Deck Master 的当前产品形态定义为：

> 面向 Agent 的专业 Deck 生产运行时，通过 CLI 管理流程，通过 localhost Web UI 提供审查，通过 Deck Workspace 固化视觉、结构和质量标准。

三类入口的关系：

| 入口 | 用户目的 | 承担职责 | 不承担职责 |
|---|---|---|---|
| Agent 对话入口 | 讨论方案、补充判断、控制 run | 需求澄清、追问、解释、调用 CLI、总结结果 | 不承载复杂页面审查 |
| CLI / Runtime | 稳定执行、恢复、记录状态 | 创建 workspace、创建 run、规划、检索、生成、质检、导出 | 不承担视觉审查体验 |
| localhost Web UI | 看、审、批、改备注 | 预览页面、看来源、看质量风险、审批、查看生成状态 | 不做完整编辑器，不替代 Agent 对话 |

关键边界：

- Web UI 不是持续打开的桌面应用。
- Web UI 不是完整 PPT 编辑器。
- Web UI 不是主对话入口。
- Web UI 是任务唤起式审查面板，围绕一次 run 工作。
- Agent 是主操作界面，负责思考、沟通和编排。
- CLI 是稳定执行面，负责状态和恢复。

## 5. DevEx Review 结论

实测内容：

- `python3 scripts/deck_master.py --help`
- `python3 scripts/deck_master.py autoplan --help`
- `python3 scripts/deck_master.py quality-gate --help`
- 从本地会议转写到 preview manifest 和 Draft Gate 的 smoke 流程。
- localhost Studio 模式。
- localhost run preview 模式。
- `uvx pytest`

评分：

| 维度 | 分数 | 结论 |
|---|---:|---|
| 第一次启动 | 5/10 | 运行能成功，但根目录没有清晰的快速开始说明。 |
| CLI 体验 | 5/10 | 命令完整，但推荐路径和下一步提示不足。 |
| 错误提示 | 4/10 | 部分错误清楚，缺 context 文件时会暴露 traceback。 |
| 文档 | 4/10 | 文档多，但像开发记录，缺产品级入口文档。 |
| Web UI | 5/10 | 审查面板雏形可用，但空状态、状态提示和信息架构不足。 |
| 开发验证 | 8/10 | `uvx pytest` 44 个测试通过，耗时约 2.36 秒。 |
| 升级路径 | 1/10 | 缺 changelog、版本边界和迁移说明。 |
| DX 度量 | 2/10 | 有 runtime events，但缺新手引导和失败体验反馈。 |

DevEx 结论：

- 当前机器执行能力可作为内部 spike。
- 首次使用体验还不足以支撑可复用 Agent-facing 产品。
- 下一轮需要补快速开始、初始化流程、统一错误输出、workspace bootstrap。

## 6. Engineering Review 决策记录

### Q1：下一轮工程范围

选择：A

结论：下一轮收敛为 Run OS Foundation + Draft Gate hardening。

后续用户补充后，Workspace 从最小版本升级为完整 Workspace Foundation。

### Q2：CLI 和 Web UI pipeline 分叉

选择：A

结论：

- 新增共享 runtime pipeline。
- CLI command 变成薄封装。
- Web UI 调用同一套 pipeline。
- 创建、续跑、恢复、预览生成都走唯一运行时路径。

### Q3：Workspace 范围

选择：D

结论：本期做完整 Workspace Foundation，以本地客户工作坊样本 PPT 工作坊为真实样本。

本期 Workspace 范围：

- `workspace_manifest.json`
- `AGENTS.md`
- `visual-system/design_spec.md`
- `visual-system/spec_lock.md`
- `visual-system/layout_blueprint.md`
- `visual-system/template/page_archetypes.md`
- `structure-assets/` 或 `ppt-structure-assets/` 注册
- `quality/quality_policy.md`
- `quality/scoring_rubric.md`
- `quality/failure_modes.md`
- `quality/repair_playbooks.md`
- `sources/`
- `projects/`
- `runs/`
- `exports/`
- `reference-analysis/`
- 默认 Build Skill 配置

边界：

- 支持注册现有工作坊。
- 支持登记 reference PPT 路径和已有分析产物。
- 本期不承诺自动从新 reference PPT 抽取完整视觉系统。

### Q4：运行时恢复和事件模型

选择：A

结论：

- 本期做 typed events。
- 本期做 canonical `next_step` 状态机。
- CLI 和 Web UI 共用。
- 状态机要能识别 missing、complete、corrupt、pending approval、quality blocked。
- 遇到坏 JSON 或人工审批结果时，不能静默覆盖。

### Q5：质量门禁位置

选择：A

结论：

- Draft Gate 进入默认硬链路。
- Render Gate 和 Delivery Gate 保留为显式 artifact check。
- Render / Delivery 可用于 fixture 和真实项目回归。
- 在 Deck Master 拥有 canonical PPTX artifact 前，不把 Render / Delivery 放进默认硬阻断链路。

### Q6：Build Skill 交接

选择：B

结论：

- 本期直接执行一个默认 Build Skill。
- 必须同时定义 Build Skill registry 和 artifact handback contract。
- 默认 Build Skill 放在 Workspace 配置里，run 可覆盖。
- 执行状态必须回写到 run。
- 失败要写 typed events，并在 Web UI 可见。
- 产物必须能追溯到 `beat_id`、`task_id`、source decision 和 build tool。

边界：

- 本期只要求一个默认 Build Skill。
- 多工具调度延后。
- 并行生成延后。
- 复杂重试延后，只保留基于 typed state 的安全重跑。

### Q7：Preview 审批状态

选择：A

结论：

- 审批状态收敛为 `needs_review`、`approved`、`rejected`。
- 备注独立保存。
- 导出默认只导出 `approved`。
- 首版反馈只写 approved / rejected outcomes。
- 替换、锁定、转生成、补证据后续作为 action request，不混进审批状态。

### Q8：CLI 错误处理

选择：A

结论：

- 本期做统一错误输出。
- 用户错误、输入错误、run 状态错误、外部工具错误要统一格式。
- 错误输出包含问题、可能原因、下一步动作。
- Agent-facing 命令支持结构化输出。
- traceback 仅保留在 debug 模式。

### Q9：Planner 读取 Workspace 资产

选择：A

结论：

- Planner 本期读取 Workspace archetypes 和 density standards。
- 无 Workspace 时回退当前默认模板。
- `page_tasks.json` 写入选中的 workspace archetype 引用。
- Draft Gate 可读取 workspace density 和 quality standards。

### Q10：测试矩阵

选择：A

结论：下一轮实现必须包含完整 contract test matrix。

必须覆盖：

- Workspace 创建和现有工作坊注册。
- Workspace manifest 校验和 include / exclude 规则。
- CLI 和 Web UI 共用 shared pipeline。
- `next_step` 覆盖 missing、complete、corrupt、approval pending、quality blocked。
- typed events 校验。
- workspace-aware planner 和 fallback。
- 默认 Build Skill fake executor。
- artifact handback 映射到 `beat_id` / `task_id`。
- Draft Gate hard path。
- Render / Delivery artifact-only。
- Preview review states 和 notes。
- approved-only export。
- CLI normalized errors。

### Q11：Workspace 注册性能边界

选择：A

结论：

- Workspace setup 只注册标准与索引。
- SVG、PPTX、PNG、review grids、历史 exports 只作为 examples 或 artifacts 引用。
- 不深度摄取所有生成物。
- include / exclude 规则写入 `workspace_manifest.json`。

### Q12：Build Skill 自动执行方式

选择：A

结论：

- 默认 Build Skill 自动执行，但必须状态化。
- CLI 和 Web UI 不隐藏长时间黑盒任务。
- Web UI 启动任务并轮询状态。
- CLI 对短步骤可等待，对长步骤需要状态输出和 no-wait 选项。
- 每一步写 typed events 和 artifact handback。

### Q13：PPTX 检查触发时机

选择：A

结论：

- 只有 gate 或 artifact handback 明确指定 PPTX 时才检查。
- Workspace setup 只登记 PPTX 路径和元数据。
- 历史 PPTX example 不作为当前 run artifact。
- Quality report 必须绑定具体 run 和 artifact path。

## 7. Engineering Review 总结

下一轮实现范围：

- shared runtime pipeline
- 完整 Workspace Foundation
- typed events + `next_step`
- workspace-aware planner
- Draft Gate hard path
- Render / Delivery explicit artifact check
- 默认 Build Skill 状态化执行
- Build Skill registry 与 artifact handback
- Preview 审批状态收敛
- CLI 错误标准化
- 完整 contract tests

明确不在本期范围：

- 多 Build Skill 调度平台
- 并行页面生成
- 复杂重试系统
- 实时飞书拉取
- OpenViking 在线查询
- 从新 reference PPT 自动抽取完整视觉系统
- 深度摄取 workspace 内所有 SVG / PPTX / PNG / 历史导出物
- 在 canonical PPTX handback 稳定前，把 Render / Delivery 作为默认硬阻断
- 复杂 Preview 操作：lock、convert、replace candidate、mark manual evidence
- 全量反馈学习系统

工程评审结论：

方案可以进入 Design Review。实现方案必须先重写为确认版 spec，不能直接沿用当前 spike 架构。

## 8. Design Review 重新定位

### 8.1 用户反馈修正

用户指出两个问题：

1. Web UI 当前语言混用，中文和英文夹杂，体验不专业。
2. 评审记录主体使用英文，与其他评审输出不一致。
3. Design Review 起点不应直接讨论布局，应先定义 Web UI 与 Agent 主操作界面的关系。
4. Web UI 是否是持续操作工作台、它解决什么问题、它和 Agent 的边界，需要先审清楚。

修正动作：

- 本文档改为中文主体。
- Web UI 文案策略进入 Design Review 第一优先级。
- Design Review 先审职责边界，再审信息架构、状态、视觉和响应式。

### 8.2 当前 Web UI 事实

当前 UI：

- 左侧：品牌、brief 创建表单、run 列表、page 列表。
- 中间：页面导航和当前页大图预览。
- 右侧：页面详情、decision、notes。

当前问题：

- 文案混用：例如 `New deck brief`、`Industry`、`Pages`、`Generate draft`、`页面中文示例` 同屏出现。
- 审批状态混乱：`keep`、`replace`、`approved` 与已确认的审批语义不一致。
- 页面优先，run 状态弱。
- Build Skill 状态、Draft Gate 阻断、下一步动作没有成为主信息。
- 空状态和错误状态偏工程提示。

### 8.3 Design Review 初评

设计完整度：4/10。

已有基础：

- 三栏审查结构合理。
- 页面预览能力可用。
- 页面详情、来源、备注已经有基础。
- 键盘翻页可用。

主要缺口：

- 缺 Web UI 产品职责定义。
- 缺语言策略。
- 缺 run-centric 信息架构。
- 缺 Build Skill 状态展示。
- 缺 Draft Gate 质量阻断展示。
- 缺 workspace / run / page 三层导航关系。
- 缺空状态、错误状态、执行中状态、部分完成状态。
- 缺设计系统和双语规则。

## 9. Design Review 第一议题：Web UI 职责边界

核心问题：

Web UI 不是主操作入口。主操作入口是 Agent 对话。Web UI 也不能扩成完整桌面工作台。它要解决的是 Agent 对话界面不适合解决的可视化审查问题。

建议定义：

> Deck Master Web UI 是一次 Deck run 的本地审查面板。它由 Agent 或 CLI 唤起，用于查看 run 状态、预览页面、审查来源、查看质量风险、确认 Build Skill 产物、写入审批和备注。

Web UI 负责：

- 看整体 run 状态。
- 看下一步动作。
- 看 Build Skill 是否在执行、失败或完成。
- 看页面预览。
- 看每页来源和理由。
- 看每页证据缺口和质量发现。
- 做 `approved / rejected / needs_review` 审批。
- 写页面级备注。
- 查看 approved queue 是否可导出。

Web UI 不负责：

- 长篇需求讨论。
- 多轮方案头脑风暴。
- 完整 PPT 编辑。
- 复杂页面重排和替换策略讨论。
- 长期知识库管理。
- 历史资产库管理。
- 多项目后台管理。

Agent 负责：

- 追问用户。
- 解释方案逻辑。
- 发起 run。
- 调用 CLI。
- 解释质量报告。
- 根据用户反馈推进下一步。

CLI / Runtime 负责：

- 创建和恢复 run。
- 记录状态。
- 调用工具。
- 生成中间产物。
- 写入事件。
- 执行质量门禁。

## 10. Design Review 第二议题：语言策略

当前问题：

Web UI 同屏出现中英文混杂，观感不统一。评审文档使用英文主体，也不符合项目已有沟通风格。

建议原则：

- Web UI 必须支持双语。
- 默认语言建议为中文。
- 英文作为可切换语言或配置项。
- 同一屏同一时刻只显示一种主语言。
- 技术文件名、状态值、命令、artifact 名称可以保留英文代码形态。
- 面向用户的标题、按钮、提示、空状态、错误提示必须走 i18n 文案表。

首版语言包：

```text
ui.locale = zh-CN | en-US

中文主界面：
  Deck Master 工作台
  新建方案
  行业
  页数
  历史库模式
  生成草案
  运行记录
  页面列表
  页面审查
  审批状态
  待审查
  已批准
  已拒绝
  备注
  保存审批
  质量发现
  生成状态
  下一步

英文主界面：
  Deck Master Studio
  New Deck
  Industry
  Pages
  Library Mode
  Generate Draft
  Runs
  Pages
  Page Review
  Review Status
  Needs Review
  Approved
  Rejected
  Notes
  Save Review
  Quality Findings
  Build Status
  Next Step
```

## 11. Design Review 第三议题：信息架构草案

推荐采用 run-centric 审查面板。

```text
顶部状态条
  Workspace | Run | 阶段 | 下一步 | 质量状态 | 生成状态 | 导出状态 | 语言切换

左侧导航
  Run 切换
  页面大纲
  筛选：全部 / 阻断 / 待审查 / 已批准 / 已拒绝

中间预览
  当前页大图
  上一页 / 下一页
  页码和章节上下文

右侧审查面板
  页面职责
  核心论点
  证据需求
  来源决策
  候选来源
  质量发现
  修复建议
  审批状态
  备注

底部或抽屉
  事件日志
  Build Skill 步骤
  Artifact handback
  Export queue
```

关键原则：

- 第一眼看 run 是否可继续。
- 第二眼看哪些页需要处理。
- 第三眼看当前页为什么这样组装。
- 用户不需要在页面列表、质量报告和生成状态之间来回猜。

## 12. 待用户确认的问题

### Q14：Web UI 的职责边界

A. 推荐：任务唤起式 Run 审查面板

Web UI 只围绕一次 run 工作。Agent 负责对话与控制，Web UI 负责看图、审查、审批、质量和状态确认。

B. 持续操作工作台

Web UI 作为日常入口，承载 workspace、run、历史项目、质量报告和导出管理。能力更完整，但产品会变重。

C. 纯预览器

Web UI 只看页面和写备注。最轻，但无法承载 Run OS 的状态和质量判断。

建议选择：A。

用户选择：A。

确认结论：

- Web UI 定位为任务唤起式 Run 审查面板。
- Agent 是主操作入口。
- Web UI 只承载 Agent 对话界面不适合承载的可视化审查工作。
- Web UI 不扩展成持续操作工作台。

### Q15：Web UI 默认语言

A. 推荐：默认中文，支持英文切换。

符合当前使用场景；也能避免同屏中英文混用。

B. 默认英文，支持中文切换。

更像通用开源工具，但不贴合当前项目使用习惯。

C. 跟随浏览器语言。

自动化更强，但调试和文档截图可能不稳定。

建议选择：A。

用户选择：C。

确认结论：

- Web UI 默认跟随浏览器语言。
- 必须提供显式语言切换。
- 用户选择的语言应写入本地偏好，优先级高于浏览器语言。
- 同一屏只显示一种主语言。
- artifact 名称、文件名、状态枚举和命令可以保留英文代码形态。
- 面向用户的按钮、标题、说明、空状态、错误提示必须走语言包。

### Q16：Design Review 是否先补线框图

A. 推荐：先补一版中文线框 spec，再进入视觉细化。

先把职责、信息层级和状态说清楚，后续再做视觉。

B. 直接做 UI 视觉稿。

能更快看到效果，但容易在职责没定清时提前讨论配色和风格。

C. 先继续文字评审，不做线框。

速度快，但设计落地风险高。

建议选择：A。

用户选择：A。

确认结论：

- 先补中文线框 spec。
- 线框先解决职责、信息层级、状态和操作路径。
- 视觉稿后置，避免在职责未收敛时提前讨论配色和风格。

### Q17：Agent 与 Web UI 的分工

A. 推荐：Agent 负责对话、判断、调度；Web UI 负责预览、审查、审批、查看质量问题。

这符合“Agent 外挂运行时 + localhost 审查面板”的应用形态。用户继续在 Agent 主会话里讨论方案、调整策略和推进 run，Web UI 只处理图形化审查和页面级决策。

B. Web UI 也做完整工作台，内置任务创建、对话和流程控制。

能力完整，但会显著变重，也会让 Agent 主会话和 Web UI 的边界变模糊。

C. Web UI 只做预览，不承载审批和操作。

最轻，但无法支撑专业 Deck 审查和 Run OS 的审批闭环。

建议选择：A。

用户选择：A。

确认结论：

- Agent 是主会话入口，负责需求澄清、方案讨论、run 调度、错误解释和下一步建议。
- Web UI 是可视化审查入口，负责页面预览、来源审查、质量风险查看、页面级决策和备注。
- Web UI 不承载完整对话流，不承担长期项目管理。
- Web UI 中的操作必须能写回 run 状态，让 Agent 可以继续接手。

### Q18：阻断问题怎么展示

A. 推荐：顶部状态条 + 页面列表标记 + 右侧修复建议；不默认弹窗，避免打断审查。

这种方式适合连续审查 10 到 60 页的 Deck。用户可以快速扫出阻断页，也可以在当前页看到具体修复建议。

B. 遇到 P0/P1 直接弹窗阻断。

阻断感强，但会打断连续审查，容易让用户陷入处理弹窗。

C. 只放到底部日志，由用户自己展开看。

界面干净，但风险太容易被忽略。

建议选择：A。

用户选择：A。

确认结论：

- 阻断问题必须在顶部状态条显示 run 级状态。
- 阻断页必须在左侧页面列表显示标记，并支持筛选。
- 当前页阻断原因和修复建议必须出现在右侧审查面板。
- 底部日志只作为补充证据，不作为主要风险入口。
- 默认不弹窗；只有用户尝试批准带 P0/P1 风险页面时，才需要显式确认。

### Q19：首版审查操作保留哪些

A. 推荐：只保留“待审查 / 批准 / 拒绝 / 备注”，其他动作后续加。

实现风险最低，但对专业用户来说干预能力偏弱。

B. 首版加入替换来源、转生成页、锁定历史页。

更符合专业 Deck 审查场景。用户看到候选页不合适时，可以直接改来源策略；看到历史页很好时，可以锁定；看到复用价值不够时，可以转为生成页。

C. 首版只允许批准，不允许拒绝和备注。

过轻，无法支持真实审查闭环。

建议选择：A。

用户选择：B。

确认结论：

- 首版审查操作包含：待审查、批准、拒绝、备注、替换来源、转生成页、锁定历史页。
- 这些操作只作用于当前页面，不能扩展成完整任务管理系统。
- 每个操作都必须写入事件日志，并更新 `preview_manifest.json` 或对应 run 状态文件。
- 替换来源必须从已有候选页中选择；首版不支持在 Web UI 里发起新检索。
- 转生成页会更新 sourcing decision，并创建或刷新对应 generation task。
- 锁定历史页会阻止后续自动决策覆盖该页来源，除非用户在 Agent 主会话中明确解锁。

### Q20：首次打开一个 run 时，用户先看到什么

A. 推荐：先看 Run 总览，再进入第一个阻断页或待审页。

有利于快速理解全局状态，但会多一层进入成本。

B. 直接进入第一页，像翻 PPT 一样审。

更符合 Deck 审查习惯。用户打开后马上看到成稿页面，顶部状态条和左侧页面列表负责提示风险与下一步。

C. 直接进入质量报告，先处理风险。

适合修复阶段，但不适合第一次判断 Deck 主线和整体观感。

建议选择：A。

用户选择：B。

确认结论：

- 首次打开 run 默认进入第一页。
- 如果用户上次在同一 run 停留过，优先恢复上次页面。
- 顶部状态条仍然显示 run 级健康状态、下一步、Draft Gate 和导出状态。
- 左侧页面列表必须显示阻断页和待审页标记，用户可以快速跳转。
- 不单独设置首屏总览页；总览信息应融入顶部状态条和左侧列表。

### Q21：视觉信息密度

A. 推荐：专业高密度审查界面，预览大、信息紧凑、状态清晰。

适合专业 Deck 审查场景。用户需要同时看页面、来源、证据、质量和审批状态。

B. 更像作品 Gallery，页面图最大化，文字信息收起来。

视觉展示更强，但不利于专业审查。

C. 更像后台表格，所有页面和状态以表格优先。

状态管理强，但页面视觉判断会变弱。

建议选择：A。

用户选择：A。

确认结论：

- UI 采用专业高密度审查界面。
- 页面预览仍是视觉中心，但不能牺牲来源、证据、质量风险和审批信息。
- 信息需要分层展示：高频判断直接可见，低频细节折叠或放到底部状态抽屉。
- 视觉风格应偏专业、克制、清晰，避免做成展示型 Gallery。

### Q22：高级页面操作放在哪里

A. 推荐：放在右侧审查面板的二级操作区，默认可见但不抢审批按钮。

这样能让专业用户快速干预页面来源，同时保持批准 / 拒绝是主动作。

B. 和批准 / 拒绝并列成主按钮。

操作很醒目，但会削弱审批动作的主次关系。

C. 收到底部抽屉，只在需要时展开。

界面更干净，但高级操作太难发现。

建议选择：A。

用户选择：A。

确认结论：

- 替换来源、转生成页、锁定历史页放在右侧审查面板的二级操作区。
- 二级操作区默认可见，但视觉权重低于审批按钮。
- 批准、拒绝、备注是页面审查主路径。
- 高级操作必须带清晰后果说明，避免用户误改 sourcing decision。

### Q23：页面列表的默认排序

A. 推荐：按 Deck 页码顺序，保留 PPT 阅读节奏。

这符合 Deck 审查习惯。用户可以按叙事顺序判断整份方案是否成立，同时通过筛选快速找到阻断页。

B. 阻断页优先，把问题页排到最前。

适合修复阶段，但会破坏阅读节奏。

C. 按来源类型分组，如 reuse / adapt / generate。

适合分析 sourcing 策略，但不适合默认审查。

建议选择：A。

用户选择：A。

确认结论：

- 左侧页面列表默认按 Deck 页码顺序排序。
- 阻断页、待审页、生成页通过筛选和标记处理，不改变默认顺序。
- 质量修复阶段可以提供筛选视图，但不改变默认阅读节奏。

### Q24：质量风险的视觉强度

A. 推荐：P0/P1 强提示，P2/P3 轻提示，避免满屏警告。

这能突出真正阻断交付的问题，同时避免用户对警告疲劳。

B. 所有质量问题都强提示。

风险可见性高，但会降低判断效率。

C. 质量问题默认折叠，只显示数量。

界面更干净，但关键风险容易被忽略。

建议选择：A。

用户选择：A。

确认结论：

- P0/P1 使用强提示，并影响顶部状态、页面列表和右侧审查面板。
- P2/P3 使用轻提示，默认显示数量和简短说明。
- 用户尝试批准 P0/P1 页面时必须显式确认。
- 质量风险的视觉层级要服务决策，不能制造满屏警告。

### Q25：Web UI 的视觉方向

A. 推荐：专业咨询审查台：高对比、克制、偏商务生产工具。

这符合 Deck Master 的第一用户和第一场景：专业方案 Deck 审查、质量判断和交付准备。

B. 创意工作室：更大画布、更强视觉氛围。

适合视觉探索，但会弱化审查效率。

C. 开发者控制台：更像运行状态和日志面板。

适合调试，但不适合专业 Deck 用户。

建议选择：A。

用户选择：A。

确认结论：

- Web UI 视觉方向是专业咨询审查台。
- 风格关键词：高对比、克制、清晰、商务、生产工具感。
- 不做创意工作室式的大氛围界面。
- 不做开发者控制台式的日志优先界面。

### Q26：双语实现范围

A. 推荐：首版只做中文 / 英文两套完整语言包，禁止同屏混排。

这能解决当前 UI 中中英文混杂的问题，也为后续开源或跨语言使用留出基础。

B. 先只做中文，后续再补英文。

速度更快，但会和已经确定的双语目标冲突。

C. 先保留当前混合文案，后续统一。

实现最快，但会延续当前设计问题。

建议选择：A。

用户选择：A。

确认结论：

- 首版实现中文和英文两套完整语言包。
- 默认语言跟随浏览器，用户显式切换后写入本地偏好。
- 同一屏不能出现中英文混排。
- 面向用户的按钮、标题、说明、空状态、错误提示必须来自语言包。
- 文件名、状态枚举、命令、artifact id 可以保留英文代码形态。

### Q27：移动端最低要求

A. 推荐：能查看和轻量审批，但不作为主场景优化。

能保留最低可用性，但会增加首版设计和测试负担。

B. 移动端也要完整可用，和桌面同等优先级。

范围明显变大，不符合当前专业审查主场景。

C. 首版不考虑移动端。

范围最清楚。Deck Master Web UI 首版聚焦 13 到 16 英寸桌面浏览器，移动端后续再设计。

建议选择：A。

用户选择：C。

确认结论：

- 首版只保证桌面浏览器体验。
- 主要设计目标屏幕是 13 到 16 英寸笔记本。
- 移动端不进入本轮验收范围。
- CSS 可以避免主动破坏窄屏，但不承诺移动端审查体验。

### Q28：Design Review 结束后的交接物

A. 推荐：输出确认版《Web UI Design Spec》，作为后续实现唯一依据。

这能把评审结论从讨论记录提升为可执行设计标准，避免实现时重新争论信息架构。

B. 直接进入实现，边做边改。

速度快，但容易回到当前 UI 的粗糙状态。

C. 先做高保真视觉稿，再写 Spec。

适合品牌视觉已经成熟的产品；当前更需要先锁定交互和信息架构。

建议选择：A。

用户选择：A。

确认结论：

- Design Review 后输出独立的《Web UI Design Spec》。
- 后续实现以该 Spec 为唯一设计依据。
- 评审日志保留决策过程，Design Spec 承载最终要求。
- 高保真视觉稿可以后续补，不阻塞下一轮工程方案评审。
- 已生成交接文档：`docs/2026-06-10-web-ui-design-spec.md`。

## 13. 中文线框 Spec v0.1

### 13.1 设计目标

Deck Master Web UI 的第一版设计目标：

> 让用户在浏览器里快速判断一次 Deck run 是否能继续、哪些页面需要处理、每页为什么这样组装、质量风险在哪里、哪些页面可以批准导出。

首屏必须回答 5 个问题：

1. 当前在看哪个 Workspace 和哪个 Run？
2. 这个 Run 现在处于什么阶段？
3. 下一步应该做什么？
4. 哪些页面阻塞交付或需要审查？
5. 当前页能否批准，风险在哪里？

首屏行为：

- 默认进入第一页。
- 同一 run 再次打开时，恢复用户上次查看的页面。
- 不设置独立总览页；总览信息融入顶部状态条、左侧页面列表和右侧当前页审查面板。
- 用户可以通过左侧筛选快速跳到阻断页、待审页、生成页和已批准页。

### 13.2 整体布局

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ 顶部状态条                                                                    │
│ Workspace | Run | 阶段 | 下一步 | Draft Gate | Build Skill | 导出 | 语言       │
├───────────────┬──────────────────────────────────────────────┬───────────────┤
│ 左侧导航       │ 中央预览                                      │ 右侧审查       │
│               │                                              │               │
│ Run 切换       │ 页码 / 章节 / 页面标题                         │ 页面职责       │
│ 页面筛选       │                                              │ 核心论点       │
│ 页面大纲       │ 当前页预览图                                  │ 来源决策       │
│ 状态计数       │                                              │ 证据状态       │
│               │ 上一页 / 下一页 / 全屏查看                       │ 质量发现       │
│               │                                              │ 审批 + 备注    │
├───────────────┴──────────────────────────────────────────────┴───────────────┤
│ 底部状态抽屉：事件日志 | Build Skill 步骤 | Artifact handback | Export queue     │
└──────────────────────────────────────────────────────────────────────────────┘
```

整体密度：

- 按专业高密度审查界面设计。
- 页面预览保持中心视觉权重。
- 来源、证据、质量风险和审批信息保持直接可见。
- 低频细节可以折叠，不能把关键风险折叠到用户难以发现的位置。

### 13.3 顶部状态条

目的：让用户先判断整个 run 是否健康。

信息顺序：

1. Workspace 名称。
2. Run 标题和 run id。
3. 当前阶段：`intake / planning / sourcing / building / draft_gate / review / export_ready`。
4. 下一步动作：例如“审查 3 页阻断项”“等待 Build Skill 完成”“运行 Draft Gate”。
5. Draft Gate 状态：`未运行 / 通过 / 有条件通过 / 需要返工`。
6. Build Skill 状态：`未开始 / 运行中 / 失败 / 完成`。
7. 导出状态：`不可导出 / 可导出 / 已导出`。
8. 语言切换：中文 / English。

设计要求：

- 状态必须短，不写长说明。
- 阻断状态必须比普通状态更显眼。
- 点击状态可以打开底部状态抽屉。

### 13.4 左侧导航

目的：让用户快速找到需要处理的页面。

模块：

- Run 切换：显示最近 run。
- 页面筛选：
  - 全部
  - 阻断
  - 待审查
  - 已批准
  - 已拒绝
- 页面大纲：
  - 页码
  - 页面标题
  - 页面角色
  - 来源类型
  - 审批状态
  - 质量标记

页面项显示：

```text
03  关键挑战
problem · reuse · 待审查 · 1 个质量风险
```

设计要求：

- 左侧不显示大段理由。
- 默认按 Deck 页码顺序排序。
- 阻断页、失败生成页、缺资产页要有明显标记。
- 30 到 60 页时仍能扫描。
- 阻断、待审查、生成、已批准作为筛选条件，不改变默认排序。

### 13.5 中央预览

目的：让用户判断页面视觉和内容是否可审查。

模块：

- 当前页标题。
- 页码和总页数。
- 章节上下文。
- 页面预览图。
- 上一页 / 下一页。
- 全屏查看。

设计要求：

- 预览图是视觉中心。
- 缺图时显示可恢复错误，不显示空白框。
- 页面加载中要有明确 skeleton 或 loading 状态。

### 13.6 右侧审查面板

目的：让用户判断当前页是否成立。

信息顺序：

1. 页面职责：这页承担什么角色。
2. 核心论点：这一页要证明什么。
3. 证据需求：需要什么证据。
4. 来源决策：reuse / adapt / generate / manual_placeholder。
5. 决策理由：为什么选这个来源。
6. 候选来源：历史 PPT、页码、置信度、截图状态。
7. 质量发现：严重级别、问题、修复建议。
8. 页面操作：替换来源 / 转生成页 / 锁定历史页。
9. 审批：待审查 / 已批准 / 已拒绝。
10. 备注。

审批区：

```text
审批状态
( ) 待审查
( ) 已批准
( ) 已拒绝

页面操作
[替换来源] [转生成页] [锁定历史页]

备注
[ 多行输入框 ]

[保存审批]
```

设计要求：

- 审批状态和备注永远在右侧底部可见。
- 质量 P0 / P1 问题要阻止误批准，至少需要显式确认。
- P0/P1 使用强提示，P2/P3 使用轻提示。
- 备注不承担复杂任务管理。
- 页面操作是二级操作，默认可见，但视觉权重低于审批按钮。
- 替换来源只能从当前页已有候选中选择。
- 转生成页必须显示生成任务是否已创建。
- 锁定历史页必须显示锁定状态和来源页。
- 页面操作要写回 run 状态，并在事件日志中可追踪。
- 页面操作必须显示后果说明，例如“转生成页会覆盖当前来源决策并刷新生成任务”。

### 13.7 底部状态抽屉

目的：让高级用户和 Agent 操作时能追踪执行过程。

默认收起。

Tabs：

- 事件日志。
- Build Skill 步骤。
- Artifact handback。
- Export queue。

设计要求：

- 默认不打扰普通审查。
- 失败时自动提示可展开。
- 只显示和当前 run 相关的信息。

### 13.8 状态覆盖表

| 功能 | 加载中 | 空状态 | 错误 | 成功 | 部分完成 |
|---|---|---|---|---|---|
| Workspace | 显示“正在读取工作区” | 提示创建或选择 Workspace | 显示路径和修复建议 | 显示 Workspace 名称 | 标记缺失配置文件 |
| Run 列表 | skeleton | 提示从 Agent 或 brief 创建 run | 显示 runs 目录读取失败 | 显示最近 run | 标记 pending run |
| 页面列表 | skeleton | 提示还没有 preview manifest | 显示 manifest 错误 | 显示页面 | 标记缺图、阻断、待生成 |
| 页面预览 | loading frame | 提示选择页面 | 显示缺资产路径和恢复建议 | 显示预览图 | 显示占位图和生成状态 |
| Build Skill | 运行中步骤 | 未开始 | 显示失败步骤和日志摘要 | 显示产物路径 | 显示部分页面完成 |
| Draft Gate | 正在检查 | 未运行 | 显示检查失败原因 | 显示通过 | 显示条件通过和修复建议 |
| 审批 | 保存中 | 待审查 | 保存失败可重试 | 保存成功 | 页面已审但 run 未完成 |
| 导出 | 正在生成 | 无批准页 | 导出失败 | 显示 approved_queue | 部分页可导出 |

### 13.9 移动端原则

移动端不进入首版验收范围。

首版原则：

- 只保证 13 到 16 英寸桌面浏览器体验。
- 窄屏不做主路径设计。
- 可以避免明显破版，但不承诺移动端审查体验。
- 移动端查看和轻量审批作为后续版本重新设计。

### 13.10 设计系统要求

下一轮实现前需要补：

- `DESIGN.md`
- `docs/design-tokens.json`
- `docs/design-tokens.css`

设计系统应包含：

- 颜色 token。
- 字体 token。
- 状态 token：success / warning / danger / blocked / pending。
- 严重级别 token：P0 / P1 / P2 / P3。
- 间距和圆角 token。
- 页面预览画布规则。
- 审批状态颜色规则。
- 质量严重级别颜色规则。
- 双语文案 key 命名规则。

视觉方向：

- 专业咨询审查台。
- 高对比、克制、清晰、商务、生产工具感。
- 页面预览是视觉中心，状态和审查信息服务判断效率。
- 避免创意工作室式装饰，也避免开发者控制台式日志优先。

### 13.11 设计验收标准

- 同一屏不能出现中英文混杂。
- 中文和英文两套语言包必须完整覆盖用户可见文案。
- 用户 5 秒内能判断 run 是否可继续。
- 用户 30 秒内能找到所有阻断页。
- 用户能在右侧面板理解当前页的来源、证据和质量风险。
- 首次打开 run 直接进入第一页。
- 同一 run 重新打开时恢复上次查看页面。
- 页面列表默认按 Deck 页码顺序排序。
- 审批状态只使用 `needs_review / approved / rejected`。
- 页面操作首版支持替换来源、转生成页、锁定历史页。
- 页面操作不能绕过 Draft Gate 阻断。
- 页面操作必须可撤销或可由 Agent 在下一步解释和恢复。
- Build Skill 失败必须可见。
- Draft Gate 阻断必须可见。
- 缺图、坏 manifest、生成失败都不能只显示技术错误。
- 首版验收只覆盖桌面浏览器，不覆盖移动端审查体验。
