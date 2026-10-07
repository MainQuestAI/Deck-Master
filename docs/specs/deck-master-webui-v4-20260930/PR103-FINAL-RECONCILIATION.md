# PR103 最终逐项对账与验收索引

本表以原诊断、FINAL-REPAIR-PLAN 和 81983a8 对账为范围，不把三个新缺陷替代整个整改。旧对账是旧提交的有效裁决，保留原件；下表解释最终行为及其证据入口。测试源码说明验收内容，**运行是否通过必须结合最终机器记录，不能从测试存在推断通过**。

原文件位于 `evidence/product-design-final-20261006/`。修复历史及旧 CI 分歧调查见 [实施记录](PR103-COMPLETE-REPAIR.md)。最终本地运行、源码/安装包身份、CI、真实 Host 边界统一记录在 `evidence/product-design-final-20261006/PR103-FINAL-ACCEPTANCE.md` 和 `output/pr103-complete-runtime/final-manifest.json`；未完成的门禁不得由本表自动关闭。

## 原 20 项

| 原项 | 最终处理与可见结果 | 证据责任 |
|---|---|---|
| OV-01 | 配置紧邻选择工具条，长列表保持范围与配置入口 | [AC06](#ac06)、[AC07](#ac07)、[AC08](#ac08) |
| OV-02 | 空选只阅读；配置和核对分态，字段阻断就近 | [AC06](#ac06)、[AC07](#ac07) |
| CS-01 | 新增材料独立入口，0/1/多材料均走正式编辑 | [AC02](#ac02) |
| CS-02 | 材料主层区分原文可读与影响判断；不补造采用/事实认可 | [AC02](#ac02)、[AC04](#ac04)、[AC23](#ac23) |
| CS-03 | 正文具体改文清单与影响同屏，材料确认保持上下文 | [AC13](#ac13)、[AC14](#ac14) |
| CS-04 | 章节内指定页，来源就近可开并返回 | [AC14](#ac14) |
| ST-01 | 两来源四阶段，查看阶段不改变业务完成事实 | [AC09](#ac09)、[AC12](#ac12) |
| ST-02 | 规范摘要先读、七维按需编辑 | [AC10](#ac10) |
| ST-03 | 拆解图直接可见、可以完整查看 | [AC10](#ac10)、[AC23](#ac23) |
| ST-04 | 待上传与已存参考区分；已成功上传有持久继续出口 | [AC03](#ac03)、[AC21](#ac21) |
| ST-05 | 同页候选真实缩略图、目标/状态/短码可区分 | [AC05](#ac05)、[AC11](#ac11) |
| ST-06 | 继续合并到 F07/F16；原生控件本身不构成缺陷 | [AC09](#ac09)、[AC10](#ac10)、[AC23](#ac23) |
| TA-01 | 就近比较、固定双方、缩放/全屏工具和决定同上下文 | [AC11](#ac11)、[AC17](#ac17)、[AC23](#ac23) |
| TA-02 | 原始依据收在详情；作品主层可读，首张原图不误称 PPT | [AC04](#ac04)、[AC11](#ac11)、[AC23](#ac23) |
| TA-03 | 私人笔记与正式意见区分，维护/恢复进入辅助区，异常可达 | [AC19](#ac19)、[AC21](#ac21)、[AC22](#ac22) |
| TA-04 | 选中/已读/当前同时呈现，动作绑定已读快照 | [AC17](#ac17) |
| TA-05 | 文件独立子区，版本—用途—结果；工程包辅助 | [AC16](#ac16)、[AC17](#ac17)、[AC24](#ac24) |
| TA-06 | 候选扫描使用实际固定图，进入实际候选比较 | [AC05](#ac05)、[AC11](#ac11) |
| TA-07 | 维持撤回：原证据不能支持该指控，不计未修，也不冒充本轮修复 | 撤回理由沿用原诊断 |
| SYS-01 | 四子区只保留一个工作上下文，交接就在实际任务旁 | [AC01](#ac01)、[AC16](#ac16)、[AC18](#ac18) |

## 17 主题与 9 工作包

| 主题 | 实现结果 | AC |
|---|---|---|
| F01 | 复制快照一致 | [AC01](#ac01) |
| F02 | 材料明确入口 | [AC02](#ac02) |
| F03 | 分页显示/请求分离 | [AC03](#ac03) |
| F04 | 范围、决定与版本事实 | [AC04](#ac04) |
| F05 | 批量三态连续路径 | [AC06](#ac06)、[AC07](#ac07)、[AC08](#ac08) |
| F06 | 正文、材料与来源连续核对 | [AC02](#ac02)、[AC13](#ac13)、[AC14](#ac14) |
| F07 | 两来源风格四阶段 | [AC09](#ac09)、[AC10](#ac10)、[AC12](#ac12) |
| F08 | 同名对象与实际图识别 | [AC05](#ac05)、[AC11](#ac11) |
| F09 | 固定比较和三版本动作 | [AC11](#ac11)、[AC17](#ac17) |
| F10 | 意见按产物身份适用 | [AC15](#ac15)、[AC22](#ac22) |
| F11 | 完整恢复差异 | [AC19](#ac19)、[AC21](#ac21) |
| F12 | 四子区与任务/文件归属 | [AC16](#ac16)、[AC18](#ac18) |
| F13 | 真实状态与下一步 | [AC20](#ac20)、[AC21](#ac21) |
| F14 | 业务语言主次层级 | [AC04](#ac04)、[AC10](#ac10)、[AC13](#ac13)、[AC16](#ac16)、[AC23](#ac23) |
| F15 | 窄屏、键盘与焦点 | [AC22](#ac22)、[AC23](#ac23) |
| F16 | 实际消费者 CSS 收敛 | [AC23](#ac23) |
| F17 | 规范、实现与证据一致 | [AC24](#ac24) |

| 工作包 | 最终验收责任 |
|---|---|
| UX-00 | [AC01](#ac01)、[AC02](#ac02)、[AC03](#ac03)、[AC04](#ac04) |
| UX-01 | [AC05](#ac05) |
| UX-02 | [AC06](#ac06)、[AC07](#ac07)、[AC08](#ac08) |
| UX-03 | [AC09](#ac09)、[AC10](#ac10)、[AC11](#ac11)、[AC12](#ac12) |
| UX-04 | [AC13](#ac13)、[AC14](#ac14)、[AC15](#ac15) |
| UX-05 | [AC16](#ac16)、[AC17](#ac17)、[AC18](#ac18) |
| UX-06 | [AC19](#ac19)、[AC20](#ac20)、[AC21](#ac21)、[AC22](#ac22) |
| UX-07 | [AC23](#ac23) |
| UX-08 | [AC24](#ac24) |

## 10 项共用职责

复用正式组件，不要求十个新类；下列证据均操作正式工作台。

| 职责 | 正式消费者 | 验收 |
|---|---|---|
| C01 对象身份 | 交接、规范、候选、版本 | [AC01](#ac01)、[AC05](#ac05)、[AC17](#ac17) |
| C02 状态与下一步 | 任务、批量、风格、恢复 | [AC08](#ac08)、[AC16](#ac16)、[AC20](#ac20)、[AC21](#ac21) |
| C03 选择动作栏 | 总览与扩展目标 | [AC06](#ac06)、[AC07](#ac07)、[AC12](#ac12) |
| C04 阶段视图 | 项目内与截图风格 | [AC09](#ac09)、[AC10](#ac10)、[AC12](#ac12) |
| C05 资产选择预览 | 参考目录、上传继续、候选图 | [AC03](#ac03)、[AC05](#ac05)、[AC21](#ac21) |
| C06 结构化阅读编辑 | 正文与材料 | [AC02](#ac02)、[AC13](#ac13)、[AC14](#ac14) |
| C07 固定比较 | 候选/历史/图标 | [AC11](#ac11)、[AC15](#ac15)、[AC17](#ac17) |
| C08 影响确认 | 批量、采用、恢复、文件 | [AC08](#ac08)、[AC12](#ac12)、[AC17](#ac17)、[AC24](#ac24) |
| C09 恢复差异 | 私人草稿与画廊双窗口 | [AC19](#ac19)、[AC21](#ac21) |
| C10 导航返回 | 四子区、来源、历史、焦点 | [AC14](#ac14)、[AC16](#ac16)、[AC18](#ac18)、[AC22](#ac22) |

## AC01–AC24 实现与证据

所有测试由完整浏览器门禁执行；源码中的合成回执只用于工程路径验证。真实 Host 另行记录，不能互相替代。

| AC | 必须观察的结果 | 实现入口（static/v2） | 正式回归 |
|---|---|---|---|
| <a id="ac01"></a>AC01 | 交接 A/B/C、读取失败与延迟复制，文本和标记绑定已读快照 | `change-handoff.js/run-desk.js` | [test_handoff_three_groups_and_late_clipboard_keep_original_copy_identity](../../../tests/rebuild/test_pr103_complete_browser.py#L414)<br>[test_handoff_copy_binds_to_the_loaded_group_not_the_pending_selection](../../../tests/rebuild/test_ux00_fixes_browser.py#L81) |
| <a id="ac02"></a>AC02 | 0/1/多材料，新增、任务要求、旧材料分别编辑核对确认 | `content-sources.js` | [test_material_editor_keeps_preview_confirmation_and_return_in_context](../../../tests/rebuild/test_pr103_repair_browser.py#L460) |
| <a id="ac03"></a>AC03 | 65 保存任务失败重试原组；参考目录首尾、快速操作和销毁 | `visual-style.js` | [test_saved_task_failure_retries_the_same_group](../../../tests/rebuild/test_pr103_complete_browser.py#L48)<br>[test_style_saved_task_and_reference_pagers_stay_within_bounds](../../../tests/rebuild/test_ux00_fixes_browser.py#L160)<br>[test_large_reference_catalog_releases_images_and_preserves_selection](../../../tests/rebuild/test_visual_styles_browser.py#L93)<br>[test_late_reference_catalog_after_leaving_style_does_not_acquire_images](../../../tests/rebuild/test_visual_styles_browser.py#L120) |
| <a id="ac04"></a>AC04 | 整稿意见不表示认可，决定摘要不伪装版本；原有提示词事实保护保留 | `annotations.js/history-labels.js/page-workbench.js` | [test_project_scope_reads_as_opinion_and_decision_ref_is_not_a_revision](../../../tests/rebuild/test_ux00_fixes_browser.py#L213) |
| <a id="ac05"></a>AC05 | 同名规范、组、候选在选择前可辨；候选实际图和固定对象 | `style-calibration.js/visual-style.js/candidate-desk.js` | [test_same_name_saved_recipes_and_groups_are_distinguishable_before_selection](../../../tests/rebuild/test_ux03_style_candidate_browser.py#L59)<br>[test_candidate_cards_show_real_fixed_images_and_release_on_navigation](../../../tests/rebuild/test_pr103_repair_browser.py#L519) |
| <a id="ac06"></a>AC06 | 30 页第 2/28 页，空选—配置—核对；长列表动作就近、返回要求保留 | `overview.js/batch-actions.js` | [test_cross_chapter_selection_reaches_config_and_survives_return](../../../tests/rebuild/test_ux02_batch_slice_browser.py#L50)<br>[test_batch_surface_states_choose_configure_confirm_adjacent_to_selection](../../../tests/rebuild/test_ux02_batch_slice_browser.py#L154)<br>[test_long_list_keeps_selection_summary_and_config_entry_in_view](../../../tests/rebuild/test_deep_review_fixes_browser.py#L220) |
| <a id="ac07"></a>AC07 | 筛选外选择和数量保留、受限范围明确处理 | `overview.js/batch-policy.js` | [test_filters_keep_selection_and_show_out_of_filter_count](../../../tests/rebuild/test_ux02_batch_slice_browser.py#L77)<br>[test_mixed_modes_keep_selection_until_explicit_range_adjustment](../../../tests/rebuild/test_batch_actions_browser.py#L63) |
| <a id="ac08"></a>AC08 | 刷新/版本前进保留选择要求，旧计划失效；未知请求核实原回执 | `batch-actions.js/business-operations.js` | [test_refresh_and_version_advance_keep_draft_and_invalidate_old_plan](../../../tests/rebuild/test_ux02_batch_slice_browser.py#L109)<br>[test_lost_commit_response_verify_original_receipt_reload_never_redispatches](../../../tests/rebuild/test_batch_actions_browser.py#L122) |
| <a id="ac09"></a>AC09 | v1/v2 四阶段和恢复；拒绝错误来源；用户手动阶段不被迟到恢复抢占 | `style-calibration.js/visual-style.js` | [test_screenshot_recipe_restore_verifies_spec_and_keeps_schema_boundary](../../../tests/rebuild/test_ux03_style_candidate_browser.py#L181)<br>[test_screenshot_route_refuses_a_project_recipe_with_a_clear_message](../../../tests/rebuild/test_ux03_style_candidate_browser.py#L229)<br>[test_delayed_recipe_restore_does_not_close_manually_chosen_phase](../../../tests/rebuild/test_pr103_repair_browser.py#L413)<br>[test_selection_to_style_path_works_after_using_the_screenshot_source](../../../tests/rebuild/test_deep_review_obligations_browser.py#L62) |
| <a id="ac10"></a>AC10 | 拆解图直接可见、借用保留和字体依据；规范先读后改，确认不等于采用 | `visual-style.js` | [test_screenshot_recipe_restore_verifies_spec_and_keeps_schema_boundary](../../../tests/rebuild/test_ux03_style_candidate_browser.py#L181)<br>[test_style_ui_trial_adoption_and_successful_expansion](../../../tests/rebuild/test_pr103_complete_browser.py#L140) |
| <a id="ac11"></a>AC11 | 固定候选切换、迟到响应、实际图、正确层空态；画布适配不遮住决定 | `candidate-desk.js/comparison-canvas.js` | [test_candidate_desk_rapid_switch_late_reply_and_decisions_target_displayed_object](../../../tests/rebuild/test_ux03_style_candidate_browser.py#L252)<br>[test_first_original_candidate_fit_is_visible_above_decisions_and_has_correct_empty_state](../../../tests/rebuild/test_pr103_complete_browser.py#L511) |
| <a id="ac12"></a>AC12 | 两路线正式 UI：规范—试作—交接—返回—比较—采用—明确目标—扩展—返回—采用 | `style-calibration.js/visual-style.js/candidate-desk.js` | [test_style_ui_trial_adoption_and_successful_expansion](../../../tests/rebuild/test_pr103_complete_browser.py#L140)<br>[test_expansion_plan_carries_adopted_sample_and_explains_core_rejection](../../../tests/rebuild/test_ux03_style_candidate_browser.py#L317) |
| <a id="ac13"></a>AC13 | 同文节点分开修改，原文→改文与影响同屏；取消/恢复后仍以正式原文核对 | `content-edit.js/page-workbench.js` | [test_same_text_body_nodes_are_distinguishable_and_editable_separately](../../../tests/rebuild/test_ux04_content_annotations_browser.py#L62)<br>[test_content_change_list_keeps_the_formal_baseline_after_draft_restore](../../../tests/rebuild/test_deep_review_fixes_browser.py#L151)<br>[test_complex_body_change_list_and_impact_share_one_screen](../../../tests/rebuild/test_deep_review_fixes_browser.py#L271) |
| <a id="ac14"></a>AC14 | 章节指定页和就近来源；材料编辑—核对—确认及返回上下文 | `content-sources.js/page-workbench.js` | [test_outline_block_reaches_its_pages_and_return_keeps_surface](../../../tests/rebuild/test_ux04_content_annotations_browser.py#L153)<br>[test_material_editor_keeps_preview_confirmation_and_return_in_context](../../../tests/rebuild/test_pr103_repair_browser.py#L460) |
| <a id="ac15"></a>AC15 | 点和框跨版本按产物身份适用；不同产物不叠加；图标交接携带实际意见及层 | `annotations.js/icon-workbench.js` | [test_point_overlay_follows_artifact_identity_across_snapshots](../../../tests/rebuild/test_ux04_content_annotations_browser.py#L112)<br>[test_narrow_screen_icon_requirement_path_is_visible_and_completable](../../../tests/rebuild/test_ux06_recovery_responsive_browser.py#L218)<br>[test_saved_opinion_is_still_saved_after_reload](../../../tests/rebuild/test_pr103_repair_browser.py#L28) |
| <a id="ac16"></a>AC16 | 147 混合记录分页筛选；四子区直达、任务正确交接，正文/SVG/PPT 按层打开 | `views.js/run-desk.js/change-handoff.js` | [test_147_mixed_tasks_paginate_filter_and_keep_subareas_reachable](../../../tests/rebuild/test_pr103_complete_browser.py#L375)<br>[test_overview_handoff_is_actionable_in_task_context](../../../tests/rebuild/test_pr103_complete_browser.py#L126)<br>[test_runs_subareas_reach_decisions_versions_files_and_shortcuts_match_layers](../../../tests/rebuild/test_ux05_runs_delivery_browser.py#L62) |
| <a id="ac17"></a>AC17 | 选 A/读 B/当前 C：比较和导出 B；恢复读 A 后以 C 为基准到 D；并发拒绝旧计划 | `delivery-desk.js` | [test_three_versions_restore_uses_read_source_and_current_basis](../../../tests/rebuild/test_pr103_complete_browser.py#L323) |
| <a id="ac18"></a>AC18 | 历史无待办/最新有待办，顶栏计数与对象一致，能够返回历史；未知执行不重派 | `project.js/run-desk.js/run-recovery.js` | [test_topbar_pending_entry_matches_the_latest_list_and_returns_to_history](../../../tests/rebuild/test_deep_review_obligations_browser.py#L114)<br>[test_topbar_pending_entry_always_lands_on_the_task_list](../../../tests/rebuild/test_deep_review_obligations_browser.py#L146)<br>[test_dispatch_unknown_explains_preservation_without_redispatch](../../../tests/rebuild/test_rollup_browser.py#L106) |
| <a id="ac19"></a>AC19 | 真实双窗口 409：同选页同层、参考不同；完整字段差异、下载和采用同一快照 | `gallery-state.js/drafts.js` | [test_gallery_conflict_same_selection_and_layer_exposes_reference_difference](../../../tests/rebuild/test_pr103_complete_browser.py#L452)<br>[test_gallery_conflict_reports_filter_anchor_and_zoom_differences](../../../tests/rebuild/test_deep_review_fixes_browser.py#L306)<br>[test_conflict_panel_lists_different_fields_and_both_snapshots](../../../tests/rebuild/test_ux06_gallery_conflict_browser.py#L50) |
| <a id="ac20"></a>AC20 | 创建成功打开失败/创建响应丢失/登记再失败，按原位置恢复且不重复创建 | `launcher-ui.js` | [test_created_project_reopens_after_open_failure_without_recreating](../../../tests/rebuild/test_ux06_recovery_responsive_browser.py#L55)<br>[test_lost_create_response_offers_register_and_open_without_recreating](../../../tests/rebuild/test_ux06_recovery_responsive_browser.py#L112) |
| <a id="ac21"></a>AC21 | 上传及分析/确认/交接成功独立于私人草稿；后写/断连/丢响应/部分成功可继续 | `visual-style.js` | [test_committed_upload_survives_private_note_afterwrite](../../../tests/rebuild/test_pr103_complete_browser.py#L88)<br>[test_upload_success_has_visible_recovery_when_private_save_fails](../../../tests/rebuild/test_pr103_complete_browser.py#L300)<br>[test_partial_upload_keeps_successful_files_and_retries_only_failed_file](../../../tests/rebuild/test_pr103_complete_browser.py#L275)<br>[test_style_ui_trial_adoption_and_successful_expansion](../../../tests/rebuild/test_pr103_complete_browser.py#L140)<br>[test_committed_upload_with_lost_response_recovers_without_new_attempt](../../../tests/rebuild/test_pr103_repair_browser.py#L378)<br>[test_pending_style_analysis_shows_business_name_and_verify](../../../tests/rebuild/test_ux06_recovery_responsive_browser.py#L189) |
| <a id="ac22"></a>AC22 | 390px 图标意见到实际复制；关闭模态触发器消失有焦点回落；键盘不被刷新抢占 | `icon-workbench.js/dom.js/page-workbench.js` | [test_narrow_screen_icon_requirement_path_is_visible_and_completable](../../../tests/rebuild/test_ux06_recovery_responsive_browser.py#L218)<br>[test_modal_close_returns_focus_to_the_surface_heading_when_trigger_is_removed](../../../tests/rebuild/test_ux06_recovery_responsive_browser.py#L155)<br>[test_optional_tools_do_not_arm_annotation_and_keep_keyboard_return](../../../tests/rebuild/test_workbench_usability_browser.py#L30) |
| <a id="ac23"></a>AC23 | 1440/1280/390：作品阅读、主动作、44px、无横溢、状态文字/颜色、焦点、字体来源 | `workbench.css/comparison-canvas.css/DESIGN.md` | [test_migrated_components_keep_targets_adjacency_and_state_text](../../../tests/rebuild/test_ux07_style_convergence_browser.py#L59)<br>[test_task_handoff_and_subarea_state_remain_readable_at_supported_viewports](../../../tests/rebuild/test_pr103_complete_browser.py#L488)<br>[test_first_original_candidate_fit_is_visible_above_decisions_and_has_correct_empty_state](../../../tests/rebuild/test_pr103_complete_browser.py#L511)<br>[test_reading_prioritizes_artwork_and_preserves_fixed_layers](../../../tests/rebuild/test_workbench_usability_browser.py#L11) |
| <a id="ac24"></a>AC24 | 最终源码全套、独立 wheel 路径与资源、安装后五任务/恢复、CI、真实 Host 单页 | `安装入口与最终机器记录见下文` | [test_style_ui_trial_adoption_and_successful_expansion](../../../tests/rebuild/test_pr103_complete_browser.py#L140)<br>[test_batch_route_normal_result_and_lost_response_recovery](../../../tests/rebuild/test_ux08_task_walkthrough_browser.py#L122)<br>[test_content_route_change_list_impact_and_draft_restore](../../../tests/rebuild/test_ux08_task_walkthrough_browser.py#L203)<br>[test_delivery_route_version_identities_files_and_blocked_delivery](../../../tests/rebuild/test_ux08_task_walkthrough_browser.py#L240)<br>[test_recovery_route_real_gallery_conflict_reports_differences](../../../tests/rebuild/test_ux08_task_walkthrough_browser.py#L277) |

## 五工作面 × 七状态

每格列出具体现象及 AC 证据。它是原方案要求的状态索引，不额外制造 270 组合配额；不适用状态保持只读，不为填表发明业务。

| 工作面 | 初始/空 | 已选择/编辑 | 进行中 | 成功/结果 | 失败/阻断 | 恢复/冲突 | 历史/只读 |
|---|---|---|---|---|---|---|---|
| 制作总览 | 空选不铺参数 AC06 | 2/28 页及隐藏选择 AC06–07 | 计划与冻结提交 AC08 | 当前任务可复制交接 AC16 | 预算/受限页/旧计划 AC07–08 | 刷新要求/未知原请求 AC08 | 固定旧版、最新待办分开 AC18 |
| 内容与来源 | 0 材料仍可新增 AC02 | 指定页和同文节点 AC13–14 | 原文改文与影响同屏 AC13 | 确认后新版本/清空改动 AC13 | 原依据变动不继续旧计划 AC08/13 | 草稿恢复正式原文基线 AC13 | 材料和正文历史不可写 AC02/14 |
| 整稿画廊 | 无图说明对应层 AC11 | 页/层/比较参考 AC05/11 | 图像切换代次守卫 AC11 | 固定真实作品比较 AC11 | 图缺失和依据变化 AC11/15 | 同选页不同参考 409 AC19 | 历史引用不混未来候选 AC11/18 |
| 风格校准 | 无参考/目标不可试作 AC09 | 五维/七维类型分离 AC09–10 | 上传/分析/试作交接 AC12/21 | 候选比较、采用后成功扩展 AC12 | 错配方/旧样例/冲突 AC09/12 | 部分上传、后写、丢回包 AC21 | 固定旧规范和只读状态 AC09/11 |
| 任务与交付 | 无任务/候选/文件真实空态 AC16 | 组/候选/版本身份 AC01/17 | 待接手≠运行≠已返回 AC16/18 | UI 采用/固定版本导出 AC17/24 | 未知不重派、交付缺项 AC18/24 | 创建恢复/任务核实/恢复计划 AC17/20 | A/B/C 区分、历史最新往返 AC17–18 |

五条连续任务的截图和请求记录：`output/playwright/ux-review/ux08/`（最终运行后复制到 `output/playwright/pr103-complete/inherited-walkthroughs/`）以及 `output/playwright/pr103-complete/` 各正式用例目录。两路线成功扩展含 `business-states.json`；最终包检查使用安装模块和同一套正式测试。

## 安装与真实工具证据

- 安装回归入口：[w12_installed_regressions.py](../../../examples/workbench/w12_installed_regressions.py)，先导入 site-packages，再运行五路径/恢复，结束逐模块核对来源；禁止借用 src。
- 独立离线界面/固定文件下载：[w12_offline_browser.py](../../../examples/workbench/w12_offline_browser.py)，网络仅允许 loopback，核对静态资源、字体与三用途下载哈希。
- 真实 Host：`output/pr103-complete-runtime/real-host/` 保存冻结输入、原生观察、候选、UI 采用请求和页面前后引用。实际只调用一次 ImageGen；不重做 30 页。prompt、透明背景、输出获得原生证据；原生事件未提供 references 的完整比较，因此输入比较为 partial、无 differences（本次冻结 references 为空），model/seed 未声称可验证。专业质量独立判断。
- 真实验收发现的 Codex 分叉会话文件名兼容问题以 `e04ec4b` 修复，仍要求线程/回合/事件唯一、真实产物和原生调用证明；增加重复事件、错线程、错回合、符号链接拒绝反例。
- 最终状态以最终验收记录为准；日常安装、HOME 和 main 不变，不自动合并。
