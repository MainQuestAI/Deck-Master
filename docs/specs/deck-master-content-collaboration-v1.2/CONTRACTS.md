# 运行控制与协作合同

状态：拟实施规范；本文件中的字段、接口和命令名均为**拟新增或拟修改**，不能据此宣称当前版本已支持。实现基线为 `af9fd7a6b4d08f753d2f16536a03f386384f49d2`。本规范只增加现有 Runtime 的数据与准入责任，不建立第二个工作流引擎。

## 1. 合同边界与默认值

1. 一个项目继续使用一个 `Store`、一个当前 Document 指针、不可变对象 Ref、现有 operation receipt/CAS/调用账本。CLI、Studio、聊天 Host 和四个公开 Skill 只能通过同一 service 修改项目；Markdown/Studio 卡片都是投影。
2. 控制对象只新增 `collaboration_decision.v1` 与 `collaboration_authorization.v1` 两族。Proposal 直接引用 Narrative、ContentPlan、Page 候选、设计提案/recipe、change plan 或交付 manifest；不另建可编辑 proposal 真源。Issue 继续落在内容未决项/Review findings 中，不新建审批平台。
3. 新建项目统一 `workbench.v3`，最低 writer 新增 `collaboration.v1`。无格式参数的 CLI 与 Studio 行为一致。迁移规则见 [MIGRATION.md](MIGRATION.md)。
4. `authority_policy=traceable` 为兼容默认：允许依据明确用户指令或既有委派的、可追溯但未独立核实的 Host 转述推进。此类记录永远标记 `host_attested`，不标记用户身份已验证。该默认保证范围、依赖和撤回按合同执行，**不声称能抵御拥有同等文件/工具权限的恶意 Host**。
5. `authority_policy=verified_user` 为显式严格策略。所需决定/委派必须有可验证用户事件；无适配器时返回 `authority_channel_unavailable`，不得自动降级。`professional_review_required_for_delivery=true` 始终要求人类专业复核，独立模型不能替代。
6. 没有明确执行范围时允许读取材料、分析缺口、提出方向和有界文字草案；不得因此取得任意页面、外部调用、整套制作或正式交付权限。每次外部生成都同时需要有界 authorization 和现有 allowance。
7. 未显式提供 `presentation_mode` 时，已有 `live/default` 只是技术兼容值，不能作为用户选择或口播要求。显式 live 默认口播为 cues。mixed 的 primary_use 必须来自明确指令或有效委派；无依据时提出 read-primary+cues 的推荐，不能自动选定。primary_use 已定后默认 cues，用户明确不要讲稿可 none。verbatim 必须明确要求；read_alone 默认 none。
8. Candidate adoption、业务决定和执行授权是不同事实。采用某张样页不自动等于接受全部视觉维度；接受视觉方案也不自动扩展制作范围。用户一次明确委派可以同时覆盖多个事实，但必须分别记录其覆盖对象。
9. 新论证驱动的 `full_deck` 默认需要前置 `independent_model_or_human` 内容审查。没有该能力时返回 `needs_reviewer` 并可交审阅稿；只有明确的审阅方式降级决定可以改为 host_self。“继续”“你自己定”不自动取消该默认要求。既有明确审阅委派可复用。已确认稿件且不改变主线时只要求 fidelity review；探索/只读请求可以带尚未完成的审查返回。

## 2. Document 中唯一协作区域

拟在 `deck_document.v1` 增加可选 `collaboration`；当 minimum writer 为 `collaboration.v1` 时由语义校验强制存在。不要更改旧快照的字节或补写历史批准。

```text
collaboration:
  schema_version: collaboration.v1
  authority_policy: traceable | verified_user
  quality_profile:
    content_review_requirement: independent_model_or_human | host_self | fidelity_only
    requirement_origin: default_new_argument | confirmed_manuscript | explicit_decision
    override_decision_ref: null | Ref
  request: null |                    # 无新工作请求的迁移初态允许 null
    request_id: stable id
    intent: full_deck | content_only | design_trial | review_only | edit
    content_intent: null | plan_only | write_only | speech_only | content_full
    instruction_evidence: Evidence
    scope: Scope
    paused: false
    pause_reason: null | string
    closed: false
    closed_reason: null | completed | rejected | withdrawn | superseded
    background_request_ids: []
    variant: null | {group_id, variant_id, label, requested_variant_ids}
  decisions: [Ref]
  authorizations: [Ref]
```

`request` 是当前用户工作请求的边界，不是另一套 Task 状态机；历史请求留在不可变 Document 历史中。`blocked`、当前阶段、下一责任、可以继续的动作均派生，不持久化第二份状态。`resume` 是操作，不是另一个 request intent。新请求默认只推进自己；旧请求只有被明确列入 `background_request_ids` 且授权仍有效，才能后台继续。打开“只试样页”或局部修改请求不得借用先前的广泛授权跨出新请求范围。

### 2.1 Scope

```text
Scope:
  subject: deck | pages | external_artifact
  page_ids: []                       # 空数组恒指没有页面，绝不表示全部
  page_manifest_ref: null | Ref      # deck 生产必须绑定固定页集合/页序
  external_artifact_ref: null | Ref
  layers: [narrative, plan, page_copy, speech, design, blueprint, svg, review, output]
  allow_page_membership_change: false
  allow_page_order_change: false
  purpose: exploratory | review | working | delivery
```

页面用稳定 `page_id`，不能用“第 5 页”作为授权主键。UI 可以显示页码，但提交前必须解析到指定版本的 ID/Ref。局部改稿若需要增删页或改主线，先返回影响说明；不能把变化偷偷塞入 page-copy patch。完整生产的 page manifest 是对应 ContentPlan 的冻结投影；改变成员、页序或覆盖边界时重新匹配委派或取得新范围。

## 3. 决定、委派与执行授权

### 3.1 Decision 对象

```text
schema_version: collaboration_decision.v1
decision_id: stable id
project_id: id
request_id: id
topic: direction | manuscript | speech | style | tradeoff | delivery_acceptance | policy
subject_refs: [ProposalRef]
scope: Scope
value: selected option / accepted dimensions / explicit constraint
disposition: accepted | rejected | deferred
authority_mode: direct_user | delegated | host_proposal | system_default | imported_unknown
evidence: Evidence
delegation_ref: null | Ref
basis: [DependencySlice]
status: active | withdrawn | superseded | invalidated
replaces: null | Ref
invalidated_by: null | operation id
created_at: timestamp
```

`direct_user` 表达所声称的决定来源，身份可信程度只由 `evidence.assurance` 决定；不能从名称直接推出已验证。`host_proposal`、`system_default`、`imported_unknown` 不能满足 required decision。`delegated` 必须可追溯到仍有效、覆盖该 topic 与 scope 的授权链。`rejected/deferred` 也是应复用的业务事实：同一提案未发生相关变化时，不能反复生成“请确认”卡片。

`ProposalRef={artifact_kind, artifact_ref, projection}`。`projection` 只能选中央注册的切片，如 `direction`、`page_roles`、`visible_copy`、`style.palette`、`style.density`；不能接受 Host 自定义任意 JSONPath。用户只认可配色时，决定必须绑定 `style.palette`，不绑定整个 recipe 的所有含义。

### 3.2 Authorization 对象

```text
schema_version: collaboration_authorization.v1
authorization_id: stable id
project_id: id
request_id: id
mode: execute | delegate
actions: [named service action]
scope: Scope
decision_refs: [Ref]
delegated_topics: []
constraints: object                 # 明确页数/风格/密度/交付等边界
max_external_calls: integer >= 0
max_candidate_count: integer >= 0
budget_template: null | initial_per_page | edit_rebuild_per_page | explicit
budget_parent_ref: null | Ref       # 数字额度共享链，与业务委派链分开
budget_key: null | stable key
adoption_policy: candidate_only | within_scope
delivery_binding: none | process_delegation | exact_artifact
evidence: Evidence
basis: [DependencySlice]
parent_authorization_ref: null | Ref
replaces: null | Ref
status: active | paused | revoked | superseded | invalidated
expires_at: null | timestamp
stop_conditions: [named condition]
created_at: timestamp
```

所有执行授权的调用上限必须是整数，不能以 null 表示无限；缺省为 0。既有项目总调用上限仍可为 null，它不免除本次授权的上限。授权额度和 Task allowance 分别检查，实际调用事实只记在已有账本，不建立第二份费用账本。成功、失败、未知调用如何占额继续遵守现有调用协议；重试不是免费新增授权。

普通“做全套”不要求用户先说出调用次数。明确覆盖整套制作的请求可以使用 §3.4 的 initial_per_page 规则，在计划固定后自动生成有界执行预算，向用户展示计算结果但不重复索取同一制作许可。缺省 0 的含义是尚未具体化的授权不允许直接调用，不能据此把正常全套路径永久卡在额外预算问题上。

`mode=delegate` 可在提案尚未出现时授权 Host 在明确约束内做决定，但不能预先声称用户批准未来字节。Runtime 将委派具体化为绑定当前 artifact/scope 的 `execute` 子授权；子授权范围、topic 和证据等级不能超过父委派。数额型执行预算通过 budget_parent_ref 共享；多个子授权共同消耗同一个预算根，不能每个复制一份上限。用户已明确委派的有效事项不重复询问。

`max_candidate_count` 对一个已约定的 1 页或 2 页样页请求可以直接覆盖全部约定样页，不要求第一张接受后才生成第二张。默认 `candidate_only`；这些候选产生后不会自动更新当前 Page/blueprint。若用户另有有效采用委派，可以在该委派覆盖的维度与范围内采用，并记录 `authority_mode=delegated`。

`delivery_binding=process_delegation` 表示“满足这些要求后交付最终文件”的先行委派，最终 manifest 记录实际文件 hash 与授权链；不能标注为用户看过该文件。只有 `exact_artifact` 要求用户决定绑定最终文件 hash。不得无条件把这两种语义合并为交付前再次点击批准。

### 3.3 记录不可变，生效状态可解释

改变决定/授权写一个新对象，通过 `replaces` 或同一授权身份的新版本挂入当前 Document；原记录保留。状态变更必须附操作收据。有效性同时要求：当前控制状态仍引用该身份的有效版本、依赖切片匹配、授权链未暂停/撤回/失效，且请求未暂停/结束。业务否决不能由再运行 `continue` 自动清除。

`budget_state=available/exhausted/unknown` 从已有调用账本派生，不是撤回状态。余额只约束新增 reserve/子授权占额；begin 验证自己的已预留 slot 仍有效，不要求为同一个 slot 再剩余一次额度。最后一份合法调用结算后即使 remaining=0，其结果仍可接纳、范围内收尾仍可继续；额外调用被拒绝。采用已有 candidate 必须有 adoption 权限，但不再消耗 image-call 额度。candidate 数额同理：上限约束新增候选/候选槽，已经合法产生的最后一个候选不因计数达到上限而失去展示/采用资格。

零调用正文纠正只免除视觉生产前审条件，不免除当前请求范围、候选数量或实际绑定授权的有效性。新派发与方法重签均从已验证的 change action 推导相同页面、写层、候选数和调用上限，不能凭 Task 的 trial/content 标签取得例外。允许无需执行授权的只读审查 Task 保持 `authorization_ref=null`；已经绑定授权的 Task 则不能因零调用、另有一份有效 grant 或重新冻结方法，复活已撤回、过期、失效或缺证的原授权及其子链。缺证/失效与用户明确撤回分别报告，实际调用结算和精确成功回放仍遵循原事实通道。

### 3.4 全套制作的默认预算与未来页集合

1. 尚无 Plan 时，delegate 的 Scope.page_ids=[] 恒是无实际目标页。父委派可另在 constraints 声明 `future_pages={selector:adopted_plan_for_this_request, max_pages:integer|null, max_pages_basis:provided|delegated|pending}`，只授予按本请求规划/提出页数的领域权限。它不是通配全部页面，也不能直接派发 blueprint。max_pages 未定时必须先得到符合已有页数委派/方向决定的有限 page budget；没有这种依据就展示具体页数取舍，不能物化生产授权。
2. 有效方向/页数决定或委派选出 fixed Plan 后，Runtime 验证其 page_order 唯一、数量不超过有效有限预算、来源和内容资格当前；把 future selector 具体化为本次真实 page_ids/Plan Ref。此时才创建 execute 授权，page_ids 不再为空。范围匹配使用这个明确定义的 selector 规则，不用“空集是全集”捷径，也不把合法未来委派永远判为空集。
3. 请求证据已明确覆盖整套制作且未规定数字额度时，`budget_template=initial_per_page`：对当前约定页集合中尚无可合法复用 blueprint 的页，每页最多 1 次首次图像调用。已有获准样页/原图符合当前稿件与 recipe 时复用，不重复计。样页调用只覆盖明确约定的选页/数量；它们自己的 trial 预算不能扩成全套预算。
4. Runtime 把上述计算物化为唯一 execution budget root，`max_external_calls=需首次图像的页数`；为该请求每个稳定 page_id 记录 `budget_key=<request_id>:initial:<page_id>` 的唯一首次 credit。credit 绑定现有 Task allowance 元数据，实际消耗仍由现有账本计算。重复 grant、重启、重新提交 Plan、换 operation ID 不会刷新已消费的相同 credit。
5. 委派父对象的 max_external_calls=0 表示它不能直接调用；它通过 initial_per_page 模板生成一次有限预算根，不参加该数字执行链的零额度求交。每个实际 Task 连接其 execute 授权与 budget_parent_ref；authority 链撤回仍会撤回其所有派生预算/任务。服务校验一个 authority 只能为同一 credit 物化一次，子授权只能分享现有数字 budget root。
6. 数字预算卡展示“选定 N 页，复用 K 页，首次生成最多 N-K 次；已授权样页单独列出；额外重试为 0”。这只具体化已有制作指令，不构成额外用户审批。若用户明确给出较小总额度，则以更严格限额为准并展示冲突取舍。
7. 初次图像失败、同页重画、样页追加变体、已用首次 credit 后内容修改导致再生成，均不能再套一次 initial_per_page。必须由原委派明确覆盖的额外额度或新的明确增额覆盖；不自动重试。合法新增页须有范围变化决定/委派匹配后获得新页 credit，不能换旧 page_id 来重置额度。删除/重建页通过 derivation 映射识别其非首次来源。

该规则只约束图像调用次数，不宣称这些次数等于货币成本。已有全局金额/次数约束及 unknown-call 停顿继续优先。

### 3.5 局部修改与同步可用图稿的预算

用户明确要求“修改这几页并给可用图稿/PPT”或“同步最终输出”时，当前 edit 请求可用 `edit_rebuild_per_page`，不要求用户另报调用次数。Runtime 先根据具体 change plan、写集合及实际下游依赖，列出已授权范围内必须重新生成 blueprint 的页面，每页最多 1 次；仅需改 SVG/notes/重新编译的页面额度为 0。先展示“受影响页面、必须重画页、复用页、首次重建上限、重试 0”的预算/影响卡；它具体化已有同步输出指令，不重复请求相同制作许可。

credit 为 `<request_id>:rebuild:<page_id>`，由该次明确修改请求的实际来源绑定。任务/operation ID、Plan 版本、重新运行影响分析或重新授权不刷新已消费 credit。失败重试/额外变体仍需原有明确额外预算或新授权。必须修改但超出已授权 page_ids/layers 的页面先列为 scope gap，不能以“依赖更新”为名全局重做。

只要求改字、提供稿件、讨论修改建议、speaker-only 或严格只读审查，不具备“制作可用图稿”的授权，不启用此模板，也不隐含图像调用。真实的新用户修改请求可以有新的有界 credit；把同一次请求重新创建一个 request_id 不能冒充新请求，见 §12 的来源去重规则。

## 4. 身份证据与 Host 的真实边界

```text
Evidence:
  kind: user_event | host_attested_instruction | approved_document | delegated | imported_unknown
  assurance: verified_user | host_attested | unverified
  source_ref: Ref
  source_locator: null | provider message/event locator
  actor_id: null | actor identifier
  transport_receipt_ref: null | Ref
  presentation_ref: null | Ref
```

`source_ref` 固定来源文本、文档或事件内容，保证后续可读和可核对；hash 只证明记录未变化，不能证明来源真实。用户原话的引用、对其含义的解释、已展示的提案投影必须能分别查看。敏感原文按原项目访问边界保存，UI 不强迫公开无关对话。

| 通道 | 默认有效证据 | 不能据此声称的事实 |
|---|---|---|
| 聊天 Host 转录用户原话/消息 ID | `host_attested_instruction + host_attested`；记录解释和范围 | 消息 ID、原文、用户身份已由 Runtime 验证 |
| Host 执行 CLI `decision record` 或提交 HTTP JSON | 与该 Host 同一信任等级 | CLI/HTTP/`actor=user` 本身是用户在操作 |
| 普通本地 Studio 按钮 | 可记录具体 artifact、选项和事件；没有独立身份通道时仍为 host_attested | UI 点击必定来自人类；本地登录态必定隔离于自动化 Host |
| 平台提供的独立用户动作适配器 | 验证成功的 `user_event + verified_user` | 未验证通道具有同等保证 |
| 外部已确认文档 | 内容/字节可核对；无签名或受信事件时为 unverified/host_attested | 文档名含“终稿”即证明某人已批准 |

`verified_user` 只能由 service 的受信 adapter context 计算，不能作为普通输入参数接受。适配器至少验证：签发方和签名/受信传输、project/request、actor、decision/action、提案或授权范围 digest、展示投影 digest、事件时间/有效期、nonce/event_id 防重放。受信密钥/用户动作能力必须不暴露给同一 Host；若做不到，能力声明必须降为 host_attested。TTY、弹窗、二次调用、截图、哈希、同一个代理提交结构化参数均不创造身份隔离。

兼容策略允许明确的 Host 转述用于正常协作，UI 必须显示“依据记录的用户指令；由 Host 转述，未独立核实”。这是公开的信任选择，不是隐蔽的安全豁免。对 verified_user、人类复核或明确指定身份的要求，无可用通道时必须阻塞该要求对应的动作；仍可输出允许的草案和具体待决定卡片。不得为了继续生产自动修改 authority policy。

实施必须先提供只读 capability 描述：`verified_user_events`、`independent_review_receipts`、`human_review_receipts`，未知时全部为 false；另返回适配器版本与可验证证据种类。每种 true 必须由“合法事件通过、同 Host 伪造 payload 被拒绝、跨提案重放被拒绝”的契约用例支持。没有可用适配器可以先实现明确的 blocked 行为和 traceable 路径，但不能将严格身份路径标为完成或通过验收。

## 5. Request intent 与 Task kind 正交

保留现有 `compose/blueprint/reconstruct/review/repair/style_analyze` 执行 kind，不用 `human-decision/review/production` 单枚举同时表达执行者和权力。

拟给新 Task 增加 `collaboration_binding`：

```text
request_id
phase: framing | argument | page_copy | speech | design | production | review | delivery
executor_type: runtime | host | external_reviewer
authorization_ref: null | Ref
decision_refs: [Ref]
write_scope: Scope
adoption_policy: proposal_only | candidate_only | within_scope
eligibility_basis: [DependencySlice]
eligibility_digest: sha256
```

`decision_requirement` 和是否可自动推进由 Runtime 依据 phase/action 派生，Host 不能靠提交 `none` 绕过。等待用户不是派给 Host 的生产任务；`continue` 返回带产物的 decision card。`review_only` 可以写审阅记录与其证据，不可以写 Page、design、生产 artifact 或启动返修。审查者写回 Review 仍须真实标明 Host 自审/独立模型/人类。

这里“可以写审阅记录”仅适用于用户授权在项目内保存审查结果的场景。用户明确“严格只读，不改项目”时必须使用 `persistence=none` 路径：从固定原项目/外部文件只读快照评价，报告和必要的隔离渲染副本输出到项目外指定位置；不为记录 request、Review、日志、缓存或 receipt 修改源项目 current，也不创建完整生产项目。该请求的分类/eligibility 只存在于调用上下文中。报告用源文件/快照 hash 绑定证据，不假装已经导入 Store。随后用户要求保存到项目时，才通过独立 import 操作把报告转换为有来源边界的 Review；这不会追认此前未发生的用户批准。

| 当前请求 | 可自动推进到的边界 | 禁止自动跨越 |
|---|---|---|
| `content_only/plan_only` | 材料读取、Brief/Narrative/Plan 提案与具体疑问 | 逐页完整制作、图像、整套 PPT |
| `content_only/write_only` | 复用有效方向或已确认稿件映射，形成约定上屏稿 | 重新定义主线、未要求的口播和视觉生产 |
| `content_only/speech_only` | 依据固定 Page/argument 写 cues 或明确要求的 verbatim | 改动上屏稿或重排页面 |
| `design_trial` | 生成范围内的 1–2 张约定样页、比较与局限说明 | 自动扩为整套、把候选采用当整套授权 |
| `review_only` | 指定证据读取、评价、可执行 findings | 自动生产或修复 |
| `edit` | 明确修改对象与依赖内返修、范围内复核 | 未授权增删页、全局改风格或主线 |
| `full_deck` | 在有效决定/委派与范围内持续制作和检查 | 新的关键取舍、范围扩张、未满足的严格复核 |

## 6. 统一 Eligibility Resolver

拟新增 `eligibility.evaluate(store, artifact_snapshot, control_snapshot, action, context)`，为无副作用计算。`control_snapshot` 对正式动作恒取当前项目 head；`artifact_snapshot` 可以是用户选择的历史版本。返回：

```text
allowed
action
scope
required_artifact_refs
required_decision_topics
reason_codes
responsible_role
next_action
decision_card_ref_or_projection
dependency_slices
eligibility_digest
authority_assurance
```

reason codes 至少包含 `request_paused`、`scope_exceeded`、`decision_needed`、`authority_insufficient`、`authority_channel_unavailable`、`basis_stale`、`authorization_revoked`、`budget_exhausted`、`input_reconciliation_pending`、`professional_review_required`、`migration_required`。阻塞返回具体缺失产物/取舍/下一责任，不能只返回“请确认”。

缺少适用的前置内容 reviewer 另返回 `needs_reviewer`。内容独立审查要求与最终人类专业复核是两个 policy 维度；满足前者不消除后者。`fidelity_only` 只有合法的已确认稿件映射且本次授权不修改主线时成立，不是可以手工选择的免审开关。

### 6.1 校验次序与原子边界

所有新写操作复用现有 operation ID、payload digest、Store lock 和 CAS，按以下顺序：

1. 校验输入形状、路径、项目身份；同一 operation ID 已提交时回放原收据，不同 payload 冲突。回放不再次生成、采用或授予权限。
2. 锁内加载当前 Document 与 writer 边界，固定目标 artifact snapshot，检查用户选择的 base revision/CAS。
3. 从受信 context 解析证据能力；普通参数不得提升 assurance。校验 request 与操作 target、实际 write slots。
4. 重算所需决定/授权及依赖切片；检查暂停、撤回、范围、必要质量产物和当前输入一致性。
5. 外部调用还需原有 allowance/unknown-call/项目总额检查及授权链预算检查。任务已领取或额度已 reserve 不意味着仍可 begin。
6. 校验拟写对象及完整写集合，不准信封实际写集合大于授权/任务写集合。把操作结果、控制变更和业务对象在同一提交中绑定。
7. 提交前在同一锁/CAS 边界复查依赖与有效授权，原子移动 current 指针；索引是可重建缓存。

`accept_result` 的例外顺序：对真实调用事实继续采用现有先结算后接纳协议；晚到/撤回/过期可以拒绝 artifact adoption，但不得抹去消耗。结算接口不要求仍有效的生产授权，因为它记录已发生事实；它不得同时发布新 Page/blueprint。

### 6.2 必须消费同一判定的入口

| 操作层 | 必须覆盖的入口/落点 |
|---|---|
| 创建与路由 | `service.create/import_draft/continue_project/open_compose_task/open_host_task/open_blueprint_task` |
| 执行与费用 | `task_start`、allowance allocate/repair、`call_begin`、生成请求派发 |
| 接纳 | `accept_result`、Page/asset/design 导入更新、直接页面编辑 |
| 候选/改变 | changes plan/commit、candidate select/adopt、style trial/expand、content operations |
| 本地生产 | SVG/preview/PPT compile 与 repair；无外部费用也不代表可越过请求范围 |
| 交付 | exports purpose=delivery、handoff delivery、final-readiness、Studio 交付动作 |
| 历史与策略 | restore、authority/policy 更新、历史 revision 的 delivery |

plan/describe/read-only eligibility 可以没有执行授权；commit/start/begin/adopt 必须重算，不能消费早先 `allowed=true` 当长期通行证。实施时由 Codex 枚举全部 `operations.public`、CLI 子命令及 HTTP 路由，对此表补齐遗漏；不能只给 `continue` 加 gate。

### 6.3 最小业务退出条件

* 方向进入写作：当前 audience/任务目标/主张或讲解任务/证据边界/约束冲突有可读产物；必要决定已接受或有效委派；明确 blocker 已解决。合法已确认稿件可用 imported mapping 进入，不伪造 Narrative confirmed。
* 进入真实样页/范围生产：约定范围的 Page 上屏稿完整，页职责与论证映射当前；该范围所需 cues/verbatim 与页面对应；适用内容审阅对阻断问题已给具体处理。Runtime 检查这些记录与版本存在，不声称机器已证明论证质量。论证阶段的 `design.feasibility`、文字线框和密度取舍可以读取未确认的候选内容先行进行，外部生成额度为 0；这些探索不要求先完成整套稿，不构成样页或正式生产依据。只试样页请求可对固定候选稿做有界探索，但未达到前置内容审查要求时不能扩为正式全套。
* 样页进入范围生产：当前 design proposal/recipe 及对应维度决定适用；代表页覆盖足够或存在明确范围内的接受风险/复用模板委派；有固定页集合与额度。样页是否选中只是输入之一。
* 完成请求：Scope 内约定产物与检查完成；不得因项目还有别的缺页就自动扩展当前请求。

前置内容审阅复用 Review 存储，拟增加 `review_stage=preproduction`，绑定当前 Narrative/Plan/Page 稿件及适用来源依赖。`independent_model_or_human` 需要不同于作者的实际模型执行，或有依据的人类评阅；模型执行必须有受信运行适配器可核对的独立执行收据、固定被审产物与只写 Review 的任务范围，不能靠 Host 自填第二个 reviewer 名称/随机 execution_ref 冒充。能力不存在时不得伪造收据。用户明确接受 host_self 降级的决定应绑定本次审阅范围和原因，投影继续显示其实际证据等级；该降级不影响 `professional_review_required_for_delivery=true`。

## 7. 精确依赖、失效与恢复

不得把整个 `collaboration` 或其全局 hash 直接加入 `content_identity`，否则无关决定会使全部任务过期。保留当前内容 freshness，并额外校验 `eligibility_basis`。

```text
DependencySlice:
  kind: task_fact | artifact | source | decision | authorization | policy
  identity: registered semantic key
  projection: registered projection name
  ref: null | Ref
  sha256: digest of canonical semantic projection
```

projection 与每类 action 的必读集合由 Runtime 中央注册；Host 不能遗漏必读项。采用现有 `canonical_json_bytes` 的排序键/UTF-8/禁止 NaN 规则。无序 page_id/Ref 集合排序；页序本身保留顺序；时间戳、展示名、文件路径、任务领取状态不混入业务切片。artifact 内容使用固定 Ref 的 hash，source 沿用实际原始/提取内容和使用语义；来源改名不使论证失效。

| 变化 | 必须失效/重评估 | 默认保留 |
|---|---|---|
| 受众、沟通目标或核心主张变更 | 方向决定、相关论证/页职责、内容审阅及由其导出的生产资格 | 已记录事实、调用成本、无关品牌 palette 决定 |
| 证据数值/来源限制变更 | 引用该证据的 argument/Page、相关审阅与产物 | 无依赖的页面和视觉维度 |
| Page P5 局部措辞/备注变更 | P5 对应 copy/speech/排版与其下游，包含该页的整套输出；有邻接过渡的页也纳入 | 无关 Page、全局配色；不能全项目强制重新访谈 |
| 页序/成员变更 | page-role/order 映射、跨页过渡、全稿时间、输出；范围 manifest 重匹配 | 不依赖页序的固定事实 |
| palette 变更 | 依赖配色的样页和生产 artifact | 内容方向、未变化的稿件 |
| density/layout 变更 | 该视觉维度认可、相关样页覆盖和布局 | 单独已认可的 palette |
| 暂停/撤回授权 | 该授权链未开始调用与未采用结果；晚到结果不采用 | 真实成本、历史产物、其他仍有效请求（需明确后台权限） |

`eligibility_digest` 是 action、scope 与所需切片的 canonical hash，不是授权令牌。接纳时仍根据当前控制状态判断授权是否有效。相同产物 hash 不能使已撤回的授权自动复活。

### 7.1 停顿、拒绝、撤回和晚到

* 暂停 request：不再派发/开始/采用其生产任务，可继续读取、展示、取消和结算已发生调用；恢复须有明确 resume 指令并重新判定。不得把“继续”解释成扩大原范围。
* 拒绝 proposal：保存被拒绝的具体版本/维度与原因；其子授权不成立。允许范围内重新提出实质不同方案；重复原提案不产生新的用户询问。
* 撤回 authorization：终止该授权及其子链的新动作；reserved 未执行额度按原协议释放；in-flight 尝试可取消但不能保证提供方撤销成功，最终只结算事实并隔离结果。
* 单个 task cancel 保持其原语义，不能冒充项目撤回。CLI/UI 必须明确区分“取消此任务”“暂停本次请求”“撤回此范围”；用户发出“别再做了”时默认暂停当前请求，而非只取消一个 task 后被 continue 重建。
* 已完成收据重放只返回历史成功事实；当前 delivery/下一动作需重新判定，不得因为回放旧 success 自动继续或宣布当前已验收。
* 精确文件交付读取来源请求在当前已提交历史中的最新状态，并同时遵守适用的当前请求控制。只有 `closed_reason=completed` 可保留该固定文件的交付资格；暂停、拒绝或撤回不能被旧 artifact 快照中的开放状态覆盖。顺序切换到另一变体本身不撤回已经授权的固定文件，但不扩大为该变体的新文件权限。
* restore 只恢复内容/视觉/产物事实，保留当前 request、decision/auth 状态、停止策略、费用与操作历史。旧内容与当前受众不匹配时显示 input reconciliation，而不自动恢复旧用户意图。

## 8. 精确交付谓词

建立一个 `delivery_eligibility` 供 exports、handoff、final-readiness、Studio 使用。三类状态分别展示：engineering checks、collaboration/scope、required professional evidence；不可压成一个含义不明的 pass。

正式交付的必要条件：

```text
delivery_allowed =
  selected_output_exists_and_matches_selected_snapshot
  AND input_alignment_is_current
  AND all_required_engineering_checks_pass
  AND no_open_blocking_findings
  AND current_control_authorizes_this_delivery_scope
  AND required_business_decisions_are_current_or_delegated
  AND required_professional_evidence_is_satisfied
```

当 `professional_review_required_for_delivery=true`：

```text
professional_satisfied = exists applicable effective review R:
  R.kind == professional_use
  AND R.review_stage == final
  AND R.status == pass
  AND R.reviewer.type in {human_internal, human_external}
  AND human_identity_and_review_evidence_verified(R)
  AND R.subjects binds exact selected PPTX plus policy-required supporting artifacts
  AND required_dependency_set(R) is complete and current
  AND R has substantive observations and evidence for the requested review scope
  AND R is not stale, superseded or replaced
  AND no unresolved applicable must-fix / required judgment remains
```

`all([])` 不构成依赖完整性。由 Runtime 按 review kind/stage 生成最小必需依赖集合再验证，不能接受提交者空数组。只有 `pass` 生效，`not_evaluated/needs_review/not_applicable` 均不能满足强制人类复核。任意 kind 的 human Review、`professional_use` 的 host_self、独立模型 pass 均不满足。一个较早 pass 不能掩盖较新的有效 fail/未关闭问题。不要把 `validate_independence()` 的返回值直接等同于 human 身份。

人类证据需受信人工评阅事件或可核实外部报告及其身份/固定文件绑定；单纯 `reviewer.id="human"`、字符串 execution_ref 或 Host 上传的自称人类报告不能升级。若只能保存 Host 转述报告，显示其事实但强制人类谓词仍不满足。人类身份验证也不自动证明行业资质；要求特定专业资质/评阅者时应由 policy 指定并核对。

默认 false 保持其含义：可以在满足其他要求时交付，不声称已有人类专业背书。独立模型要求可作为单独明确 policy，不能反向替换人类要求。

review/working/engineering 导出仍可用于用户查看允许的候选，但 manifest/presentation 必须保持 purpose 和实际证据等级；不得从该入口投影为正式交付就绪。历史版本交付同时读取“选中快照的 artifact”与“当前 head 的控制/撤回/策略”，不允许旧 policy 绕过当前撤回。

## 9. 拟新增接口清单与不变量

以下是设计签名，不是现有可运行命令：

```text
collaboration.describe(project, revision=None)
collaboration.record_decision(project, input, base_revision, operation_id, adapter_context)
collaboration.grant(project, input, base_revision, operation_id, adapter_context)
collaboration.pause_request / resume_request / revoke_authorization(...)
eligibility.describe(project, action, targets, revision=None)
```

CLI/HTTP 只是这些 service 的适配器；`adapter_context` 来自实际传输集成，不能暴露成 `--verified-user` 或 JSON 中可自选的 assurance。返回数据包含操作收据、决定/授权 Ref、适用范围、实际证据等级和下一责任。

必须用正式 service/CLI/HTTP 路径验证以下不变量：

1. 单个模糊提示不能借默认样式/空决定直接派发全套图像；可生成有界提案。
2. 同一已有效委派的决定不重复询问；无意义确认数不能通过人为拆卡增加。
3. 1–2 张已约定样页都可制作，完成后停在该范围；候选选择不扩页、不复制预算。
4. `review_only` 提交任何 Page/blueprint 修改都被拒绝，当前文件保持原样。
5. 受众改变即使 Page 字节不变也使相关生产资格失效；不相关措辞修改不使全局 palette 决定失效。
6. reserve 后撤回，begin 被拒绝；in-flight 后撤回，accept 只保留费用事实；restore 不复活 grant。
7. 所有正式交付入口对相同 artifact/current-control 组合返回相同判定与原因。
8. 人类政策矩阵包含 host_self/pass、independent_host/pass、human/not_evaluated、human/pass 旧文件、缺依赖、伪造事件、有效真实人类/pass 正例；测试 fixture 显式声明身份，不再用 seed 名称暗示 human。
9. 新 writer 项目经旧 CLI/旧 Runtime 不可写；旧项目不得由选择 legacy 格式避开准入。
10. 身份未验证时如实降级；schema pass、用户认可、独立模型、工程通过不互相替代。
11. 单次授权 max_external_calls=1 时，reserve→begin→settle→accept 成功；新的 reserve/未获预留的 begin 失败。达到 max_candidate_count 后能查看并在有采用权限时采用最后候选，不能创建第 N+1 个；子授权不能复制父级额度。

## 10. 基线实现落点

以下是固定基线的实际依据，实施与运行测试均**需要 Codex 核验**：

* [Document 与 writer 校验](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/models.py#L262-L310)：保留 rank，新增 writer 并修复手写枚举遗漏；[当前 task/policy](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/models.py#L567-L604)。
* [现有 Store 原子提交](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/store.py#L306-L378) 与 [operation receipt](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/operations.py#L103-L145)：复用，不另建权限事件数据库。
* [当前 continue](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/service.py#L715-L775)、[task start/cancel](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/service.py#L1738-L1787)：补请求边界和动作判定。
* [现有精细任务 freshness](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/tasks.py#L343-L397)、[结算后接纳](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/tasks.py#L915-L1065)、[调用额度](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/tasks.py#L1335-L1365)：增加授权切片与链预算，不破坏已有事实账本。
* [restore 保留事实](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/editing.py#L383-L404)：同样保留当前 collaboration。
* [错误的 professional gate](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/exports.py#L106-L155)、[handoff 的工程投影](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/handoff.py#L58-L93)：合并消费统一判定，不让任何 human kind 或非 fail 状态放行。

## 11. 产物对象与结果协议

本节冻结最小可实施的数据责任，不把 schema 有字段等同于内容方法成立；写作方法、完整样例和评价锚点仍是对应实现项的验收输入。所有对象使用现有 `Ref={path,sha256}`，只有真正存在于 Store 的不可变对象可被引用；不同 schema 由注册表按 `schema_version` 分发校验。

### 11.1 Narrative：语义与论证的唯一真源

拟新增 `narrative.v1`，Document 增加 `narrative: null | Ref`。Artifact 本身不保存 confirmed 布尔值，是否采用/授权取决于 Decision。当前已选语义指向 Document.narrative；未采用提案保存在相应 Task.result_refs 和 operation result 中，不挤掉当前指针。

```text
schema_version: narrative.v1
narrative_id, version, project_id
origin: host_composed | user_imported | user_edited
maturity: framing | argument
input_basis: [DependencySlice]
communication_job:
  mode: explain | train | report | decide | persuade | mixed
  audience_fact_key: task.audience
  audience_question: string
  desired_outcome: string
  observable_success: string
  use_mode: live | read_alone | mixed | undecided
  primary_use: live | read_alone | null
central_node_id: null | node id
nodes: [
  node_id,
  role: claim | evidence | reasoning | qualification | objection | recommendation | explanation | example,
  statement,
  authority: reported_fact | inference | calculation | recommendation | target | hypothesis | instruction,
  source_links: [{source_id, source_version, locator}],
  qualification_node_ids: [node id],
  unresolved_issue_ids: [issue id]
]
edges: [{from_node_id, to_node_id,
  relation: supports | qualifies | challenges | explains | prerequisite | leads_to | illustrates}]
issues: [{issue_id, question, impact: blocker | needs_judgment | advisory,
  affected_node_ids, resolution: open | resolved | accepted_limit,
  resolution_ref: null | Ref}]
alternatives: [{option_id, description, benefit, cost, affected_node_ids}]
previous_ref: null | Ref
```

`maturity=framing` 可没有 central node/nodes，必须有可展示的问题、已知约束与具体缺口；不能凭该形态满足完整方向退出条件。argument 形态必须有中心节点和连通的相关论证/讲解结构，所有 ID 唯一、所有 edge/qualification 引用存在。报告/教学不强制商业 CTA；中心节点可以是解释命题或教学任务。

reported_fact/calculation 必须有可核对来源定位或明确 blocker；calculation 还需把计算说明和输入节点表达在 reasoning/来源中。inference/hypothesis/target 不得因无事实来源而假装 reported_fact；必要的限定通过 qualification 节点连接到具体结论，并映射至相应上屏内容。SourceLink 沿用当前 ContentPlan 的 `{source_id,source_version:{original_sha256,extract},locator}` 结构。Schema 检查引用/类型，独立审查判断来源是否真的支持结论，二者不可互代。

### 11.2 ContentPlan：预先计划与当前稿件映射

拟新增 `content_plan_input.v2`、`content_plan.v2`，保留当前 plan_id/version/project_id/origin/basis/previous_ref 的外壳。Document.content_plan 仍是唯一当前 Plan 指针，不增加 Storyboard 真源。

```text
schema_version: content_plan.v2
plan_id, version, project_id, task_id, origin, basis, previous_ref
mode: planned | bound | imported_mapping
narrative_ref: null | Ref
imported_manuscript:
  null | {source_ref, claimed_confirmation_evidence: Evidence,
          preserve_mainline: true, unresolved_mapping_items: [string]}
input:
  schema_version: content_plan_input.v2
  chapters: [{chapter_id, title, page_ids}]
  page_order: [stable page id]
  page_roles: [{page_id, role, audience_question, intended_takeaway,
    narrative_node_ids, source_links, required_qualifications,
    content_profile: simple | evidence | mechanism | data_dense | mixed,
    density_rationale, timing_seconds: null | integer,
    transition_to_next: string | null}]
  page_budget: {exact: integer | null, target: integer | null, max: integer | null}
  time_budget: {total_seconds: integer | null, speaking_seconds: integer | null,
    interaction_seconds: integer | null, constraint: hard | soft | unspecified}
  speech_policy: {mode: none | cues | verbatim, source: provided | delegated | default,
    output: none | separate_script | pptx_notes | both}
  issues: [{issue_id, question, impact: blocker | needs_judgment | advisory,
    affected_page_ids, resolution: open | resolved | accepted_limit,
    resolution_ref: null | Ref}]
  tradeoff_issue_ids: [issue id]
page_links: [{page_id, page_ref, plan_role_page_id}]
```

planned 允许 `page_links=[]`，其 page_order 是拟议页序，Document.pages 可以尚不存在这些页；因此前置策划不必伪造 Page 正文。bound 的 page_order 必须与本次原子提交后 `Document.pages[].page_id` 完全一致，page_links 必须覆盖每页且绑定实际 Page hash，不允许幽灵页、重复页或只补部分过期 links。最终实际页序始终是 Document.pages；Plan 保留计划及其对实际顺序的一致映射。

page_budget 中 exact 是用户/有效委派确定的精确页数，max 是硬上限，target 是可解释调整的软目标，各自可为 null。“最好 6 页、最多 8 页”明确存 target=6/max=8/exact=null。exact 与 max 冲突时必须解决取舍；不得把上限解释为必须填满，也不得把软目标当硬约束偷偷缩字。

tradeoff_issue_ids 只引用同一 Plan.input.issues 中唯一存在的 issue_id；不隐式跨到 Narrative.issues。Plan 的本地 issues 可记录页数/时长/密度/布局冲突，故 imported_mapping 没有 Narrative 时仍可合法表达取舍。来源/主张问题继续由 Narrative issues 承担；需要关联时通过明确 resolution_ref/专业产物 Ref 表达依据，不使用悬空字符串 ID。

`mode=imported_mapping` 允许 `narrative_ref=null`、node mapping 为空，但必须绑定原稿来源和“已确认”声明的真实证据等级。保留原稿的版面职责与正文，未能推断的论证关系标明未知，不回填一份假确认 Narrative。只要本次不改变主线，可走 fidelity-only；改变受众/中心主张/说服结构后必须回到新论证流程。

`Scope.page_manifest_ref` **明确指向上述 content_plan.v2 对象**，不是新对象族；其 `projection=page_order` 切片列出固定页面成员与页序。生产授权必须再绑定对应 page_links/当前稿件切片。planned Plan 的 manifest 可用于文字策划授权，不能单凭它派发真实图像。page_links 更新导致 Plan 对象 hash 变化时，未变的 page_order 切片不使页集合授权无意义地失效，但 Page 内容资格仍须单独校验。

### 11.3 Page、口播与制作说明

保留 `deck_page_package.v2` 的真实字段名：`customer_visible` 为上屏正文真源，`speaker_notes` 为口播文本真源，`visual_spec` 为页面表达意图，`internal_only.production_notes` 为制作说明。不要实现第二份 `visible` 字段或另一份可独立编辑的稿件 Markdown。

拟给 Page v2 增加可选 `content_mapping`（新 writer 的新生成/修改页按策略必需）：

```text
content_mapping:
  narrative_ref: null | Ref
  plan_role_page_id: stable page id
  visible_links: [{element_ref, narrative_node_ids,
    source_links: [{source_id, source_version, locator}]}]
  speech_segments: [{segment_id, start_codepoint, end_codepoint,
    narrative_node_ids, kind: cue | verbatim, estimated_seconds: integer | null}]
```

element_ref 必须取现有 `content.visible_atoms(page)` 生成的稳定 atom_id，例如 `atom:p5:title`、`atom:p5:block:b1:text`、`atom:p5:footnote:f1:text`；复用 `content.atom_ids/validate_page_references` 的身份体系，不另造 block-only ID、JSONPointer 或显示页码。新页 visible_links 必须覆盖当前 visible_atoms 的完整 atom_id 集合，正文、表格列名/单元格、labels/callouts 和 footnotes 均不得漏掉；每个 atom_id 恰好一条映射。纯导航/格式原子可以空 narrative/source mapping，不能为凑字段捏造主张；具有事实/限定作用的原子由语义审阅核查支持关系。speech range 是 `speaker_notes` 的 Unicode codepoint 半开区间，禁止越界、重叠，所有非空口播文本由段覆盖；估时是估计，实际讲述计时另存 Review evidence。none 不强制写口播。逐字稿可由 Page 按 Document.pages 顺序导出；导出的 Markdown/文档不成为第二真源，修改必须回写原 Page 再重投影。

visible_links.source_links 直接使用 §11.1 的结构化 SourceLink；source_version 指向本次实际读取的原始/提取版本，locator 必须非空。不存在独立的 source_link_id 注册表，也不接受未定义 ID。Runtime 校验对应 source/版本存在、引用属于该页相关论证或输入范围；语义支持性仍由内容审阅判断。

整页局部改文需要同时更新该页映射与受影响 notes；speech-only 只许改 speaker_notes/content_mapping 的 speech 段，不能顺便改上屏正文。增删/拆合/重排页面必须原子更新 Plan mapping 和明确授权的 Page/order；新页 ID 不继承旧页的身份。导出 PPTX notes 的要求必须贯穿 compiler 输入、native writer、notes XML/回读验证；只生成 Page.speaker_notes 不算已交付讲稿。

### 11.4 Design plan 与 recipe

不另建可写 `design_plan` 顶层真源。将其作为新增 `style_proposal.v3` 的规划部分，包含：`basis`、`intent=initial_design|restyle|feasibility`、`page_profiles`（page_id/profile/density/diagram/task）、`layout_rationale`、`sample_targets`（page_id/覆盖风险）、`uncovered_cases`、`tradeoffs`、`reference_refs`、`recipe_draft`。所有可执行视觉参数集中在 recipe_draft 中；提案里的解释文字不能作为另一个优先级覆盖配置。

冻结后创建 `style_recipe.v3`，作为唯一实际 palette/typography/density/composition/spacing/icon 规则来源；记录 proposal_ref、parent_recipe_ref、scope、参数及其依据。Document.design_context 和 Page.design_overrides 的当前允许投影继续保留，但生成请求按 recipe 编译到这些字段，同一维度不得存在相互冲突的独立可编辑值。override 必须是 recipe 允许的页面级差异，并显示在 diff。

initial_design 允许 `reference_refs=[]`、目标 `blueprint_ref=null`，但必须有范围内当前 Page 或明确 trial 候选 Page 引用。不能沿用当前 v2 必须已有目标原图的 service 前置条件。restyle 保持原图/参考图的真实 fixed Ref。feasibility 可只有 Narrative/Plan 候选与文字线框，不产生真实样页。

纯 design-only 方案请求仍使用 `request.intent=design_trial`，但 `max_external_calls=0/max_candidate_count=0`、Scope.layers=[design]、actions 只含 `design.feasibility/design.propose`。UI 显示“只出设计方案”；不得在显示名称中误称“已生成样页”。有 1–2 张样页授权时才开放真实 trial 入口。

### 11.4.1 内容密度到生产请求的最小接口约定（2026-10-13 修订）

本节固定 I04 的接口设计；是待实现合同，不声明现有运行时已接通。本次只修改文档，JSON schema 与产品代码保持原状。

| 项目 | 唯一约定 |
|---|---|
| 输入 | 同一选定快照中的当前 Page Ref、对应 Plan 页级条目（允许 fidelity 路径缺省）、有效 recipe Ref 与适用设计决定 Ref。T03 提交内容与 Plan；T05 的 service 解析器负责读取、校验和投影，不由调用 Agent 自由拼接 |
| 派生位置 | 在 service 构建 generation input、调用 `project_prompt` 之前派生 `resolved_design_context.content_requirements`。冻结到既有 `generation_input.design_context.content_requirements`；`project_prompt` 将同一结果完整映射到 `projection.content_requirements` 并序列化进入实际 prompt。不得仅写 `layout_hint` 摘要，也不得把派生值回写为另一份可编辑的 Plan/Page |
| 内容投影 | 版本标识 `content_requirements.v1`；`mode=planned|fidelity`、page_id、page_role（role/audience_question/intended_takeaway/transition_to_next）、content_profile、density_rationale、required_qualifications、structure_refs（现有 atom/node/edge 身份）、Page 的 visual_intent/layout_hint。取实际输入原值，不补论据、不润色或概括密度理由；真正表格和正文仍只来自 Page |
| 依据投影 | 同一 design_context 中保存 `content_basis`：Page/Plan/recipe/适用决定的实际 Ref 与被消费页级切片摘要。该内部依据用于追踪和失效，不进入图像 prompt，也不成为客户可见文字。Ref 用于追溯，失效依据用切片；不得因无关 Plan 页变化使全稿失效 |
| 权威与冲突 | Page 的事实、限定、职责、比较对象及因果/业务关系不可被 recipe 或布局指令覆盖。Plan 与当前 Page 映射过期、版本混用或语义冲突时拒绝冻结并指出对象和冲突。设计取舍不能静默改变内容；recipe 仍是视觉参数的唯一来源 |
| 依赖与失效 | 消费该页可见内容及视觉语义、Plan 该页实际消费字段、有效 recipe 参数和适用决定切片；全局设计变化只影响适用页。无关页、未消费的 Plan 字段或仅审计 Ref 外壳变化不触发全稿重生。沿现有 registered slices 实施，不引入第二套缓存或批准状态 |
| 无完整 Plan | 已确认稿/导入稿沿 fidelity 路径：mode=fidelity；缺少的 page_role/profile/rationale 明确为 null，保留 Page 全部可见结构、限定和既有有效设计。不强迫新建 Narrative，不伪造历史决定；必要新冲突按现有范围处理。应有 Plan 的新论证流程不能借 fidelity 绕过要求 |
| 历史请求 | 旧冻结请求按旧版本只读与回放，不补写或重新解释；新请求登记此投影版本。既有 generation input 的 design_context 对象可承载派生项；实施时补语义校验/允许键合同，若实际兼容检查证明需升版则先显式修订合同与迁移，不静默接受未知键 |

`content_basis` 的页级消费切片至少包括：Page 的 customer_visible 和与意义有关的 nodes/edges/标签归属/visual intent，Plan 对应 page_role 中上述实际投影字段，以及该页适用的 recipe/决定。纯几何字段与业务关系字段分别比较；不能只比较文本 hash。来源变化若经内容影响分析改变了判断，先更新内容再投影，不让设计解析器重新解释来源。

边界用例：仅将相同节点、边方向和归属整体从左右排列改为上下排列，是设计修改；文字全部保留但把“人工确认后提交”变成“模型直接提交”，或交换表格两主体的单元格归属，是语义修改，必须回内容责任与审查。必要字段变更后，旧设计请求及相关产物/复核失效；仅 notes 修改沿 T06 规则处理，不重生未变视觉。

数量判断缺必要数据时回到内容阶段处理；有依据的定性关系可用机制图。仅在稿件明确需要教学示意且不会制造量化印象时保留示意图，不自动生成装饰性“示意数据”。

### 11.5 Compose v2 结果 variant 与原子写集合

当前 compose.v1 把 Page 与 ContentPlan 同步接纳；不能把空 Page 塞进旧信封来模拟前置步骤。拟新增 Task `protocol_version=compose.v2`、`required_capabilities=[compose.v2,collaboration.v1]`，结果 schema `compose_result.v2`，按 task 上的 protocol/version/phase 选择解析器。旧 compose.v1 仅用于历史读取/收据回放与旧调用结算，不派发新生产。

```text
schema_version: compose_result.v2
kind: compose
variant: framing | narrative | page_copy | speech | input_revision
task_id, operation_id, produced_against, eligibility_digest
payload: variant-specific object
usage_events: []
```

| variant | payload 必须/允许 | 严禁的写入 | 原子接纳 |
|---|---|---|---|
| framing | maturity=framing Narrative | Page、image、SVG、PPT、用户 Decision | 存提案 Ref + Task/result receipt；不覆盖当前语义 |
| narrative | argument Narrative，planned Plan 可选 | 完整 Page、外部生成、用户确认 | 存 Narrative/Plan 提案 Ref；topic 决定/委派后由 proposal adopt 更新当前指针 |
| page_copy | Page 集合、完整结果 page_order、bound Plan input；Narrative 只能固定 Ref | 偷改 Narrative/来源/全局设计、超 scope 页面 | 先验证所有 Page，再由 Runtime 生成全部 page_links，同一次 pointer swap 写 Pages+Plan+必要下游失效 |
| speech | 固定 Page Ref 的 notes 更新与 speech segments | customer_visible、页序、视觉配置 | 对指定 Page 写 notes/mapping 并绑定新 page_links；对应输出/口播审阅失效 |
| input_revision | 明确 changed-layer mask、相关 Narrative/Plan/Page proposals 或范围内修订、diff | 未授权主线重写或全局替换 | 更新所有受影响对象/依据/映射并对范围外差异拒绝；不能半写成功 |

`adoption_policy=proposal_only/candidate_only` 时结果留在 Task.result_refs/candidate，不改当前 Document.narrative/content_plan/pages。已有明确用户接受或有效委派时，拟新增 `collaboration.adopt_proposal` 可自动将**被该决定覆盖的**提案 Ref 提升为当前指针；该动作仍有精确写集合、scope/CAS 与收据，不生成新确认，也不授权制作。页面采用复用现有 candidate adopt 语义。

旧信封的 notes、files、content_plan 字段不能被用作新合同的隐藏通道。未知字段、variant 与 task 不匹配、空 Page 冒充计划、纯 speech 改正文、Page order 与 Plan 不一致、结果附伪造 decision/auth 都拒绝。调用事实依旧可先结算，业务对象部分不允许接纳。

### 11.6 Review v2 与文件注册

拟新增 `deck_review.v2`，保留当前 Review 的 subjects/dependencies/observations/findings/replaces 语义，增加 `reviewer.evidence_ref`、`reviewer.assurance` 和可验证执行/人工 receipt Ref。`review_stage` 为 `preproduction | page_visual | final | use_validation`；`kind` 保留现有集合并新增 `interview`、`argument`、`speech`、`page_copy`、`progression`、`visual_expression`、`use_effectiveness`。每条记录只评价一个 kind，不能把六层评价压进一个平均总分。schema validator 必须按版本分发，旧 deck_review.v1 可读取，不升级证据等级。

新论证 full_deck 的前置 required units 为 argument/page_copy/progression；有明确 speech 输出时加 speech。页面级视觉仍复用 blueprint_content/blueprint_fidelity/readability；final 当前六维工程/交付检查继续保留。use_effectiveness 只能由实际使用证据满足，静态模型评估不能填写 observed user success。人类 professional_use 是独立的要求与 kind，不能由其他 human kind 替代。

所有新 schema 放入 `src/deck_master/resources/contracts/` 并由 `models.SCHEMA_FILES`/版本分发注册：

| 文件 | schema_version/用途 |
|---|---|
| `narrative.v1.schema.json` | narrative.v1 |
| `content-plan-input.v2.schema.json` / `content-plan.v2.schema.json` | content_plan_input.v2 / content_plan.v2 |
| `collaboration.v1.schema.json` | Document collaboration 区域；Request/Scope/Evidence/DependencySlice 定义 |
| `collaboration-decision.v1.schema.json` | collaboration_decision.v1 |
| `collaboration-authorization.v1.schema.json` | collaboration_authorization.v1 |
| `compose-result.v2.schema.json` | compose_result.v2 variant 联合类型 |
| `style-proposal.v3.schema.json` / `style-recipe.v3.schema.json` | style_proposal.v3 / style_recipe.v3 |
| `review.v2.schema.json` | deck_review.v2 |
| 更新 `document.v1.schema.json` / `task.v1.schema.json` / `page.v2.schema.json` | 显式声明本节新增字段，writer 边界防旧写入 |
| 更新 `export-manifest.v1.schema.json` | 可选 variant 元数据与固定 Narrative/Plan Ref；已有 revision_id/files/hash 语义保持 |

不得在新协议还未写入正式 schema/validator/资源安装包时仅修改 Skill 提示语后宣称实现。JSON Schema 的引用约束、Runtime 语义/原子性、专业审阅三者分别验收。

### 11.7 同项目的 live/read 两份优化稿：顺序子请求

本版不建设通用分支工作流。只有用户明确要求两份优化稿或有效委派已覆盖两份时，采用同一项目内两次**顺序、独立、有界**的子请求；mixed 本身不自动授权双做。两次请求共享固定 Narrative Ref 和源事实，各自有独立的 Plan/Page/recipe/output 与 scope/预算。

1. 原指令在 authority constraints 中明确 `variant_ids`，如 `[live,read]`；两个子请求分别带 `request.variant={group_id,variant_id,label,requested_variant_ids}`。每个子请求有自己的 request_id/制作预算，原始用户来源相同但必须属于声明的不同 variant；不凭换 label 产生第三份。若原指令有共享总限额，两份具体预算必须通过同一 budget_parent_ref 共享，不各复制总额。
2. 先完成 live 子请求，固定一个真实 revision，其中 Document.narrative/content_plan/pages/outputs 完整一致。用现有 versioned export 保存该版本；manifest 原有 revision_id/files.sha256 保持固定，新增 variant 元数据记录 group_id/variant_id/label/narrative_ref/plan_ref。
3. 再通过 request replace 开启 read 子请求，保持同一 Narrative Ref，产生 read 的 Plan/Page/输出。Document.current 始终只有一个，完成第二份后指向第二份。第一份靠现有历史 revision 与 versioned export 寻址，不建立第二个 current 或第二套页面状态。
4. 历史导出通过各自 manifest.revision_id 读取固定 Plan/Page/output；第二份的 Page 字节变化不是第一份文件改变，不能把当前 read 的页面 hash 与旧 live 导出的主体 hash 混比。每份 Review 的 artifact 依赖按该份固定 revision 解析；第二份本身不会无故使第一份的内容/视觉评阅记录失效。
5. 交付两份时，每份分别以自己的 artifact snapshot 加当前 control snapshot 评估。当前受众、来源权限、共享主张、用户撤回/策略变更等仍使相关旧交付资格重评；不能借 immutable snapshot 保留已经撤回的权力。同一组中已完成子请求的**固定文件交付**授权可以继续适用，完成仅终止生产推进；不能从旧完成请求再次派发生产或借它覆盖新文件。
6. 再改某一份，必须以该 manifest/revision 开启对应 variant 的局部 edit 子请求，按实际授权范围生成新 revision/export，并保留替代关系。新重建预算按 §3.5 计算。两份之一的修订不能自动重做另一份；若共享主张确需变更，先给两份受影响范围与取舍，再匹配原委派/新指令。

上述 variant 元数据只是现有请求与不可变导出的标签/引用，不形成可单独编辑的内容真源或分支状态机。只有单稿的项目保持 variant=null。

## 12. 拟新增 CLI/HTTP 接口与错误协议

本节命令/路径是**实施目标**，不是当前可执行命令。CLI 的 PROJECT 解析沿用当前 registry/path 规则；HTTP 的 project_id 由同一 service 解析。所有写入都要求 base_revision、operation_id，service 计算 payload digest，实际 adapter context 来自传输层。

| CLI 目标 | HTTP 目标 | 必需 request / response 要点 |
|---|---|---|
| `deck-master collaboration show PROJECT` | GET `/api/projects/{id}/collaboration` | 返回当前 request、有效决定/授权/证据等级、阻塞卡片、capabilities |
| `deck-master collaboration request start PROJECT --input request.json` | POST `/api/projects/{id}/collaboration/requests` | {base_revision,operation_id,request:{intent,content_intent,scope,instruction_evidence,variant?},replace_request_id:null,request_source_key} → {request_id,effective_scope,eligibility,receipt} |
| `deck-master collaboration request replace PROJECT --input request.json` | POST `/api/projects/{id}/collaboration/requests` | 同 start，replace_request_id 指向当前请求；另可传明确授权的 background_request_ids → {request_id,prior_request_disposition,affected_tasks,paused_authorizations,eligibility,receipt} |
| `deck-master eligibility PROJECT --action ACTION --input targets.json` | POST `/api/projects/{id}/eligibility` | 只读；{action,targets,artifact_revision?} → §6 判定含 selected/current revision |
| `deck-master collaboration decision PROJECT --input decision.json` | POST `/api/projects/{id}/collaboration/decisions` | {base_revision,operation_id,decision} → {status,revision_id,decision_ref,effective,assurance,next_action} |
| `deck-master collaboration grant PROJECT --input grant.json` | POST `/api/projects/{id}/collaboration/authorizations` | {base_revision,operation_id,authorization} → {authorization_ref,effective_scope,budget,assurance,receipt} |
| `deck-master collaboration adopt-proposal PROJECT --input adoption.json` | POST `/api/projects/{id}/collaboration/proposal-adoptions` | {base_revision,operation_id,proposal_ref,decision_ref,write_scope} → {adopted_refs,invalidated_refs,revision_id,receipt} |
| `deck-master collaboration pause PROJECT --input pause.json` | POST `/api/projects/{id}/collaboration/request/pause` | {request_id,reason,evidence,base_revision,operation_id} → {paused_request,affected_tasks,receipt} |
| `deck-master collaboration resume PROJECT --input resume.json` | POST `/api/projects/{id}/collaboration/request/resume` | {request_id,evidence,base_revision,operation_id} → {same_scope,eligibility,receipt}；不接受隐式扩大范围 |
| `deck-master collaboration revoke PROJECT --input revoke.json` | POST `/api/projects/{id}/collaboration/authorizations/{authorization_id}/revoke` | {reason,evidence,base_revision,operation_id} → {revoked_chain,settlement_only_tasks,receipt} |
| `deck-master collaboration migration describe PROJECT` | GET `/api/projects/{id}/collaboration/migration` | 只读，返回 migration plan/plan_digest |
| `deck-master collaboration migration apply PROJECT --input migration.json` | POST `/api/projects/{id}/collaboration/migration` | {base_revision,operation_id,plan_digest,instruction_evidence?} → {revision_id,preserved_refs,pending_decisions,receipt} |
| `deck-master review evaluate SOURCE --persistence none --report-output PATH` | POST `/api/reviews/evaluate` | {source,source_sha256,scope,persistence:none,report_output?} → {source_hashes,report_ref_or_inline,evidence_level,limitations}；不修改源项目，不创建生产项目 |
| `deck-master review import PROJECT --input report.json` | POST `/api/projects/{id}/reviews/import` | {base_revision,operation_id,external_report,source_bindings,evidence} → {review_refs,assurance,receipt}；必须有项目写入意图，不提升原报告身份 |

framing/narrative/page_copy/speech 继续使用既有任务派发/start/result 提交入口，只扩展 compose.v2 variant；不再增加四套任务队列。Design 复用 style proposal/trial/expand API，增加 `intent` 与 v3 对象。Review 复用现有 accept path 的版本分发。只读 POST eligibility 不得因为 HTTP method 名称而创建 Task 或写 operation receipt。

request start/replace 的 Python service 是 `collaboration.start_request(project,input,adapter_context)`，create 和既有项目的独立 Content/Design/Edit 入口都调用它；适配器不得各自写 Document.collaboration.request。无当前请求或已完成请求时可 start；有未结束请求则必须明确 replace_request_id，避免误覆盖并发用户工作。replace 原子保存新请求、旧请求处置和不再有执行资格的旧授权/任务事实；默认暂停旧未完成范围，只有明确 background 委派可以继续。固定旧输出的有效交付授权不等于后台生产许可。

`request_source_key` 由 Runtime 从固定指令证据（可核对消息/event locator；无 locator 时为来源 Ref 与显式请求标识）、规范化意图/目标和明确 variant_id 计算/校验。相同来源的同一工作请求在不同 operation ID 下重试返回原 request_id，不重发首次/rebuild credit。新建/替换 Request 本身不是额外预算授权；只有新的明确用户修改指令、有效预算扩额或已明确覆盖的不同 variant 可产生对应新预算边界。traceable 来源仍保持其既定证据等级，去重规则不宣称验证了消息身份。

`review evaluate` 的 SOURCE 可以是项目只读快照、单个外部 PPTX/稿件或明确文件集，不要求 Document 存在。持久 Review 中的 Ref 必须是 Store Ref；项目外报告在导入前使用 `{source_uri,sha256}` 描述源主体，不能冒充 `.deckmaster/objects` Ref。严格只读验收应比较源目录内容/current 指针前后不变，报告目录变更单独核对。

每个响应共用 `schema_version=collaboration_response.v1` 外壳：`status,project_id,artifact_revision_id,control_revision_id,operation_id?,result?,error?,next_action`。成功写返回 200/CLI 0，已提交相同 operation 重放也为 200/0 且 status=already_applied。错误内容为 `{code,path,message,recoverable,details}`，details 至少给受影响 artifact/decision/scope，不泄露来源中的无关对话。

| 错误类 | CLI exit | HTTP | 例子 |
|---|---:|---:|---|
| 输入/对象形状非法 | 2 | 400 | unknown variant、Ref 非法、Page/Plan 不一致 |
| 无效认证/伪造受信事件 | 4 | 403 | 伪造 verified_user、receipt 签发方/nonce 无效 |
| 可恢复准入缺口 | 4 | 409 | decision_needed、needs_reviewer、authority_channel_unavailable、migration_required、paused、scope_exceeded、budget_exhausted |
| 并发/重放冲突 | 5 | 409 | stale base、同 operation 不同 payload、过期产物/授权依据 |
| 不存在的项目/对象 | 2 | 404 | 无此 request/Ref |

这是新 collaboration API 的固定映射；已有 CLI 错误码若不同，由适配层保持旧命令兼容并在新接口统一，不悄悄改变所有旧脚本。

### 12.1 提前修复人类谓词与可信适配器的分界

T01 可以先完成所有明显错误负例、status/kind/主体/依赖精确匹配与全交付入口一致；T07 的可信人类证据适配器未完成时，真实严格人类策略可以诚实地保持 blocked。T01 的受控 verifier stub 正例只证明谓词组合逻辑，必须标明 synthetic/unit fixture，不能宣称端到端人类身份验证通过。T07 需以真实适配器的合法收据正例和同 Host 伪造/跨文件重放负例解除这一验收缺口；不会把 independent_model_or_human 前置内容审阅当作人类交付验收。
