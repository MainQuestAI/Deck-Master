# Deck Master v0.9.12 Skill Suite Runtime - Stack Spec Pack

本包把当前 v0.9.12 大轮次拆成三个连续 Stack：

1. **Stack A / v0.9.12a：Suite Runtime Foundation**
   - 安装、manifest、capability readiness、first-run setup、routing guard。
2. **Stack B / v0.9.12b：Companion Workflow Contracts**
   - PPT Library read-only adapter、PPT Quality Gate structured import、PPT Deck Pro Max dry-run handoff；复用现有 CLI 和 run artifact，避免平行链路。
3. **Stack C / v0.9.12c：Production Closure & Governance**
   - feedback event queue、Review Cockpit 状态收口、E2E suite QA、release hardening；真实写回只作为显式实验能力。

推荐按 A -> B -> C 顺序开发。A 是阻断项；B 是主集成；C 是业务闭环与发布收口。
