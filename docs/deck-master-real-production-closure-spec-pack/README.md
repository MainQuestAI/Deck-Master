# Deck Master Real Production Closure Spec Pack

**迭代名称**：Real Production Closure
**规划版本**：v0.9.14 → v0.9.15 → v0.9.16
**主仓基线**：`MainQuestAI/Deck-Master origin/main @ 14fc43dc6e955928100f02f0e82af5b833c29177`
**状态**：待开发基线包
**最终目标**：把 Deck Master 从“可追踪的方案生产运行时”收口为“可以产出真实、可验证、可交付 Deck 的专家型 Private Beta / v1.0 RC 候选”。

## 一、这轮只解决什么

这轮只解决四件事：

1. **真实生产**：Production Run 不再由 placeholder generator 冒充完成。
2. **真实构建与渲染**：形成 HTML、PDF、PPTX 和逐页预览等真实产物。
3. **状态可信**：任何 `completed / ready / deliverable` 都必须由可解析、未过期、来源一致的真实 artifact 支撑。
4. **可发行、可证明**：release tree 自包含，并用真实案例 benchmark 证明效率和质量。

本轮不继续增加新的 P5 团队模块、Connector、Dashboard、行业模板或更多独立 Gate。

## 二、包内文件

| 路径 | 用途 |
|---|---|
| `00-master-spec.md` | 总目标、硬决策、范围、状态机与最终验收 |
| `01-baseline-gap-register.md` | 当前版本事实、Gap 与阻断项 |
| `02-cross-repo-contracts.md` | Deck Master、PPT Deck Pro Max、PPT Library、PPT Master 的边界 |
| `stacks/` | 三个顺序开发 Stack |
| `tasks/` | 16 个可直接交给 Agent 的任务 Spec |
| `schemas/` | 下一轮 canonical contract JSON Schema |
| `acceptance/` | QA、RC、真实 benchmark 的验收文件 |
| `agents/` | Codex / Claude Code 执行协议、提示词与评审协议 |
| `combined-spec.md` | 便于通读的一体化版本 |

## 三、建议执行顺序

```text
A0
 └─ A1
     ├─ A2（PPT-Deck-Pro-Max）
     ├─ A3（Deck Master Agent handoff/handback）
     └─ A4（PPT Master build/render）
          └─ A5（主链路与工作台）

B1
 ├─ B2
 ├─ B3
 └─ B4
     └─ B5

C1
 ├─ C2
 ├─ C3
 └─ C4
     └─ C5
```

Stack A、B、C 必须按顺序合并。单个 Stack 内允许并行，但 canonical schema 与状态语义必须先冻结。

## 四、开发完成后的产品口径

允许对外表述：

> Deck Master 可以在本地 Agent 工作流中，把客户材料、方案规划、历史资产、页面生产、构建渲染、质量审查、人工决策和交付产物统一到一个可追踪 Run，并对真实产物做可验证的交付判断。

不允许表述：

- “无人工即可稳定生成所有高质量 PPT”；
- “所有 PPTX 都是原生可编辑”；
- “已达到企业多人在线协作产品”；
- “已通过 10× 效率验证”，除非真实 benchmark 达到本包门槛。
