# 固定目标独立工程复审

结论：**需要修复后复核，不能将本候选标为 S1/S2 工程验收完成。确认 6 项缺陷，其中 3 项 P1、3 项 P2。** 本轮为受委派的全新只读工程 reviewer，不是真实内容模型审稿、真人专业认可或外部独立安装环境认证。

审查目标为 `1493cc28bd24edd06505dd99ac4bf1b23e7ec77a`，实际 tree 为 `5caff055e8457d9db77873393fb07a0d90b7067e`。基线 `6797b2070d8650ea0e319bae0c39cd2c052a40c6` 的 tree 为 `13f925e917955262c97907f3065c445087cb07b2`。不据此宣称恢复原父链。所有本轮脚本、项目夹具和日志都在 `/workspace/reviewer-1493/`；未修改仓库、提交、推送、上传或调整环境权限。

## 确认缺陷（按严重程度）

### R1 / P1：页级授权被空页 outline 派发扩大为整份大纲审查

位置：`src/deck_master/outline_review.py:89`（向 guard 传 `page_ids=[]`）、`:108`（派发）；`src/deck_master/service.py:1395`（重复以空页集检查）；`:1379` 的新 outline 分支没有检查主体覆盖范围。

触发条件：当前请求是 `review_only`，scope 为 `subject=pages, page_ids=['p1'], layers=['review']`，现有 Narrative/Plan 覆盖 p1、p2。通过正式 `collaboration.start_request` 替换原请求，再调用正式 outline dispatch。

复现：`test_adversarial.py::test_page_scoped_review_does_not_dispatch_whole_outline`。`scope-formal.log` 记录正式请求只含 p1，但返回 `review_dispatched`、Task `scope_pages=[]`，packet 的 `plan.input.page_order=['p1','p2']`。这不是通过直接篡改请求得到的最终反例；独立的早期 `scope-probe.log` 仅为定位资料。

影响：新增空页特例借用了页集合的空集包含关系，绕过本次审阅范围；将整份 Narrative/Plan 作为 Task 主体交付给审阅者。此次没有模型调用，但真实 Host 可被要求审超出范围的大纲。未发现它因此取得 page_copy 或视觉生产资格，不能把这项问题扩大描述为所有生产授权失效。

建议：在两条正式写入口以明确 outline 主体与本次 scope 验证覆盖关系；仅有局部页权限时拒绝全纲派发或采用有版本、有边界的局部大纲主体，不能把空页当全稿许可。保留 Task 空页特例及旧 Page 合同。

### R2 / P1：大纲语义变化后旧 argument/progression 仍被判为当前 pass

位置：`src/deck_master/outline_review.py:38` 调用 manuscript `_applicable_reviews`；根因在 `src/deck_master/content_review.py:760` 至 `:769` 的 `_unit_dependency_equivalent`。

触发条件：已合法接纳 outline 的 argument/progression pass，此后只改变 Plan 的某页 `required_qualifications`、`source_links` 或 `narrative_node_ids`，Narrative 不变。

复现：`test_adversarial.py::test_changed_outline_semantics_invalidates` 的三个参数用例。每次先经 native runner 的明确合成 transport 完成一次接纳，再写入通过模型语义校验的 Plan 新版本。`adversarial.log` 与 `installed-adversarial.log` 均显示三种变更后 status 仍为 pass，satisfied_units 仍为 argument/progression。

根因：outline 无 `content:page:*` dependencies，因此 equivalence 内的 ids 为空、roles 被筛空；global projection 并不保留上述三个字段。实际所审 Plan Ref 已变，却被错误当作无关语义变化。

影响：去掉关键限定、去掉证据关联或改变论点到页职责的绑定，可以不触发早审；dispatch/native run 又会据此返回 already_reviewed。该结论仅为工程失效错误，不是模型漏检统计。

建议：为 outline 采用完整相应 Plan 语义投影，至少覆盖所有页职责的论点、来源和限定；或先用严格 Narrative/Plan 版本失效，再明确白名单保留纯审计/非语义变化。增加上述三种变化以及无关视觉/notes 变化的对照。

### R3 / P1：已有可信完成结果待接纳时，outline dispatch 仍创建新任务并可重复执行

位置：`src/deck_master/outline_review.py:92` 至 `:108` 只检索 running/awaiting_host/queued；`src/deck_master/native_review.py:378` 仅在 task is None 时优先返回 recoverable。

触发条件：native outline 已产生并持久化 observed、ready checkpoint，接纳阶段出错使 Task failed；随后调用 outline dispatch，再调用 native outline。

复现：`test_dispatch_recovers_before_new_task`、`test_new_dispatch_bypasses_recoverable_result_and_reexecutes`。`adversarial.log` 表明新 dispatch 之前 native 正确返回 recovery_available，但 dispatch 创建了不同 Task ID。`double-execution.log` 进一步证明随后 native run 返回 reviewed，合成 session 调用数从 1 变 2，旧 ready 结果未先恢复。

影响：通道接纳故障可以被新 Task 掩盖，真实运行可能重复审查与收费。这是合成调用计数，不是本轮发生实际收费；没有新增真实外部调用。

建议：将原 operation/Task/checkpoint 的待恢复检查收敛到共用派发前判断，包括 failed、有可信完成结果及未知执行状态；新任务存在也不能遮蔽同主体、版本、单位的待恢复结果。先恢复或明确处置旧任务，再允许新执行。

### R4 / P2：完整 PPT 已满足当前交付门禁，current_work.delivery 仍永远 in_progress

位置：`src/deck_master/current_work.py:43` 直接将内容完成投影当成所有请求交付投影；`src/deck_master/content_production.py:540` 只允许 content_only 得到 completed；`current_work.py:91` 至 `:122` 没有 full_deck 完成分支。

复现：`test_current_adversarial.py::test_completed_full_deck_projection` 使用已有明确标注的 L1 `_passing_deck`，并独立调用正式 `delivery_eligibility.describe` 交叉核对。`completed-deck-evidence.json` 中相同 revision 的结果为：readiness=ready、engineering_ready=true、review_status=pass、next_action=deliver_selected_file；current_work 却是 delivery.state=in_progress、responsible_role=content、next=review_quality，delivery.outputs 也不包含 PPT 输出。

影响：统一投影与既有交付真源矛盾；用户完成整稿后仍被引向内容/历史质量记录，无法靠统一 current_work 判断本次已交付。原完成函数早已只适用于部分场景，本增量把它直接扩为全场景权威，未补适配。

建议：复用既有交付/样页/局改完成事实做按请求类型的统一组合，而不是修改门禁为放行；完成态优先呈现产物阅读/交付，将历史质量记录作为可读附项。增加已完成、待审、撤回、只比较不采用等终点矩阵，不能只测缺图起点。

### R5 / P2：两前端在控制快照刷新后仍显示旧 current_work 主动作

位置：`src/deck_master/resources/static/v2/collaboration-desk.js:217` 新增 `currentWork(app)`；`current-work.js:6` 默认取 `app.summary.current_work`；`project.js:90` 至 `:119` 轮询仅更新 latest/info，没有重取固定 artifact + 新 control 的 current_work。

触发条件：打开当前制作总览，另一个窗口/调用暂停当前请求，等待正常轮询（本测试通过 window focus 触发同一 SummaryPoll 路径），然后打开“本次工作与范围”。

复现：`test_current_adversarial.py::test_control_refresh_recomputes_current_work[studio|v2]`，真实本地 Chromium、两条前端路由均复现。弹窗已显示暂停原因和“恢复本次请求”，却仍显示旧“2 页原图待生成 / 主协调 / 查看待补页”；重新查询所看 artifact revision 的 summary v2，正确标题应为“正在查看历史版本”。日志 `current-adversarial.log` 保留两端 DOM 断言和输出。

影响：同一弹窗混合新控制事实和旧行动判断，identity.control_revision_id 也过时。后端写入仍有 guard，本轮没有发现暂停可被此 UI 绕过；这是当前责任/动作及跨端一致性的实质缺陷。

建议：保留固定稿件和草稿，单独用固定 artifact、新 control 重取只读投影并更新主动作；不要把 latest 的整份产物直接替换历史视图。暂停、撤回、替换请求、权限变化均加轮询后验证。

### R6 / P2：native outline 恢复成功返回了逐页稿 gate 和错误下一步

位置：`src/deck_master/native_review.py:266` 的 `_recover` 无条件调用 `content_review.preproduction_status`，没有沿本增量 `_run` 的 outline 分支。

触发条件：无 Page 大纲 native 审查已有 ready checkpoint，初次接纳失败，随后使用原 Task `recover` 成功接纳。

复现：`test_adversarial.py::test_outline_recovery_gate`；源码和安装环境均复现。返回 `status=recovered`、`model_called=false`，但 preproduction.status=no_manuscript、next_action=write_manuscript，列出 page_copy/speech 缺口；同快照 `outline_review.status` 为 pass、production_qualified=false；session 只执行一次。

影响：恢复本身成功且不重调模型，但出口错误引导开始写稿，不能正确结束只做大纲的请求。

建议：恢复与正常完成共用按 frozen task.review_subject 选择的 gate；保持 production_qualified=false，不让大纲通过替代逐页或视觉资格。

## 实际审查与证据

- 先读取仓库 AGENTS.md；检查 `/workspace/.agents`（无 skills 文件）、任务索引、恢复手册、相关 RC5/UI 规范及 Review Skill。Library skill `c3/library` 后，通过当前 Library read 分页完整读至权威 DOCX 的 1213 行，最终 has_more=false；不以摘要或作者报告替代正文。
- 阅读 baseline..target 代码增量、schema 变化、current_work、outline_review、native 正常/恢复分支、Review subjects/dependencies/finding_closed、scope/eligibility、任务接纳、四职责方法 reader、CLI/HTTP 协商、两前端消费链及 S3 准备脚本。
- 独立正常回归：`regression.log`，46 passed、12 browser deselected；涵盖 current_work、outline、native recovery、review owner scope、scoped preproduction。浏览器异常用例另跑，未将 deselected 算通过。
- 新反例：最初 `adversarial.log` 为 5 failed/1 passed（3 个大纲失效参数、恢复 gate、恢复前派发失败；不可读 Narrative 局部 unknown 通过）。后追加重复执行及正式页级 scope 反例，分别见 `double-execution.log`、`scope-formal.log`。`current-adversarial.log` 三个失败为两前端刷新和完整交付投影。
- 安装验证：用 `/workspace/deck-installed/bin/python -I`，根模块及测试后所有已加载 deck_master 模块均来自 site-packages；重复首批 6 个反例得到相同 5 failed/1 passed。源码目录内 285 个非 pycache 文件与安装包逐字节一致，无差异。安装包 release 标注 source_sha=4a2e8f87；独立 git diff 显示其到目标仅增加 validation.md，未声称 release 元数据直接绑定 1493。源码执行器为 `/workspace/deck-dev/bin/python`。
- 原始作者日志读取：core-candidate 341 passed、source-final-vertical 46 passed、native-outline-final 16 passed、installed-final 387 passed；这些是原日志观察，不计入本 reviewer 重跑分母，也不能抵消反例。
- v1 默认响应无 current_work、新 v2 显式协商、read 不调用 continue/open_host_task、历史查看动作清空、不可读 Narrative 局部 unknown、outline pass 不满足 manuscript gate、同 finding owner/替换主体保护等已有回归本轮通过或代码确认。并非所有历史迁移与并发交错都已穷举。
- 多动作策略代码已核对：verify/recovery 排在前，随后 handoff/compare/results/quality/制作缺层；完整交付时 quality 历史项抢主动作由 R4 实证。没有把所有排序偏好都升级为确认缺陷。

## 未跑验收与环境限制

- 真实 Host 子职责退出后自动接续、中性样稿真实语义审查→修订→原 finding 复查、真实图片/SVG/PPT 阅图效果、方法 A/B/C 成稿及真人理解观察，均 **not_run**。本轮 FixtureSession/合成 receipt 只能证明机制。
- S3 脚本确实生成 24 个匿名诊断输入并标 prepared_not_run、execution_denominator=0，Q10/Q12 还缺实际像素/对象；这不是模型准确率、真实好坏稿盲评或方法改善证据。未执行真实客户、付费制作、RP24 新调用或伪造 A/B 执行/结算身份。
- 阅读已有 initialize 诊断：native-initialize-probe.json 为 startup_failed、phase=initialize、model_called=false；stderr 记录只读文件系统与 CODEX_HOME SQLite 初始化失败。未重新启动真实 native、改 CODEX_HOME、复制凭据、改权限或挂载。环境限制不影响上述独立工程反例。
- 无待审批、无被拒绝的本轮操作、无不确定外部写入。代码修复属于作者下一步；请保持此报告和日志对应原目标，修复后交同一 reviewer 复核。
