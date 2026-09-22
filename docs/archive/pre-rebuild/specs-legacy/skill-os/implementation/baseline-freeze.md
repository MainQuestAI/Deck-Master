# Skill OS Runtime v1.1 — Baseline & Version Freeze (A0)

任务：A0 — Baseline & Version Freeze
分支：`feat/skill-os-runtime-v1.1`
工作区：`<deck-master-skill-os-worktree>`
记录日期：2026-06-24

## 1. main / release / suite / contract 基线

| 项目 | 值 |
|---|---|
| main HEAD（本轮基线） | `4605213f1ee3ba937e4658855582c7517b5af027` (Merge PR #9 codex/deck-master-review-desk-ui, 2026-06-24 13:29 +0800) |
| 前一关键合并 | PR #8 `98101c212bae9c4461ce2c5448808a3dbec27138`（v1 Skill Suite Runtime） |
| 本轮迭代分支 | `feat/skill-os-runtime-v1.1`（基线吸收 commit `30e9da7`） |
| Skill Suite 版本 | 现状 `1.0.0`（`skills/manifest.json`），目标统一映射到 `1.1.0` |
| Conformance 版本 | `1.0.0` → 目标 `1.1.0` |
| Runtime 目标版本 | `1.1.0`（master spec 00 §0） |
| Review Desk | v0.3 已合入 main（PR #9） |

## 2. 版本映射（无歧义口径）

本轮所有「1.1.0」指同一对象：

- `skills/manifest.json` `version` → `1.1.0`
- `skills/manifest.json` `conformance_version` → `1.1.0`
- `deck_capability_lock.json` `suite_version` → `1.1.0`（安装侧，升级后生效）
- `release-manifest.json` `suite_version` → `1.1.0`（发布侧）
- Spec / 文档口径：Skill Suite / Runtime `1.1.0`

C4 完成前不得宣称 `1.1.0 ready`（非绕行规则）。

## 3. 兼容命令与 schema 真源

### 3.1 兼容入口（manifest `compat_aliases`，全部 public）

| 公开 Skill | compat alias | 来源阶段 |
|---|---|---|
| deck-init | `init-workspace` | workspace init |
| deck-brief | `build-brief` | briefing |
| deck-planner | `autoplan` | planning |
| deck-sourcing | `ppt-library` | sourcing |
| deck-producer | `ppt-deck-pro-max` | production |
| deck-builder | `ppt-master`, `render` | build |
| deck-quality | `ppt-quality-gate` | quality |
| deck-review | `export`, `final-readiness` | review/export |
| deck-learn | `build-learning-pack` | learning |
| deck-autopilot | `autopilot-v1` | orchestrator |

兼容 `ppt-*` 入口（D15）：`ppt-library`、`ppt-deck-pro-max`、`ppt-master`、`ppt-quality-gate` —— v1.x 保留，必须映射到公开 Stage 并遵守同一 Handoff / Artifact Contract（C3 处理）。

### 3.2 Skill identity 真源

- `skills/manifest.json`（14 个公开 `deck-*` + 上述 compat alias）—— 唯一 Skill identity 真源（D4）。
- A1 起 Runtime / Installer / Route Resolver / Release Builder 全部读同一 Manifest。

### 3.3 现有 schema 真源（事实层，不在本轮 spec pack 内）

`docs/contracts/`：`generation-result.v2`、`final-readiness.v1`、`artifact-manifest.v1`、`benchmark-aggregate-report.v1`、`build-manifest.v1`、`ppt-library-selection.v1`、`quality-findings.v1`、`generation-result.v1`、`customer-visible-safety-gate.v1`、`setup-status.v2`、`artifact-validation.v1`、`rc-gate-report.v1`、`render-result.v2`、`final-version-lineage.v1`、`companion-manifest.v2`。

本轮新增契约 schema（来自 spec pack `schemas/`，A 阶段起逐步落地为运行时真源）：`deck_stage_contract.v1`、`deck_workflow_state.v1`、`deck_skill_handoff.v1`、`deck_stage_approval.v1`、`deck_workflow_policy.v1`、`deck_decision_record.v1`、`deck_sourcing_plan.v2`、`deck_page_package.v1`、`deck_build_manifest.v2`。

### 3.4 现有 Runtime 真源（A5 统一的对象）

- `scripts/runtime/skill_route.py`（Runtime stage + input type → public skill）
- `scripts/runtime/run_state_resolver.py`（输出 `recommended_skill` / `skill_stage` / `skill_route`）
- `scripts/runtime/run_state.py`
- `scripts/runtime/next_step.py`
- `scripts/runtime/orchestration.py`（autopilot v1，对应 `deck-autopilot` / `autopilot-v1`）
- `scripts/runtime/artifact_validator.py`、`final_readiness.py`、`rc_gate.py`、`builder_backend.py`、`build.py`、`render.py`

A5 要求：`run-state`、`next-step`、`route-skill`、`workflow status` 返回同一 Stage 解析结果（单一 state resolver 真源）。

## 4. 本机外部能力路径（脱敏事实）

| 能力 | 状态 |
|---|---|
| `~/.deck-master/current` | 指向本地安装的 self-contained release tree（`1.0.0`，`built_at 2026-06-23T09:32:32`） |
| 安装根 | `~/.deck-master`，`active_workspace` = 本机测试工作区（路径已脱敏，记录于 `~/.deck-master/config.json`） |
| Codex skill links | `~/.codex/skills/deck-*` → `~/.deck-master/current/skills/deck-*`（已链接 deck-master/setup/upgrade/doctor/init/brief/planner/sourcing/producer/builder/quality/learn/autopilot） |
| Claude Code skill links | `~/.claude/skills` 含 deck-master/deck-planner/deck-review/ppt-deck-pro-max（部分链接） |
| Review Cockpit URL | `http://127.0.0.1:5050`（配置口径，本机服务） |
| Python 测试环境 | worktree 独立 `.venv`（Python 3.14.5，pytest 9.1.1，jsonschema 4.26.0）；主仓 `.venv` 无 pytest |

PPT Master / PPT Library / PPT Deck Pro Max 的具体安装路径与版本不在本机 `current` 树内可读，按 gap register §4 口径不臆测填写，C5 dogfood 前再以实际核验结果补充。

## 5. 基线测试结果（不得掩盖失败）

- 命令：`python -m pytest -q`
- 结果：**836 passed, 38 subtests passed（17.39s），0 failed**
- `git diff --check`：clean
- JSON / Markdown：spec pack 19 个 JSON 全部可解析（spec pack `validation-report.json errors: []`）

## 6. 已识别偏差（初始 deviation）

详见 `spec-deviation-log.md` DEV-001：本机已装 `~/.deck-master/current`（1.0.0，构建于 2026-06-23T09:32）**早于**本轮基线 commit `4605213`（PR #9，2026-06-24 13:29）。即本地活动安装未指向基线 SHA，且 `deck_capability_lock.json` 的 `source.git_head` 为 `null`（安装树非 git repo，无法直接回溯 SHA）。

影响：在本地进行 dogfood / clean-install 验收（C5）前，需要先重新构建并激活 1.1.0 release，否则验收的是旧 1.0.0 树。该偏差不影响 Stack A/B 的代码与单测，仅影响端到端安装侧验收。

## 7. 成功标准（A0）

- ✅ 后续任务拥有唯一基线（main `4605213`，分支 `feat/skill-os-runtime-v1.1`）
- ✅ 版本映射无歧义（统一 `1.1.0` 口径）
- ✅ 兼容命令与 schema 真源已列出
- ✅ 本机能力路径只写脱敏事实
- ✅ deviation log 已建立
- ✅ 全量测试结果如实记录

## 8. 未完成项 / 风险

- DEV-001（见上 §6）。
- spec pack JSON Schema 二次校验未独立执行（本机已具备 jsonschema，A1 起对接 schema 校验时补）。
