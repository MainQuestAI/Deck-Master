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

### DEV-002 — input_type 共享不作为硬冲突

- 日期：2026-06-24
- 发现任务：A1
- 事实：现有 `skills/manifest.json` 中 `page_tasks` 同时是 `deck-sourcing` 与 `deck-producer` 的 input_type，`generation_session` 同时是 `deck-producer` 与私有 `ppt-deck-pro-max` 的 input_type。这是基线既有、合法的设计——`skill_route` 由 runtime stage + input_type 联合消歧，不单凭 input_type。
- 决策：A1 loader 不把「input_type 共享」作为硬冲突；仍保留 skill name 重复、compat alias 冲突、stage order 重复作为硬错误。
- 影响：路由仍依赖 stage 消歧；A5 route 统一时复核该假设。
- 兼容：不破坏现有 manifest 与 skill_route 行为。
- 验证：`tests/test_skill_manifest.py` 27 passed；全量 863 passed。

## 任务进度

| 任务 | 状态 | 完成证据 |
|---|---|---|
| A0 | ✅ done | baseline-freeze.md，836 passed |
| A1 | ✅ done | manifest.py loader + 9 contracts + schema；27 新测试，863 passed |
| A2 | ✅ done | scripts/workflow/ (state/validator/fingerprint)；workflow_state.v1 schema；runtime_stage 桥接；21 新测试，884 passed |
| A3 | ✅ done | scripts/workflow/handoff.py (append-only prepare/accept/consume/reject/stale/supersede, idempotent, file lock, current 投影)；13 新测试，897 passed |
| A4 | ✅ done | scripts/workflow/approval.py + policy.py（绑定 handoff/fingerprint，accept/reject/revoke/stale，non-bypassable，final export 不可预授权）；17 新测试，914 passed |
| A5 | ✅ done | workflow CLI 组 (status/stages/handoff/approval/preauth)；manifest 驱动 route；四入口 current_skill_stage 一致；15 新测试，929 passed |
| B1 | ✅ done | questions.py + decisions.py（gap-only，required/assumption 区分，blocking 阻断 exit，answer 绑 input_fingerprint，stale 重现）；7 新测试，936 passed |
| B2 | ✅ done | scripts/sourcing/plan.py（per-page 6 类决策，authority/freshness/permission，coverage/approval_readiness，v1 安全迁移）；11 新测试 |
| B3 | ✅ done | scripts/production/page_package.py（customer_visible/internal_only 严格分区，leak 检测，claim/evidence/asset 绑定，index 覆盖，generation result 引用）；12 新测试，959 passed；DEV-003 跨仓库 bridge 待独立 PR |
| B4 | ✅ done | scripts/build/manifest.py（白名单投影，package/customer_payload hash，backend 契约版本校验，直接 preview 阻断，显式 legacy adapter）；12 新测试，971 passed |
| B5 | ✅ done | scripts/workflow/autopilot.py（5 模式，validate/action/exit/handoff 循环，approval 停，final export 永停，repair routing，evidence）；state.py 接 handoff；11 新测试，983 passed；DEV-004 |
| C1–C5 | ⏳ pending | — |

### DEV-003 — 跨仓库 PPT Deck Pro Max bridge 需独立 PR + 固定 SHA

- 日期：2026-06-24
- 发现任务：B3
- 事实：B3 要求「PPT Deck Pro Max bridge 对应分支」与 generation result 引用 page_package，但 PPT Deck Pro Max 是独立仓库（`MainQuestAI/PPT-Deck-Pro-Max`）。本轮只能在 Deck-Master 侧定义 bridge 契约接口（`generation_result_reference`），无法在单一 PR 内修改外部仓库并固定 SHA。
- 处理：Deck-Master 侧 page_package + generation_result_reference 已落地；跨仓库 bridge 适配留待独立 PR，落地后回填 SHA 到 capability lock。
- 兼容：不破坏现有 generation session 机制。
- 验证：`tests/test_page_package.py` 12 passed；全量 959 passed。

### DEV-004 — state.py 接入 handoff runtime（B5 集成所需，跨 A2 路径）

- 日期：2026-06-24
- 发现任务：B5
- 事实：A2 的 `WorkflowStateResolver` 仅按 artifact 推导阶段完成，不感知 handoff；导致 B5 autopilot 在 accept/consume 高影响阶段 handoff 后，state 仍标记 awaiting_approval，无法推进 ladder。
- 处理：给 `WorkflowStateResolver` 增加可选 `handoff_runtime` 注入；当某阶段存在 accepted/consumed handoff 时标记 COMPLETED。默认不注入时行为与 A2 一致（向后兼容）。同时修正 `fingerprint_set` 使其与路径无关（只 hash 内容），并让 staleness 排除 `workflow/` 自身运行时记录与本阶段输出，避免误判 stale。
- 影响：state.py（A2 路径）被修改；属 B5 必需集成，已在此登记。A2 原测试全绿（无 handoff 注入分支不变）。
- 兼容：向后兼容；handoff_runtime=None 时行为不变。
- 验证：`test_workflow_autopilot_v2.py` 11 passed + A2-A4+B1 全绿；全量 983 passed。

| C1 | ✅ done | workspace_api skill_os_projection（9-stage 安全展示，blocker/awaiting 区分，stale 原因，accept/reject 写 runtime，无 raw path）；server /api/skill-os；9 新测试 |
| C2 | ✅ done | scripts/skills/validator.py + 18 SKILL.md 契约附录；100% public 合规；8 新测试 |
| C3 | ✅ done | scripts/workflow/migration.py（legacy bootstrap 不伪造审批，回滚，inference report）；docs/migration/；8 新测试 |
| C4 | ✅ done | tests/test_skill_os_release_contract.py（9 schema 真校验 + contracts hash + smoke 流水线）；CI 增 pytest+jsonschema 步骤；docs/releases/v1.1.0 |
| C5 | ✅ done | docs/qa/skill-os/（acceptance-matrix + dogfood-summary）+ test_skill_os_acceptance.py（量化指标断言）；clean-install dogfood 待 1.1.0 release 重建（DEV-001） |
