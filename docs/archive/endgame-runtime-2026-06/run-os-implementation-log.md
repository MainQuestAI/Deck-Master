# Deck Master Run OS 实现进度日志

> 历史分支归档说明：本文来自 `origin/codex/deck-master-endgame-runtime`，仅用于追溯 2026-06 Run OS 迁移期间的阶段实现和验证记录。当前生产基线以 `main` 在 v0.9.13 之后的 suite runtime、product capabilities、setup/readiness 和 UC story review 结构为准。

日期：2026-06-11
分支：`codex/deck-master-endgame-runtime`
工作区：`<deck-master-endgame-runtime-worktree>`

## 1. 当前目标

基于完整开发 spec，启动独立分支、独立 worktree 和 subagent，实现 Deck Master 终局目标。

本轮先进入 P0：

- P0-0：迁移保护与仓库对齐。
- P0-1：Runtime Contract Hardening。
- 后续：Workspace Foundation、Context / Brief / Claim Map、Planner、Sourcing、Draft Gate、Review UI、Quality-aware Export。

## 2. 已完成

- 已从 `origin/main` 创建独立分支：`codex/deck-master-endgame-runtime`。
- 已创建独立 worktree：`<deck-master-endgame-runtime-worktree>`。
- 已启动 worker subagent：`Godel`。
- 已将 `Godel` 的写入范围限定在 Runtime Contract：
  - `scripts/runtime/events.py`
  - `scripts/runtime/run_state.py`
  - `scripts/runtime/next_step.py`
  - `scripts/deck_master.py` 的 runtime CLI 接入
  - runtime 相关测试
- 已创建迁移保护清单：`docs/migration/2026-06-run-os-migration-map.md`。
- 已完成 P0-1 Runtime Contract Hardening 第一版。
- 已提交并推送远程分支：`codex/deck-master-endgame-runtime`。
- 阶段提交：`37ea6c3 feat: harden runtime contract for Run OS`。
- 已完成 P0-2 Workspace Foundation 第一版。
- P0-2 阶段提交：`eb2b83a feat: add workspace foundation`。
- 已完成 P0-3 Context / Brief / Consulting Judgments / Claim-Evidence Graph 第一版。
- P0-3 增量已通过专项测试、全量回归、CLI smoke 和 diff 检查。
- 已完成 P0-4 Workspace-aware Planner 第一版。
- P0-4 增量已通过专项测试、全量回归、CLI smoke 和 diff 检查。
- 已完成 P0-5 Quality-aware Draft Gate 第一版。
- P0-5 增量已通过专项测试、全量回归、CLI smoke 和 diff 检查。
- 已完成 P0-6 Review Cockpit / Preview Manifest 增强第一版。
- P0-6 增量已通过专项测试、全量回归、前端脚本检查、HTTP smoke 和 diff 检查。
- 已完成 P0-7 Export 阻断与 feedback/outcome 对齐第一版。
- P0-7 增量已通过专项测试、全量回归、CLI smoke 和 diff 检查。
- 已完成 P1-1 Build Skill Runtime / PPT Deck Pro Max handoff 第一版。
- P1-1 增量已通过专项测试、全量回归、CLI smoke 和 diff 检查。
- 已完成 P1-2 Review Cockpit 构建状态展示与操作约束第一版。
- P1-2 增量已通过专项测试、全量回归、HTTP smoke 和 diff 检查。
- 已完成 P1-12 Delivery Gate PPTX handoff smoke 第一版。
- P1-12 增量已通过专项测试、全量回归、前端脚本检查、禁句扫描和 diff 检查。
- 已完成 P1-13 Workspace feedback loop 第一版。
- 已完成 P1-14 Workspace asset health report 第一版。
- 已完成 P1-15 Workspace asset health runtime visibility 第一版。
- 已完成 P1-16 Workspace asset health Review Cockpit rendering 第一版。
- 已完成 P1-17 Review Cockpit filters and export queue visibility 第一版。
- 已完成 P1-18 Review Cockpit preview zoom and canvas reading 第一版。
- 已完成 P1-19 Review Cockpit structured event drawer 第一版。
- 已完成 P1-20 Review Cockpit quality gate approval guard 第一版。
- 已完成 P1-21 Review Cockpit run-level blocker and repair action 第一版。
- 已完成 P1-22 Review Cockpit repair action operations 第一版。
- 已完成 P1-23 Review Cockpit repair status and gate rerun 第一版。
- 已完成 P1-24 Review Cockpit repair note and batch rerun 第一版。
- 已完成 P1-25 Quality gate report diff 第一版。
- 已完成 P1-26 Quality gate diff history 第一版。
- 已完成 P1-27 Review Cockpit high-risk finding aggregation 第一版。
- 已完成 P1-28 Review Cockpit quality risk filtering 第一版。
- 已完成 P1-29 Review Cockpit export readiness explanation 第一版。
- 已完成 P1-30 Review Cockpit export blocker actions 第一版。
- 已完成 P1-31 Review Cockpit delivery outcome handoff 第一版。
- 已完成 P1-32 Review Cockpit asset health refresh after delivery 第一版。
- 已完成 P1-33 Review Cockpit delivery feedback review 第一版。
- 已完成 P1-34 Review Cockpit feedback trend and reuse recommendations 第一版。
- 已完成 P1-45 Review Cockpit browser smoke 第一版。
- 已完成 P1-46 Review Cockpit quality-rich browser smoke 第一版。
- 已完成 P1-47 Review Cockpit review action browser smoke 第一版。
- 已完成 P1-48 Review Cockpit export and delivery outcome browser smoke 第一版。
- 已完成 P1-49 Review Cockpit workspace asset health browser smoke 第一版。
- 已完成 P1-50 Review Cockpit quality repair browser smoke 第一版。
- 已完成 P1-51 Review Cockpit repair batch browser smoke 第一版。
- 已完成 P1-52 Review Cockpit quality history browser smoke 第一版。
- 已完成 P1-53 Review Cockpit export blocker status browser smoke 第一版。
- 已完成 P1-54 Review Cockpit export blocker rerun browser smoke 第一版。
- 已完成 P1-55 Review Cockpit export blocker jump/copy browser smoke 第一版。

## 3. 基线验证

在 worker 改动前，当前 worktree 基线测试已通过：

```text
python3 -m unittest discover -s tests -v
Ran 44 tests
OK
```

该结果作为 P0-1 Runtime Contract 改造后的回归对照。

P0-1 集成后验证：

```text
python3 -m unittest tests.test_runtime_state tests.test_runtime_next_step -v
Ran 11 tests
OK

python3 -m unittest discover -s tests -v
Ran 52 tests
OK

git diff --check
OK

python3 -m py_compile scripts/deck_master.py scripts/runtime/events.py scripts/runtime/run_state.py scripts/runtime/next_step.py
OK
```

P0-2 集成后验证：

```text
python3 -m unittest tests.test_workspace_foundation -v
Ran 6 tests
OK

python3 -m unittest discover -s tests -v
Ran 58 tests
OK

python3 -m py_compile scripts/deck_master.py scripts/planning/page_tasks.py scripts/workspace/__init__.py scripts/workspace/bootstrap.py scripts/workspace/reader.py scripts/workspace/workspace_manifest.py
OK

git diff --check
OK

CLI smoke:
init-workspace -> workspace_initialized, valid=true
validate-workspace -> valid=true
plan --workspace -> page_tasks planning.workspace_refs populated
```

P0-3 集成后验证：

```text
python3 -m unittest tests.test_context_conversation tests.test_conversation_cli -v
Ran 8 tests
OK

python3 -m unittest discover -s tests -v
Ran 62 tests
OK

python3 -m py_compile scripts/deck_master.py scripts/context_intake/local_sources.py scripts/conversation/session_builder.py scripts/conversation/brief_compiler.py scripts/planning/claim_map.py
OK

git diff --check
OK

禁用句式扫描
OK
```

P0-3 CLI smoke：

```text
start-conversation -> context_manifest.json + conversation_session.json
build-brief -> deck_brief.json
build-judgments -> consulting_judgments.json
build-claim-map -> claim_map.json
build-claim-graph -> claim_evidence_graph.json

conversation run -> autoplan fixture -> preview_manifest.json
quality-gate draft -> pass
page_tasks -> 12 tasks
claim_evidence_graph -> 12 page_claim_links + 12 evidence_page_links
```

P0-4 集成后验证：

```text
python3 -m unittest tests.test_narrative_planner tests.test_workspace_foundation -v
Ran 9 tests
OK

python3 -m unittest discover -s tests -v
Ran 63 tests
OK

python3 -m py_compile scripts/deck_master.py scripts/planning/narrative_planner.py scripts/planning/page_tasks.py
OK

git diff --check
OK

禁用句式扫描
OK
```

P0-4 CLI smoke：

```text
conversation run -> build-brief -> build-judgments -> build-claim-map -> autoplan fixture
narrative_plan -> deck_narrative_plan.v1
page_tasks -> deck_page_tasks.v1
architecture beat -> core_claim + decision_intent + argument_chain dict + evidence_policy.required=true
workspace refs -> present on architecture beat
preview -> autoplan_preview_ready
draft gate -> pass
```

P0-5 集成后验证：

```text
python3 -m unittest tests.test_quality_gate tests.test_conversation_cli tests.test_runtime_next_step -v
Ran 11 tests
OK

python3 -m unittest discover -s tests -v
Ran 64 tests
OK

python3 -m py_compile scripts/deck_master.py scripts/quality/gate_runner.py scripts/quality/draft_gate.py
OK

git diff --check
OK

禁用句式扫描
OK
```

P0-5 CLI smoke：

```text
conversation run -> autoplan fixture -> build-claim-graph -> quality-gate draft
claim_evidence_graph -> 12 page_claim_links
draft_gate summary -> claim_graph_links=12
draft_gate -> pass, blocks_delivery=false, findings=0
```

P0-6 集成后验证：

```text
python3 -m unittest tests.test_conversation_cli tests.test_preview_manifest tests.test_preview_server tests.test_end_to_end_autoplan -v
Ran 10 tests
OK

python3 -m unittest discover -s tests -v
Ran 64 tests
OK

python3 -m py_compile scripts/orchestrate/preview_builder.py scripts/orchestrate/build_run.py scripts/preview/manifest.py scripts/preview/server.py
OK

node --check scripts/preview/static/app.js
OK

git diff --check
OK

禁用句式扫描
OK
```

P0-6 HTTP smoke：

```text
preview server -> /
preview server -> /static/app.js
preview server -> /api/deck
index_has_chinese_title=true
app_has_chinese_labels=true
deck_strategy_present=true
planning_summary_present=true
page_planning_present=true
page_review_present=true
page_quality_status_present=true
pages=12
```

P0-7 集成后验证：

```text
python3 -m unittest tests.test_orchestration tests.test_feedback tests.test_conversation_cli -v
Ran 10 tests
OK

python3 -m unittest discover -s tests -v
Ran 66 tests
OK

python3 -m py_compile scripts/deck_master.py scripts/orchestrate/export_queue.py scripts/feedback/record_deal.py
OK

git diff --check
OK
```

P0-7 CLI smoke：

```text
conversation run -> autoplan fixture -> build-claim-graph -> quality-gate draft
manual approve first page -> export
export_ok_pages=1
inject Draft Gate P1 blocker -> export
blocked_export_failed=true
blocked_error_contains_export_blocked=true
```

P1-1 集成后验证：

```text
python3 -m unittest tests.test_generation_tasks tests.test_orchestration -v
Ran 11 tests
OK

python3 -m unittest discover -s tests -v
Ran 70 tests
OK

python3 -m py_compile scripts/deck_master.py scripts/generation/task_builder.py scripts/generation/build_runtime.py scripts/orchestrate/export_queue.py
OK

git diff --check
OK
```

P1-1 CLI smoke：

```text
conversation run -> autoplan fixture -> run-build-skill --executor fake
build_status=completed
manifest_updated=true
page_source_type=generated
page_preview_exists=true
generation_status=completed
artifact_path=build_artifacts/beat_04_solution/page.svg
```

P1-2 集成后验证：

```text
python3 -m unittest tests.test_preview_manifest tests.test_preview_server tests.test_generation_tasks tests.test_orchestration -v
Ran 22 tests
OK

python3 -m unittest discover -s tests -v
Ran 73 tests
OK

node --check scripts/preview/static/app.js
OK

python3 -m py_compile scripts/preview/manifest.py scripts/preview/server.py
OK

git diff --check
OK
```

P1-2 HTTP smoke：

```text
preview server -> /static/app.js
preview server -> /api/deck
app_has_build_label=true
completed_pages=1
completed_page_source_type=generated
completed_asset_exists=true
completed_generation_status=completed
```

P1-3 集成后验证：

```text
python3 -m unittest tests.test_generation_tasks -v
Ran 8 tests
OK

python3 -m unittest discover -s tests -v
Ran 75 tests
OK

python3 -m py_compile scripts/deck_master.py scripts/generation/build_runtime.py scripts/tools/deck_pro_max_client.py tests/test_generation_tasks.py
OK

git diff --check
OK

forbidden phrase scan
OK
```

P1-3 CLI smoke：

```text
autoplan --library-mode fixture
autoplan_status=autoplan_preview_ready
pages=15

run-build-skill --executor deck-pro-max-init
build_status=running
task_id=generation_004_beat_04_solution
handoff=deck_pro_max_project/deck_master_task_bundle.json
handoff_md=deck_pro_max_project/deck_master_task_bundle.md
project_exists=true
manifest_updated=true
```

P1-3 已完成能力：

```text
run-build-skill 支持 deck-pro-max-init 执行器
Deck Master 能调用 PPT Deck Pro Max init 创建项目骨架
Deck Master 会向 deck_pro_max_project 写入 deck_master_task_bundle.json 和 deck_master_task_bundle.md
generation_tasks/index.json 会记录 executor、last_command、deck_pro_max_project 和 handoff
preview_manifest.json 会同步展示 generation_task 的 running / failed 状态
下游 init 失败会写入 task errors、events 和 preview manifest
```

P1-4 集成后验证：

```text
python3 -m unittest tests.test_runtime_next_step -v
Ran 12 tests
OK

python3 -m unittest discover -s tests -v
Ran 81 tests
OK

python3 -m py_compile scripts/runtime/next_step.py tests/test_runtime_next_step.py
OK

git diff --check
OK

forbidden phrase scan
OK
```

P1-4 已完成能力：

```text
next_step.json artifact_status 纳入 claim_evidence_graph.json
缺 claim_evidence_graph.json 时，下一步指向 build_claim_graph
generation_tasks/index.json 中 buildable pending 会指向 run_build_skill
generation_tasks/index.json 中 buildable running 会指向 wait_for_build_skill
generation_tasks/index.json 中 buildable failed 会阻断运行态并指向 repair_generation_task
quality_reports/render_gate.json 的 P0/P1 或 rework_required 会阻断到 review_render_gate_findings
quality_reports/delivery_gate.json 的 P0/P1 或 rework_required 会阻断到 review_delivery_gate_findings
```

P1-5 集成后验证：

```text
python3 -m unittest tests.test_orchestration tests.test_generation_tasks -v
Ran 15 tests
OK

python3 -m unittest discover -s tests -v
Ran 83 tests
OK

python3 -m py_compile scripts/orchestrate/export_queue.py tests/test_orchestration.py
OK

git diff --check
OK

forbidden phrase scan
OK
```

P1-5 已完成能力：

```text
approved_queue 导出前统一读取 Draft / Render / Delivery 三段质量报告
Draft / Render / Delivery 任一 gate 出现 P0/P1 finding 会阻断导出
Draft / Render / Delivery 任一 gate 出现 rework_required 或 blocks_delivery 会阻断导出
allow_blocked=true 时仍可导出审计队列，并在 blockers 中保留 gate 来源
quality_gate 摘要保留 draft_status，并新增 render_status、delivery_status 和 gates 明细
```

P1-6 集成后验证：

```text
python3 -m unittest tests.test_feedback -v
Ran 6 tests
OK

python3 -m unittest discover -s tests -v
Ran 85 tests
OK

python3 -m py_compile scripts/deck_master.py scripts/feedback/delivery_outcome.py tests/test_feedback.py
OK

git diff --check
OK

forbidden phrase scan
OK
```

P1-6 CLI smoke：

```text
record-delivery-outcome
delivery_status=delivery_outcome_recorded
delivery_outcome_exists=true

record-feedback
feedback_status=feedback_recorded
sourcing_lines=2
```

P1-6 已完成能力：

```text
新增 record-delivery-outcome CLI
新增 record-feedback CLI
delivery_outcome.json 按 deck_delivery_outcome.v1 写入 run
feedback/delivery_outcomes.jsonl 记录交付结果事件
feedback/sourcing_outcomes.jsonl 记录页面级 delivered / not_delivered / rejected 等反馈事件
事件日志写入 delivery.outcome.recorded 和 feedback.event.recorded
```

P1-7 集成后验证：

```text
python3 -m unittest tests.test_generation_tasks -v
Ran 11 tests
OK

python3 -m unittest discover -s tests -v
Ran 88 tests
OK

python3 -m py_compile scripts/deck_master.py scripts/generation/build_runtime.py tests/test_generation_tasks.py
OK

git diff --check
OK

forbidden phrase scan
OK
```

P1-7 CLI smoke：

```text
autoplan --library-mode fixture
run-build-skill --executor deck-pro-max-init
write deck_pro_max_project/review_package.json with page_images mapping
run-build-skill --executor deck-pro-max-handback

handback_status=completed
artifact=deck_pro_max_project/rendered/architecture_final.png
review_package=review_package.json
deck_html=assemble/batch_01/starter/index.html
assemble_batches=1
```

P1-7 已完成能力：

```text
新增 run-build-skill --executor deck-pro-max-handback
Deck Master 能从 deck_pro_max_project/review_package.json 的 page_images 映射发现页面级预览图
Deck Master 能兜底扫描 rendered/、actual_page_images/、build_artifacts/、exports/ 中的页面图
发现页面图后会生成 deck_build_artifact.v1 并复用 ingest_build_artifact
generation task 会从 running 回填为 completed
preview_manifest 会同步更新 preview_path、source_type、generation_task.artifacts
artifact 中会记录 deck_pro_max 项目摘要，包括 review_package、slide_state、layout_manifest、asset_manifest、deck_html、deck_pptx、rendered_dir、page_images 和 assemble_batches
页面图缺失时返回 not_ready，保留 running 状态
```

P1-8 集成后验证：

```text
python3 -m unittest tests.test_preview_i18n tests.test_preview_manifest tests.test_preview_server -v
Ran 20 tests
OK

python3 -m unittest discover -s tests -v
Ran 97 tests
OK

python3 -m py_compile scripts/preview/manifest.py scripts/preview/server.py scripts/orchestrate/export_queue.py scripts/feedback/delivery_outcome.py
OK

node --check scripts/preview/static/app.js
OK

git diff --check
OK
```

P1-8 HTTP smoke：

```text
python3 scripts/preview/server.py examples/preview-run --host 127.0.0.1 --port 5055
GET /
GET /static/i18n/en-US.json
GET /static/i18n/zh-CN.json
GET /api/deck
GET /api/events

结果：
首页可访问
中英文语言包 JSON 可解析
Deck API 返回 3 页并带 review_status
Events API 返回事件数组
```

P1-8 已完成能力：

```text
preview_manifest 读取时兼容旧 decision / notes，并自动补齐 review_status、review_note、action_intent、locked、reviewed_at
旧 decision 映射规则已落地：needs_review、approved、keep、replace 均可稳定迁移
新增 update_page_review，并保留 update_page_decision 兼容入口
新增 replace-source、convert-to-generate、lock-source 页面操作
新增 GET /api/quality、GET /api/events、POST /api/page/<page_id>/review、POST /api/page/<page_id>/replace-source、POST /api/page/<page_id>/convert-to-generate、POST /api/page/<page_id>/lock-source、POST /api/export
人工审查操作写入 events.jsonl
approved / rejected / excluded_by_quality 会写入 feedback/sourcing_outcomes.jsonl
approved_queue 导出队列显式携带 review_status、review_note、action_intent、locked、reviewed_at
Review Cockpit UI 改为 review_status 口径，支持批准、拒绝、备注、替换来源、转生成页、锁定来源和事件抽屉
新增 zh-CN / en-US 语言包、浏览器语言默认选择、显式语言切换、localStorage 语言偏好
新增语言包 key 一致性测试
```

P1-9 集成后验证：

```text
python3 -m unittest tests.test_generation_tasks -v
Ran 18 tests
OK

python3 -m unittest discover -s tests -v
Ran 104 tests
OK

python3 -m py_compile scripts/deck_master.py scripts/generation/build_runtime.py scripts/tools/deck_pro_max_client.py tests/test_generation_tasks.py
OK

python3 scripts/deck_master.py run-deck-pro-max-stage --help
OK

git diff --check
OK
```

P1-9 CLI smoke：

```text
临时 run + fake Deck Pro Max pipeline
run-build-skill --executor deck-pro-max-init
run-deck-pro-max-stage --stage visual-composition
run-deck-pro-max-stage --stage post-assemble-qa

cli_smoke_status=completed
cli_smoke_preview=deck_pro_max_project/rendered/slide_01.png
cli_smoke_stages=visual-composition,post-assemble-qa
```

P1-9 已完成能力：

```text
新增 run-deck-pro-max-stage 项目级 CLI
Deck Master 可状态化执行 Deck Pro Max 阶段：visual-composition、asset-plan、generate-assets、dispatch-build、prepare-assemble、assemble-html、post-assemble-qa
新增 Deck Pro Max 后续阶段命令构造器和执行器
generation_tasks/index.json 新增 build_stages[] 阶段记录
相关 generation task 会回写 current_step、last_step_status、last_command、build_steps[]
preview_manifest 中 generation_task 同步展示阶段状态、最近命令、Deck Pro Max 项目摘要
阶段失败会标记所有 buildable task 为 failed，并写入错误与 event
post-assemble-qa 成功后会自动尝试 handback，发现 review_package 或 rendered 页面图后刷新 preview
保留 task 级 deck-pro-max-step 执行能力，供单页任务诊断和精细化重跑使用
```

P1-10 集成后验证：

```text
python3 -m unittest tests.test_quality_gate -v
Ran 7 tests
OK

python3 -m unittest tests.test_preview_server tests.test_preview_i18n -v
Ran 10 tests
OK

python3 -m py_compile scripts/deck_master.py scripts/quality/gate_runner.py scripts/quality/html_audit.py scripts/quality/artifact_discovery.py scripts/preview/manifest.py scripts/preview/server.py tests/test_quality_gate.py tests/test_preview_server.py
OK

python3 -m unittest discover -s tests -v
Ran 108 tests
OK

node --check scripts/preview/static/app.js
OK

git diff --check
OK
```

P1-10 CLI smoke：

```text
临时 run + Deck Pro Max review_package + deck.html
quality-gate --run-dir <tmp>/runs/smoke render

cli_smoke_status=pass
cli_smoke_artifact=deck.html
cli_smoke_source=auto
cli_smoke_report=true
```

P1-10 已完成能力：

```text
Render Gate 新增 HTML 成果稿审计，覆盖页数估算、文本密度、图片承载风险和禁用词复核
quality-gate render 未传 --artifact 时会从 Deck Pro Max 项目、review_package、exports 和 build_artifacts 自动发现 HTML/PPTX
quality-gate delivery 未传 --artifact 时会自动发现 PPTX 成果稿
质量报告 index 会记录 artifact_discovery，便于审计成果来源
Review Cockpit 的 /api/deck 新增 build 摘要，展示 generation task 状态、阶段记录、当前阶段和 Deck Pro Max 项目路径
页面列表和详情会显示 generation task 当前阶段、最近阶段状态、阶段链路、HTML/PPTX 成果路径
中英文语言包同步新增 build 阶段展示字段
```

P1-11 集成后验证：

```text
python3 -m unittest tests.test_workspace_foundation tests.test_generation_tasks -v
Ran 29 tests
OK

python3 -m py_compile scripts/workspace/workspace_manifest.py scripts/workspace/bootstrap.py scripts/workspace/reader.py scripts/workspace/__init__.py scripts/generation/task_builder.py scripts/generation/build_runtime.py tests/test_workspace_foundation.py tests/test_generation_tasks.py
OK

python3 -m unittest discover -s tests -v
Ran 113 tests
OK

node --check scripts/preview/static/app.js
OK

git diff --check
OK
```

P1-11 CLI smoke：

```text
init-workspace --workspace <tmp>/workspace --name Smoke Workspace
create-generation-tasks --run-dir <tmp>/runs/smoke

cli_smoke_workspace_status=workspace_initialized
cli_smoke_tasks_status=generation_tasks_ready
cli_smoke_default_build_skill=ppt-deck-pro-max
cli_smoke_task_build_skill=ppt-deck-pro-max
cli_smoke_registry_source=workspace
```

P1-11 已完成能力：

```text
Workspace 初始化会创建 build-skills/registry.json
workspace_manifest.json 会记录 default_build_skill 和 build_skill_registry
validate-workspace 会校验默认 Build Skill 是否存在于 registry
validate-workspace 会读取真实 build-skills/registry.json，并标记坏 JSON、默认技能禁用、支持范围缺失
create-generation-tasks 会读取 workspace 默认 Build Skill
create-generation-tasks 会拒绝无效 registry，避免静默选择错误构建器
generation_tasks/index.json 会写入 workspace、default_build_skill 和 build_skill
每个 generation task 会写入 build_skill_id 和 build_skill
Deck Pro Max task bundle 会包含 Build Skill 信息，方便下游执行器审计
首版默认 Build Skill 收紧为 ppt-deck-pro-max，避免 registry 声明和执行链路漂移
```

P1-12 集成后验证：

```text
python3 -m unittest tests.test_quality_gate -v
Ran 9 tests
OK

python3 -m py_compile tests/test_quality_gate.py scripts/quality/pptx_audit.py scripts/quality/gate_runner.py scripts/quality/artifact_discovery.py scripts/deck_master.py
OK

node --check scripts/preview/static/app.js
OK

python3 -m unittest discover -s tests -v
Ran 115 tests
OK

git diff --check
OK

禁句扫描
OK
```

P1-12 已完成能力：

```text
Delivery Gate CLI 已补真实 PPTX 自动发现 smoke 覆盖
测试验证最终 PPTX 可从 Deck Pro Max review_package.json 的 artifacts.deck_pptx 进入质量门禁
通过路径会记录 artifact_discovery.source=auto、PPTX 路径、slide_count 与 media_count
禁用词路径会输出 rework_required 并阻断 delivery
最小 PPTX fixture 在图片计数存在时写入 media 文件，支撑 media_count 审计断言
完整开发 spec、spec pack 和测试矩阵已同步 Delivery Gate 自动发现验收口径
```

P1-13 专项验证：

```text
python3 -m unittest tests.test_feedback tests.test_workspace_foundation -v
Ran 16 tests
OK

python3 -m py_compile scripts/feedback/delivery_outcome.py scripts/workspace/workspace_manifest.py scripts/workspace/bootstrap.py scripts/deck_master.py tests/test_feedback.py tests/test_workspace_foundation.py
OK

python3 -m unittest discover -s tests -v
Ran 116 tests
OK

node --check scripts/preview/static/app.js
OK

git diff --check
OK

禁句扫描
OK
```

P1-13 已完成能力：

```text
Workspace 初始化补齐 assets/、assets/slides、assets/cases、assets/evidence、assets/visuals 和 feedback/ 目录
workspace_manifest.json paths 补齐 assets 与 feedback
record-delivery-outcome 会读取 run request.json 中的 workspace 指针
交付结果会同步写入 workspace/feedback/delivery_outcomes.jsonl
页面级 delivered / not_delivered 结果会同步写入 workspace/feedback/sourcing_outcomes.jsonl
delivered 页面会写入 workspace/feedback/asset_candidates.jsonl，形成可复用页面候选
CLI 返回 workspace_feedback 汇总，便于 Agent 判断反馈闭环是否完成
```

P1-14 专项验证：

```text
python3 -m unittest tests.test_feedback -v
Ran 9 tests
OK

python3 -m py_compile scripts/feedback/asset_health.py scripts/feedback/delivery_outcome.py scripts/deck_master.py tests/test_feedback.py
OK

python3 -m unittest discover -s tests -v
Ran 118 tests
OK

node --check scripts/preview/static/app.js
OK

git diff --check
OK

禁句扫描
OK
```

P1-14 已完成能力：

```text
新增 workspace-asset-health CLI
新增 scripts/feedback/asset_health.py
workspace feedback 会生成 feedback/asset_health_report.json
报告汇总 asset_candidates、sourcing_outcomes 和 delivery_outcomes
报告输出 strong_reuse_candidate、watch、weak_signal、unproven 四类资产健康状态
测试覆盖强复用候选、弱信号资产和 CLI 写出报告
```

P1-15 专项验证：

```text
python3 -m unittest tests.test_runtime_next_step tests.test_preview_server tests.test_feedback -v
Ran 32 tests
OK

python3 -m py_compile scripts/feedback/asset_health.py scripts/runtime/next_step.py scripts/preview/server.py scripts/deck_master.py tests/test_runtime_next_step.py tests/test_preview_server.py tests/test_feedback.py
OK

python3 -m unittest discover -s tests -v
Ran 120 tests
OK

node --check scripts/preview/static/app.js
OK

git diff --check
OK

禁句扫描
OK
```

P1-15 已完成能力：

```text
status 和 next-step 在 run 绑定 workspace 时返回 workspace_asset_health 摘要
GET /api/deck 在 run 绑定 workspace 时返回 workspace_asset_health 摘要
报告缺失时返回 status=missing 和 next_step=workspace-asset-health
报告存在时返回 summary、created_at 和 top_assets
测试覆盖 runtime next-step 与 Review Cockpit API 两个出口
```

P1-16 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server -v
Ran 12 tests
OK

python3 -m unittest discover -s tests -v
Ran 121 tests
OK

git diff --check
OK

禁句扫描
OK

browser smoke
meta: sample-preview-run · Draft · 3 pages · Assets: 1 strong / 1 weak
asset health panel: Report Ready、Unique Assets、Strong Reuse、Weak Signals、High-Value Assets、Candidate Count
OK
```

P1-16 已完成能力：

```text
Review Cockpit 右侧面板渲染 workspace_asset_health
顶部 run 状态条显示资产强复用和弱信号摘要
面板显示报告状态、关键计数、高价值资产、下一步、报告路径和错误信息
新增 asset_health 双语文案，并修正新增区域的中英文分隔符
测试覆盖 i18n 键一致性与前端资产健康面板入口
```

P1-17 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_orchestration tests.test_preview_server -v
Ran 21 tests
OK

python3 -m unittest discover -s tests -v
Ran 122 tests
OK

git diff --check
OK

禁句扫描
OK

browser smoke
filter: approved -> 1 / 3 pages visible
filtered list: Target Architecture
export: Export queue generated: 1 page
OK
```

P1-17 已完成能力：

```text
Review Cockpit 左侧新增审查结论和来源类型筛选
页面列表、翻页按钮和键盘导航遵守当前筛选结果
Review Cockpit 右侧新增导出队列面板，显示批准、待审查、拒绝数量
导出队列面板可调用 POST /api/export 生成批准页队列
修正 approved 导出口径，兼容历史 decision=keep 映射后的 review_status=approved
新增 filters/export 双语文案，并修正英文单数 page 显示
```

P1-18 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server -v
Ran 14 tests
OK

python3 -m unittest discover -s tests -v
Ran 124 tests
OK

git diff --check
OK

禁句扫描
OK

browser smoke
initial: Fit / fit
zoom in: 150% / manual / 150%
after page change: 150% / manual
fit: Fit / fit
OK
```

P1-18 已完成能力：

```text
Review Cockpit 中央预览新增 Fit、缩小、放大和比例显示
预览图使用可滚动画布，手动缩放时支持查看细节
页面切换后保留当前缩放状态
支持 Cmd/Ctrl + +、Cmd/Ctrl + -、Cmd/Ctrl + 0 快捷缩放
新增 zoom 双语文案，并补静态测试覆盖缩放入口
```

P1-19 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server -v
Ran 15 tests
OK

browser smoke
event filter: manual_action -> 1 / 5 visible
event filter: warning -> 1 / 5 visible
event cards: type、time、message、step/action、target、refs visible
OK
```

P1-19 已完成能力：

```text
Review Cockpit 底部事件抽屉新增事件类型筛选
事件抽屉按 run_created、step_started、step_completed、tool_call、tool_result、decision、manual_action、warning、error 展示
事件卡显示类型、时间、消息、阶段、动作、目标和引用
warning / error 事件使用不同左侧强调色
语言切换后事件抽屉保留当前事件数据并刷新文案
新增 event_type 双语文案，并补静态测试覆盖事件抽屉入口
```

P1-20 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_preview_manifest -v
Ran 27 tests
OK

browser smoke
quality gate cards: draft gate rework_required visible
page findings: P1 finding and repair instruction visible
approval guard: selecting approved disables save
OK
```

P1-20 已完成能力：

```text
Review Cockpit 右侧新增质量门禁面板
质量门禁面板显示 draft、render、delivery 状态、finding 数量和阻断标记
选中页面后显示当前页质量问题和修复建议
存在 P0/P1 finding 或生成失败时，批准动作前置显示阻断提示
用户选择批准且页面存在阻断时，保存按钮禁用
新增 quality guard 双语文案，并补静态测试覆盖质量门禁入口
```

P1-21 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_preview_manifest -v
Ran 27 tests
OK

browser smoke
run blockers: P1 blocker visible with refs
repair actions: repair instruction visible with refs
approval guard: blocked page still disables approved save
OK
```

P1-21 已完成能力：

```text
Preview API 的 quality 摘要新增 blockers 和 repair_actions
blockers 从 P0/P1 findings 和 gate blocking 状态聚合
repair_actions 从 findings 的 repair_instruction 和 report repair_plan 聚合
Review Cockpit 质量门禁面板新增整份 Deck 阻断列表
Review Cockpit 质量门禁面板新增建议修复动作列表
新增 run blockers / repair actions 双语文案，并补 API 与静态测试覆盖
```

P1-22 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_preview_manifest -v
Ran 27 tests
OK

browser smoke
repair action copy: status updated
jump-to-page: selected page changes to page_001
rerun gate command: command copied and shown
OK
```

P1-22 已完成能力：

```text
Review Cockpit repair action 新增复制修复说明按钮
带 page_id 的 blocker / repair action 新增跳到页面按钮
每条 blocker / repair action 新增复制重跑 gate 命令按钮
跳转页面会清空页面筛选，确保目标页可见
复制动作带剪贴板 fallback 和状态反馈
新增 repair action 操作双语文案，并补静态测试覆盖
```

P1-23 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_preview_manifest tests.test_quality_gate -v
Ran 38 tests
OK

python3 -m unittest discover -s tests -v
Ran 128 tests
OK

browser smoke
repair status: Open / Done toggles visible
rerun gate: Draft Gate rerun from Review Cockpit
OK
```

P1-23 已完成能力：

```text
Review Cockpit repair action 新增处理状态标签
repair action 可在 Web UI 标记为已处理或重开
修复状态写入 quality_reports/repair_checklist.json
Preview API 新增 POST /api/quality/repair
Preview API 新增 POST /api/quality/<gate>/rerun
Web UI 可直接触发 quality gate 重跑，并自动刷新质量报告
保留复制重跑命令作为备用操作
新增 repair checklist 和 rerun gate API 测试覆盖
```

P1-24 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_preview_manifest tests.test_quality_gate -v
Ran 39 tests
OK

python3 -m unittest discover -s tests -v
Ran 129 tests
OK

browser smoke
repair note: saved and preserved after status toggle
batch rerun: visible gate rerun from Review Cockpit
OK
```

P1-24 已完成能力：

```text
Review Cockpit repair action 新增修复备注输入和保存按钮
切换 repair action 处理状态时保留当前备注
Preview API 新增 POST /api/quality/rerun-all
批量重跑支持单个 gate 成功、单个 gate 失败的混合结果
批量重跑写入 quality.gates.batch_rerun_requested 事件
质量面板顶部新增重跑全部可见 Gate 操作
新增 repair note 和 batch rerun API 测试覆盖
```

P1-25 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_preview_manifest tests.test_quality_gate -v
Ran 39 tests
OK

python3 -m unittest discover -s tests -v
Ran 129 tests
OK

browser smoke
quality diff: absent before rerun, visible after rerun
quality card: resolved / new / persistent counts visible
OK
```

P1-25 已完成能力：

```text
quality gate 重跑前读取旧报告摘要
quality gate 重跑后写入 quality_reports/<gate>_gate.diff.json
diff 记录 status 前后变化、finding 数量变化、已解决、新增和仍存在问题数
Preview API 返回单 gate 和 batch rerun 的 diff
GET /api/deck 的 quality 摘要带最近一次 diff
Review Cockpit quality gate 卡片展示 diff 摘要
新增 report diff API 与静态入口测试覆盖
```

P1-26 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_preview_manifest tests.test_quality_gate -v
Ran 39 tests
OK

python3 -m unittest discover -s tests -v
Ran 129 tests
OK

browser smoke
diff detail: resolved / new / persistent findings visible
diff history: history count reaches 2 after two reruns
OK
```

P1-26 已完成能力：

```text
diff 产物新增 persistent 问题明细
每次 quality gate 重跑追加 quality_reports/<gate>_gate.diff.history.jsonl
GET /api/deck 的 quality diff 回传 history_count 和最近 5 次 history
Review Cockpit quality gate 卡片显示历史次数
Review Cockpit quality gate 卡片显示 resolved / new / persistent 明细
新增 diff history API 与静态入口测试覆盖
```

P1-27 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_preview_manifest tests.test_quality_gate -v
Ran 39 tests
OK

python3 -m unittest discover -s tests -v
Ran 129 tests
OK

git diff --check
OK

forbidden phrase scan
OK

browser smoke
quality risk summary: High-Risk Findings visible
severity count: P1 visible
top page: page_001 visible
OK
```

P1-27 已完成能力：

```text
Preview API 新增 quality_risk_summary
quality_risk_summary 聚合 P0/P1 blockers 的总数、严重等级计数、gate 计数和页面计数
quality_risk_summary 返回置顶 finding 和高风险页面列表
Review Cockpit 质量面板新增高风险 finding 聚合区
高风险 finding 聚合区展示总量、P0/P1 计数、高风险页面和置顶问题
新增 API 与静态入口测试覆盖
```

P1-28 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_preview_manifest tests.test_quality_gate -v
Ran 39 tests
OK

python3 -m unittest discover -s tests -v
Ran 129 tests
OK

git diff --check
OK

forbidden phrase scan
OK

browser smoke
quality risk filter: visible page count reduced to 1 / 3
top risk page button: jumps to page_001
OK
```

P1-28 已完成能力：

```text
左侧页面筛选新增质量风险筛选项
质量风险筛选可筛出含 P0/P1 finding 的页面
高风险摘要新增只看高风险页按钮
高风险页面聚合项改为可点击按钮
点击高风险页面可跳转到对应页面
新增静态入口测试和双语文案
```

P1-29 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_preview_manifest tests.test_quality_gate tests.test_orchestration -v
Ran 47 tests
OK

browser smoke
export readiness: Export Preflight visible
export blocker explanation: 页面缺少主论点 visible
OK
```

P1-29 已完成能力：

```text
GET /api/deck 新增只读 export_readiness
export_readiness 返回导出状态、可导出页数、质量门禁摘要和阻断原因
Review Cockpit 导出面板显示导出前检查
导出面板显示高风险数和可导出页数
导出面板显示质量门禁或页面级阻断原因
新增 API、静态入口和双语文案测试覆盖
```

P1-30 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_preview_manifest tests.test_quality_gate tests.test_orchestration -v
Ran 47 tests
OK

browser smoke
export blocker actions: jump / copy / rerun buttons visible
export blocked button: disabled
OK
```

P1-30 已完成能力：

```text
导出阻断状态禁用默认导出按钮
导出阻断项新增复制阻断说明按钮
导出阻断项新增跳到页面按钮
导出阻断项新增重跑关联 Gate 按钮
导出阻断操作复用现有页面跳转、复制和 Gate 重跑能力
新增静态入口和双语文案测试覆盖
```

P1-31 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_feedback -v
Ran 29 tests
OK

browser smoke
delivery outcome pending prompt: visible after export
delivery outcome recorded state: visible after record
OK
```

P1-31 已完成能力：

```text
GET /api/deck 新增只读 delivery_outcome 摘要
Preview API 新增 POST /api/delivery-outcome
Review Cockpit 导出面板新增交付结果区
生成批准页队列后提示待记录交付结果
交付结果区可写入 delivered、final_artifact、customer_status 和 customer_notes
写入交付结果后复用现有 record_delivery_outcome，同步 run feedback 与 workspace feedback
新增 API、静态入口和双语文案测试覆盖
```

P1-32 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_feedback -v
Ran 30 tests
OK

browser smoke
asset health after delivery: strong reuse candidate visible
manual asset health refresh: success status visible
OK
```

P1-32 已完成能力：

```text
Preview API 新增 POST /api/workspace-asset-health/rerun
Review Cockpit 工作区资产健康面板新增刷新按钮
记录 delivery outcome 后自动刷新 workspace asset health
delivery outcome API 返回最新 workspace_asset_health 摘要
工作区资产健康刷新写入 typed event
新增 API、静态入口和双语文案测试覆盖
```

P1-33 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_feedback -v
Ran 31 tests
OK

browser smoke
delivery review pending state visible
delivery review recorded state visible
latest delivery customer feedback visible
workspace feedback counts visible
OK
```

P1-33 已完成能力：

```text
新增 feedback delivery review summary 模块
GET /api/deck 新增只读 delivery_review 摘要
delivery outcome API 返回最新 delivery_review 摘要
Review Cockpit 导出面板新增交付复盘摘要
交付复盘展示本次交付、workspace feedback 计数、业务信号和最近交付记录
新增 API、静态入口、反馈模块和双语文案测试覆盖
```

P1-34 专项验证：

```text
node --check scripts/preview/static/app.js
OK

python3 -m unittest tests.test_preview_i18n tests.test_preview_server tests.test_feedback -v
Ran 31 tests
OK

browser smoke
feedback trend visible after delivery outcome
reuse recommendations visible after delivery outcome
positive rate and strong asset rate visible
OK
```

P1-34 已完成能力：

```text
delivery_review 新增 trend 摘要
delivery_review 新增 reuse_recommendations 推荐列表
Review Cockpit 交付复盘面板展示反馈趋势
Review Cockpit 交付复盘面板展示复用推荐、推荐原因和信心值
复用推荐复用 workspace asset health 的资产汇总口径
新增 API、静态入口、反馈模块和双语文案测试覆盖
```

P1-35 专项验证：

```text
python3 -m py_compile scripts/planning/sourcing_decider.py scripts/deck_master.py tests/test_sourcing_decider.py
OK

python3 -m unittest tests.test_sourcing_decider -v
Ran 7 tests
OK

python3 -m unittest discover -s tests -v
Ran 135 tests
OK

node --check scripts/preview/static/app.js
OK

git diff --check
OK

禁用句式扫描
OK
```

P1-35 已完成能力：

```text
decide-sourcing 在 run 绑定 workspace 时读取 delivery_review.workspace_feedback.reuse_recommendations
候选页排序新增 workspace_feedback_boost，命中资产写入 workspace_feedback_signal
sourcing_plan 顶层新增 feedback_signal_summary
无 workspace 或无反馈推荐时，旧排序保持稳定
新增 sourcing 单元测试覆盖反馈提升、无反馈稳定、汇总输出
```

P1-36 专项验证：

```text
python3 -m py_compile scripts/planning/sourcing_decider.py scripts/deck_master.py scripts/preview/server.py tests/test_sourcing_decider.py tests/test_end_to_end_autoplan.py tests/test_conversation_cli.py tests/test_preview_server.py
OK

python3 -m unittest tests.test_sourcing_decider tests.test_end_to_end_autoplan tests.test_conversation_cli tests.test_preview_server.StudioServerTests -v
Ran 11 tests
OK

python3 -m unittest discover -s tests -v
Ran 136 tests
OK

node --check scripts/preview/static/app.js
OK

git diff --check
OK

禁用句式扫描
OK
```

P1-36 已完成能力：

```text
新增 apply_sourcing_to_page_tasks，将 sourcing_plan 决策按 beat_id 写回 page_tasks.tasks[].sourcing
page_tasks 顶层新增 sourcing_sync 审计摘要，记录 updated_tasks、missing_task_decisions 和 feedback_signal_summary
CLI decide-sourcing 写入 sourcing_plan 后同步 page_tasks
Web Studio 创建 run 时生成 page_tasks，并在 sourcing 后同步分层状态
端到端测试覆盖 CLI autoplan、会话链路和 Web Studio 创建 run 的 page_tasks sourcing sync
```

P1-37 专项验证：

```text
python3 -m py_compile scripts/quality/gate_runner.py tests/test_quality_gate.py
OK

python3 -m unittest tests.test_quality_gate.DraftGateTests.test_draft_gate_checks_sourcing_layer_state tests.test_quality_gate.DraftGateTests.test_draft_gate_checks_decision_intent_evidence_policy_and_claim_links tests.test_conversation_cli.ConversationCliTests.test_local_context_to_preview_and_draft_gate -v
Ran 3 tests
OK

python3 -m unittest discover -s tests -v
Ran 137 tests
OK

node --check scripts/preview/static/app.js
OK

git diff --check
OK

禁用句式扫描
OK
```

P1-37 已完成能力：

```text
Draft Gate 读取 page_tasks.tasks[].sourcing
缺 sourcing decision 输出 P1 finding
sourcing_sync.missing_task_decisions 输出 P1 finding
manual_placeholder 页面输出 P1 finding
reuse / adapt 页面缺 selected_candidate 输出 P1 finding
reuse 页面缺截图输出 P1 finding
新增质量门禁测试覆盖 sourcing 分层状态
```

P1-38 专项验证：

```text
python3 -m py_compile scripts/preview/manifest.py scripts/preview/server.py tests/test_preview_server.py tests/test_preview_i18n.py
OK

python3 -m unittest tests.test_preview_server.ServerTests.test_quality_repair_api_persists_checklist_status tests.test_preview_server.ServerTests.test_quality_repair_actions_keep_finding_level_items tests.test_preview_i18n.PreviewI18nTests.test_review_cockpit_exposes_quality_gate_guard -v
Ran 3 tests
OK

node --check scripts/preview/static/app.js
OK

python3 -m unittest discover -s tests -v
Ran 138 tests
OK

git diff --check
OK

禁用句式扫描
OK
```

P1-38 已完成能力：

```text
repair action 改为 finding 级粒度，同一 repair_instruction 下的不同页面问题保留独立 repair_key
GET /api/page/<page_id> 返回 page quality finding 的 repair_status、repair_note 和 repair_updated_at
Review Cockpit 当前页 quality finding 支持标记已处理、重开、保存备注、复制修复说明和重跑 Gate
quality_reports/repair_checklist.json 继续作为统一修复状态文件
新增 Preview API 与前端静态测试覆盖 finding-level repair action
```

P1-39 专项验证：

```text
python3 -m py_compile scripts/preview/manifest.py scripts/preview/server.py tests/test_preview_server.py tests/test_preview_i18n.py
OK

python3 -m unittest tests.test_preview_server.ServerTests.test_quality_repair_api_rejects_manual_resolved_status tests.test_preview_server.ServerTests.test_quality_rerun_marks_done_repair_resolved tests.test_preview_server.ServerTests.test_quality_rerun_api_writes_report_and_event tests.test_preview_i18n.PreviewI18nTests.test_language_packs_have_matching_keys tests.test_preview_i18n.PreviewI18nTests.test_review_cockpit_exposes_quality_gate_guard -v
Ran 5 tests
OK

node --check scripts/preview/static/app.js
OK

python3 -m unittest discover -s tests -v
Ran 140 tests
OK

git diff --check
OK

禁用句式扫描
OK
```

P1-39 已完成能力：

```text
repair checklist 状态扩展为 open / done / resolved
Gate 重跑时识别已处理且已消失的 finding，并自动回写 resolved 状态
手动写入 resolved 状态会被拒绝，保证复检结论只来自 quality rerun
quality_reports/<gate>_gate.diff.json 展示 repair_resolution.resolved_repairs
事件流追加 quality.repair_status.resolved，便于审计本次复检关闭了哪些修复项
Review Cockpit diff 展示已关闭修复项数量，并支持 resolved 状态重开
新增 Preview API 与前端静态测试覆盖 repair resolved 闭环
```

P1-40 专项验证：

```text
python3 -m py_compile scripts/preview/manifest.py scripts/preview/server.py tests/test_preview_server.py tests/test_preview_i18n.py
OK

python3 -m unittest tests.test_preview_server.ServerTests.test_quality_repair_api_persists_checklist_status tests.test_preview_server.ServerTests.test_quality_repair_actions_keep_finding_level_items tests.test_preview_i18n.PreviewI18nTests.test_language_packs_have_matching_keys tests.test_preview_i18n.PreviewI18nTests.test_review_cockpit_exposes_quality_gate_guard -v
Ran 4 tests
OK

node --check scripts/preview/static/app.js
OK

python3 -m json.tool scripts/preview/static/i18n/zh-CN.json
OK

python3 -m json.tool scripts/preview/static/i18n/en-US.json
OK

python3 -m unittest discover -s tests -v
Ran 140 tests
OK

git diff --check
OK

禁用句式扫描
OK
```

P1-40 已完成能力：

```text
每个 quality gate 返回 repair_summary 只读摘要
repair_summary 按 gate、严重级别和修复说明聚合 finding 级 repair action
repair_summary 展示 total、status_counts、page_count、page_ids 和 sample_repair_keys
Review Cockpit 新增修复批次区块，展示待处理、已处理、复检通过和影响页面范围
finding 级 repair action 继续保留独立操作，不改变现有修复 API
新增 Preview API 与前端静态测试覆盖 repair summary 聚合与展示
```

P1-41 专项验证：

```text
python3 -m py_compile scripts/preview/manifest.py scripts/preview/server.py tests/test_preview_server.py tests/test_preview_i18n.py
OK

python3 -m unittest tests.test_preview_server.ServerTests.test_quality_repair_batch_api_updates_matching_repairs tests.test_preview_i18n.PreviewI18nTests.test_language_packs_have_matching_keys tests.test_preview_i18n.PreviewI18nTests.test_review_cockpit_exposes_quality_gate_guard -v
Ran 3 tests
OK

node --check scripts/preview/static/app.js
OK

python3 -m json.tool scripts/preview/static/i18n/zh-CN.json
OK

python3 -m json.tool scripts/preview/static/i18n/en-US.json
OK

python3 -m unittest discover -s tests -v
Ran 141 tests
OK

git diff --check
OK

禁用句式扫描
OK
```

P1-41 已完成能力：

```text
新增 POST /api/quality/repair-batch
repair batch 按 repair_summary.group_key 批量写入 open / done 人工状态
批量操作继续写入 quality_reports/repair_checklist.json
事件流追加 quality.repair_batch.updated，保留 group_key、更新数量和 repair_keys
Review Cockpit 修复批次卡片新增批量标记已处理和批量重开按钮
新增 Preview API 与前端静态测试覆盖批量修复操作
```

P1-42 专项验证：

```text
python3 -m py_compile scripts/deck_master.py tests/test_conversation_cli.py
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_print_url_only_reports_launch_metadata -v
Ran 1 test
OK

python3 scripts/deck_master.py open-preview --run-dir examples/preview-run --port 5098 --print-url-only
OK

test ! -e examples/preview-run/next_step.json
OK

python3 -m unittest discover -s tests -v
Ran 142 tests
OK

git diff --check
OK

禁用句式扫描
OK
```

P1-42 已完成能力：

```text
新增 python3 scripts/deck_master.py studio
新增 open-preview 兼容别名
支持 --run-dir 固定 run 预览模式
支持 --run-id + --runs-dir Studio 指定 run URL
支持 --print-url-only 输出 URL、启动命令、run 状态和 next_step
--print-url-only 只读解析状态，不写入 next_step.json
真实启动复用 scripts/preview/server.py，避免新增 Web runtime
新增 CLI 测试覆盖 studio/open-preview 启动元数据
```

P1-43 专项验证：

```text
python3 -m py_compile scripts/deck_master.py scripts/preview/smoke_review_cockpit.py tests/test_conversation_cli.py
OK

python3 scripts/deck_master.py studio-smoke
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_smoke_validates_fixture_run -v
Ran 1 test
OK

python3 -m unittest discover -s tests -v
Ran 143 tests
OK
```

P1-43 已完成能力：

```text
新增 scripts/preview/smoke_review_cockpit.py
新增 python3 scripts/deck_master.py studio-smoke
无参数时复制 examples/preview-run 到临时 runs 目录并启动 localhost Studio
自动检查首页、前端脚本、run 列表、Deck API 和首张预览资源
支持 --run-dir 或 --run-id --runs-dir 检查真实 run
smoke 模式输出纯 JSON，便于 agent 和 CI 解析
新增 CLI 测试覆盖 studio-smoke fixture run
```

P1-44 专项验证：

```text
tmp=$(mktemp -d); python3 scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --runs-dir "$tmp" --run-id real-smoke > "$tmp/autoplan.json" && python3 scripts/deck_master.py studio-smoke --run-dir "$tmp/real-smoke"; result_code=$?; rm -rf "$tmp"; exit $result_code
OK

python3 -m unittest tests.test_end_to_end_autoplan.EndToEndAutoplanTests.test_fixture_autoplan_builds_preview_manifest -v
Ran 1 test
OK
```

P1-44 已完成能力：

```text
E2E fixture 增加 autoplan-generated run studio-smoke 回归
验证真实 autoplan 产物可被 localhost Studio 列出并读取
验证真实 run 的 Deck API 页数与 preview_manifest 保持一致
验证真实 run 的首张预览资源可通过 Review Cockpit 服务访问
```

P1-45 专项验证：

```text
python3 -m py_compile scripts/deck_master.py scripts/preview/browser_smoke_review_cockpit.py tests/test_conversation_cli.py
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_browser_smoke_reports_missing_node -v
Ran 1 test
OK

python3 scripts/deck_master.py studio-browser-smoke --output-dir <tmp>
OK

tmp=$(mktemp -d); python3 scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --runs-dir "$tmp" --run-id p1-45-real-browser > "$tmp/autoplan.json" && python3 scripts/deck_master.py studio-browser-smoke --run-dir "$tmp/p1-45-real-browser" --output-dir docs/migration/review-cockpit-smoke/p1-45 --language zh-CN; result_code=$?; rm -rf "$tmp"; exit $result_code
OK

browser report
run_id=p1-45-real-browser
viewport=1440x1000
language=zh-CN
pages=12
preview_visible_in_viewport=true
zoom_label=125%
current_label=2 / 12 · beat_02_problem
console_errors=0
```

P1-45 截图证据：

```text
docs/migration/review-cockpit-smoke/p1-45/01-cockpit-overview.png
docs/migration/review-cockpit-smoke/p1-45/02-preview-zoom.png
docs/migration/review-cockpit-smoke/p1-45/03-page-navigation.png
docs/migration/review-cockpit-smoke/p1-45/04-quality-export-panels.png
docs/migration/review-cockpit-smoke/p1-45/browser_smoke_report.json
```

P1-45 已完成能力：

```text
新增 scripts/preview/browser_smoke_review_cockpit.py
新增 python3 scripts/deck_master.py studio-browser-smoke
browser smoke 使用 Playwright 打开真实浏览器视口，默认 zh-CN
检查页面列表、首屏预览图、缩放、切页、质量面板、导出面板和截图归档
报告记录 preview image bounding box 和 visibleInViewport
修复 Review Cockpit 三栏布局：桌面端固定 100vh，左右栏独立滚动，中间预览首屏可见
```

P1-46 专项验证：

```text
python3 -m py_compile scripts/deck_master.py scripts/preview/browser_smoke_review_cockpit.py tests/test_conversation_cli.py
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_browser_smoke_reports_missing_node -v
Ran 1 test
OK

tmp=$(mktemp -d); python3 scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --runs-dir "$tmp" --run-id p1-46-quality-browser > "$tmp/autoplan.json" && python3 scripts/deck_master.py quality-gate --run-dir "$tmp/p1-46-quality-browser" draft > "$tmp/draft_gate.json" && python3 scripts/deck_master.py studio-browser-smoke --run-dir "$tmp/p1-46-quality-browser" --output-dir docs/migration/review-cockpit-smoke/p1-46 --language zh-CN --expect-quality-findings; result_code=$?; rm -rf "$tmp"; exit $result_code
OK

browser report
run_id=p1-46-quality-browser
viewport=1440x1000
language=zh-CN
pages=12
preview_visible_in_viewport=true
zoom_label=125%
current_label=2 / 12 · beat_02_problem
console_errors=0
gateCards=1
riskSummaries=1
runBlockers=4
repairActions=5
repairBatches=4
exportBlockers=5
filteredRiskPages=3
```

P1-46 截图证据：

```text
docs/migration/review-cockpit-smoke/p1-46/01-cockpit-overview.png
docs/migration/review-cockpit-smoke/p1-46/02-preview-zoom.png
docs/migration/review-cockpit-smoke/p1-46/03-page-navigation.png
docs/migration/review-cockpit-smoke/p1-46/04-quality-export-panels.png
docs/migration/review-cockpit-smoke/p1-46/05-quality-findings-filter.png
docs/migration/review-cockpit-smoke/p1-46/browser_smoke_report.json
```

P1-46 已完成能力：

```text
studio-browser-smoke 新增 --expect-quality-findings
开启后强校验 quality gate card、risk summary、run blocker、repair action、repair batch、export blocker 和 high-risk page filter
报告新增 quality_stats 和 quality_findings_visible check
质量样本归档第 5 张截图 05-quality-findings-filter.png
CLI 参数、专项测试、Spec Pack、合并版开发规范和迁移日志已同步
```

P1-47 专项验证：

```text
python3 -m py_compile scripts/deck_master.py scripts/preview/browser_smoke_review_cockpit.py tests/test_conversation_cli.py
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_browser_smoke_reports_missing_node -v
Ran 1 test
OK

python3 scripts/deck_master.py studio-browser-smoke --output-dir docs/migration/review-cockpit-smoke/p1-47 --language zh-CN --exercise-review-actions
OK

browser report
run_id=smoke-run
viewport=1440x1000
language=zh-CN
pages=3
preview_visible_in_viewport=true
zoom_label=125%
review_actions_persisted=true
rejectedPersisted=true
approvedPersisted=true
finalReviewStatus=approved
console_errors=0
```

P1-47 截图证据：

```text
docs/migration/review-cockpit-smoke/p1-47/01-cockpit-overview.png
docs/migration/review-cockpit-smoke/p1-47/02-preview-zoom.png
docs/migration/review-cockpit-smoke/p1-47/03-page-navigation.png
docs/migration/review-cockpit-smoke/p1-47/04-quality-export-panels.png
docs/migration/review-cockpit-smoke/p1-47/06-review-actions.png
docs/migration/review-cockpit-smoke/p1-47/browser_smoke_report.json
```

P1-47 已完成能力：

```text
studio-browser-smoke 新增 --exercise-review-actions
开启后在临时 run 中执行 reject、写备注、approve
操作后通过 Deck API 回读 manifest，确认 rejectedPersisted 和 approvedPersisted
报告新增 review_action_stats 和 review_actions_persisted check
审查操作样本归档 06-review-actions.png
CLI 参数、专项测试、Spec Pack、合并版开发规范和迁移日志已同步
```

P1-48 专项验证：

```text
python3 -m py_compile scripts/deck_master.py scripts/preview/browser_smoke_review_cockpit.py tests/test_conversation_cli.py
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_browser_smoke_reports_missing_node -v
Ran 1 test
OK

python3 scripts/deck_master.py studio-browser-smoke --output-dir docs/migration/review-cockpit-smoke/p1-48 --language zh-CN --exercise-export-delivery
OK

browser report
run_id=smoke-run
viewport=1440x1000
language=zh-CN
pages=3
preview_visible_in_viewport=true
zoom_label=125%
export_delivery_persisted=true
pendingAfterExport=true
recordedAfterDelivery=true
customerStatusPersisted=true
finalArtifactPersisted=true
notesPersisted=true
deliveredPages=1
console_errors=0
```

P1-48 截图证据：

```text
docs/migration/review-cockpit-smoke/p1-48/01-cockpit-overview.png
docs/migration/review-cockpit-smoke/p1-48/02-preview-zoom.png
docs/migration/review-cockpit-smoke/p1-48/03-page-navigation.png
docs/migration/review-cockpit-smoke/p1-48/04-quality-export-panels.png
docs/migration/review-cockpit-smoke/p1-48/07-export-delivery.png
docs/migration/review-cockpit-smoke/p1-48/browser_smoke_report.json
```

P1-48 已完成能力：

```text
studio-browser-smoke 新增 --exercise-export-delivery
开启后在临时 run 中点击生成批准页队列
随后记录最终文件路径、正向客户反馈和交付备注
操作后通过 Deck API 回读 delivery_outcome，确认 pendingAfterExport 和 recordedAfterDelivery
报告新增 export_delivery_stats 和 export_delivery_persisted check
导出交付样本归档 07-export-delivery.png
CLI 参数、专项测试、Spec Pack、合并版开发规范和迁移日志已同步
```

P1-49 专项验证：

```text
python3 -m py_compile scripts/deck_master.py scripts/preview/browser_smoke_review_cockpit.py tests/test_conversation_cli.py
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_browser_smoke_reports_missing_node -v
Ran 1 test
OK

python3 scripts/deck_master.py studio-browser-smoke --output-dir docs/migration/review-cockpit-smoke/p1-49 --language zh-CN --exercise-workspace-asset-health
OK

browser report
run_id=smoke-run
viewport=1440x1000
language=zh-CN
pages=3
preview_visible_in_viewport=true
zoom_label=125%
workspace_asset_health_refreshed=true
refreshed=true
workspacePresent=true
strongReuseCandidates=1
uniqueAssets=1
topAssetCount=1
console_errors=0
```

P1-49 截图证据：

```text
docs/migration/review-cockpit-smoke/p1-49/01-cockpit-overview.png
docs/migration/review-cockpit-smoke/p1-49/02-preview-zoom.png
docs/migration/review-cockpit-smoke/p1-49/03-page-navigation.png
docs/migration/review-cockpit-smoke/p1-49/04-quality-export-panels.png
docs/migration/review-cockpit-smoke/p1-49/08-workspace-asset-health.png
docs/migration/review-cockpit-smoke/p1-49/browser_smoke_report.json
```

P1-49 已完成能力：

```text
studio-browser-smoke 新增 --exercise-workspace-asset-health
开启后为临时 run 绑定最小 workspace feedback fixture
浏览器点击刷新资产健康，并通过 Deck API 回读 workspace_asset_health
校验 refreshed、workspacePresent、strongReuseCandidates 和 topAssetCount
资产健康样本归档 08-workspace-asset-health.png
CLI 参数、专项测试、Spec Pack、合并版开发规范和迁移日志已同步
```

P1-50 专项验证：

```text
python3 -m py_compile scripts/deck_master.py scripts/preview/browser_smoke_review_cockpit.py tests/test_conversation_cli.py
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_browser_smoke_reports_missing_node -v
Ran 1 test
OK

python3 scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --runs-dir /tmp/deck-master-p1-50.GrrRy2 --run-id p1-50-quality-repair
OK
pages=12

python3 scripts/deck_master.py quality-gate draft --run-dir /tmp/deck-master-p1-50.GrrRy2/p1-50-quality-repair
OK
status=rework_required
findings=8

python3 scripts/deck_master.py studio-browser-smoke --run-dir /tmp/deck-master-p1-50.GrrRy2/p1-50-quality-repair --output-dir docs/migration/review-cockpit-smoke/p1-50 --language zh-CN --expect-quality-findings --exercise-quality-repair-actions
OK

browser report
run_id=p1-50-quality-repair
viewport=1440x1000
language=zh-CN
pages=12
preview_visible_in_viewport=true
zoom_label=125%
gateCards=1
riskSummaries=1
runBlockers=4
repairActions=5
repairBatches=4
exportBlockers=5
filteredRiskPages=3
notePersisted=true
donePersisted=true
noteRetainedAfterDone=true
console_errors=0
```

P1-50 截图证据：

```text
docs/migration/review-cockpit-smoke/p1-50/01-cockpit-overview.png
docs/migration/review-cockpit-smoke/p1-50/02-preview-zoom.png
docs/migration/review-cockpit-smoke/p1-50/03-page-navigation.png
docs/migration/review-cockpit-smoke/p1-50/04-quality-export-panels.png
docs/migration/review-cockpit-smoke/p1-50/05-quality-findings-filter.png
docs/migration/review-cockpit-smoke/p1-50/09-quality-repair-actions.png
docs/migration/review-cockpit-smoke/p1-50/browser_smoke_report.json
```

P1-50 已完成能力：

```text
studio-browser-smoke 新增 --exercise-quality-repair-actions
开启后在质量报告充足 run 中保存 repair note
随后点击 repair action 标记已处理
操作后通过 Deck API 回读 repair checklist，确认 notePersisted、donePersisted 和 noteRetainedAfterDone
质量修复样本归档 09-quality-repair-actions.png
CLI 参数、专项测试、Spec Pack、合并版开发规范和迁移日志已同步
```

P1-51 专项验证：

```text
python3 -m py_compile scripts/deck_master.py scripts/preview/browser_smoke_review_cockpit.py tests/test_conversation_cli.py
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_browser_smoke_reports_missing_node -v
Ran 1 test
OK

python3 scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --runs-dir /tmp/deck-master-p1-51.Rox7LO --run-id p1-51-quality-repair-batch
OK
pages=12

python3 scripts/deck_master.py quality-gate draft --run-dir /tmp/deck-master-p1-51.Rox7LO/p1-51-quality-repair-batch
OK
status=rework_required
findings=8

python3 scripts/deck_master.py studio-browser-smoke --run-dir /tmp/deck-master-p1-51.Rox7LO/p1-51-quality-repair-batch --output-dir docs/migration/review-cockpit-smoke/p1-51 --language zh-CN --expect-quality-findings --exercise-quality-repair-batch-actions
OK

browser report
run_id=p1-51-quality-repair-batch
viewport=1440x1000
language=zh-CN
pages=12
preview_visible_in_viewport=true
zoom_label=125%
gateCards=1
riskSummaries=1
runBlockers=4
repairActions=5
repairBatches=4
exportBlockers=5
filteredRiskPages=3
donePersisted=true
reopenPersisted=true
doneCountAfterDone=3
openCountAfterDone=0
openCountAfterReopen=3
console_errors=0
```

P1-51 截图证据：

```text
docs/migration/review-cockpit-smoke/p1-51/01-cockpit-overview.png
docs/migration/review-cockpit-smoke/p1-51/02-preview-zoom.png
docs/migration/review-cockpit-smoke/p1-51/03-page-navigation.png
docs/migration/review-cockpit-smoke/p1-51/04-quality-export-panels.png
docs/migration/review-cockpit-smoke/p1-51/05-quality-findings-filter.png
docs/migration/review-cockpit-smoke/p1-51/10-quality-repair-batch-actions.png
docs/migration/review-cockpit-smoke/p1-51/browser_smoke_report.json
```

P1-51 已完成能力：

```text
studio-browser-smoke 新增 --exercise-quality-repair-batch-actions
开启后在质量报告充足 run 中点击 repair batch 批量标记已处理
随后点击同一批次批量重开
操作后通过 Deck API 回读 repair summary，确认 donePersisted、reopenPersisted、doneCountAfterDone、openCountAfterDone 和 openCountAfterReopen
质量批量修复样本归档 10-quality-repair-batch-actions.png
CLI 参数、专项测试、Spec Pack、合并版开发规范和迁移日志已同步
```

P1-52 专项验证：

```text
python3 -m py_compile scripts/deck_master.py scripts/preview/browser_smoke_review_cockpit.py tests/test_conversation_cli.py
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_browser_smoke_reports_missing_node -v
Ran 1 test
OK

python3 scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --runs-dir /tmp/deck-master-p1-52.GP8Ttt --run-id p1-52-quality-rerun
OK
pages=12

python3 scripts/deck_master.py quality-gate draft --run-dir /tmp/deck-master-p1-52.GP8Ttt/p1-52-quality-rerun
OK
status=rework_required
findings=8

python3 scripts/deck_master.py studio-browser-smoke --run-dir /tmp/deck-master-p1-52.GP8Ttt/p1-52-quality-rerun --output-dir docs/migration/review-cockpit-smoke/p1-52 --language zh-CN --expect-quality-findings --exercise-quality-rerun-actions
OK

browser report
run_id=p1-52-quality-rerun
viewport=1440x1000
language=zh-CN
pages=12
preview_visible_in_viewport=true
zoom_label=125%
gateCards=1
riskSummaries=1
runBlockers=4
repairActions=5
repairBatches=4
exportBlockers=5
filteredRiskPages=3
diffAvailable=true
historyPersisted=true
historyCount=1
resolvedFindings=0
newFindings=0
persistentFindings=8
console_errors=0
```

P1-52 截图证据：

```text
docs/migration/review-cockpit-smoke/p1-52/01-cockpit-overview.png
docs/migration/review-cockpit-smoke/p1-52/02-preview-zoom.png
docs/migration/review-cockpit-smoke/p1-52/03-page-navigation.png
docs/migration/review-cockpit-smoke/p1-52/04-quality-export-panels.png
docs/migration/review-cockpit-smoke/p1-52/05-quality-findings-filter.png
docs/migration/review-cockpit-smoke/p1-52/11-quality-rerun-actions.png
docs/migration/review-cockpit-smoke/p1-52/browser_smoke_report.json
```

P1-52 已完成能力：

```text
studio-browser-smoke 新增 --exercise-quality-rerun-actions
开启后在质量报告充足 run 中点击单个 Gate 重跑
操作后通过 Deck API 回读 quality diff 与 history count
校验 diffAvailable、historyPersisted 和 historyCount
质量重跑样本归档 11-quality-rerun-actions.png
CLI 参数、专项测试、Spec Pack、合并版开发规范和迁移日志已同步
```

P1-53 专项验证：

```text
python3 -m py_compile scripts/deck_master.py scripts/preview/browser_smoke_review_cockpit.py tests/test_conversation_cli.py
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_browser_smoke_reports_missing_node -v
Ran 1 test
OK

python3 scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --runs-dir /tmp/deck-master-p1-53.7Cb6Iw --run-id p1-53-quality-rerun-all
OK
pages=12

python3 scripts/deck_master.py quality-gate draft --run-dir /tmp/deck-master-p1-53.7Cb6Iw/p1-53-quality-rerun-all
OK
status=rework_required
findings=8

python3 scripts/deck_master.py studio-browser-smoke --run-dir /tmp/deck-master-p1-53.7Cb6Iw/p1-53-quality-rerun-all --output-dir docs/migration/review-cockpit-smoke/p1-53 --language zh-CN --expect-quality-findings --exercise-quality-rerun-all-actions
OK

browser report
run_id=p1-53-quality-rerun-all
viewport=1440x1000
language=zh-CN
pages=12
preview_visible_in_viewport=true
zoom_label=125%
gateCards=1
riskSummaries=1
runBlockers=4
repairActions=5
repairBatches=4
exportBlockers=5
filteredRiskPages=3
requestedGateCount=1
successfulGateCount=1
allRequestedGatesRerun=true
batchGateEventsPersisted=true
batchSummaryEventPersisted=true
console_errors=0
```

P1-53 截图证据：

```text
docs/migration/review-cockpit-smoke/p1-53/01-cockpit-overview.png
docs/migration/review-cockpit-smoke/p1-53/02-preview-zoom.png
docs/migration/review-cockpit-smoke/p1-53/03-page-navigation.png
docs/migration/review-cockpit-smoke/p1-53/04-quality-export-panels.png
docs/migration/review-cockpit-smoke/p1-53/05-quality-findings-filter.png
docs/migration/review-cockpit-smoke/p1-53/12-quality-rerun-all-actions.png
docs/migration/review-cockpit-smoke/p1-53/browser_smoke_report.json
```

P1-53 已完成能力：

```text
studio-browser-smoke 新增 --exercise-quality-rerun-all-actions
开启后在质量报告充足 run 中点击重跑全部 Gate
操作后通过 Deck API 回读 Gate diff/history，并通过 Events API 回读批量事件
校验 allRequestedGatesRerun、batchGateEventsPersisted 和 batchSummaryEventPersisted
质量批量重跑样本归档 12-quality-rerun-all-actions.png
CLI 参数、专项测试、Spec Pack、合并版开发规范和迁移日志已同步
```

P1-54 专项验证：

```text
python3 -m py_compile scripts/deck_master.py scripts/preview/browser_smoke_review_cockpit.py tests/test_conversation_cli.py
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_browser_smoke_reports_missing_node -v
Ran 1 test
OK

python3 scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --runs-dir /tmp/deck-master-p1-54.IdJlH6 --run-id p1-54-export-blocker-rerun
OK
pages=12

python3 scripts/deck_master.py quality-gate draft --run-dir /tmp/deck-master-p1-54.IdJlH6/p1-54-export-blocker-rerun
OK
status=rework_required
findings=8

python3 scripts/deck_master.py studio-browser-smoke --run-dir /tmp/deck-master-p1-54.IdJlH6/p1-54-export-blocker-rerun --output-dir docs/migration/review-cockpit-smoke/p1-54 --language zh-CN --expect-quality-findings --exercise-export-blocker-rerun-actions
OK

browser report
run_id=p1-54-export-blocker-rerun
viewport=1440x1000
language=zh-CN
pages=12
preview_visible_in_viewport=true
zoom_label=125%
gateCards=1
riskSummaries=1
runBlockers=4
repairActions=5
repairBatches=4
exportBlockers=5
filteredRiskPages=3
diffAvailable=true
historyPersisted=true
historyCount=1
rerunEventPersisted=true
exportStatus=已重跑关联 Gate。
console_errors=0
```

P1-54 截图证据：

```text
docs/migration/review-cockpit-smoke/p1-54/01-cockpit-overview.png
docs/migration/review-cockpit-smoke/p1-54/02-preview-zoom.png
docs/migration/review-cockpit-smoke/p1-54/03-page-navigation.png
docs/migration/review-cockpit-smoke/p1-54/04-quality-export-panels.png
docs/migration/review-cockpit-smoke/p1-54/05-quality-findings-filter.png
docs/migration/review-cockpit-smoke/p1-54/13-export-blocker-rerun-actions.png
docs/migration/review-cockpit-smoke/p1-54/browser_smoke_report.json
```

P1-54 已完成能力：

```text
studio-browser-smoke 新增 --exercise-export-blocker-rerun-actions
开启后在导出阻断项中点击重跑 Gate
操作后通过 Deck API 回读 quality diff/history，并通过 Events API 回读 manual action event
校验 diffAvailable、historyPersisted 和 rerunEventPersisted
导出阻断重跑样本归档 13-export-blocker-rerun-actions.png
CLI 参数、专项测试、Spec Pack、合并版开发规范和迁移日志已同步
```

P1-55 专项验证：

```text
python3 -m py_compile scripts/deck_master.py scripts/preview/browser_smoke_review_cockpit.py tests/test_conversation_cli.py
OK

python3 -m unittest tests.test_conversation_cli.ConversationCliTests.test_studio_browser_smoke_reports_missing_node -v
Ran 1 test
OK

git diff --check
OK

python3 scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --runs-dir /tmp/deck-master-p1-55.RmBopG --run-id p1-55-export-blocker-jump-copy
OK
pages=12

python3 scripts/deck_master.py quality-gate draft --run-dir /tmp/deck-master-p1-55.RmBopG/p1-55-export-blocker-jump-copy
OK
status=rework_required
findings=8

python3 scripts/deck_master.py studio-browser-smoke --run-dir /tmp/deck-master-p1-55.RmBopG/p1-55-export-blocker-jump-copy --output-dir docs/migration/review-cockpit-smoke/p1-55 --language zh-CN --expect-quality-findings --exercise-export-blocker-jump-copy-actions
OK

browser report
run_id=p1-55-export-blocker-jump-copy
viewport=1440x1000
language=zh-CN
pages=12
preview_visible_in_viewport=true
zoom_label=125%
gateCards=1
riskSummaries=1
runBlockers=4
repairActions=5
repairBatches=4
exportBlockers=5
filteredRiskPages=3
targetPageId=beat_06_architecture
selectedPageId=beat_06_architecture
copyValue=证据密集页缺少可引用证据。
copiedText=证据密集页缺少可引用证据。
jumpPersisted=true
copiedTextPersisted=true
copiedStatusShown=true
exportStatus=已复制阻断说明。
console_errors=0
```

P1-55 截图证据：

```text
docs/migration/review-cockpit-smoke/p1-55/01-cockpit-overview.png
docs/migration/review-cockpit-smoke/p1-55/02-preview-zoom.png
docs/migration/review-cockpit-smoke/p1-55/03-page-navigation.png
docs/migration/review-cockpit-smoke/p1-55/04-quality-export-panels.png
docs/migration/review-cockpit-smoke/p1-55/05-quality-findings-filter.png
docs/migration/review-cockpit-smoke/p1-55/14-export-blocker-jump-copy-actions.png
docs/migration/review-cockpit-smoke/p1-55/browser_smoke_report.json
```

P1-55 已完成能力：

```text
studio-browser-smoke 新增 --exercise-export-blocker-jump-copy-actions
开启后在导出阻断项中点击跳到页面和复制阻断说明
操作后回读当前页面、复制内容和导出状态提示
校验 jumpPersisted、copiedTextPersisted 和 copiedStatusShown
导出阻断跳转复制样本归档 14-export-blocker-jump-copy-actions.png
CLI 参数、专项测试、Spec Pack、合并版开发规范和迁移日志已同步
```

P1 完成条件盘点：

```text
Phase 1 目标：一次客户方案 Deck 生产可运行、可追踪、可审查

完成项：
1. Workspace Foundation：已完成
2. Typed Events：已完成
3. Next Step Resolver：已完成
4. Context / Brief / Claim Map：已完成
5. Workspace-aware Planner：已完成
6. Sourcing Decision：已完成
7. Draft Gate：已完成
8. Review UI 基础审查：已完成
9. Approved Queue：已完成
```

P1 完成验收：

```text
python3 scripts/deck_master.py start-conversation --context-file examples/context/retail_meeting_transcript.txt --industry retail --runs-dir /tmp/deck-master-p1-final.KR5vb2 --run-id p1-final-retail-context
OK
status=conversation_started
sources=1

python3 scripts/deck_master.py build-brief --run-dir /tmp/deck-master-p1-final.KR5vb2/p1-final-retail-context
OK
status=brief_ready
core_points=8

python3 scripts/deck_master.py build-judgments --run-dir /tmp/deck-master-p1-final.KR5vb2/p1-final-retail-context
OK
status=judgments_ready
judgments=5
risks=0

python3 scripts/deck_master.py build-claim-graph --run-dir /tmp/deck-master-p1-final.KR5vb2/p1-final-retail-context
OK
status=claim_graph_ready
claims=8
evidence=1

python3 scripts/deck_master.py build-claim-map --run-dir /tmp/deck-master-p1-final.KR5vb2/p1-final-retail-context
OK
status=claim_map_ready
claims=8

python3 scripts/deck_master.py autoplan --run-dir /tmp/deck-master-p1-final.KR5vb2/p1-final-retail-context --library-mode fixture
OK
status=autoplan_preview_ready
pages=12

python3 scripts/deck_master.py quality-gate --run-dir /tmp/deck-master-p1-final.KR5vb2/p1-final-retail-context draft
OK
status=rework_required
findings=1
blocks_delivery=true

python3 scripts/deck_master.py export --run-dir /tmp/deck-master-p1-final.KR5vb2/p1-final-retail-context --decision approved --allow-blocked --output /tmp/deck-master-p1-final.KR5vb2/p1-final-retail-context/approved_queue.json
OK
status=exported
pages=0
queue_status=blocked
blockers=2

python3 scripts/deck_master.py export --run-dir examples/preview-run --output /tmp/deck-master-p1-final.KR5vb2/preview-run-approved_queue.json
OK
status=exported
queue_status=ready
queue_pages=1
blockers=0
```

P1 结论：

```text
P1 Run OS Core 已满足进入 qa 的条件
零售 context run 可以从本地资料进入 preview 和 Draft Gate
Draft Gate 能发现证据缺口并阻断导出
approved queue 正常路径可导出已批准页面
后续远端推送等待 qa 完成
```

P1 QA 完成状态：

```text
qa status=PASS
issues_found=0
fix_commits=0

quality-blocked browser QA:
status=ok
pages=12
gateCards=1
runBlockers=4
exportBlockers=5
filteredRiskPages=3
export_blocker_rerun_actions_persisted=true
export_blocker_jump_copy_actions_persisted=true
console_errors=0

approved-delivery browser QA:
status=ok
pages=3
review_actions_persisted=true
export_delivery_persisted=true
workspace_asset_health_refreshed=true
deliveredPages=2
strongReuseCandidates=3
console_errors=0
```

P1 QA 证据：

```text
docs/migration/qa/p1-run-os-core/qa-report.md
docs/migration/qa/p1-run-os-core/quality-blocked/browser_smoke_report.json
docs/migration/qa/p1-run-os-core/approved-delivery/browser_smoke_report.json
```

P1 当前状态：

```text
P1 Run OS Core 完成
本地提交完成
QA 已通过
远端推送进入最后一步
P2-P5 后续按阶段评审、拆包、任务边界和 QA gate 推进
```

## 4. 当前并行状态

| 角色 | 状态 | 说明 |
|---|---|---|
| 主控 agent | P1 QA 已通过 | 负责迁移清单、验收、集成和后续拆包 |
| Worker Godel | 已完成并关闭 | P0-1 Runtime Contract 已集成、测试通过、已推送远程分支 |
| Worker Ohm | 已完成并关闭 | P0-2 Workspace Foundation 已集成、测试通过、已推送远程分支 |
| Worker Carver | 已完成 | P0-3 Context / Brief / Consulting Judgment / Claim-Evidence Graph 已集成并通过验证 |
| Worker Dalton | 已停止 | P0-4 中途产出已由主控接管、修正、补测试并完成验证 |

## 5. 收口策略更新（2026-06-11）

老板已更新 P1 收口规则：

1. P1 增量先完成本地提交，暂缓远端推送。
2. P1 全部完成后，先发起 `qa`。
3. `qa` 完成且必要修复落地后，再推送远端并记录 P1 完成状态。
4. P2-P5 更换开发方式：先做阶段评审、拆包、任务边界和 QA gate，再进入执行。

## 6. 下一步

1. 提交 P1 QA 报告和完成状态。
2. 推送远端分支。
3. P2-P5 更换开发方式，先做阶段评审和任务拆包。
