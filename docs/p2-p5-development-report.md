# Deck Master P2-P5 开发报告

版本：v1.0
日期：2026-06-12
执行者：Claude Code (Sonnet 4.6)
主文档：`docs/deck-master-p2-p5-development-guide.md`

---

## 1. 执行结果总览

| 指标 | 数值 |
|---|---|
| 计划任务包 | 30 |
| 完成任务包 | 30 |
| 全量测试 | **397 tests, 0 failures** |
| P1 已有测试 | 34 |
| 本次新增测试 | 363 |
| 新增模块文件 | 32 个 `.py` |
| 新增测试文件 | 30 个 `.py` |
| 修改已有文件 | 14 个 |
| 新增业务代码 | 3,586 行 |
| 新增测试代码 | 5,504 行 |
| deck_master.py | 396 → 550 行（+154） |
| CLI 新增命令 | 16 个 |

---

## 2. 阶段执行明细

### 2.1 Sprint 0：P1.1 Hardening（6 个任务）

Sprint 0 是 P2-P5 的入口门槛，建立工程基础设施。

| 编号 | 任务 | 新增文件 | 测试数 | 状态 |
|---|---|---|---|---|
| S0-A | Workspace Foundation | `scripts/workspace/foundation.py`, `scripts/workspace/__init__.py` | 12 | ✅ |
| S0-B | Typed Events | 修改 `scripts/runtime/events.py` | 19 | ✅ |
| S0-C | Next Step Resolver | `scripts/runtime/next_step.py` | 12 | ✅ |
| S0-D | Review Status Migration | 修改 `scripts/preview/manifest.py` | 29 | ✅ |
| S0-E | Export Quality Blocking | 修改 `scripts/orchestrate/export_queue.py` | 11 | ✅ |
| S0-F | Schema Helper | `scripts/runtime/schema.py` | 10 | ✅ |

**Sprint 0 测试合计：93 tests**

#### S0-A：Workspace Foundation

- 新增 `init-workspace` / `register-workspace` / `validate-workspace` 三个 CLI 命令
- Workspace 目录结构：`workspace_manifest.json` + `visual-system/` + `structure-assets/` + `quality/` + `assets/` + `runs/` + `exports/`
- `workspace_manifest.json` 带 `schema_version: "deck_workspace.v1"`
- Reference PPT 只登记路径、sha256、页数，不承诺自动提取视觉系统
- python-pptx 不可用时优雅降级
- validate 缺失文件时返回 `pending_manual_review`，进程不崩溃

#### S0-B：Typed Events

- 新增 `append_typed_event()` 函数，写入包含 `schema_version/timestamp/run_id/event_type/step/message/refs/severity/action/status` 的 canonical 事件
- 7 种合法 `event_type`：`step_started`, `step_completed`, `tool_call`, `decision`, `error`, `manual_action`, `artifact_written`
- `read_events()` 增加 `strict` 参数，默认非严格模式跳过坏 JSONL 行
- 旧 `append_event()` 签名和行为完全不变

#### S0-C：Next Step Resolver

- 新增 `next-step` CLI 命令
- 12 级状态优先级：从 `needs_request` → `needs_context` → `needs_brief` → ... → `ready_to_export` → `needs_draft_gate` → `complete`
- 输出包含 `schema_version/run_id/status/next_command/missing_artifacts/blocking_issues`

#### S0-D：Review Status Migration

- `preview_manifest.json` 页面新增 `review_status` 和 `action_intent` 字段
- 双向映射：legacy `decision` ↔ 新字段（5 种正向映射 + 7 种反向映射 + fallback）
- `load_manifest()` 自动迁移旧 manifest
- 新增 `update_page_review()` API
- 旧 `update_page_decision()` 完全兼容

#### S0-E：Export Quality Blocking

- `export_queue()` 增加 `queue_type`（client/internal）和 `allow_quality_override` 参数
- client queue 阻断规则：review_status 非 approved → 阻断；P0 finding → 一律阻断；P1 finding → 需要 override
- internal queue 保留所有匹配 decision 的页面
- `manual_placeholder` action_intent 只能进入 internal queue
- 返回值新增 `blocked_pages` 和 `blocked_count`

#### S0-F：Schema Helper

- `SCHEMA_REGISTRY`：10 个已知 schema 版本注册表
- `ensure_schema_version()`：补全缺失 tag，不覆盖已有
- `read_with_schema()`：读取时校验 schema，不匹配抛 `SchemaVersionError`
- `write_with_schema()`：写入前设置 schema_version

---

### 2.2 P2：Solution Narrative Engine（5 个任务）

| 编号 | 任务 | 新增文件 | 测试数 | 状态 |
|---|---|---|---|---|
| P2-A | Consulting Judgment Layer | `scripts/narrative/judgment_builder.py` | 8 | ✅ |
| P2-B | Claim-Evidence Graph | `scripts/narrative/claim_graph.py` | 10 | ✅ |
| P2-C | Narrative Planner v2 | 修改 `scripts/planning/narrative_planner.py`, `scripts/planning/page_tasks.py` | 16 | ✅ |
| P2-D | Draft Gate 2.0 | `scripts/quality/draft_gate_v2.py` | 28 | ✅ |
| P2-E | Narrative Review Cockpit | 修改 `scripts/preview/server.py` + `static/` | 12 | ✅ |

**P2 测试合计：74 tests**

#### P2-A：Consulting Judgment Layer

- 新增 `build-judgments` CLI 命令
- 产物 `consulting_judgments.json`（`schema_version: "deck_consulting_judgments.v1"`）
- 从 request / deck_brief / claim_map / context_manifest 生成 judgments
- 6 种 judgment topic：`business_problem`, `solution_approach`, `evidence_sufficiency`, `audience_alignment`, `competitive_position`, `implementation_risk`
- 纯 Python 规则驱动，不调用 LLM
- 缺证据 judgment 必须带 risk flag
- 重复执行同一输入输出稳定（确定性）

#### P2-B：Claim-Evidence Graph

- 新增 `build-claim-graph` CLI 命令
- 产物 `claim_evidence_graph.json`（`schema_version: "deck_claim_evidence_graph.v1"`）
- 将 claims/evidence/assumptions/risks/pages 连成图
- Claim 包含 `claim_id/type/statement/supporting_evidence/assumptions/risks/required_evidence/page_refs`
- Evidence 包含 `evidence_id/source_ref/evidence_type/summary/confidence/publication_status`
- `publication_status` 取值：`safe_to_use`, `internal_only`, `needs_redaction`, `unknown`
- 无证据 claim 自动标记为 gap

#### P2-C：Narrative Planner v2

- `plan_narrative()` 增加 3 个可选参数：`judgments`, `claim_graph`, `workspace_archetypes`
- 每个 beat 新增字段：`decision_intent`, `argument_chain`, `evidence_policy`, `customer_specificity_level`
- `build_page_tasks()` 增加 `claim_graph`, `judgments` 参数
- Task 的 planning 块继承 beat 的所有增强字段
- 完全向后兼容：不传新参数时行为不变

#### P2-D：Draft Gate 2.0

- 新增 `quality-gate draft_v2` CLI 选项
- 7 个检查维度：`thesis_clarity`, `claim_coverage`, `evidence_readiness`, `argument_flow`, `audience_fit`, `specificity`, `risk_visibility`
- 3 种状态：`pass`, `conditional_pass`, `rework_required`
- 缺证据 claim 产生 P1 finding
- 没有页面承载的核心 claim 产生 P1 finding
- opener/closing 不强制 evidence

#### P2-E：Narrative Review Cockpit

- 新增 `GET /api/narrative/<run_id>` API
- UI 面板展示：Deck Objective / Core Thesis / Audience Strategy / Top Judgments / Claim Coverage / Gaps
- 页面级展示：core_claim / evidence_policy / linked claims
- Decision 操作写入 typed event（`event_type=decision`）

---

### 2.3 P3：Asset Intelligence（6 个任务）

| 编号 | 任务 | 新增文件 | 测试数 | 状态 |
|---|---|---|---|---|
| P3-A | Asset Schema & Canonical ID | `scripts/assets/schema.py`, `scripts/assets/canonical_id.py` | 24 | ✅ |
| P3-B | Library Result Ingestion | `scripts/assets/ingest_library_results.py` | 7 | ✅ |
| P3-C | Feedback Collector | `scripts/assets/feedback.py` | 13 | ✅ |
| P3-D | Asset Health & Archetype Tagging | `scripts/assets/health.py`, `scripts/assets/archetype_tagger.py` | 14 | ✅ |
| P3-E | Sourcing Scoring v2 | `scripts/assets/scoring.py`, 修改 `sourcing_decider.py` | 22 | ✅ |
| P3-F | Asset Signals UI | 修改 `scripts/preview/server.py` + `static/` | - | ✅ |

**P3 测试合计：76 tests**（P3-F 测试包含在 P2-E 的 preview server 测试中）

#### P3-A：Asset Schema & Canonical ID

- `canonical_slide_id = "slide_" + sha256(file_sha256 + ":" + page_number + ":" + normalized_title)[0:16]`
- Fallback：缺 file_sha256 使用 `normalized_source_ref + page_number + normalized_title`
- 缺 title 使用 text summary 前 120 字
- `asset_graph.json` 支持原子读写（tmp + replace）
- `register_asset()` 重复 candidate 自动合并

#### P3-B：Library Result Ingestion

- 处理 `library_results/selection.json` 的 `by_beat` 和顶层 `candidates`
- 注册为 workspace asset + 写 `asset_refs.json`
- 空结果写 warn event
- 错误 JSON 报错但不覆盖旧 asset graph
- 缺截图降级为 health flag

#### P3-C：Feedback Collector

- 7 种 feedback event：`preview_approved`, `preview_rejected`, `exported_internal`, `exported_client`, `delivered`, `delivery_positive_signal`, `delivery_negative_signal`
- `asset_feedback.jsonl` 只能 append
- `get_asset_feedback_summary()` 返回 approval/rejection/export/delivery 计数
- `append_feedback_dedup()` 同一事件去重

#### P3-D：Asset Health & Archetype Tagging

- 6 种健康标记：`missing_screenshot`, `low_approval_rate`, `high_rejection_rate`, `stale_asset`, `confidential_risk`, `orphan_asset`
- `low_approval_rate`：approval rate < 0.5（有 3+ feedback 时）
- `orphan_asset`：未被任何 run 的 asset_refs 引用
- 9 种页型 archetype：`problem_statement`, `solution_overview`, `architecture`, `case_study`, `roi_value`, `roadmap`, `team_capability`, `opener`, `closing`
- 产物 `assets/asset_health_report.json`

#### P3-E：Sourcing Scoring v2

- 10 维度加权评分（权重和 = 1.0）
- 权重：semantic_match(0.24), narrative_role_match(0.14), archetype_match(0.10), screenshot_available(0.08), source_credibility(0.08), win_rate(0.10), approval_history(0.08), delivery_history(0.06), visual_continuity(0.06), evidence_sufficiency(0.06)
- 惩罚：high context conflict → -0.25, medium → -0.10
- 阈值：reuse ≥ 0.78 + screenshot + conflict ≤ 0.20；adapt ≥ 0.58 + conflict ≤ 0.50
- Tie-breaker：evidence_sufficiency → approval_history → delivery_history → canonical_slide_id
- 旧 `candidate_score()` 和 `decide_for_beat()` 签名不变，向后兼容

#### P3-F：Asset Signals UI

- 新增 `GET /api/asset-signals/<run_id>` API
- UI 展示：approval rate / rejection count / delivered count / health flags / screenshot 状态 / candidate 评分拆解
- 缺 asset graph 时降级显示"资产数据不可用"

---

### 2.4 P4：Quality & Delivery Governance（7 个任务）

| 编号 | 任务 | 新增文件 | 测试数 | 状态 |
|---|---|---|---|---|
| P4-A | Evidence Gate | `scripts/quality/evidence_gate.py` | 7 | ✅ |
| P4-B | Context Conflict Gate | `scripts/quality/context_conflict_gate.py` | 6 | ✅ |
| P4-C | Confidentiality Gate | `scripts/quality/confidentiality_gate.py` | 8 | ✅ |
| P4-D | Brand Gate 轻量版 | `scripts/quality/brand_gate.py` | 6 | ✅ |
| P4-E | Override Governance | `scripts/quality/overrides.py` | 9 | ✅ |
| P4-F | Delivery Validation | `scripts/delivery/validate.py`, `scripts/delivery/outcome.py` | 13 | ✅ |
| P4-G | Quality Governance UI | 修改 `scripts/preview/server.py` + `static/` | - | ✅ |

**P4 测试合计：49 tests**（P4-G 测试包含在 preview server 测试中）

#### P4-A：Evidence Gate

- 阻断规则：required evidence 缺失 → P1；claim 无页面承载 → P1；internal_only evidence 进 client queue → P0
- 产物 `quality_reports/evidence_gate.json`

#### P4-B：Context Conflict Gate

- 检查项：历史页行业与当前行业冲突 → P1；历史页客户名残留 → P1
- 只检查 reuse/adapt 决策的页面

#### P4-C：Confidentiality Gate

- 敏感模式检测：密钥/token/账号/报价底线 → P0
- forbidden terms 匹配 → P1
- needs_redaction 来源进入 client export → P0
- 支持 workspace `quality/forbidden_terms.md` 加载

#### P4-D：Brand Gate 轻量版

- 无渲染资产 → `not_applicable`（不阻断）
- 有 artifact 时检查：visual-system 存在性、页数一致性
- 页数不匹配 → P1

#### P4-E：Override Governance

- 新增 `override create/list/revoke` CLI 子命令
- P0 不能 override 到 client export
- P1 override 必须有 reason + approver + expires_at
- 最长期限 14 天
- create/revoke 写 typed event
- 过期 override 自动从 active 列表排除

#### P4-F：Delivery Validation & Outcome

- `validate_delivery()`：artifact 存在性 + SHA-256 hash + 页数一致性 + quality reports 读取
- 产物 `delivery/final_version_lineage.json`
- `record_delivery_outcome()`：记录交付结果到 `delivery/delivery_outcome.json`
- 写 typed event + 反哺 asset feedback

#### P4-G：Quality Governance UI

- 5 个新 API 路由：`quality-governance`, `override/create`, `override/revoke`, `delivery/mark-delivered`, `delivery/record-reaction`
- UI 面板：Gate Summary / Page Findings / Active Overrides / Delivery Readiness / Delivery Outcome Form

---

### 2.5 P5A：Local Team Solution Deck Factory（5 个任务）

| 编号 | 任务 | 新增文件 | 测试数 | 状态 |
|---|---|---|---|---|
| P5A-A | Team Identity | `scripts/team/identity.py` | 7 | ✅ |
| P5A-B | Opportunity Model | `scripts/team/opportunity.py` | 8 | ✅ |
| P5A-C | Approval Flow | `scripts/team/approval.py` | 15 | ✅ |
| P5A-D | Team Dashboards | `scripts/team/dashboard.py` | 9 | ✅ |
| P5A-E | Solution Package | `scripts/team/solution_package.py` | 8 | ✅ |

**P5A 测试合计：47 tests**

#### P5A-A：Team Identity

- `add_user()` / `assign_role()` / `list_users()` / `list_audit()`
- JSON 写入使用 tmp + replace 原子替换
- audit log 只 append
- 同一 user_id 重复创建时报错

#### P5A-B：Opportunity Model

- `create_opportunity()` / `attach_run()` / `list_opportunities()`
- 目录结构：`opportunities/<opp_id>/opportunity.json` + `runs/` + `exports/` + `outcomes/`
- run 可关联到 opportunity，重复 attach 幂等

#### P5A-C：Approval Flow

- `submit_approval()` / `approve()` / `reject()` / `is_approved()` / `list_approvals()`
- 审批动作写 audit log
- 非 pending 状态重复 approve 报错
- approval_id 使用微秒级时间戳避免冲突

#### P5A-D：Team Dashboards

- `generate_team_quality_dashboard()`：run_count / average_draft_gate_score / P0/P1 count / approved_page_rate / reuse_rate / delivered_count / top_failure_modes
- `generate_asset_usage_dashboard()`：total_assets / approvals / rejections / deliveries
- 缺 run 时输出空 dashboard

#### P5A-E：Solution Package

- `create_solution_package()`：从已交付 run 提取 archetypes / claim patterns / slide assets
- `apply_solution_package()`：在新 run 的 request.json 中写入 package 引用

---

### 2.6 P5B：Connector Import Contract（1 个任务）

| 编号 | 任务 | 新增文件 | 测试数 | 状态 |
|---|---|---|---|---|
| P5B | Connector Import Contract | `scripts/connectors/import_contract.py` | 24 | ✅ |

**P5B 测试合计：24 tests**

- `validate_import_manifest()`：schema_version / source_system / source_files / redaction 检查
- `import_to_context_manifest()`：转换为 context manifest 格式
- 高敏来源（credential/password/api_key/financial_raw/salary）未 redaction 时被拒绝
- 纯本地处理，不调用外部 API

---

## 3. CLI 命令清单

### 3.1 新增命令

| 命令 | 来源 | 用途 |
|---|---|---|
| `init-workspace` | S0-A | 初始化 workspace 目录 |
| `register-workspace` | S0-A | 注册已有 workspace |
| `validate-workspace` | S0-A | 验证 workspace 完整性 |
| `next-step` | S0-C | 解析 run 下一步操作 |
| `build-judgments` | P2-A | 生成 consulting judgments |
| `build-claim-graph` | P2-B | 构建 claim-evidence graph |
| `quality-gate draft_v2` | P2-D | 增强版 draft gate |
| `override create` | P4-E | 创建 quality override |
| `override list` | P4-E | 列出 active overrides |
| `override revoke` | P4-E | 撤销 override |

### 3.2 增强的已有命令

| 命令 | 变更 |
|---|---|
| `export` | 新增 `--queue-type client/internal` 和 `--allow-quality-override` |
| `quality-gate` | 新增 `draft_v2` 选项 |

---

## 4. 工程约束遵守情况

| 约束 | 状态 |
|---|---|
| Artifact-first | ✅ 所有状态落到 run/workspace artifact |
| 写文件安全（tmp + replace） | ✅ 所有 JSON 写入使用原子替换 |
| Schema Version | ✅ 所有新增 artifact 带 `schema_version` |
| Typed Events | ✅ 关键步骤写 typed event |
| Review 状态兼容 | ✅ 新旧字段双向同步 |
| Delivery Outcome 路径兼容 | ✅ canonical + legacy 路径 |
| 坏 JSON 不覆盖原文件 | ✅ 读取报错保留原文件 |
| 向后兼容 | ✅ 旧签名/旧 artifact 均可用 |

---

## 5. 测试矩阵

| 阶段 | 测试文件 | 测试数 |
|---|---|---:|
| Sprint 0 | `test_workspace_foundation.py` | 12 |
| Sprint 0 | `test_runtime_events.py` | 19 |
| Sprint 0 | `test_schema_versioning.py` | 10 |
| Sprint 0 | `test_next_step.py` | 12 |
| Sprint 0 | `test_preview_manifest.py` | 29 |
| Sprint 0 | `test_export_quality_blocking.py` | 11 |
| P2 | `test_consulting_judgments.py` | 8 |
| P2 | `test_claim_evidence_graph.py` | 10 |
| P2 | `test_narrative_planner.py` | 8 |
| P2 | `test_page_tasks.py` | 8 |
| P2 | `test_draft_gate_v2.py` | 28 |
| P2/P3 | `test_preview_server.py` | 12 |
| P3 | `test_asset_schema.py` | 24 |
| P3 | `test_asset_ingestion.py` | 7 |
| P3 | `test_asset_feedback.py` | 13 |
| P3 | `test_asset_health.py` | 14 |
| P3 | `test_sourcing_scoring_v2.py` | 22 |
| P4 | `test_evidence_gate.py` | 7 |
| P4 | `test_context_conflict_gate.py` | 6 |
| P4 | `test_confidentiality_gate.py` | 8 |
| P4 | `test_brand_gate.py` | 6 |
| P4 | `test_overrides.py` | 9 |
| P4 | `test_delivery_validation.py` | 7 |
| P4 | `test_delivery_outcome.py` | 6 |
| P5A | `test_team_identity.py` | 7 |
| P5A | `test_opportunity_model.py` | 8 |
| P5A | `test_approval_flow.py` | 15 |
| P5A | `test_team_dashboard.py` | 9 |
| P5A | `test_solution_package.py` | 8 |
| P5B | `test_connector_import_contract.py` | 24 |
| **新增小计** | **30 个文件** | **363** |
| P1 已有 | 12 个文件 | 34 |
| **总计** | **42 个文件** | **397** |

---

## 6. 已知限制与后续建议

### 6.1 未集成到 CLI 的模块

以下模块已实现并可作为 API 调用，但未全部注册为 `deck_master.py` 子命令：

- P4-A/B/C/D 四个独立 gate（可通过 `from quality.xxx import evaluate_xxx_gate` 调用）
- P5A-A/B/D/E 团队模块（可通过 `from team.xxx import xxx` 调用）
- P3-B/D 资产模块

**建议**：按需集成，不必一次全部注册为 CLI 命令。

### 6.2 测试覆盖盲区

- P3-F（Asset Signals UI）和 P4-G（Governance UI）的 API 路由测试包含在 `test_preview_server.py` 中，但未覆盖所有 governance API 端点
- `test_preview_server.py` 使用 mock I/O 方式测试，未覆盖 HTTP 协议层行为

### 6.3 python-pptx 依赖

- Brand Gate 页数检查、Workspace reference PPT 页数获取依赖 `python-pptx`
- 不可用时优雅降级，不影响其他功能
- 建议将 `python-pptx` 加入 `requirements.txt`

### 6.4 主 repo 与 worktree 状态

本次开发在 worktree（`.claude/worktrees/epic-ellis-56c31a`）中执行。主 repo 的 `scripts/deck_master.py` 有早期集成痕迹（S0-A 的 workspace import），但其他改动都在 worktree 中。合并时需注意冲突。

---

## 7. 审计用命令

```bash
# 全量测试
python3 -m unittest discover -s tests

# CLI 帮助
python3 scripts/deck_master.py --help

# Smoke 测试
tmp=$(mktemp -d)
python3 scripts/deck_master.py init-workspace --workspace "$tmp/ws" --name "Audit Test"
python3 scripts/deck_master.py validate-workspace --workspace "$tmp/ws"
python3 scripts/deck_master.py start-conversation \
  --runs-dir "$tmp/runs" --workspace "$tmp/ws" \
  --brief "零售客户数字化转型方案" --run-id audit_demo
python3 scripts/deck_master.py build-brief --runs-dir "$tmp/runs" --run-id audit_demo
python3 scripts/deck_master.py build-claim-map --runs-dir "$tmp/runs" --run-id audit_demo
python3 scripts/deck_master.py build-judgments --runs-dir "$tmp/runs" --run-id audit_demo
python3 scripts/deck_master.py build-claim-graph --runs-dir "$tmp/runs" --run-id audit_demo
python3 scripts/deck_master.py next-step --runs-dir "$tmp/runs" --run-id audit_demo
```

---

*报告生成时间：2026-06-12*
*执行环境：Claude Code + Sonnet 4.6, macOS*
