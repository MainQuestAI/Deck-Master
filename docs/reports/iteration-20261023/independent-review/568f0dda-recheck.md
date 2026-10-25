# 568f0dda 同一 reviewer 修复复核

结论：原 R1–R6 在本轮复现边界内均已修复，补充边界未发现新的 P1/P2 缺陷；**仍有一项已独立复现的旧 UI 完成文案兼容测试失败，修正前不建议宣称整套回归全通过**。真实审稿和方法效果验收仍未执行。

固定源码：`568f0dda1fd0d03c7be6ac999d53d66a4da16b87`；tree `1fa6569a3100332b8c46bcb5cc9ae361b9e4493f`。复核前后 HEAD 不变、git status 干净。原 `/workspace/reviewer-1493/` 报告和脚本未改。此次文件均在 `/workspace/reviewer-568f/`。

## 六项修复判断

| 原问题 | 独立复核结果 |
|---|---|
| R1 局部页范围变全纲 | 原正式 p1-only 请求派发反例已拒绝。代码由 `review_targets` 形成完整 frozen Plan 的 deck/page scope，并在 dispatch/direct 派发及 task.start/task.accept 共用 guard。补测派发后同请求收窄 scope：start 返回 EligibilityBlocked/scope_exceeded；已启动后的接纳先由 StaleInputContext 拒绝，独立 task.accept 权限投影也明确 scope_exceeded。未接纳任何 Review。 |
| R2 旧 outline pass 错误保鲜 | required_qualifications、source_links、narrative_node_ids 三个原反例均使旧 pass 失效；outline 不再使用 manuscript equivalence 和 notes alias。严格 Narrative/Plan 版本失效符合此次显式合同；未外推为所有语义变更最小化重审已完成。 |
| R3 可恢复结果被新 Task 遮蔽 | 原派发反例返回 recovery_available。新反例在失败前先存在另一 awaiting Task，再令原 Task 产生 ready checkpoint 并接纳故障；选择另一 Task 执行仍返回原 Task recovery_available，Document 不变，合成 session 仅调用一次。direct open_host_task 也有恢复检查。 |
| R4 ready 整稿仍 in_progress | 原 `_passing_deck` 完成反例通过；delivery completed/read_delivery 与既有交付事实一致。另直接测试 describe_snapshots：传入已固定 artifact/control 后禁止无 revision 的 load_document，仍正常 ready；全部项目文件字节前后相同。未调用制作或恢复动作。 |
| R5 控制刷新仍显示旧主动作 | 原 studio/v2 暂停刷新反例均通过。新增真正编辑场景：输入尚未提交的标题，在另一个调用暂停并触发正常 SummaryPoll，打开/关闭控制弹窗；编辑器保持同一 DOM 节点、文本值不变、URL 固定 revision 不变，Page refs 未改变，两端均通过。 |
| R6 outline recover 返回 manuscript gate | 原恢复反例通过：恢复后返回 outline pass、production_qualified=false，仍只执行一次合成 session；与正常完成共用 subject gate。 |

## 剩余兼容项

已独立复现：`tests/rebuild/test_rc3_studio_control_browser.py:134`，`test_completed_overview_returns_content_without_prioritizing_unrequested_artwork[write_only]`。

当前 `src/deck_master/current_work.py:106` 附近对 completed content_only 统一显示“本次内容产物已齐备”，丢失旧用户出口的 write_only 类型文案“本次上屏稿已完成”。按钮仍是阅读本次内容，未诱发视觉制作；这不是授权绕过或交付假通过。应由后端沿既有 content_intent 恢复大纲/上屏稿/口播稿/完整内容的完成标题，保持各端一致，不应只放宽旧断言。该项是尚未关闭的兼容回归，不算 R1–R6 修复失败。

同次独立固定 HEAD 兼容复跑中，旧 `test_visual_orders_keep_complete_pages_originals_notes_design_and_result_policy` 的 reconstruct、page_visual、review-final 三个参数全部通过。作者较早扩大运行的 review-final 失败保留在其日志；作者说明涉及运行中 Git 身份变化，本 reviewer 没有重建当时并发现场，故不把解释当独立证明，但也未在当前固定身份下复现该失败。

## 本轮实际执行证据

- `original-regression.log`：原 reviewer 脚本 10 passed、1 deselected。排除的是原测试中的打印 `dispatched['task']`，修复后预期返回 recovery_available 不含 task；原脚本未改，新实质“不再执行”反例已覆盖。
- `followup3.log` / `test_followup.py`：新增 6 项通过（start/accept 收窄、另一待执行 Task 的恢复优先、固定快照纯读、两端真实编辑器 DOM/草稿保持）。
- `compat.log`：旧合同针对性复跑 3 passed、1 failed，即上述完成文案项。
- 安装来源：`/workspace/handoff/review-fixed-release/release.json` 为 source_sha=568f、source_dirty=false；`/workspace/deck-installed/bin/python -I` 下根模块来自 site-packages，285 个源码包文件逐字节匹配。测试后所有 deck_master 模块均来自该安装目录。
- `installed.log` 首轮为 14 passed、2 failed；这两个失败是本 reviewer 新测试误用 URL 参数 `page_id`（正确为 `page`），未进入编辑器，属于测试脚本错误，日志保留。更正临时脚本后 `installed-draft-corrected.log` 两端 2 passed，ALL_DECK_MODULES_INSTALLED=true。故安装版 16 个独立验证场景均已实际通过，不把最初失败抹掉。
- `followup.log` 的接纳期最初要求特定 EligibilityBlocked，实际更早由 StaleInputContext 安全拒绝；随后改为验证合法拒绝类别并独立检查 task.accept 的 scope_exceeded。`followup2.log` 保留 URL 参数错误；最终 `followup3.log` 为正确脚本结果。

## 范围和限制

本轮重新读了 1493..568f 全部产品代码差异及相关读写调用，不继承作者 fixes.md 的通过结论。没有重读未改变的全部权威 DOCX；沿上轮已完整读取的 1213 行方案和授权边界执行。没有修改仓库、提交、推送、上传、调整权限/配置或运行真实模型。

真实 native initialize、真实 Host 自动交接、真实内容审查修复闭环、视觉像素审查、A/B/C 方法效果与真人理解观察仍为 not_run；本轮模拟 session、mechanism receipt、浏览器 UI 通过不能替代这些验收。暂停后的正式写保护已抽查；撤回、所有并发交错及全部历史数据组合并未穷举。

固定目标检查现已结束，可修复完成文案并在新固定身份下完成最终兼容回归。无待审批操作、无被拒绝环境操作、无不确定外部写入。
