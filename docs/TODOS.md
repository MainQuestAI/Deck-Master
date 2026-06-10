# Status — Deck Master

Implementation status for the Deck Master orchestration layer.

## Deck Master 编排层
- **Why:** 三项目架构中的编排层——单入口，整合 PPT Library（搜索）和 PPT Deck Pro Max（生成），实现叙事驱动的 Deck 组装。
- **Pros:** 用户只需一个入口，叙事弧线→缺口识别→搜索→组装全链路自动化
- **Cons:** 真实搜索和真实生成接入仍依赖 PPT Library V1 与 PPT Deck Pro Max 稳定。
- **Context:** vNext 已在 `codex/web-preview-ui` 分支落地：`scripts/deck_master.py autoplan` 可以从用户 brief 创建 run；Studio 模式可以直接在网页里输入需求并生成草案。系统会生成 `request.json`、`narrative_plan.json`、`library_results/selection.json`、`sourcing_plan.json`、`generation_tasks/index.json` 和 `preview_manifest.json`。详见 `docs/2026-06-06-demand-to-preview-autoplan.md`。
- **Depends on:** 真实生产检索仍依赖 PPT Library CLI 和索引状态；PPT Library 不可用时会降级为 fixture 候选，保证流程可审查。

## Web 预览 UI
- **Why:** Deck Master 需要在导出前预览组装效果，先审查页面来源、顺序、叙事连贯性和复用合理性。
- **Pros:** 用户可以在浏览器中确认草案，减少直接导出后再返工的成本。
- **Cons:** 需要维护一次组装任务的运行时状态、资源引用和断链处理。
- **Context:** Preview UI 已支持 Studio 首页、run 列表、网页创建草案、来源决策、决策理由、候选页、风险标记和生成任务，同时保留原有页面预览、状态/备注回写和 sample run。详见 `docs/2026-05-28-deck-master-web-preview-ui.md`、`docs/2026-06-01-web-preview-ui-implementation-plan.md` 与 `docs/2026-06-06-demand-to-preview-autoplan.md`。
- **Depends on:** 生成页真实图片仍依赖 PPT Deck Pro Max 后续执行；未生成前会显示 Deck Master 占位预览。

## Slide 胜率追踪与反馈闭环
- **Why:** CEO Plan 10x Check #3——每页 slide 记录被用过的 Deal、赢/输结果，搜索排序 = 语义相似度 × 实战胜率。
- **Pros:** 搜索从"语义匹配"升级为"实战验证"，结果排序更有业务含义
- **Cons:** 需要手动或半自动记录 slide 使用和 deal 结果，数据积累需要时间
- **Context:** 本地 MVP 已在 `codex/web-preview-ui` 分支落地：基于审批队列记录 Deal 赢/输结果，并统计每个 slide 的使用次数、赢单次数、输单次数和胜率。详见 `docs/2026-06-06-slide-win-rate-feedback-mvp.md`。
- **Depends on:** 后续写回搜索排序仍依赖 PPT Library 提供稳定 slide id 与 metadata 写回入口。

## Deck Workspace 与质量门禁
- **Why:** Deck Master 下一阶段需要从一次性 autoplan 升级为长期可复用的 Deck 生产运行时，统一管理工作区、视觉规范、页面原型、质量标准、审批和反馈闭环。
- **Pros:** 用户可以围绕一个品牌或客户持续生产 Deck，减少重复定义模板、页面结构和验收规则的成本。
- **Cons:** 需要新增 workspace manifest、质量报告、页面原型读取和更多 UI 状态，实施面比单次 preview 更大。
- **Context:** 方案已整理为 vNext 实施文档，核心是 `Deck Workspace + Quality Gate + Runtime-first orchestration`。Quality Gate 已升级为 Deck Master 内建子系统，首版支持 Draft/Render/Delivery 三段报告。详见 `docs/deck-master-vnext-workspace-quality-gate-plan.md` 与 `docs/2026-06-10-built-in-quality-gate.md`。
- **Depends on:** 当前 autoplan/runtime/preview 基础能力；PPT Library 候选检索；PPT Deck Pro Max、PPT Master、Guizang 等生成与渲染工具的任务交接。

## 专业 Deck 对话生产运行时
- **Why:** Deck Master 的 10x 目标是把专业客户方案 Deck 从高注意力手工成片，压缩成“本地资料 + AI 引导式对话 + 可审查草案”的生产链路。
- **Pros:** 用户可以把精力放在业务判断、论点取舍和证据组织上，Deck Master 负责上下文引用、论点编译、页面规划、历史页检索、预览和 Draft Gate。
- **Cons:** 首版只支持本地/已导出资料，不实时拉取飞书，也不依赖 OpenViking 在线查询。
- **Context:** 本地上下文到 preview 的首版链路已实现：`start-conversation`、`build-brief`、`build-claim-map`、`autoplan --run-id` 和 `quality-gate draft`。详见 `docs/2026-06-10-guided-conversation-runtime.md`。
- **Depends on:** 后续如果要接实时飞书、OpenViking 或语音入口，需要先稳定 context source 契约和客户敏感资料边界。

## Professional Deck Run OS
- **Why:** Office Hour 已确认下一阶段产品路线：服务售前解决方案架构师，把会后客户上下文、历史方案资产和业务判断转成可审查客户 Solution Deck 草案。
- **Pros:** 目标从泛泛“提升做 Deck 效率”收敛为约 12 小时到约 2 小时的硬指标，并把上下文、对话、论点、页面、来源、预览、质量门禁和审批纳入一次 run。
- **Cons:** `Run OS` 容易过早平台化，下一轮 CEO Review 需要严格控制首版范围，避免一次性扩到资产系统、实时知识库和完整视觉自动化。
- **Context:** Office Hour 结论已落盘为 `docs/2026-06-10-office-hour-run-os.md`，顶层规划稿已升级为 `Professional Deck Run OS` 基线。首版切口是会后客户 Solution Deck 草案。
- **Depends on:** 下一轮 `plan-ceo-review` 需要确认 2 小时目标、最窄可赢切口、首版运行时对象和真实客户项目回归样本。

## 顶层产品规划设计稿
- **Why:** 当前实现已经有原型链路，但 Deck Master 的顶层产品定位、专业用户场景、规划评审问题和后续实现优先级仍需要单独沉淀。
- **Pros:** 顶层设计稿已吸收 Office Hour 结论，明确第一用户、第一场景、12h→2h 指标和 `Run OS` 路线。
- **Cons:** 该文档仍是 CEO Review 输入，不是最终工程 spec。
- **Context:** 顶层设计稿已更新为 `Professional Deck Run OS` 基线，覆盖用户表达、真实场景、产品定位、能力模块、当前缺口和下一轮评审问题。详见 `docs/deck-master-top-level-product-design-draft.md`。
- **Depends on:** 下一轮规划评审确认 `Run OS` 是否过早平台化、首版最小运行时对象、Draft Gate 标准和真实项目验收方式。
