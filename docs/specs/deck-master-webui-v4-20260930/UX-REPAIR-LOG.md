# UX 整改实施日志（UX-00–UX-08）

日期：2026-10-06 · 基线：`4fefd0b3`（`codex/v1-rc-closure` 审计基线）· 实施分支：`codex/webui-ux-repair`。

按[最终修复方案](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/evidence/product-design-final-20261006/FINAL-REPAIR-PLAN.md)逐包实施。本文件记录每包的代码变化、反例测试与验证结论；产品决定见 [UX-REPAIR-DECISIONS](UX-REPAIR-DECISIONS.md)。测试命令：`python -m pytest tests/rebuild -q`（浏览器用例加 `-m browser`）。

## 环境备注（预先存在的失败，均在干净基线 `4fefd0b3` 上复现，不计入实施回归）

- `test_gallery_core.py::test_gallery_and_thumbnail_http_keep_host_origin_hash_and_csp_guards`：Host 头校验返回 502 而非 403（本机回环环境差异）。
- `test_workbench_reads.py::test_new_gets_keep_host_boundary_and_no_read_token`：同上同类。
- `test_generation_protocol.py::test_cli_http_freeze_and_fixed_reads_are_the_same_contract`：子进程 `-m deck_master` 经 venv 可编辑安装解析到主仓库（`6996a29`）代码，与工作树服务端版本错位导致快照读取拒绝；属运行方式问题，非工作树代码缺陷。
- ~~`test_ui_design_browser.py::test_damaged_personal_reading_does_not_block_workbench`~~（已解决）：复核证明产品降级链路本身正常（runs 面板如实显示"个人已读记录暂不可用，任务按未过滤状态展示"）；测试先前失败的原因是它用手改 hash 切换工作面，把总览偏好参数（q/filter/sort）带进 runs 路由而被路由守卫按设计拒绝。测试改用导航按钮（真实用户路径）后通过，产品代码无需改动。

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

## UX-03 · 风格与候选切片（已完成：AC09–AC12）

已实施的修复：

- N07：截图路线的已保存分析/已确认规范选项在恢复前可区分——分析选项加任务短尾，规范选项加目标页数与配方短尾（`visual-style.js`）。
- ST-05：同页候选比较按钮加候选短码（`比较 <页名> · <ref 前 8 位>`），不再完全同名（`visual-style.js`）。
- N08：修改组在交接面板与运行筛选中共享同一短尾与"页数"计数（modern 模式两处同源于 `/api/tasks` 分组），选择前可对上（`change-handoff.js` + `run-desk.js`）。
- N06：任务详情的快捷阅读按任务种类进入产物层——reconstruct/repair → SVG、compose → 正文、blueprint → 原图，按钮名注明层（`run-desk.js`）。

反例测试：`test_ux03_style_candidate_browser.py`——同名规范选项可区分（mock `/api/styles`）、修改组跨面短尾一致、SVG 任务快捷入口 `layer=svg`。

同步：`test_overview_state.py` 的"必拒字段"参数化按 D1 更新——`selected_page_ids` 成为合法阅读字段后，改用其非法值（非字符串项、超长项、非数组）保留拒绝覆盖，并新增"合法选择可持久化且不动业务事实"的直接断言；`test_ui_design_browser.py` 的键盘连续性测试按 D1 改为"搜索后第 02 页仍选中"。

- **AC09/AC10（截图路线恢复与规范核对）**：截图路线恢复 `style_recipe.v2` 后，拆解图可完整查看，借用/保留维度默认借用配色与文字层级，证据按"已观察/待核实"呈现，近似字体判断如实标注；样例选择只列已采用候选（确认规范不显示为已采用页面）；同页两候选比较按钮以短码区分；项目内配方传入截图路线被明确拒绝（"这不是截图视觉规范"）。v1 路线的恢复与试作流程由既有 `test_style_content_browser.py` 覆盖。
- **AC11（候选台反例）**：同页两候选快速切换后展示对象随选择切换；候选 2 的状态回包晚到（先切回候选 1 再放行回包）时被代次守卫丢弃，展示对象与固定比较不变；读取期间保留/采用/预览停用且显示"正在读取所选候选"；采用计划与保留决定的 payload 均绑定当时展示的候选（捕获 `/api/candidates/plan`、`/api/candidates/decision` 请求体断言）。
- **AC12（扩展拒绝路径）**：核心侧拒绝（错配方、未选页/参考页、目标基准变化使样例失效、非当前采用候选）由既有 `test_styles.py::test_unselected_or_reference_page_and_other_recipe_cannot_expand` 与 `test_visual_style_freshness.py::test_self_adoption_permits_expansion_but_later_target_changes_invalidate_sample` 覆盖；新增 UI 腿反例——扩展请求 payload 绑定仍采用样例与明确选页（`adopted_candidate_id`、`page_ids`），`style_conflict` 拒绝以业务翻译呈现（"风格要求或目标页基准已变化……"）而非原始失败。

**UX-03 完成**：AC09–AC12 全部有通过的反例与回归；F07/F08/F09 的实现落点为命名身份修复 + 既有守卫/恢复机制的验收。

## UX-04 · 内容与共享单页（已完成：AC13–AC15）

- **N04/AC13**：正文编辑字段按"块 + 块内位置 + 叶类型"命名（如 `正文块 2 · 发布检查单 · 条目 1 · 文字`），块之间插入以块自身标题为锚点的分组标签；同文节点可区分、可分别修改；不确认即离开 = 取消，业务版本不变（`content-edit.js`）。
- **N11/AC15**：画布叠层与意见列表统一按产物身份（layer + artifact_ref 相等）判定；删除了"快照 revision 相等"这一多余限制——此前列表显示"适用"的点/框意见在无关版本前进后从画布消失（`annotations.js`）。反例：同产物跨快照叠层保留（`.annotation-mark.saved` 计数 1），其它产物的意见只列在"其它页面"分组不误叠。
- **AC14**：大纲块显示章节页范围（`第 1–2 页`）并经"看逐页稿"直达；返回保持工作面。材料编辑—影响—确认连续与来源定位由既有 `test_content_ops.py` / `examples/workbench/w09_content_inputs.py` 覆盖。

两处修复均验证"旧代码失败、新代码通过"。测试：`test_ux04_content_annotations_browser.py`。

## UX-05 · 任务版本与文件（已完成：AC16–AC18）

- **F12/AC16**：任务与交付新增四个子区直达（「正在进行｜待决定｜版本｜文件」按钮导航，点击滚动并聚焦子区标题 h2，替代原单一"查看版本与文件"锚点）；面板以 `runs-tasks` / `runs-decisions` / `runs-versions` / `runs-files` 标识（`views.js`）。render 任务的快捷阅读进入 PPT 层并注明（此前落到原图）（`run-desk.js`）。
- **AC17**：版本记录面板的"阅读历史版本"选择 + "读取所选版本"切换已读对象；恢复预览对话框同时显示"来源版本"与"当前基准"、明确"确认恢复并创建新版本"；取消恢复零业务变化。测试断言 URL revision、恢复对话框两侧对象与取消后 revision 不变。
- **AC18**：历史版本固定记录只含当时任务（最新待办不可见）；"查看当前版本"后待办与历史记录并存可达；awaiting_host 卡片如实显示"待接手"。

反例测试：`test_ux05_runs_delivery_browser.py`。旧代码失败点：render 任务快捷层为原图（测试断言 PPT 层即失败）。

- UX-06 恢复异常与响应式（F11/F13/F15，AC19–AC22）
- UX-07 样式收敛与规范同步（F16/F17，AC23）
- UX-08 组合验收与交付结论（AC24）

这些包的状态是**未开始**；任何 AC 不因其它包的通过而视为通过。
