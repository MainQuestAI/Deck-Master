# UI 重构工程落点与能力保全

2026-10-24 · 只读盘点与实施建议；本轮没有修改产品代码，也没有运行产品行为验收。

## 结论

重构应落在现有工作台的呈现层、信息结构和组件规则上。项目入口、五工作面、单页链路、候选比较、草稿保护、固定版本和恢复交易已存在；它们应被重新组织和统一呈现，而不是被新的静态样页替换。继续使用原生 ES Modules 和现有服务，既不引入前端框架，也不新造后端状态机。

本轮精修参考稿的 32/36px 桌面控件、44px 触控目标和抽屉模式是**拟采纳规范**。当前根 `DESIGN.md` 仍写统一 44px，实施基线需明确记录本次变更，再同步相应设计断言。不可通过删掉旧断言，让新的尺寸规则在没有覆盖的情况下通过。

## 盘点基线与证据边界

| 对象 | 本次读到的事实 | 使用方式 |
|---|---|---|
| 本地 checkout | `main@92e9f567eaf506f004cac1ef68f44f314739631a`，提交时间 2026-10-14 15:10:45 +08:00，PR #112 merge | 下文文件落点只代表这个本地源码快照 |
| 远端 main | 2026-10-24 只读 `git ls-remote` 返回 `afcc23d1654a6ce24583677c4de9d4a80f0f89bd` | 与本地不同；本轮未 fetch、切分支或覆盖工作区 |
| 工作区 | 有用户原有修改与未跟踪文档 | 不重置、不清理、不提交；本报告只写指定设计输出目录 |
| 默认入口 | 本地 `web.py:515` 根路径服务 `/studio/`；`launcher.py:19` 默认 `ui="studio"` | 不能只验收 `/v2/`，也不能把 v4 旧规划当现状 |
| 前端接线 | `studio/index.html` 复用 `/v2/app.js`、`icons.js` 与 47 个原生 JS 模块 | `studio` 目录没有独立 JS，实现共用同一套业务接线 |
| 样式级联 | Studio 初始加载 9 个 CSS；比较画布按需增加第 10 个 | 必须建立一份最终组件样式归属，不能在末尾持续叠加覆盖 |
| 产品运行 | 本轮没有启动服务、读取客户项目、生成、采用或导出 | 源码存在、历史测试记录、当前实现通过是三种不同证据 |

开工先核对最新 remote main、活动安装模块路径/BUILD_ID、`/api/health` 与资产指纹，再把本文文件落点映射到实际实施 SHA。修复基线 PR #184 与当前 Issue 状态以独立现场核验为准；不沿用本地旧文件推断已关闭或尚未实现。

## 当前页面与模块覆盖

下表的“保留”是重构回归范围，不表示本轮已重新验证。

| 范围 | 当前落点（`src/deck_master/resources/static/v2/` 下） | 重构后必须保留的能力 | 建议改动边界 |
|---|---|---|---|
| 项目入口 | `app.js`、`launcher-ui.js` | 新建、打开、登记已有目录、只读示例、搜索、不可读项目说明、目录选择取消/失败恢复、创建成功但打开失败后的同项目恢复 | 清晰项目列表和新建入口；次要管理动作归对象菜单，保留明确对象名 |
| 全局工作台 | `project.js`、`routes.js` | 五个一级工作面、项目/版本上下文、深链接、返回路径、只读历史、连接状态、能力禁用原因、背景读取不劫持阅读位置 | 固定全局层级；导航不是业务主按钮；同步详情按需展开，未知业务保存仍显著可见 |
| 制作总览 | `overview.js`、`overview-state.js`、`action-targets.js` | 真实 `next_actions/attention` 到对象的定位、制作矩阵、正文/原图/SVG/PPT 状态、提示词记录、搜索/筛选/排序 | 最需处理事项为首屏焦点；矩阵是进度入口，不在每格堆常驻大按钮 |
| 内容与页序 | `content-sources.js`、`content-edit.js`、`material-uploads.js` | 整合摘要、章节与页目标、材料关联与位置、待确认事实、输入更新、完整正文、页序/合并/拆分/移除/改写影响预览 | 阅读默认，编辑按任务进入；页级动作放上下文菜单；有选择才显示批量工具条 |
| 整稿画廊 | `gallery.js`、`gallery-state.js`、`images.js` | 联系表/连续阅读/并排、内容/原图/SVG/PPT 层、搜索/筛选、参考页、选页制作、固定引用、图片失败恢复和资源释放 | 画布优先；视图设置与业务制作分开；未选页不展示批量动作墙 |
| 风格校准 | `style-calibration.js`、`visual-style.js`、`style-phases.js` | 项目内五维与截图七维两种来源、参考/目标、借用与保持、规范确认、单页试作、候选决定、明确扩选、恢复定位 | 同一四阶段阅读结构；仅展开当前任务，不合并两种 schema，不伪造已验证的风格结论 |
| 任务与交付 | `views.js`、`run-desk.js`、`change-handoff.js`、`delivery-desk.js` | 四子区（正在进行/待决定/版本/文件）、任务分页与准确目标、交接/复制、核实/取消、版本预览、恢复、固定版本导出与下载 | 子区一次显示一个上下文；当前任务动作不泄露到文件/版本区；输出用途和版本紧邻行动 |
| 共享单页 | `page-workbench.js`、`page-reading.js`、`page-text.js`、`production-view.js`、`request-view.js` | 来源→逐页稿→提示词→原图→SVG→PPT；上下页、完整阅读、预备与实际提示词分别显示、读/改/标注互斥、只读历史 | 先保证内容/图稿可读，再放页状态与生产工具；编辑抽屉复用既有交易与草稿，不能保存后假装通过审阅 |
| 来源阅读 | `content-edit.js:sourceReader`、`content-sources.js` | 固定来源版本/定位、材料读取事实、缺失/提取待核实、原材料不可变、页目标关联 | 小量补充信息用侧面阅读；多材料修改与长差异应使用宽编辑区，不能一律塞进窄抽屉 |
| 候选比较 | `candidate-cards.js`、`candidate-desk.js`、`changeset-desk.js`、`comparison-canvas.js`、`text-diff.js` | 同页同层固定基准、正文差异/图稿完整比较、多个候选独立、采用影响预览、保留当前/重开决定、失效基准拒绝、结果迟到保护 | 三个入口复用同一候选身份与卡片；复杂比较使用宽工作区，抽屉只承担简短详情 |
| 批量与意见 | `batch-actions.js`、`batch-policy.js`、`annotations.js`、`annotation-submission.js`、`text-selection.js`、`icon-workbench.js` | 筛选后保留选择并报筛选外数量、仅选可操作对象、意见与调用分离、精确选段/图标范围与键盘替代、重复提交防护 | 状态选择、导航和执行按钮采用不同组件；高影响操作必须显示确切选页及范围 |
| 草稿与恢复 | `drafts.js`、`business-operations.js`、`receipt-verdict.js`、`personal-recovery.js`、`run-recovery.js` | 跨端口项目草稿 ACK、独立窗口缓冲、基准冲突双方保留、丢响应原 operation 核实、同 ID 原请求重放、取消/晚回包、个人状态清理恢复 | 保持内核，改呈现与容器；移动 DOM 或关闭抽屉不应销毁有效编辑器、待核实请求或后写内容 |

## 样式和组件迁移

### 先查清覆盖关系

Studio 初始顺序为 `tokens.css → style.css → workbench.css → navigation-usability.css → studio.css → studio/workspace.css → studio/overview.css → studio/delivery.css → studio/reading.css`；比较时另加载 `comparison-canvas.css`。

本地 `tokens.css` 同时存在基础绿色 accent、衬线 display 与大展示字号，产品样式又覆盖主色和字体；`style.css`、`studio.css` 及分工作面 CSS 多次改写按钮、行高和布局。问题不只在数值，而在**同一组件的最终规则跨文件分散**。这不是删除基础 token 的充分理由：先记录每个工作面真实 computed style 和所有引用，再迁移。

1. 将新的语义 token 作为一个受版本管理的产品层：颜色、字号/行高、间距、控件尺寸、圆角、边框、焦点、层级、动效。保留原始数值来源与旧名映射，逐项标记“沿用/替换/待验证/已退役”。
2. 组件样式只允许一个主定义。最小集合为 Button、IconButton、导航项、分段切换、文字链接、Menu、Field、Status、Row、Dialog/Drawer、Notice、EmptyState、阅读画布；状态不是按钮变体。
3. `dom.js` 现有 `button(text, action, primary, props)` 保留兼容适配，再逐工作面显式选用 variant/size。不要一次性机械把全部 `button()` 改成同一高度；导航、页标题、单元格链接和执行操作需按语义分流。
4. 从主题入口逐步移走已覆盖的旧声明；每批只清理本批已迁移组件的旧样式。保留可回退的提交边界，不留永久“双主题开关”来掩盖未收口。
5. 内容宽度、抽屉宽度、表格列和画布尺寸由各场景布局负责；不要为了“全部 token 化”把每个局部尺寸都提升为全局 API。

### 抽屉不能成为新的拥挤来源

`dom.js` 当前复用一个原生 `<dialog id="modal">`，有关闭后焦点回退。新增 Drawer 应复用这套语义，定义受控内容区/底部动作区，保持焦点、Escape 与移动端全屏，不再引入第二套弹层框架。

- 适用：页属性、正文编辑、简短来源、任务详情和轻量筛选。
- 宽区：长正文差异、多材料修改与影响确认、双图比较、跨页结构变更。宽区依然保留清晰返回入口与原草稿。
- 弹层叠加：优先在同一容器内前进/返回；需要确认时保持原编辑器存活，不重建其身份。
- 有效草稿关闭与未核实提交是不同状态：前者可保存后返回，后者必须能恢复原请求；不得以“关闭即丢弃”简化。

## 必须沿用的事实与交易边界

| 边界 | 现有实现/合同 | 不允许的 UI 简化 |
|---|---|---|
| 当前与固定版本 | `routes.js`、`project.js`，`workbench.py` 读投影 | 自动把历史/候选切成新 current；选中版本就暗中改变所有动作对象 |
| 服务支持与对象可写 | `health.ui_capabilities`、`project.effective_actions`；服务仍独立验证 | 只靠按钮隐藏代替权限/能力校验，或把能力缺失变成空白 |
| 草稿与业务提交 | `DraftEditor`、`ui_journal.py`，`ui-draft*.schema.json` | 将本地输入标成内容已更新；刷新后丢失已 ACK 草稿 |
| 业务结果未知 | `BusinessOperations`、`receipt-verdict.js`、`operations.py` | 丢响应显示“失败”并自动另发 UUID；把网络失败写成任务 failed |
| 内容/输入影响 | `content_ops.py`、`content-operation-*.schema.json` | 上传即宣称已读、更新材料即宣称正文对齐、合并/拆分结果返回即自动采用 |
| 候选与决定 | `candidates.py`、`candidate*.schema.json` | 以当前图替代缺失候选、保留当前只改本地显示、比较双方随轮询漂移 |
| 风格路线 | `styles.py`、`visual_styles.py`、v1/v2 recipe/input/proposal 合同 | 合并五维和七维状态，确认规范就启动模型，单页完成就自动扩到全稿 |
| 任务与调用 | `run_desk.py`、`changes.py`、`task.v1.schema.json` | 复制等于接手，返回等于采用，取消后的晚结果覆盖新稿 |
| 导出与恢复 | `exports.py`、`service.py`、`export-manifest.v1.schema.json` | 检查通过等于已发布；历史恢复回滚执行事实；文件下载不绑定版本 |
| 后台更新 | `SummaryPoll`、route generations/disposables、`images.js` | 每个新组件各自增设轮询；旧回包替换用户新选择；泄漏图片/监听器 |

## 建议实施批次

每批是可独立审查、回退和验收的边界；不估算人日，也不重新编号或宣称关闭原 A01–A08/B01–B07 或 UX AC。

| 批次 | 可审查产物与顺序 | 主要回归与退出条件 |
|---|---|---|
| E0 基线对齐 | 确定最新实施 SHA、活动入口、修复基线与 Issue 所属；导出全工作面真实样式/动作清单；记录 32/36/44 规范变更 | API/契约与 UI 入口清单一致；旧 AC 和未完成真实层义务映射到新计划，不用样稿替代 |
| E1 组件与框架 | 语义 token、按钮/导航/菜单/字段/状态/弹层，项目入口与全局壳；先用现有真实数据跑一个工作面 | `/studio/` 主入口及 `/v2/` 兼容入口有明确处理；长名称、空/错误、键盘、两个桌面主视口与窄屏布局通过 |
| E2 总览与内容 | 唯一主要待办、制作矩阵、页序/材料/内容计划与按需动作；把选择/批量回归带进来 | 30 页合成稿选第 2/28 页后筛选/返回保持；来源、材料编辑及影响确认同上下文；无功能被菜单化后失联 |
| E3 单页与阅读 | 六段链路、默认阅读、抽屉编辑、图稿工具、来源和意见 | 保存/取消/刷新/切层/冲突/丢响应/晚回包；正文不截断，图稿完整，焦点可靠，无未承诺的自动业务变化 |
| E4 画廊与候选 | 全稿节奏、连续/并排、共享候选卡和固定比较、变更集预览 | 快切/迟到、图片释放、同页多候选、正文/图稿差异、采用失效、保留当前；所有入口对同候选呈现一致 |
| E5 风格与任务交付 | 两种风格四阶段、任务四子区、版本/文件、恢复详情 | 配方来源可区分，人工阶段不被恢复抢走；A 选中/B 已读/C 当前身份清楚；导出固定版本与取消晚结果守卫 |
| E6 收口 | 移除本轮替代的样式覆盖，检查能力清单；连续五条任务与最终安装资源指纹验证 | 最终冻结包的适用测试、浏览器/键盘/截图/下载证据；真实 Host、真实交付、HOME 激活、用户认可单列状态 |

依赖原则：E1 是共同基础；E2 与 E3 共用稳定组件并可在明确文件责任后并行；E4 依赖 E3 的阅读/比较容器；E5 消费 E4 的候选决定。E6 不用不同包、不同 SHA 的通过数拼接。发现接口真实缺口时分出有归属的能力任务，前端继续完成可读部分；不在视觉 PR 中顺手重写后端。

## 回归资产与证据等级

以下是本地已有回归入口，**本轮未运行**。实施时只针对变化与风险选择子集；产品提交最终门禁按仓库规则执行，不因视觉更新扩展无关测试。

| 回归组 | 可复用文件（`tests/rebuild/` 下） | 关键判据 |
|---|---|---|
| 基础语义/几何 | `test_ui_design_browser.py`、`test_container_hierarchy_browser.py`、`test_ui_font_tokens.py`、`test_static_modules.py` | 表头/表体对齐，按钮语义，键盘焦点，字号/触控按新决定核验，不删行为断言 |
| 导航与总览 | `test_navigation_usability_browser.py`、`test_overview_preferences_browser.py`、`test_studio_overview_browser.py`、`test_ux02_batch_slice_browser.py` | 深链接、过滤外选择、准确对象、返回位与旧事件不回写 URL |
| 内容与输入 | `test_studio_content_browser.py`、`test_ux04_content_annotations_browser.py`、`test_pr103_repair_browser.py`、`test_pr105_inputs_browser.py` | 多材料、读改分离、来源完整、关闭/刷新保持草稿、核对依据变化即失效 |
| 单页与画廊 | `test_studio_page_browser.py`、`test_studio_reading_browser.py`、`test_gallery_reading_browser.py`、`test_comparison_canvas_browser.py` | 阅读比例、六层、连续阅读、精确选段、键盘替代、画布与焦点 |
| 候选与风格 | `test_ux03_style_candidate_browser.py`、`test_studio_style_browser.py`、`test_studio_candidate_batch_browser.py`、`test_candidate_decisions.py` | 两种风格、固定基准、真实候选对象、采用/保留、不抢手动阶段 |
| 版本与交付 | `test_ux05_runs_delivery_browser.py`、`test_studio_delivery_browser.py`、`test_versioned_exports.py`、`test_delivery_control_snapshot.py` | 四子区、版本身份、冻结下载、恢复产生新版本、交付门禁 |
| 恢复与性能 | `test_summary_poll.py`、`test_task_receipt_recovery.py`、`test_personal_recovery_browser.py`、`test_late_results_and_stops.py` | 不增加重复轮询、断线保留、原操作核实、后写草稿不被晚回包覆盖 |

PR103 历史记录仅作行为债务和反例来源。其 2026-10-07 文件明确区分工程行为、局部组件视觉、完整任务体验；AC03/AC24 当时部分完成，历史报告不是当前验收。它要求的材料编辑同区、统一候选呈现、导航时序、意见去重、上传核实原 UUID、固定版本与焦点回退应完整延续。旧 required CI 等状态不在此重断言。

E6 建议使用同一冻结实现完成五条连续任务：创建并补材料；阅读并调整页序与正文；选页制作并交接；比较候选并采用/保留；固定版本检查和导出。故障路径至少附带一次丢响应、一次基准冲突、一次取消晚回包。数据应为隔离合成项目；真实 Host 和客户验收保持单独记录。

## 核心风险

1. **审美重构变成能力删减。** 样页只显现三种场景，实际产品有完整制作链与恢复；以清单逐项确认入口、状态、返回路径，而不以截图好看替代能力。
2. **继续叠 CSS。** 初始九表加动态比较表已构成多层级联；每批必须收回对应旧规则的所有权，避免第十一层“修补主题”。
3. **移动容器破坏身份。** 草稿、候选、固定版本和原请求绑定稳定对象；抽屉开关、路由销毁、晚回包是必须验证的连接处。
4. **把未知压缩成一个通用状态。** 简洁文案仍要区分保存/提交、复制/接手、返回/采用、检查/交付。正文与来源的简短摘要必须可展开到真实证据。
5. **旧源码或历史测试冒充当前结论。** 当前本地与远端不同；实施和验收只绑定最终冻结 SHA/BUILD_ID。
6. **视觉修复掩盖性能故障。** 本报告只建议复用读取生命周期，不宣称解决 #142 或其它性能 Issue；性能修复需独立实现与测量证据。

## 读取依据

- 根 `AGENTS.md`、`DESIGN.md`、`docs/agent-task-index.md`、`docs/agent-recovery-playbook.md`。
- `docs/specs/deck-master-webui-v4-20260930/README.md`、`A-UI-SPEC.md`、`INTERFACES.md`、`UX-REPAIR-DECISIONS.md`、`PR103-JOINT-REPAIR.md`。
- `src/deck_master/resources/static/{v2,studio}/`、`web.py`、`launcher.py` 与活动合同目录。
- 本文同目录 `coverage-inventory.json` 包含机器可读范围、路径和状态；路径存在性已静态核验，不代表相应测试已运行。
