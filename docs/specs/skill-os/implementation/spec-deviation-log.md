# Skill OS Runtime v1.1 — Spec Deviation Log

本文件记录本轮迭代相对 spec pack（`docs/specs/skill-os-runtime-v1.1/`）的任何偏离，以及任务中超出「允许修改路径」的改动。任何超出路径的修改必须先在本文件登记：原因、影响、兼容、验证。

## 红线（非绕行规则，来自 master spec 与 LOCAL_ADOPTION §7）

- A1 完成前，不新增独立 route / next-step 真源。
- A3 完成前，不让下游阶段直接消费上游产物。
- A4 完成前，不改造 Autopilot 跨越高影响阶段。
- B3 完成前，不让 Builder 把 `page_package.v1` 当正式输入。
- B4 完成前，不允许 Builder 读取 `internal_only` 字段进入客户文件。
- C4 完成前，不宣称 v1.1 ready。
- `review → client export` 永远需要显式确认（不可预授权）。

## 偏差登记

### DEV-001 — 本机活动安装未指向基线 SHA

- 日期：2026-06-24
- 发现任务：A0
- 事实：`~/.deck-master/current` 为 `1.0.0` self-contained release，`built_at 2026-06-23T09:32:32`，早于基线 commit `4605213`（PR #9，2026-06-24 13:29 +0800）。`deck_capability_lock.json.source.git_head = null`（安装树非 git repo）。
- 影响：仅在端到端安装侧验收（clean install / dogfood，C5）有效；Stack A/B 的代码与单测不受影响。
- 处理：C4 重新构建并激活 `1.1.0` release 前不进行本地 dogfood 验收；C5 以新构建的 1.1.0 树为准。
- 兼容：不破坏现有 1.0.0 运行。
- 验证：A0 全量测试 836 passed；C5 clean install / dogfood 阶段复核 SHA。

## 任务进度

| 任务 | 状态 | 完成证据 |
|---|---|---|
| A0 | ✅ done | baseline-freeze.md，836 passed |
| A1 | ⏳ pending | — |
| A2 | ⏳ pending | — |
| A3 | ⏳ pending | — |
| A4 | ⏳ pending | — |
| A5 | ⏳ pending | — |
| B1–B5 | ⏳ pending | — |
| C1–C5 | ⏳ pending | — |
