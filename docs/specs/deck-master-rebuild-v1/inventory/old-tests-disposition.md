# 旧测试取舍记录(T24 / AC-L06)

判定原则:真实行为断言已有 tests/rebuild 对应者记 migrate;断言针对已退役旧 OS 命令/门禁、
或本轮入口切换后依赖旧 `import deck_master` 语义者记 retire(点名已知失败);无任何 skip 装绿。
共退役 123 个文件(tests/*.py 全量);tests/rebuild/ 与 tests/rebuild/conftest.py 未动。

## 分组判定

| 旧测试 | 判定 | 说明 |
| --- | --- | --- |
| tests/test_adapters.py | migrate → tests/rebuild/test_svg_parser.py + test_native_pipeline.py | SVG/适配行为已由声明子集解析/IR 测试覆盖 |
| tests/test_agent_ready_contract.py | migrate → tests/rebuild/test_contracts.py + test_install.py | 合同校验由新 schema 套件覆盖;"ready 门禁"语义由 doctor 分步(test_install 隔离断言)+ rebuild CI 组承接 |
| tests/test_approval_flow.py | migrate → tests/rebuild/test_review.py + test_export.py | 审批平台按 spec 07 刻意退役;approval 语义由 evaluate_current 唯一解释 + delivery 导出门(test_delivery_export_rejected_with_specific_reason)承接 |
| tests/test_artifact_validator.py | migrate → tests/rebuild/test_contracts.py + test_service_flow.py(test_pptx_artifact_and_export_declare_shape_text_editability) | artifact schema 与 editability 断言已覆盖 |
| tests/test_benchmark_aggregate.py | migrate → retire — benchmark-* 命令已退役(09.6) | 无替代(功能退役) |
| tests/test_benchmark_case.py | migrate → retire — benchmark-* 命令已退役(09.6) | 无替代(功能退役) |
| tests/test_benchmark_checkpoints.py | migrate → retire — benchmark-* 命令已退役(09.6) | 无替代(功能退役) |
| tests/test_benchmark_report.py | migrate → retire — benchmark-* 命令已退役(09.6) | 无替代(功能退役) |
| tests/test_benchmark_runner.py | migrate → retire — benchmark-* 命令已退役(09.6) | 无替代(功能退役) |
| tests/test_benchmark_scoring.py | migrate → retire — benchmark-* 命令已退役(09.6) | 无替代(功能退役) |
| tests/test_connector_import_contract.py | migrate → retire — 旧 connector 命令已退役(09.6) | 无替代(功能退役) |
| tests/test_library_feedback_queue.py | migrate → retire — 库流程不实现(T17 指引) | 替代行为:create 直入新流程(test_service_flow/test_cli) |
| tests/test_library_status.py | migrate → retire — 库流程不实现(T17 指引) | 替代行为:create 直入新流程(test_service_flow/test_cli) |
| tests/test_rc_gate.py | retire | 旧 RC 门禁(rc-gate 已退役,09.6);8 个预存失败;替代:tests/rebuild/test_export.py(delivery 门)+ rebuild.yml CI 组 |
| tests/test_skill_installation.py | retire | 旧 suite/skill 安装器测试;17 个已知失败(入口切换后依赖旧 import deck_master 语义);替代:tests/rebuild/test_install.py(AC-I04/I05/I06 隔离安装) |
| tests/test_workflow_cli.py | migrate → tests/rebuild/test_cli.py | 唯一 CLI 入口矩阵(AC-I04) |
| tests/__init__.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_asset_feedback.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_asset_health.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_asset_ingestion.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_asset_schema.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_astra_task_routing.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_brand_gate.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_brief_intake.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_build_manifest_v2.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_build_runtime.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_claim_evidence_graph.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_companion_tool_validators.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_confidentiality_gate.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_consulting_judgments.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_context_conflict_gate.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_context_conversation.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_context_pack_import.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_conversation_cli.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_customer_visible_safety.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_deck_project_init.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_delivery_outcome.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_delivery_validation.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_draft_gate_v2.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_end_to_end_autoplan.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_evidence_gate.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_export_quality_blocking.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_external_quality_review.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_feedback.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_final_artifact_approval.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_final_readiness.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_gate_freshness.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_generation_handback.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_generation_pipeline.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_generation_preview_sourcing_v2.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_generation_session_bridge.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_generation_tasks.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_high_density_builder.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_high_density_builder_v2.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_high_density_distinct_acceptance.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_high_density_icon_stability.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_import_full_draft.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_narrative_advice.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_narrative_planner.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_next_step.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_no_library_path.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_open_source_preview_gate.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_opportunity_model.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_orchestration.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_orchestration_enforcement.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_overrides.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_page_package.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_page_tasks.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_planner_sourcing_controls.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_ppt_library_bridge_v2.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_ppt_library_client.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_preview_manifest.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_preview_server.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_preview_static_contract.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_preview_workspace_gate_regression.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_project_skill_installation.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_quality_gate.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_rc_gate_d4_closure.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_rc_gate_installed_release_regression_001.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_release_runtime.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_render_runtime.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_review_cockpit.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_review_desk_skill_os.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_review_policy.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_review_workbench.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_run_metrics.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_run_mode_inheritance.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_run_state_resolver.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_runtime_events.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_runtime_state.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_schema_versioning.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_setup_enforcement.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_setup_install_suite_regression_001.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_skill_doc_contract.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_skill_handoff.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_skill_manifest.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_skill_os_acceptance.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_skill_os_migration.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_skill_os_release_contract.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_skill_route.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_smoke_real_workflow.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_solution_package.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_sourcing_decider.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_sourcing_decision_matrix.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_sourcing_plan_v2.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_sourcing_scoring_v2.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_stage_contract_registry.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_stage_validation.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_team_dashboard.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_team_identity.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_uat_generation_tool.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_uat_ppt_library.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_uat_render_tool.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_uat_report.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_workflow_approval.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_workflow_autopilot.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_workflow_autopilot_v2.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_workflow_questions.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_workflow_stage_checks.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_workflow_state.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_workspace_audit_scenarios.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_workspace_foundation.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |
| tests/test_workspace_learning_pack.py | retire | 旧 OS 耦合(workflow/runtime/sourcing/quality 等);替代行为见 tests/rebuild 对应领域测试 |

## 已知失败点名
- tests/test_skill_installation.py:17 failed(2026-09-21 入口切换后核查,全部 suite/skill 安装类)
- tests/test_rc_gate.py:8 failed(预存,rc-gate 环境类)
退役理由已含于上表;保留 Git 历史可查。

## 可靠性敏感条目点名(approval/ready/gate 家族)

| 旧测试 | 具名替代 |
| --- | --- |
| test_approval_flow.py | tests/rebuild/test_review.py(evaluate_current 唯一解释)+ test_export.py(delivery 拒未解决 must_fix) |
| test_agent_ready_contract.py | tests/rebuild/test_contracts.py(schema)+ test_install.py(doctor 分步隔离断言)+ .github/workflows/rebuild.yml(CI 组) |
| test_rc_gate.py | tests/rebuild/test_export.py(delivery 门)+ rebuild.yml(report 组);rc-gate 命令本身退役(09.6) |
| test_quality_gate* / test_*_gate_* | tests/rebuild/test_readback.py(readback findings)+ test_review.py;旧 gate 命令按 09.6 退役 |

其余模板化 "retire | 旧 OS 耦合" 条目按领域对应:workflow/runtime/sourcing/quality/learning 等旧 OS 模块的断言,
其真实行为替代分别在 test_service_flow/test_tasks/test_review/test_budget/test_legacy 等领域测试中。
