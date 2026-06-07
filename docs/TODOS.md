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
