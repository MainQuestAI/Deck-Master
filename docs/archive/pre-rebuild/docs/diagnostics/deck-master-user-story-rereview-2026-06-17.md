# Deck Master 用户故事复审

日期：2026-06-17  
对象：`docs/diagnostics/deck-master-current-implementation-user-story-2026-06-17.md`  
依据：当前仓库代码、当前本机安装状态、临时 HOME 新装验证、相关测试。

## 1. 总结论

原用户故事的大方向仍然成立：Deck Master 当前最适合定位为客户方案 Deck 的运行时和审查中枢，可以把 setup、workspace、run、主叙事、sourcing、生成任务、质量门禁、Review Cockpit、export 和反馈串成可追踪链路。

需要更新的地方有三类：

1. **安装链路已有明显改善。** 当前代码进入 v0.9.13，新增 Product Capability Suite，`setup --install-suite` 可以在新环境一次装齐 `deck-master`、`deck-planner`、`deck-review`、`ppt-master`、`ppt-library`、`ppt-deck-pro-max`、`ppt-quality-gate`。
2. **生成和渲染链路已有最小闭环。** 当前代码会优先发现 bundled `ppt-deck-pro-max` capability，`run-generation` 可产出占位 generation result，`render --format html --fixture-safe` 可写 canonical render result。
3. **真实产品体验仍有 P0 问题。** 本机实际 suite 仍 degraded；`start` 仍只展示 setup ready；主叙事仍依赖固定页型；PPT Library fixture fallback 仍会让用户误解候选来源；生成后质量门禁状态推进存在新阻断。

所以，当前产品叙事需要从“输入材料后得到最终 PPT”继续收紧为：

> 输入客户材料后，Deck Master 可以生成可审查草案、页面来源决策、生成任务、最小生成/渲染结果、质量状态和下一步动作。高质量最终 PPT 仍依赖外部能力质量、人工审查和状态闭环修复。

## 2. 原报告问题复审

| 原问题 | 当前判断 | 复审结论 |
|---|---|---|
| P0-1 Setup ready 与 suite ready 没有清晰区分 | 仍成立，但安装能力已改善 | `setup --install-suite` 新环境可 full ready；本机实际仍 degraded；`start` 仍没有包含 suite 摘要 |
| P0-2 active workspace 是全局状态 | 仍成立 | 代码有 request workspace 和 CLI conflict 检查，但新 production run 入口仍容易继承 setup active workspace |
| P0-3 主叙事偏模板化 | 仍成立 | `BASE_BEATS` 仍有固定零售页型；claim/judgment 只是增强字段，没有替代模板骨架 |
| P0-4 真实生成工具安装引导不足 | 部分改善 | bundled `ppt-deck-pro-max` 已减少 registry 阻断；本机 suite 冲突迁移仍会阻断生产 readiness |
| P0-5 PPT Library fixture fallback 不够显眼 | 仍成立 | `auto` 模式失败后 fallback fixture；selection 有 `source=fixture`，但 preview 主视图仍容易显示成普通 library slide |
| P1-1 质量状态容易被误读 | 升级为 P0 | 生成结果导入后 session 留在 `quality_required`，即使 draft gate pass，run-state 仍卡 `needs_draft_gate` |
| P1-2 Playbook 与 CLI 漂移 | 仍成立 | `codex-run-solution-deck.md` 仍写 `--context-dir`；handoff 文档仍写 one entry per generate page |

## 3. 已有改善

### 3.1 Suite 安装能力改善

当前代码新增了 `product-capability-manifest.json` 和 suite 安装路径。临时 HOME 验证结果：

- `setup --install-suite --target codex --target claude-code` 可完成。
- `full_suite_ready=true`。
- 所有 required skills 在临时 HOME 下 ready。
- task readiness 覆盖 planning、review、library_sourcing、new_generation、standalone_audit、render、delivery。

这说明原报告里“Companion suite 在本机降级”仍是本机状态事实，但已经不能代表当前代码能力上限。

### 3.2 Generation Session 改善

当前 `tool_registry.py` 会优先发现 bundled capability：

- `ppt-deck-pro-max` bundled capability 存在时，不再强依赖 `~/.deck-master/tools.json`。
- 临时 run 里 `generation-session create` 成功创建 8 个任务的 session。
- `run-generation` 成功执行 bundled placeholder generator。
- `generation_results/` 产出 8 个 result JSON。

需要明确：这只是最小生成占位路径，生成的 `slide.pptx` 和 `preview.png` 是 placeholder，不代表真实页面质量。

### 3.3 Render Path 改善

当前新增最小 PPT Master render path：

- `render --run-id <run_id> --format html --fixture-safe` 可生成 `rendered/index.html`。
- canonical render result 写入 `render_results/render_result.json`。

这让“渲染结果回写 Deck Master run”有了最小闭环，但当前 HTML 只是 fixture-safe 输出，不能等同于最终客户 PPT。

### 3.4 Review Cockpit 可见性改善

Review Cockpit 已经能看到：

- run-state
- deck readiness
- claim coverage
- next actions
- external results
- suite readiness
- quality blocking
- pending feedback
- export queue

原报告里“UI 偏运维审查面板”的判断仍成立，但状态可见性已经比早期版本更完整。

## 4. 仍存在的关键问题

### P0-1：`start` 仍会让用户误判完整可用

当前本机 `setup-status --include-suite` 显示：

- setup status：ready
- production_ready：true
- suite status：degraded_ready
- full_suite_ready：false
- next_command：`deck-master suite-repair --target codex --target claude-code`

但 `deck-master start` 输出仍是：

- status：ready
- production_ready：true
- next_command：`deck-master setup-status`

它没有把 suite degraded、blocked task readiness 和 suite repair action 放到首屏。对真实用户来说，这会造成“系统可生产”的误判。

建议：`start` 默认调用 `setup_status(..., include_suite=True)`，并把 `full_suite_ready=false` 时的 blocked capabilities 放到 first action。

### P0-2：本机安装与仓库代码存在状态差

仓库内 `skills/deck-master/SKILL.md` 已经推荐 `setup --install-suite`，但本机 Codex/Claude 仍指向旧 release 下的 `deck-master` skill；其他 suite skills 存在 missing、foreign symlink、real dir conflict。

这意味着产品层面需要一条清晰迁移路径：

- 识别 legacy real directory。
- 提供 dry-run migration plan。
- 用户确认后再替换或保留现有 skill。
- 修复后复查 `suite-status`。

### P0-3：主叙事仍被固定页型牵引

当前 `page_budget.py` 仍保留固定 `BASE_BEATS`，包含：

- 全渠道场景
- 库存可视化
- 最后一公里配送

`narrative_planner.py` 会补充 judgment、claim、evidence policy、workspace refs，但 page title 和主结构仍从固定模板开始。部分受限样本会过滤掉不合适页型，通用场景仍会继承模板。

产品影响：用户会感觉 Deck Master 在“套方案结构”，没有完全根据客户材料做主叙事判断。

建议：production path 中固定模板只作为 fallback。页面计划应优先来自 claim graph、conversation decisions、narrative advice 和 workspace archetypes。

### P0-4：PPT Library fallback 仍不够显眼

当前 `library-mode auto` 逻辑是：

- 能跑 `ppt-lib` 就调用真实检索。
- 真实检索失败且 mode 为 `auto` 时，写 warning event。
- 然后使用 fixture candidate。

虽然 `library_results/selection.json` 有 `source=fixture`，候选页也带 `fixture_` id 和 fixture source file，但 preview 页面主字段仍可能显示为 `library_slide`。产品用户很容易把 fixture 候选当作真实历史页。

建议：

- preview 页面增加显眼 badge：`真实库 / fixture / imported`。
- production run 下 `auto -> fixture` 需要明确确认。
- Review Cockpit 的 page detail 直接展示 candidate source 和 fallback warning。

### P0-5：生成后质量状态无法自然推进

临时完整链路暴露了一个新问题：

1. `generation-session create` 成功。
2. `run-generation` 成功。
3. `generation-session import-results` 后 session status 变成 `quality_required`。
4. `render` 成功。
5. `quality-gate draft_v2` pass。
6. `quality-gate draft` pass。
7. `run-state` 仍显示 stage=`needs_draft_gate`，blocked reason=`generation results require fresh quality gate`。

代码原因在 `run_state_resolver.py`：只要 generation session status 是 `quality_required`，就直接返回 `needs_draft_gate`，没有检查 draft gate 是否已经存在且不阻断。

产品影响：用户按系统提示跑完质量门禁后，系统仍要求重复跑同一个 gate，形成死循环感。

建议两条选一：

- `quality-gate draft/draft_v2` pass 后更新 `generation_session.json`，把 session status 改成 `preview_refreshed` 或 `quality_passed`。
- `run_state_resolver` 在看到 `quality_required` 时先检查 draft gate；如果 gate 存在且不阻断，继续进入 review 阶段。

### P1-1：最终 readiness 口径仍分散

`run_state` 已经把 render result 放进 readiness summary，但 stage 判定到 `ready_for_client_export` 前没有强制 render present。Review readiness 的 `export_ready` 只看 evidence、quality 和 approved pages，没有把 generation/render 完整性纳入判断。

建议：统一 final readiness 口径，至少包含：

- setup ready
- full suite ready 或当前任务必需 capability ready
- generation session complete/imported/quality passed
- render result present
- draft/evidence/confidentiality/brand/delivery gates clear
- all client pages approved

### P1-2：Playbook 漂移仍需先修

当前仍可见：

- `skills/deck-master/playbooks/codex-run-solution-deck.md` 使用 `--context-dir`，但 CLI 的 conversation path 是 `--context-file`。
- `skills/deck-master/playbooks/ppt-deck-pro-max-handoff.md` 写 “one entry per generate page”，实际 generation tasks 覆盖 `adapt` 和 `generate`。
- repo skill 已写 v0.9.13 flow，但 installed release skill 仍像旧版。

建议先修文档，成本低、收益高，可以减少 Agent 按错路径执行。

## 5. 用户故事应如何修正

建议把 PM 视角用户故事改成 7 步：

1. 用户选择当前客户 workspace，并执行 `setup --install-suite`。
2. 系统显示三层 readiness：基础 setup、当前任务能力、完整生产 suite。
3. 用户导入客户材料，系统创建 run、brief、claim map。
4. 系统生成可审查 narrative plan 和 page tasks，同时标出证据缺口。
5. 系统做 sourcing：真实历史页、fixture、generate、adapt 都必须清晰标识。
6. 系统执行 bundled 或外部 generation/render，并把结果回写 run。
7. 系统通过统一 final readiness 判断是否允许 export。

对外承诺建议：

> Deck Master 能把客户方案 Deck 的生产过程从材料、主叙事、页面来源、生成、质检、审查到导出放到一个可追踪 run 里。当前版本已经具备最小生成和渲染闭环，但最终交付质量仍取决于真实素材库、生成工具和人工审查闭环。

## 6. 建议的最小修复顺序

1. 修 `run_state_resolver` 的 `quality_required` 死循环：质量 gate 已 pass 时推进到 review。
2. 修 `start`：默认展示 suite readiness 和 blocked task readiness。
3. 修 playbook：`--context-file`、`adapt/generate`、v0.9.13 setup flow。
4. 在 preview 和 Review Cockpit 显示 fixture badge。
5. 增加 production run 创建前 workspace 确认。
6. 将固定 `BASE_BEATS` 降级成 fallback，优先使用 claim/advice 驱动的 page plan。

## 7. 验证记录

本轮复审执行过：

- 当前本机 `setup-status --include-suite`：setup ready，suite degraded，full_suite_ready=false。
- 当前本机 `start`：只显示 setup ready，没有 suite 摘要。
- 临时 HOME `setup --install-suite --target codex --target claude-code`：full_suite_ready=true。
- 临时 run：`start-conversation -> build-brief -> build-claim-map -> autoplan` 成功，生成 12 页 preview。
- 临时 run：`generation-session create` 成功，自动使用 bundled `ppt-deck-pro-max`。
- 临时 run：`run-generation` 成功，产出 8 个 generation result。
- 临时 run：`render --format html --fixture-safe` 成功，写入 canonical render result。
- 临时 run：`quality-gate draft_v2` 和 `quality-gate draft` 均 pass。
- 临时 run：质量 gate pass 后 `run-state` 仍卡 `needs_draft_gate`。
- 相关测试：`python3 -m unittest tests.test_skill_installation tests.test_generation_session_bridge tests.test_render_runtime tests.test_run_state_resolver`，61 tests passed。
