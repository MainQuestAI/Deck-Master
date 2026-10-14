# 外部联合审查修复轮记录（F01–F06，2026-10-14）

状态：**六项修复全部实现并通过联合回归；等待独立复验与用户合并授权**。
本记录只陈述已验证的事实，不构成任何"已收口/已批准"结论。
审查原文与六项问题的裁决口径见
`output/development-chain-assessment-20261013/sources/pr110-112-external-review.md`（工作区副本）。

## 基线与执行方式

- 审查基线：`main@293579f1`；三个 PR 的受审 head：#110 `54b82c15`、#111 `bcb27cd7`、#112 `43c8ba58`，均为 Open/Draft/未合并。
- 执行顺序完全按审查建议：先在联合树（`integration/t03-t04`）复现（红测试），修复至绿，再按责任回填单卡，最后重新并入联合树核对最终代码树与联合回归一致。
- 全部复现与修复由本会话（Codex 执行环境）在真实 service/store 路径上运行；测试命令：
  `PYTHONPATH=src .venv/bin/python -m pytest -q tests/rebuild -m 'not render and not browser'` + `ruff check src/deck_master tests/rebuild`。
- 禁止事项遵守：未使用 `_stamp_binding` 手工补齐授权冒充真实派发；F01/F05/F06 的证据全部来自真实派发/领取/接纳路径。

## 逐项关闭记录

| 项 | 红测试（先复现） | 修复提交（联合树） | 单卡回填 | 关键语义 |
|---|---|---|---|---|
| F01 | `test_a_real_dispatch_binds_the_covering_authorization` / `test_revoking_the_bound_grant_refuses_the_late_result`（修复前红） | `3b38bce1`（上一会话完成） | 留在 #112（T03 binding 构造 + T04 消费的联合职责） | 派发时解析覆盖授权并精确写入 binding；撤回后晚到结果拒绝采用、调用事实保留 |
| F02 | `test_a_review_delegate_never_replaces_the_preproduction_review`、`test_a_partial_preproduction_failure_keeps_production_blocked`（修复前双红） | `bc749196` | 留在 #112 | `preproduction_state` 不再自建弱判定，改为消费 `content_review.preproduction_status/qualify_for_production`：全部必需单元在当前稿件上被适用 pass 审查覆盖才满足；委派只复用安排审查（AC-R06），永不代替审查结果；无效 fidelity_only 档案按 T03 语义降级。新注册 `preproduction_blocked` code（与合同 `needs_reviewer`＝缺 reviewer 区分），next_action 按状态给具体指引 |
| F03 | `test_a_scoped_page_copy_result_never_deletes_unselected_pages`（修复前：遗漏 p2 被静默接受） | `2a5f8378` | #110 `0cde6ce9` | 接纳侧计算真实 removed 集合；范围不允许成员变化时，遗漏当前页＝未声明删除，拒绝并点名列出；成员变化范围内收缩仍可表达（`test_a_membership_scope_may_express_a_real_deletion` 正例保持通过） |
| F04 | `test_a_batch_request_larger_than_the_remaining_credit_gets_zero`（修复前：count=2 越过剩余 1 次成功） | `e9f96b68` | #111 `f572bd25` | 申请数量随 guard 进入统一预算判定：批量超过绑定授权链剩余额度即 `budget_exhausted`（detail 携带 requested），同一项目锁内、账本变更前拒绝；单次申请、项目总额、unknown 暂停、change-plan 上限不变 |
| F05 | `test_the_input_revision_task_stays_claimable_during_reconciliation`（修复前：协调任务自身领取被拒，死锁） | `0e6a221c` | #111 `bdc63e1f` | 豁免精确限定：`task.start` 的 compose.v2 `input_revision` 任务，其 stamped input digest 等于当前输入且 binding 指向当前 request；其他依赖旧内容的生产仍被 `input_reconciliation_pending` 阻断。`check_host` 接受自己派发的 `compose.v2` 协议。闭环 inputs_update → task_start → accept → alignment=current 全程真实路径 |
| F06 | `test_a_paused_request_gains_no_phase_tasks_through_continue`（修复前：暂停后 continue 仍派发 framing 任务） | `ba334309` | 留在 #112（T03 派发底层 + PR112 衔接） | gate 落在真实写入点 `open_phase_task`：先消费 `dispatch.compose` 再建任务/提交；continue 保持路由合同（拒绝转 needs_input 卡片），显式恢复后下一相位恰好派发一次；speech 之后进入视觉生产被既有 gate 以 scope/authority/前审正确拦截，无旁路任务 |

## 回归证据（本会话实际执行）

| 树 | head | 结果 |
|---|---|---|
| integration/t03-t04（修复中） | `ba334309` | 1638 passed, 455 deselected；ruff clean |
| impl/t03-content-production（回填后） | `0cde6ce9` | 1509 passed, 455 deselected（与 PR110 记录同量级） |
| impl/t04-eligibility-scope（回填后） | `bdc63e1f` | 1545 passed, 455 deselected（与 PR111 记录一致）；ruff clean |
| integration/t03-t04（回填并回后最终 head） | `b36745cb` | 1638 passed, 455 deselected；ruff clean |

`git diff ba334309 b36745cb` 为空：回填并回后的最终联合树与通过联合回归的修复树**逐字节一致**，满足"最终进入 main 的完整代码树就是通过联合回归的那一份"的核对要求。

## 行为语义变化的诚实披露

统一前审判定（F02）使以下先前被弱判定放行的情形改为阻断，属修复预期：

- 声明 `fidelity_only` 但无合法确认稿映射的项目：按 T03 `requirement_state` 降级为 `independent_model_or_human`，生产门禁要求真实前审（此前直接满足）。
- 覆盖审查主题的有效委派不再使前审"已满足"（此前 `via=delegate` 即放行）。
- 无稿件项目的前置审查维度显式报告 `preproduction_blocked`（此前 fidelity_only 夹具静默通过）。

既有测试的相应更新均为语义对齐，未削弱断言：resolver 的两条前审测试改为要求页与完整单元集（含"单条 pass 不够"负例）、host_self 测试改用真实生效的降级决定；两处钉在 builder 裸 `ModelError` 的派发测试改为期望更早的类型化 `decision_needed` 拒绝（§6.2 row 1 方向）。

## 未完成与待授权

1. 三个 PR 仍为 Open/Draft；**合并需要用户重新授权**，建议顺序 #110 → #111 → #112，合并后由 Codex 核对 main 树与 `b36745cb` 一致。
2. 上一轮 PR 描述/评论中"已收口"口径的撤回与更正由后续 PR 更新处理。
3. 审查建议的八条联合回归中，本记录覆盖 F01–F06 对应六条；"旧通过后出现新失败"已并入 F02 联合测试（`test_a_full_pass_qualsifies_production_and_a_new_revision_revokes_it`），"输入更新→协调领取接纳"即 F05 测试。
4. 独立 code-reviewer 复验与 CI 状态确认在推送后进行；CI 结果以 GitHub 工作流实际运行为准。
