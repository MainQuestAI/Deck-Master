# TODOS — Deck Master

Deferred work for the Deck Master orchestration layer.

## Deck Master 编排层
- **Why:** 三项目架构中的编排层——单入口，整合 PPT Library（搜索）和 PPT Deck Pro Max（生成），实现叙事驱动的 Deck 组装。
- **Pros:** 用户只需一个入口，叙事弧线→缺口识别→搜索→组装全链路自动化
- **Cons:** 依赖 PPT Library V1 和 PPT Deck Pro Max 都稳定，过早做编排会因下游变化而频繁重构
- **Context:** 当前两个子项目独立运行，Agent 手动编排。Deck Master 的价值在子项目稳定后才会显现。
- **Depends on:** PPT Library V1 完成 + PPT Deck Pro Max 稳定

## Slide 胜率追踪与反馈闭环
- **Why:** CEO Plan 10x Check #3——每页 slide 记录被用过的 Deal、赢/输结果，搜索排序 = 语义相似度 × 实战胜率。
- **Pros:** 搜索从"语义匹配"升级为"实战验证"，结果排序更有业务含义
- **Cons:** 需要手动或半自动记录 slide 使用和 deal 结果，数据积累需要时间
- **Context:** slides 表 metadata_json 已预留扩展点。Deck Master 未来可写入胜率数据。
- **Depends on:** Deck Master 编排层
