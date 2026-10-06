# UX 整改实施日志（UX-00–UX-08）

日期：2026-10-06 · 基线：`4fefd0b3`（`codex/v1-rc-closure` 审计基线）· 实施分支：`codex/webui-ux-repair`。

按[最终修复方案](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/evidence/product-design-final-20261006/FINAL-REPAIR-PLAN.md)逐包实施。本文件记录每包的代码变化、反例测试与验证结论；产品决定见 [UX-REPAIR-DECISIONS](UX-REPAIR-DECISIONS.md)。测试命令：`python -m pytest tests/rebuild -q`（浏览器用例加 `-m browser`）。

## 环境备注

- 审计基线包含 main（`6996a29`）之外 34 个提交（含 PR102 修补 `0406807`/`e203982`）；实施从 `4fefd0b3` 分支，不回迁 main。
- 本机存在一个与代码无关的既有失败：`test_gallery_core.py::test_gallery_and_thumbnail_http_keep_host_origin_hash_and_csp_guards` 在干净基线上同样失败（Host 头校验返回 502 而非 403，本机回环环境差异）；已从回归口径中单列，不计入实施回归。

## UX-00 · 明确错误与证据基线（已实施）

| AC / 主题 | 代码变化 | 反例测试（旧败新过） |
|---|---|---|
| AC01 / F01 交接复制错组 | `change-handoff.js`：新增 `copySnapshot` 纯守卫——复制只作用于"已成功读取且与当前所选一致"的组；`copied` 标记改记快照身份；面板渲染改用已读组身份（`data-change-id`、已复制提示）；切换组时立即重绘（复制按钮对新对象禁用并提示）；`refresh` 忙碌时合并重跑，不再丢组切换 | `test_ux00_object_identity.py`（node 契约）+ `test_ux00_fixes_browser.py::test_handoff_copy_binds_to_the_loaded_group_not_the_pending_selection`（route 隔离延迟，断言剪贴板为空、本机提示不写入、返回后复制绑定正确组）。回退修复后 4/4 反例失败，恢复后通过 |
| AC02 / F02 材料新增入口 | `content-sources.js`：提取 `.materials-adjust-form` 具名折叠；头部入口直接打开它并聚焦"新增材料完整路径"；历史版本（无当前输入）入口不出现 | `test_ux00_fixes_browser.py::test_material_entry_opens_the_adjust_form_not_the_first_material_card`（2 份材料下验证打开的是表单而非第一张材料卡；历史版本无入口） |
| AC03 / F03 分页越界 | `visual-style.js`：保存任务与参考截图两组分页的边界条件从 `button` 第三实参（primary）改为 `props.disabled`——首组禁用"上一组"，末组禁用"下一组" | `test_ux00_fixes_browser.py::test_style_saved_task_and_reference_pagers_stay_within_bounds`（31 个真实任务 + 13 张 mock 参考图，断言首尾禁用与 offset≥0）+ node `button` 契约测试 |
| AC04 / F04 范围与决定语义 | `annotations.js`：project 范围显示"整稿意见"，分组说明改为"范围记录，不表示已认可整稿"；`dom.js` 新增 `shortRef`；`candidate-desk.js` 保留决定摘要改用 `shortRef`，不再伪装 `R` 版本码 | `test_ux00_fixes_browser.py::test_project_scope_reads_as_opinion_and_decision_ref_is_not_a_revision` + `test_deep_quality_browser.py` 文案同步 |

证据：旧代码 4 反例全失败（`git stash` 验证）→ 恢复后全过；全量非浏览器回归通过（除上述环境既有失败）。

## UX-01 · 交互规则与最小共用能力（已实施）

- `docs/specs/deck-master-webui-v4-20260930/UX-REPAIR-DECISIONS.md`：D1–D4 按方案推荐默认定稿记录。
- 最小共用能力只建了两个切片实际用到的：`dom.shortRef`（C01 对象短码，非版本）、`change-handoff.copySnapshot`（C01 快照身份守卫）。未预建组件目录或框架（按方案 §5"抽象只从实际复用处形成"）。
- AC05（同名对象选择前可区分）随 UX-03 的规范/候选/修改组命名落地后单独验收。

## UX-02 · 批量任务切片（已实施）

| AC | 代码变化 | 反例测试 |
|---|---|---|
| D1 落地 | `overview.js`：移除筛选/搜索/偏好同步三处 `selected.clear()`；`selectionNote` 显示"已选择 N 页，当前筛选外 M 页"；空态文案"已选页面不受筛选影响"；选择经 `saveSelection()` 持久化（项目键 localStorage 连续性 + `ui_overview.v1` 新可选字段 `selected_page_ids` 按版本记录）；`batch-actions` 移除受限页/清除选择同步持久化 | `test_ux02_batch_slice_browser.py` |
| 合同扩展 | `ui-overview.v1.schema.json`：可选 `selected_page_ids`（minLength 1、maxLength 128、maxItems 500）；旧记录天然兼容；迁移说明：缺字段按未选择处理 | `validate_schema` 新旧两态均通过 |
| 要求保留 | `batch-actions.js`："所选页的制作要求"保存到本机项目键（`deck-master:overview-working:<identity>`），返回/刷新后恢复；它不是业务草稿、不进 payload | AC06/AC08 断言跨面返回与刷新后要求仍在 |
| AC06 | 30 页样本选第 2、28 页 → 配置面板"2 页用于原图试作"、预算=选页数、预览出现"2 页 · 原图试作 · 图像调用 2 次"；跨面返回保留；预览不改业务事实 | `test_cross_chapter_selection_reaches_config_and_survives_return` |
| AC07 | 搜索/筛选保留选择并显示筛选外计数；空结果空态保选择；全选只含当前筛选可操作对象（30 页全过）；清除选择为唯一整体清空 | `test_filters_keep_selection_and_show_out_of_filter_count` |
| AC08 | 版本前进后：恢复位置（旧版本只读，诚实降级）→"查看当前版本"→ 选择/要求仍在、旧计划不随新版本提交（保存禁用）→ 重新预览后可提交；未知提交沿原请求核实由 lost-commit 反例继续覆盖（其"刷新后要求为空"断言按 D1 更新为恢复值） | `test_refresh_and_version_advance_keep_draft_and_invalidate_old_plan` |

同步：`DESIGN.md` D1 一句已改；`test_batch_actions_browser.py`、`test_overview_preferences_browser.py` 两条旧规则断言按 D1 更新并注明。

## UX-03–UX-08（未实施）

- UX-03 风格与候选切片（F07/F08/F09，AC09–AC12）
- UX-04 内容与共享单页（F06/F10，AC13–AC15）
- UX-05 任务版本与文件（F12/F09，AC16–AC18）
- UX-06 恢复异常与响应式（F11/F13/F15，AC19–AC22）
- UX-07 样式收敛与规范同步（F16/F17，AC23）
- UX-08 组合验收与交付结论（AC24）

这些包的状态是**未开始**；任何 AC 不因 UX-00–02 的通过而视为通过。
