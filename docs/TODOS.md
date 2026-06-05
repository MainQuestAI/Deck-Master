# Status — Deck Master

Implementation status for the Deck Master orchestration layer.

## Deck Master 编排层
- **Why:** 三项目架构中的编排层——单入口，整合 PPT Library（搜索）和 PPT Deck Pro Max（生成），实现叙事驱动的 Deck 组装。
- **Pros:** 用户只需一个入口，叙事弧线→缺口识别→搜索→组装全链路自动化
- **Cons:** 真实搜索和真实生成接入仍依赖 PPT Library V1 与 PPT Deck Pro Max 稳定。
- **Context:** MVP 已在 `codex/web-preview-ui` 分支落地：组装计划 JSON 可以生成 `runs/<run_id>/preview_manifest.json`，Web UI 可审查并回写审批状态，`export_queue.py` 可导出确认后的页面队列；外部工具适配器已覆盖 PPT Library JSON 与 PPT Deck Pro Max 页面截图。详见 `docs/2026-06-06-deck-master-orchestration-mvp.md` 与 `docs/2026-06-06-external-tool-adapters.md`。
- **Depends on:** 生产接入时仍需先由 PPT Library 产出搜索 JSON，PPT Deck Pro Max 产出页面截图。

## Web 预览 UI
- **Why:** Deck Master 需要在导出前预览组装效果，先审查页面来源、顺序、叙事连贯性和复用合理性。
- **Pros:** 用户可以在浏览器中确认草案，减少直接导出后再返工的成本。
- **Cons:** 需要维护一次组装任务的运行时状态、资源引用和断链处理。
- **Context:** MVP 已在 `codex/web-preview-ui` 分支落地，提供本地三栏预览、manifest 读取、页面资源预览、状态/备注回写和 sample run。详见 `docs/2026-05-28-deck-master-web-preview-ui.md` 与 `docs/2026-06-01-web-preview-ui-implementation-plan.md`。
- **Depends on:** 生产接入时仍需先由 PPT Library 和 PPT Deck Pro Max 生成可被适配器消费的产物。

## Slide 胜率追踪与反馈闭环
- **Why:** CEO Plan 10x Check #3——每页 slide 记录被用过的 Deal、赢/输结果，搜索排序 = 语义相似度 × 实战胜率。
- **Pros:** 搜索从"语义匹配"升级为"实战验证"，结果排序更有业务含义
- **Cons:** 需要手动或半自动记录 slide 使用和 deal 结果，数据积累需要时间
- **Context:** 本地 MVP 已在 `codex/web-preview-ui` 分支落地：基于审批队列记录 Deal 赢/输结果，并统计每个 slide 的使用次数、赢单次数、输单次数和胜率。详见 `docs/2026-06-06-slide-win-rate-feedback-mvp.md`。
- **Depends on:** 后续写回搜索排序仍依赖 PPT Library 提供稳定 slide id 与 metadata 写回入口。
