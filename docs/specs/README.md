# Deck Master v0.9.5 - v0.9.11 Spec Pack

本包包含 6 份连续开发 Spec，已按 Deck Master v0.9.x 到 v1.0.0 RC 的顺序组织：

1. `deck-master-v0.9.5-review-cockpit-frontend-spec.md`
   - 目标：把 v0.9 已完成的 F1/F2/F3 后端 API 收成可持续使用的 localhost Review Cockpit 前端体验。

2. `deck-master-v0.9.6-companion-tool-uat-spec.md`
   - 目标：验证 Deck Master 与 PPT Library / PPT Deck Pro Max / PPT Master 的真实交接质量，输出 UAT reports 和 real workflow smoke。

3. `deck-master-v0.9.7-benchmark-harness-spec.md`
   - 目标：建立 benchmark case / runner / report / checkpoint 机制，为 v1.0.0 RC 真实 10x readiness 验证做准备。

4. `deck-master-v0.9.9-installation-chain-hardening-spec.md`
   - 目标：固定真实用户安装链路，确保 Deck Master 安装源位于 `~/.deck-master/current`，Agent skill 目录只保留入口软链接。

5. `deck-master-v0.9.10-first-run-orchestration-enforcement-spec.md`
   - 目标：补齐首次 Setup 引导、真实 run 门禁、顶部编排器约束、人工规划回写和外部工具 handback 登记。

6. `deck-master-v0.9.11-orchestration-runtime-realignment-spec.md`
   - 目标：重对齐 Deck Master 主控运行时，统一 run mode、setup/workspace/run state、workspace-bound request、Planner guard、sourcing 回写、tool registry、production session 和 benchmark gate。

`v0.9.11` 本轮补齐点：

- 真实生产链路先走 `setup-status / setup / bind-workspace / run-state`，再进入 `start-conversation` 等编排命令。
- benchmark 报表分成常规 `benchmark-report` 与 RC 用 `benchmark-rc-report`。
- fixture benchmark 案例在创建时走 `run_mode=fixture`，不会被纳入 v1.0 RC 判断。
- 文档优先说明 Deck Master 为顶层运行时，外部工具产物统一回写。

发布说明：

- `docs/2026-06-16-v0.9.11-wave2-release-note.md`

推荐落库路径：

```text
docs/specs/README.md
docs/specs/deck-master-v0.9.5-review-cockpit-frontend-spec.md
docs/specs/deck-master-v0.9.6-companion-tool-uat-spec.md
docs/specs/deck-master-v0.9.7-benchmark-harness-spec.md
docs/specs/deck-master-v0.9.9-installation-chain-hardening-spec.md
docs/specs/deck-master-v0.9.10-first-run-orchestration-enforcement-spec.md
docs/specs/deck-master-v0.9.11-orchestration-runtime-realignment-spec.md
```

推荐开发顺序：

```text
v0.9.5 Review Cockpit Frontend
→ v0.9.6 Companion Tool UAT
→ v0.9.7 Benchmark Harness
→ v0.9.9 Installation Chain Hardening
→ v0.9.10 First-Run Setup + Orchestration Enforcement
→ v0.9.11 Orchestration Runtime Realignment
→ v1.0.0 RC Real Benchmark Runs
```
