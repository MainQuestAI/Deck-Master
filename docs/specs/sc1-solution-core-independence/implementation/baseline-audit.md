# SC-1 Q0｜基线审计（baseline-audit）

- 执行日期：2026-09-07
- 执行环境：macOS arm64（darwin 25.6.0），Python 3.12 venv（系统默认 3.14 不在 `requires-python >=3.11,<3.14` 范围内，已按 AGENTS 惯例改用 3.12）
- 工作树：`.claude/worktrees/sc1-solution-core`，分支 `codex/sc1-solution-core`

## 1. 源码基线核对

| 项 | 值 |
|---|---|
| 工作树 HEAD | `bcb5b37a4e32b5b98b063ec31e745a8ce017c8f1` |
| origin/main | `bcb5b37a4e32b5b98b063ec31e745a8ce017c8f1`（与 HEAD 一致） |
| 规格基线 | `4199a6a8cc17ac522e074fee95bc114d4e274849`（PR #29 合并点） |
| 基线→HEAD 差异 | 仅 2 个 spec pack 文档提交（`534adf4` 落库、`bcb5b37` 审查修订），**无代码差异** |
| 未提交修改 | 开工时工作树干净，无需保护 |
| 本轮新增本地状态 | 新建 `.venv`（Python 3.12）并 `pip install -e ".[dev]"`；`.venv` 未入库 |

结论：规格包声明的基线与本地实际一致，主分支未前移，无差异表需要提交。

## 2. 现有测试命令与结果

```text
.venv/bin/python -m pytest tests/ -q
→ 1490 passed, 119 subtests passed in 926.95s (0:15:26)
```

- 121 个测试文件，全部通过，**无红灯用例**。
- 含义：F01—F12 与五个链路问题都是"测试未覆盖的行为缺口"，不是失败测试；修复时必须新增映射验收 ID 的测试（WP 卡共同约束）。

## 3. 运行环境与后端实际条件

| 项 | 实际状态 | 证据 |
|---|---|---|
| agent-doctor preview | `ready`（2 个 warn：fixture demo 未创建、production_backend_projection warn） | 本轮实跑 JSON |
| agent-doctor production | `blocked`：`suite_installation_blocked`、`production_backend_uncertified`、`client_delivery_blocked`（缺 rc_gate_report） | 同上 |
| suite-status | `blocked`；19 个 skill 均 `external_adoptable`；仅发现 codex global 一条安装记录 | 本轮实跑 JSON |
| PPT Master 标准后端 | **未绑定**：`binding_status=unbound`，"No formal backend binding found for PPT Master"；本机无可用 PPT Master 仓库 | `agent-doctor --mode production` |
| render_runtime_ready | `True` 但 `runtime_ready_source=contract_probe`（自报探针），与后端 unbound 并存——坐实 F12 家族问题 | suite-status JSON |
| capability_lock | `~/.deck-master/current/deck_capability_lock.json` **不存在** | agent-doctor 细节 |
| 本机 release 树 | `~/.deck-master/current/` 仅剩 `companion-manifest.json`，release 树实质为空 | 本机目录检查 |
| `~/.claude/skills` | 存在 deck-* 技能但至少 10 个 symlink 失效：deck-upgrade、ppt-library、deck-quality、deck-sourcing、deck-autopilot、deck-planner、deck-brief、deck-doctor、ppt-deck-pro-max、deck-producer | `find -type l ! -exec test -e` |
| `~/.codex/skills` | **无任何 deck-*/ppt-* 技能**（仅有无关第三方技能） | 目录列举 |
| PPT Library | `ppt-lib` 2.0.1.dev0 在 PATH（`~/.local/bin/ppt-lib`），真实检索可执行程序可用 | `which ppt-lib` |
| 真实样本 | 仓库内仅有元数据模板（`benchmarks/cases/real_*` 各含一个 `benchmark_case.json`），无真实客户素材——符合"真实素材不入库"设计 | 目录检查 |
| 真实 UAT 可用条件 | 需用户提供 ≥3 类真实方案样本 ×2 配对运行；宿主图像/研究工具授权不可本机自证 → C5/E 组用例本轮只能预登记，不能声称执行 | `benchmarks/`、`scripts/uat/` |

**对本轮的约束**：A-03/A-04/P-01 等"真实标准 smoke"用例在本机当前无法执行（后端未绑定），必须先由 A1/A2 建立托管安装与绑定；绑定完成前相关验收只能登记为 blocked，不得虚报。Q0 未发现任何允许 fixture 顶替的路径（见 §5 Q4）。

## 4. F01—F12 逐项核验结果

| ID | 结论 | 最小证据（file:line） |
|---|---|---|
| F01 | **属实**。rejection_counter 有统计但 approval_rate=approval/(approval+delivered)，拒绝不计入 | `scripts/learning/pack.py:64-148`（counter 定义 64-66；rate 134-139） |
| F02 | **属实**。`claims_with_evidence = sum(1 for c in claims if not c.get("risk_flags"))`——无 risk_flags 即视为有证据 | `scripts/narrative/judgment_builder.py:123` |
| F03 | **属实（文档/行为冲突）**。`docs/agent-task-index.md:113` 要求"需要外部后端或 handoff 输出即停止上报"，但 next-step 把 `awaiting_agent_execution` 映射为 `needs_generation_execution`，是宿主 Agent 自己可执行的动作；AGENTS.md 的 Stop 规则未区分"外部等待"与"Agent 可自执行等待" | `docs/agent-task-index.md:113`、`scripts/runtime/next_step.py:34,59` |
| F04 | **属实**。主新建 playbook 10 步止于 build-preview→advice→gates→export，无 deck-producer 页面生产、无 deck-builder 标准/HD 构建、无 review/交付批准环节 | `skills/deck-master/playbooks/codex-run-solution-deck.md`（134 行，步骤 1-10） |
| F05 | **属实**。`summarize_text(text, limit=900)` 头部截取；摘要仅 900 字符，材料尾部约束会丢 | `scripts/context_intake/local_sources.py:31,58` |
| F06 | **属实（两点均核验）**。(a) 生产叙事 beat 标题来自 `beat_templates()` 的硬编码 tuple（GENERIC_BEATS/RETAIL_BEATS + extra_roles）；(b) `_template_filter` 在 `production_narrative` 模式下按零售主题词过滤模板，且 `_is_restricted_sample` 用 医药/医疗/healthcare/pharma/内容底座/内容中台/dam/cms/ai 关键词误伤 | `scripts/planning/page_budget.py:51-66`、`scripts/planning/narrative_planner.py:144-209,346` |
| F07 | **属实**。fixture 渲染会话/结果硬编码 `"tool": "ppt-master"`；render request payload 同样硬编码 | `scripts/runtime/render.py:96,106`、`scripts/runtime/render_handoff.py:46` |
| F08 | **部分过时，残留属实**。`docs/contracts/generation-result.v2.schema.json` 在基线中**已存在**（commit `979adec`），"无 v2 schema"不成立；残留问题：(a) skill 侧 `skills/deck-master/schemas/generation_result.schema.json` 仍是 v1，运行时 handback 强制 `deck_generation_result.v2`（`scripts/generation/handback.py:32`）；(b) 同一契约散落 4 处（docs/contracts v1+v2、skills/deck-master/schemas v1、product_capabilities/ppt-deck-pro-max/contracts v1）；(c) 悬空引用属实：`skills/deck-master/playbooks/ppt-library-handoff.md:24` 引用的 `schemas/ppt_library_candidate.schema.json` 全仓库不存在 | 见左 |
| F09 | **属实**。RESOLVER.md 将页面生产/审查/渲染/检索路由到 4 个非公开 `ppt-*` 兼容别名 skill | `skills/RESOLVER.md:16-19`（ppt-library/ppt-master/ppt-deck-pro-max/ppt-quality-gate） |
| F10 | **属实**。`deck-planner`、`deck-review` 的 agents/openai.yaml `version: 0.9.13`，manifest package_version `0.9.14a4` | `skills/deck-planner/agents/openai.yaml:2`、`skills/deck-review/agents/openai.yaml:2`、`skills/manifest.json` |
| F11 | **属实**。`append_feedback` 仅被 `scripts/delivery/outcome.py:57-65` 与 `scripts/assets/ingest_library_results.py:12` 调用；Review Desk 逐页 approve/reject（`api_review_action`→`execute_review_action`）不写 `asset_feedback.jsonl`；server.py 只读该文件 | `scripts/preview/server.py:1331-1358,163`、`scripts/review/workbench.py:121-179`（无 feedback 写入）、`scripts/assets/feedback.py:28` |
| F12 | **属实**。`render_handoff_contract_ready()` 返回常量自比较（恒真）；`runtime_ready=True` 实测来自 `contract_probe`，而后端 binding unbound | `scripts/runtime/render_handoff.py:21-23`、本轮 suite-status JSON |

## 5. 五个链路问题的实测答案

1. **Page Package 是否被标准后端真实消费：否。** 标准构建输入是 `preview_manifest.json`（`scripts/runtime/build.py:193-207`），产出 v1 build manifest；`scripts/build/manifest.py` 的 v2/Page Package 投影在生产运行时无调用方；`page_packages/` 在生产链路**没有任何写入方**（仅 HD fixture/dev 降级适配器与测试写入）。HD 侧真实消费（`high_density/content.py:39-59`、`engine.py:444,463`）。→ B5 的"标准真实消费 Page Package"是从零建立，不是修补。
2. **HD MBB 是否在 Builder 内被再次编写：部分。** 生成代码在 builder 内（`high_density/content.py:625-722,857-932,1178-1277`，含模板句插值），但仅 `fixture/dev` 模式自动执行（`engine.py:599-628`）；production 等 Agent 产物（`engine.py:940-1022`）→ 运行时只 seal。→ B4 的"提取公共内容逻辑"对象存在且边界清楚。
3. **旧 schema/readback/gate 来源绑定范围：** v1 generation-result 无任何来源字段；v2 仅要求自报 64-hex `source_fingerprint`，不绑定具体输入字节。readback 绑定 PPTX/SVG hash + content lock（lock 再绑 `page_package_sha256`，`content.py:1118`）。gate 对 render/delivery/customer_visible_safety 要求 artifact sha + manifest fingerprint 绑定，未绑/stale fail-closed（`quality/gate_freshness.py:9-176`、`gate_policy.py:181-215`）。
4. **生产模式是否强制真实 Library：是。** `run_mode∈{production,benchmark}` 为 strict：fixture 回退显式 raise `FIXTURE_FALLBACK_BLOCKED`（`ppt_library_client.py:1131-1141`）；缺 `ppt-lib` 可执行 raise `PPT_LIBRARY_UNAVAILABLE`（1145-1155）；库状态缺 CLI 落 blocking_summary（`library_status.py:591-711`）。
5. **Project/global 安装对各宿主的实际覆盖：部分。** 宿主仅 codex/claude-code/hermes/custom（`installer.py:70`）；project scope 仅限 codex（602-625）；ppt-master 在 project scope 只 `central_compatibility_only`（2540-2543）；宿主目录只放 symlink，schema/capability 只在中心 release 树（1790-1915）。本机实况见 §3。

## 6. 同名 Spec 与既有实现差异

- 旧包 `docs/deck-master-real-production-closure-spec-pack/` 与 `docs/specs/real-production-closure/` 为历史迭代，其阶段命名（P2—P5）不作为本轮缺失清单（遵守规格 §1.1）。
- 本包落库位置采用仓库现行惯例：实现/Q0 产物放 `docs/specs/sc1-solution-core-independence/implementation/`（先例：`docs/specs/real-production-closure/implementation/baseline-lock.json`、`docs/specs/skill-os/implementation/baseline-freeze.md`）。
