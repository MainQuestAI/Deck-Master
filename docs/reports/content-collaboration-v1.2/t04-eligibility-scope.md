# T04 证据：请求路由、统一 eligibility、范围/预算/晚到控制

本文件按 [TASKS.md](../../specs/deck-master-content-collaboration-v1.2/TASKS.md) §2 模板记录 T04 的实际实现与证据。
它只包含合成 fixture 与仓库内命令结果，不含客户材料、绝对本地路径或生成项目。

```text
Task: T04
Implementation commit / source baseline:
  基线 = origin/main 293579f1（含 T00–T02 全部交付）
  8aaf04a6  feat(eligibility): add the pure eligibility resolver (T04 slice 1)
  e14c1701  feat(eligibility): classify every public entry against one decision (T04 slice 2)
  9e493050  feat(eligibility): enforce one admission decision at every boundary (T04 slice 3)
  7d82ad33  feat(eligibility): isolate requests and bound delegation budgets (T04 slice 4)
  264bfc53  feat(eligibility): keep late results and stop facts honest (T04 slice 5)
  （审查修复见本文“审查修复对照表”；该修复的提交 = 本分支最后一条 fix(eligibility) 提交）
  源基线只读核对：本卡未修改 T00/T01/T02 已冻结的合同、schema 版本或旧项目字节。

Changed paths and resulting behavior:
  新增
    src/deck_master/eligibility.py            统一 eligibility 解释器（纯计算 + guard + describe）
    src/deck_master/eligibility_entries.py    入口清单与机器可检覆盖表
    src/deck_master/collaboration_budget.py   两个预算模板 + delegate 具体化 + credit 幂等
    tests/rebuild/test_eligibility_resolver.py、test_eligibility_entry_coverage.py、
    test_eligibility_enforcement.py、test_scope_and_delegation.py、
    test_budget_templates.py、test_late_results_and_stops.py、
    test_delivery_control_snapshot.py        （共 107 条新测试）
    docs/reports/content-collaboration-v1.2/t04-entry-inventory.md（330 条入口清单）
  修改（接线，不改既有协议语义）
    service.py / tasks.py / changes.py / candidates.py / styles.py / content_ops.py /
    editing.py / pipeline.py / exports.py / handoff.py / stages.py / icons.py /
    candidate_preview.py / visual_styles.py / annotation_service.py / restoration.py /
    collaboration.py / collaboration_migration.py / cli.py / dependency_slices.py /
    collaboration_scope.py / operations.py（加 __public_operation__ 标记）
    tests/rebuild/test_dependency_slices.py、test_collaboration_restore.py（两处 fixture
    按新合同更新，见“失败样例与修复”）

  行为变化要点
    1. 所有 §6.2 边界调用 eligibility.guard(...)（同一判定、同一 reason code 词表）。
    2. accept_result 仍是“先结算后接纳”：结算写入独立 revision，随后才用统一判定决定
       是否接纳；被拒时原稿字节与页集合不变、已发生调用保留为 consumed 事实。
    3. continue 是路由动作：把被拒的派发变成 decision/stop card（needs_input 响应带
       reason_codes / responsible_role / next_action / decision_card），不抛异常、不派发。
    4. 撤回优先于结构判断：绑定指向的授权被撤回时报告 authorization_revoked（不是
       binding_invalid）；任务自己的绑定授权也覆盖它的有界调用槽。
    5. 换请求默认切断旧范围：被替换请求的授权失效（request_superseded），响应返回
       prior_request_disposition / paused_authorizations / affected_tasks；只有新请求
       显式列入 background_request_ids 的旧请求才继续，且其任务绑定视为有效。
    6. 预算：initial_per_page（选定 N、复用 K、首次生成≤N-K、重试 0）、
       edit_rebuild_per_page（必须重画页每页≤1、仅 SVG/notes/编译页 0、范围外页列为
       scope gap）；credit 以 <request_id>:initial|rebuild:<page_id> 记账，换
       operation ID / 重启 / 重复 grant 不刷新已消费 credit；子授权共享父预算根。
    7. 无绑定任务的兜底（审查 P1-1）：受管项目中任何没有 collaboration_binding 的任务，
       其生产/派发与一切写项目状态的生产接纳一律拒绝（decision_needed，missing=task_binding，
       next_action 指向"经协作感知路径重新派发为带绑定的任务"），与协议版本及是否撤回无关；
       已发生调用仍可结算，仅记录审阅观察的 accept（record-only）仍属事实通道。
       binding 写入方是 T03：集成前受管项目的正向接纳测试用合法构造 binding 模拟集成后状态，
       派发路径本身在 binding 落地前停在同一条具体缺口上（见 AC-R04/R05 与对照表）。
    8. 停止事实分开：request pause / authorization revoke / task cancel /
       policy.user_stop / 预算耗尽互不等价；结算、取消、暂存是事实通道，任何停止下都可写。

AC IDs and status:  见下表（逐条给证据；L1 = 合成 fixture + 仓库内命令）

| AC | 状态 | 证据（测试 + 机制） |
|---|---|---|
| AC-R01 | pass at L1 | 解释器：`test_plan_only_stops_before_image_production`、`test_review_only_never_produces`；入口：`test_continue_reports_a_blocked_dispatch_as_a_decision_card`（write_only 请求下 continue 返回 scope_card，`needs_input`，未派发任何 Host 任务）、`test_compose_dispatch_refused_while_paused`、`test_blueprint_dispatch_requires_scope_and_authorization`。生产任务/外部调用数为零由此断言。真实 Q1 会话属 T08。 |
| AC-R02 | pass at L1（路由/控制半边） | `test_delivery_control_snapshot.py`：`test_historical_delivery_entry_consumes_the_current_control`、`test_a_current_withdrawal_stops_a_historical_delivery`、`test_an_old_relaxed_policy_cannot_override_a_current_requirement`、`test_a_current_loosening_is_honored_for_a_historical_snapshot`、`test_restored_scope_is_still_the_current_request_scope`；fidelity_only 不重置问卷（`preproduction_state` 对 `fidelity_only` 返回 required=False，enforcement fixture 即用该 profile）。内容侧复用/冲突检查属 T03/T05。 |
| AC-R03 | partial | 已实现：`review_only` 不生产（`test_review_only_request_refuses_page_import_and_blueprint_dispatch`）、严格只读判定（`test_persistence_none_forbids_project_writes`，`review.strict` 允许且不写项目）、局改只执行授权范围（`test_local_compile_needs_the_output_layer_in_scope`、`test_change_commit_refuses_pages_outside_the_request`）、跨页冲突→scope gap 列表（`test_edit_scope_gaps_are_listed_not_rebuilt`）。未实现：§12 的 `review evaluate --persistence none` 项目外报告入口与报告落盘属 T07；真实源目录 hash 前后比对在 T07 验收中跑。 |
| AC-R04 | pass at L1（口径见下） | 入口清单 330 条（112 接 gate / 218 显式豁免），`test_eligibility_entry_coverage.py` 9 条：未分类新入口直接 fail、旧行失效 fail、子表面最小数量防“发现器坏掉”、写边界必须是 action 而非豁免、§6.2 边界动作全部有直接或显式 via 覆盖；`test_eligibility_enforcement.py` 27 条按边界正/反例；`test_blocked_actions_never_write` 断言拒绝后 document 逐字节不变。覆盖口径（如实）：**分类覆盖**是完整的（每条入口都有归属）；**执行面覆盖**在受管项目上完整，但"带 binding 的正向派发"要等 T03 的 binding 写入方落地——在此之前受管项目在派发/接纳处停在同一具体缺口（decision_needed / missing=task_binding），不会被绕过；正向接纳测试用合法构造 binding 模拟集成后状态。 |
| AC-R05 | pass at L1（真实路径兜底见下） | `test_late_results_and_stops.py` 12 条：① 真实派发路径兜底（审查 P1-1 回归）`test_real_dispatch_without_binding_cannot_be_accepted`（`service.open_host_task` 真实派发→无 binding→接纳被拒、原稿不变、next_action 具体）、`test_real_dispatch_without_binding_refused_even_after_a_revocation`、`test_real_dispatch_without_binding_settles_its_historical_cost_only`（历史 consumed 槽保留为事实，settle/cancel 仍开放、生产接纳仍拒）；② 撤回三轨迹（start 前 / 调用中 / accept 前，绑定任务经协作路径）与 `test_a_revoked_result_is_never_adopted_later`；③ `test_task_cancel_is_not_a_scope_withdrawal`、`test_continue_neither_widens_nor_revives`、`test_restore_does_not_revive_a_withdrawal`。审查者探针 probeA2（真实 generation.v1 全流程：dispatch→start→begin→native settle→revoke→accept）在本修复后不再出现"late result adopted after revoke"。 |
| AC-R06 | partial | 四条准入解释均有正/反例：普通继续 `test_needs_reviewer_until_independent_preproduction_review`（needs_reviewer 且稿件/审阅稿仍可取——拒绝只拦派发）；明确降级 `test_host_self_is_only_accepted_through_the_explicit_override`（且 region 结构要求 override 决定）；已有审阅委派 `test_delegate_covering_the_topic_satisfies_the_decision`；确认稿 fidelity `test_host_self_is_only_accepted_through_the_explicit_override` 同族 + fidelity_only fixture。人类政策保持独立：`test_professional_review_required_is_independent_of_preproduction`、`test_delivery_without_the_human_policy_is_allowed`、`test_readiness_reports_the_delivery_policy_without_raising`。未做：把 needs_reviewer 做成用户可见卡片投影（T07 Studio/Host 展示）；前审任务派发本身属 T03。 |
| AC-R07 | pass at L1 | `test_budget_templates.py` 11 条：`max_external_calls=1` 结算后 remaining=0 仍可接纳（`test_exhausted_budget_accepts_the_last_result_and_refuses_new_calls`）、新 begin 被拒、耗尽≠撤回（`test_withdrawal_refuses_adoption_while_exhaustion_does_not`，撤回拒收且结算仍可）、candidate 采用需 adoption 授权但不耗图像额度（`test_candidate_adoption_needs_adoption_authority_not_image_budget`）、子授权共享父预算（`test_child_grants_share_one_ceiling_instead_of_copying_it`）、无新指令不刷新（`test_repeated_materialization_never_refreshes_a_consumed_credit`）、局改与 text-only 两个分支（`test_edit_rebuild_bounds_each_page_once_and_zero_for_cheap_layers`、`test_text_only_edit_has_no_image_budget`）。 |

Actual commands, environment, inputs and outputs:
  环境：darwin arm64，仓库工作树（分支 impl/t04-eligibility-scope），
  PYTHONPATH=src + 共享 venv 的 Python 3.12，pytest -m 'not render and not browser'。

  1) 全量非浏览器回归（单独运行，无并发测试进程）
     $ cd <worktree> && PYTHONPATH=src <venv>/python -m pytest -q tests/rebuild \
         -m 'not render and not browser'
     → 1545 passed, 455 deselected in 112.60s（本卡最终数字，含审查修复的 8 条回归）
     基线：主工作树 1430 passed（本卡开始前）；本卡新增 115 条 eligibility 测试；
     T01/T02 测试照常运行，不替换任何旧用例的语义（仅两处 fixture 按新合同更新，见下）。

  2) 本卡新增测试（逐文件，最新一次实跑）
     test_eligibility_resolver.py            37 passed（每个 reason code 正/反例 + 无副作用 + 历史快照）
     test_eligibility_entry_coverage.py       9 passed（入口分类/未分类 fail/发现器自检）
     test_eligibility_enforcement.py         27 passed（§6.2 各边界正/反例 + 拒绝后状态 + 渲染严格度一致 + restore 报告型）
     test_scope_and_delegation.py            10 passed（请求隔离/背景清单/授权绑页/具体化/链撤回/replace 如实报告）
     test_budget_templates.py                12 passed（两模板 + 耗尽/撤回 + 共享预算 + credit 幂等 + slot 不外溢）
     test_late_results_and_stops.py          13 passed（真实路径无绑定兜底 + record-only 限观察任务 + 三轨迹 + cancel/continue/user_stop/restore）
     test_delivery_control_snapshot.py        7 passed（历史快照 × 当前控制 + 恢复保留）

  3) 相关既有套件（回归）
     test_collaboration_* + test_dependency_slices + test_delivery_professional_gate +
     test_candidates + test_styles + test_content_ops + test_tasks + test_budget +
     test_export + test_changes → 199 passed（一处 T02 fixture 按新合同更新，见下）

  4) 静态检查
     $ <venv>/python -m ruff check src/deck_master tests/rebuild → All checks passed!
     $ git diff --check → 无输出（无空白错误）

  5) 入口覆盖统计（由 eligibility_entries.coverage_stats() 实跑）
     total 330（gated 112 / exempt 218）；by_surface = service 15 / operations 45 /
     collaboration 16 / cli 158 / http 96；uncovered {} / stale {}；消费 39 个 action。

Evidence layer for each claim:
  * 逻辑层（L1）：上列测试都是合成 fixture（自建 collaboration.v1 项目、真实写路径产生的
    request/decision/authorization/task/allowance 对象），只证明判定与原子边界；不证明内容
    质量、真实 Host、人类身份或听众效果。
  * 人类/身份：`authority_policy=verified_user` 在无适配器时返回
    `authority_channel_unavailable`（`test_authority_channel_unavailable_under_verified_user_policy`）；
    严格人类交付谓词复用 T01 的 `delivery_eligibility.professional_policy`，未注册任何生产
    适配器，正例仍只在 T01 的 synthetic stub 里（L1）。
  * 文件/PPT 层：本卡不产出真实 PPTX/SVG 证据；编译与交付入口只验证“是否消费同一判定”，
    真实文件回读属 T06/T08。

Failing examples and repair performed:
  1. 42 条既有测试红：新增 gate 在 visual_styles.py / stages.py 里引用了未导入的 Store
     （NameError）。→ 补导入（visual_styles 用既有 Store(project) 形态），全绿。
  2. 撤回后的绑定被报成 binding_invalid：任务绑定引用的授权被撤回后，region 里的 ref 变成
     撤回版本，结构门禁先失败。→ task_binding_state 区分 withdrawn，报告
     authorization_revoked（“撤回继续有效”），并新增 `test_begin_after_withdrawal_*`。
  3. 任务自己的授权不覆盖调用槽：grant 只写 dispatch.blueprint 时 reserve/begin 被判
     authority_insufficient。→ 引入 SLOT_ACTIONS：任务绑定的授权同时覆盖它的
     call.begin/generation.dispatch/allowance.allocate/repair 槽（§1.6 同一授权链）。
  4. future_pages 首版过宽：父 delegate 未声明 future_pages 空页集也会放行子授权任意页，
     被 T02 的 `test_sub_authorization_cannot_exceed_parent` 抓住。→ 改为只有显式声明
     `constraints.future_pages={selector:adopted_plan_for_this_request,max_pages}` 且子页数在
     界内才放行，空集仍然是“没有页”，T02 与新增 `test_delegate_materializes_*` 同时绿。
  5. T02 fixture 的两处旧假设（新合同下必须更新，不是放松 gate）：
     - test_dependency_slices：直接页面编辑现在是接纳边界，fixture 的 request 未命名所编辑
       的页/层 → request scope 明确列出 p1/p2 + page_copy。
     - test_collaboration_restore：fixture 先暂停再编辑页面（暂停下新写被正确拒绝）→ 调整为
       先完成编辑再暂停，断言（暂停/撤回/费用/最低 writer 保留）不变。
  6. 全量套件中的 11–12 条 workbench/launcher 服务测试在与其他 pytest 进程并发时超时/失败；
     相关文件集：tests/rebuild/test_workbench_services.py、test_workbench_e2e.py、
     test_studio_integration.py（均为启动分离式本地服务/端口/注册表的用例）。
     单独运行该文件集两次均通过（无遗留 deck-master workbench 进程）。结论：环境/端口竞态，
     不是回归；本卡最终验证单独运行（数字见下），不与其他 pytest 并发。

Preserved state / calls / unaffected pages:
  * `test_blocked_actions_never_write`：拒绝后 document dict 逐字节相同（无新 task、
    allowance、决定对象、current 变化）。
  * `test_accept_refused_out_of_scope_settles_calls_and_keeps_the_draft`：越界结果的接纳被拒，
    原页正文不改，页集合不变，已发生调用结算为 consumed（费用如实）。
  * 撤回三轨迹：start 前撤回不消耗（槽仍 reserved）、调用中撤回把 in_flight 结算为 consumed、
    accept 前撤回保留已结算成本；`test_a_revoked_result_is_never_adopted_later` 重复提交仍不采纳。
  * restore：内容回退，request/撤回/暂停/费用/minimum_writer 保持（T02 已实现 + 本卡
    `test_restore_does_not_revive_a_withdrawal`、`test_restore_to_a_relaxed_snapshot_does_not_restore_its_policy`）。
  * 未受影响页：`test_scope_and_delegation`、`test_budget_templates` 中按页断言
    （p2 的 SVG-only 改动 0 额度、范围外页只列 gap 不重画）。

Scope of this change; next dependent card:
  * 本卡只增加准入判定与执行面 enforcement 的实现与接线；不翻转 create 默认 writer
    （仍是 content-plan.v1），不新增 §12 的 CLI/HTTP collaboration 命令（T07），不派发
    compose.v2 相位任务或前审任务（T03），不做 PPTX 备注（T06），不动四 Skill。
  * enforcement 启用边界（如实记录）：
      - `minimum_writer=collaboration.v1`（或存在 collaboration 区域）的项目：全量 enforcement
        生效，gate 会拒绝（EligibilityBlocked，CLI exit 4 / HTTP 409）。
      - 低于该 writer 的历史项目：本增量保持现行行为；解释器仍计算 `migration_required`
        （`test_legacy_project_keeps_current_behaviour` 锁定 enforcement="shadow" +
        reason_codes 含 migration_required）。该开关尚未对旧项目生效，需要与发布集成步骤
        一起打开。
      - 与 MIGRATION.md §5.3“尚未全部覆盖时不向真实项目启用新 writer 的生产”一致；本卡在
        collaboration.v1 项目上的覆盖是完整的（入口清单机器可检）。
  * 下一卡：T05（初始设计与代表样页）在本卡 gate 上接入 scope/预算模板；
    T07 把 §12 的 CLI/HTTP collaboration API、严格只读审查入口、身份适配器与 Studio 投影
    接到同一 service；T03 提供 compose.v2 相位任务与 binding 写入。

Not run / blocked evidence and concrete next step:
  * not_run：真实 Q1–Q4 Host/用户会话、12 个比较会话、Owner 试用与听众验收（T08）；真实
    PPTX/SVG 文件与备注回读（T06/T08）；安装路径验收（T07）。
  * not_run：`verified_user` 真实受信适配器正例（T07）；当前只有 traceable 路径 + 无通道时
    的诚实阻塞。
  * not_run：严格只读审查的项目外报告落盘与“源目录 hash 前后不变”比对（T07 入口）；
    本卡只提供判定语义与豁免登记。
  * not_run：对旧项目开启 enforcement 的部署步骤（需与 T07 一起；本卡保留 shadow 语义与
    锁定测试）。
  * 下一步：T03 落地 binding/相位派发后，用同一 digest 公式复核 gate 的 binding 校验；
    T07 接入口后本卡的入口清单需新增对应行（覆盖测试会强制）。
```

## 审查修复对照表（REQUEST-CHANGES 后）

| 审查项 | 修复 | 回归测试 |
|---|---|---|
| **P1-1** 撤回后晚到结果经真实派发路径仍被接纳（accept 侧只经 binding 拦截） | `evaluate` 的 binding 缺失分支改为无条件：受管项目中任何无 `collaboration_binding` 的任务，其生产/派发与一切写项目状态的生产接纳一律拒绝（`decision_needed`，`missing=task_binding`，next_action 指向"经协作感知路径重新派发为带绑定的任务"），与协议版本、是否撤回无关；事实通道（`call.settle`/`task.cancel`/staging）与"仅记录审阅观察"的 record-only accept 保持允许（该豁免很窄：只有 review/style_analyze 观察类任务 + 信封仅含 reviews 才成立，生产类任务永不适用）；已结算费用不抹去。绑定存在时维持结构 + digest 时效 + 撤回拦截。 | `test_late_results_and_stops.py::test_real_dispatch_without_binding_cannot_be_accepted`（真实 `open_host_task` 派发→接纳被拒、原稿不变、next_action 具体）、`::test_real_dispatch_without_binding_refused_even_after_a_revocation`、`::test_real_dispatch_without_binding_settles_its_historical_cost_only`、`::test_record_only_acceptance_is_limited_to_observation_tasks`；`test_eligibility_resolver.py::test_binding_absent_task_settles_facts_but_never_produces_or_adopts`（两协议 × 生产/接纳 + 事实通道 + record-only）、`::test_a_bound_task_is_judged_by_its_other_gates` |
| **次生问题（probeE）** replace 的 `affected_tasks` 漏掉无绑定活动任务 | replace 报告把无绑定活动任务列入 `affected_tasks`，并新增 `unbound_tasks[]`（task_id/status/reason=no_collaboration_binding/handling="only settled call facts remain; re-dispatch through the collaboration-aware path"），不夸大覆盖 | `test_scope_and_delegation.py::test_replace_reports_unbound_active_tasks_honestly` |
| **P2-1** 空测试重写（`raises((EligibilityBlocked, Exception))` 等价 `raises(Exception)`） | 改为真实候选采用状态：`create_sample` 项目 + 真实 change-plan trial 派发 + `_stamp_binding`（模拟 T03 盖章）+ 真实 claim/accept 产出 candidate + `candidates.plan`→`adopt`；撤回前 `evaluate` allowed、撤回后 `authorization_revoked`，真实 `adopt` 抛 `EligibilityBlocked`，原稿与 candidate_adoptions 不变 | `test_eligibility_enforcement.py::test_candidate_adoption_refused_after_withdrawal` |
| **P3-1** `render.preview` 两个入口 targets 严格度不一致 | `render.preview`/`compile.svg` spec 声明 `layers=("svg",)`；`candidate_preview.request` 在 gate 前解析候选的 page_id 并传 `layers=["svg"]`（与 `icons.preview` 一致） | `test_eligibility_enforcement.py::test_local_rendering_entries_use_the_same_layer_strictness`（两个入口都拒、带 svg 层都过 gate） |
| **P3-2** `restore` 在 ROUTING_ACTIONS（永不 raise）与清单表述不符 | 清单行/注释改为"reporting-only decision（报告型判定：恢复内容事实、保留当前控制，故当前停止不阻断恢复）"，并注明 T07 的 `persistence=none` 严格只读风险（该声明仍拒绝经此路径的项目写入） | `test_eligibility_enforcement.py::test_restore_is_a_reporting_decision_not_a_veto`（清单措辞 + restore 可执行 + persistence_none 仍拒） |
| **P3-3** SLOT_ACTIONS 让绑定授权覆盖未声明的调用槽 | `_slot_covered_by_binding` 限定为 `spec.external_calls=True` 的调用槽动作，且绑定的授权必须同时命名一个生产动作，否则不覆盖 | `test_budget_templates.py::test_a_bound_authorization_never_widens_beyond_call_slots` |
| **P3-4** 证据文档"41 passed"未点名文件集 | 本文点名 `test_workbench_services.py` + `test_workbench_e2e.py` + `test_studio_integration.py`，并说明并发竞态与单独运行结论 | 文档项（无测试） |
| 证据文档同步 | AC-R05 行按真实路径证据重写；覆盖口径（分类完整 / 执行面在 T03 落地前停在同一缺口）与 T03 依赖如实披露；新增本对照表 | 文档项（无测试） |

修复后仍保留的口径：受管项目的**正向接纳**测试一律携带合法 binding（`_stamp_binding` 模拟 T03 集成后状态）；
派发路径在 binding 落地前停在同一条具体缺口（`decision_needed` / `missing=task_binding`），
集成步骤由 T03 侧 sweep 补齐盖章后可直接跑本卡的回归集。

## 与 T03 的接口点（实现约定，已在本卡代码中固定）

1. **binding digest 公式**（`eligibility.binding_eligibility_digest`，docstring 注明与 T03 一致）：

   ```text
   sha256_bytes(canonical_json_bytes({
       "phase": phase,
       "write_scope": <scope 规范化 JSON：page_ids/layers 排序，manifest/顺序保留>,
       "basis": [按 slice_key 排序的 slice sha256 列表],
   }))
   ```

   `test_binding_digest_formula_is_the_t03_contract` 锁定公式与顺序无关性；T03 的
   compose.v2 派发写 `collaboration_binding.eligibility_digest` 时必须用同一函数（集成时
   统一为这一实现）。

2. **binding 校验方式**（`eligibility.task_binding_state` / `evaluate(context={"task": ...})`）：
   - 携带 binding → 先走 `models.require_task_binding` 结构门禁，再按上式重算 digest 比对，
     并用 `dependency_slices.assess_basis` 检查 `eligibility_basis` 是否仍然当前。
   - 结构失败但原因是绑定的授权被撤回/替换 → 报 `authorization_revoked`（撤回优先）。
   - 无 binding 且任务声明 `collaboration.v1`（或 `*.v2` 协议）→ 生产动作
     `decision_needed`（只允许结算），对应 TASKS T04 第 3 条“按任务协议版本区分”。
   - 无 binding 的旧协议任务 → 不额外拒绝，按 request/authorization/scope 判定。

3. **集成注意**：
   - T03 派发任务时请同时写 `binding.request_id/phase/write_scope/eligibility_basis/
     eligibility_digest`；`budget_key`（`<request_id>:initial|rebuild:<page_id>`）只在有界
     credit 场景需要，本卡的预算检查会按 binding.budget_key 记账。
   - 若 T03 采用不同的 scope 规范化细节（例如新增字段），必须与本文件第 1 条的规范化实现
     同步，否则 `binding_stale` 会误报。
   - 相位 → action 的映射建议：framing/argument → `dispatch.compose`，
     page_copy → `dispatch.compose`/`task.accept`，design/production → `dispatch.blueprint`
     /`style.trial`，delivery → `export.delivery`。这些 action 已在入口清单中登记。
