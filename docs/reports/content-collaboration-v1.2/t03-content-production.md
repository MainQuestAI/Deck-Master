# T03 实施记录：分阶段内容生产、Writer 方法与前置审查

状态：**T03 按 TASKS.md 完成实现与本地运行验证（L1），等待逐条验收核验**。本卡关闭 AC-M01–M05 的 Runtime 结构与行为部分；真实 Host 会话、真实写作质量、用户/听众验证仍为 `not_run`（T08）。日期：2026-10-12（Asia/Shanghai）。

## 任务卡提交模板

```text
Task: T03（分阶段内容生产、Writer 方法、前置审查与返修），按 6 个切片提交

Implementation commit / source baseline:
  - 基线：293579f1（origin/main，含 T00–T02 全部交付）
  - 切片 1 提交：2447aa09650f42c1421e5e2e5e0c3fd59c57087a
    feat(content): phased compose.v2 production with collaboration bindings
  - 切片 2 提交：46b38ddcf8b26edb1cf6c70100b7b2122151613e
    feat(collaboration): binding gate on every dispatch and digest contract
  - 切片 3 提交：64a3630c7e85e00ae77bb25f6309ace7d6df0dc2
    feat(content): preproduction review, reviewer evidence and phase methods
  - 切片 4 提交：689564a8a475c971afa1d90d7823c9a9ac03267d
    feat(content): page mapping checks, time budget and input impact analysis
  - 切片 5 提交：53b7c714902ab504b52a8dc905389ffb21ac6b75
    feat(content): speech policy projection and sequential variant requests
  - 切片 6（本文档）：docs/reports/content-collaboration-v1.2/t03-content-production.md
  - 分支：impl/t03-content-production（本地提交，未 push / 未合并 / 未开 PR）

Changed paths and resulting behavior:
  新增模块
  - src/deck_master/content_production.py：compose.v2 分阶段派发与变体接纳
    （framing / narrative / page_copy / speech / input_revision）、阶段推进
    （content_phase_status / next_phase_task）、口播政策投影（speech_policy）、
    提案采用（adopt_proposal）。
  - src/deck_master/collaboration_binding.py：binding 构造、固定 digest 公式、
    binding_errors/require_binding 门禁、derive_requirements 需求派生。
  - src/deck_master/content_review.py：前置审查 packet、独立执行收据校验、
    needs_reviewer、preproduction_status / qualify_for_production。
  - src/deck_master/content_impact.py：事实源变更影响分析（claim/Page 清单、
    未决项与 review findings 复用）。
  - src/deck_master/variant_requests.py：live/read 两版顺序子请求的声明、
    组身份派生与重复/第三份拒绝、共享 Narrative 校验。
  既有模块行为变化
  - tasks.py：parse_envelope 接受 compose_result.v2 外壳（旧槽位仍拒绝）；
    _accept_result_locked 在 task.protocol_version=compose.v2 时路由到变体接纳；
    review_stage=preproduction 结果走 content_review 校验；_accept_content_update
    增加可注入的 plan_builder（v2 Plan 复用同一原子接纳路径）；新增可选的
    adapter_context 透传（受信执行收据）。compose.v1 路径逐字未改。
  - service.py：open_compose_task / revision_compose_task 在 collaboration.v1
    项目派发 phased compose.v2（import_draft 保持旧信封）；_continue_project
    增加内容阶段推进与 await_decision 返回；open_host_task 支持 extra_inputs /
    executor_type / phase=review|production；inputs_update 返回 content_impact
    并把受影响 claim/Page 写入修订任务指令；accept_result 投影变体写集合。
  - content_plan.py：content_plan.v2 绑定（build_v2_plan / validate_plan_input_v2 /
    validate_source_links / refresh_v2_plan_links）与逐页时间预算
    （timing_budget / check_time_budget）。
  - editing.py：依赖摘要表新增 content:narrative / content:content_plan。
  - dependency_slices.py：新增 ("task", phase) 注册基线与 artifact:narrative /
    artifact:content_plan 当前指针切片。
  - method_resources.py：按 phase 派发方法资源。
  - exports.py：versioned export 的 manifest 增加 variant 元数据
    （group_id / variant_id / label / narrative_ref / plan_ref）。
  - collaboration.py：validate_variant_request 接入 start_request（variant
    子请求替换语义）；新增 ACTION_ADOPT_PROPOSAL。
  - resources/contracts/task.v1.schema.json（及 docs 镜像）：protocol_version
    增加 compose.v2、review_stage 增加 preproduction、stage_request.speech_kind。
  - skills/deck-master/references/{content-methods,source-reading,content-examples}.md：
    四阶段方法、claim→source→page 映射纪律、无依据因果示例修正。

AC IDs and status（详见下节状态表）:
  AC-M01 partial（结构与方法已实现，内容质量=not_run）
  AC-M02 pass at L1
  AC-M03 pass at L1
  AC-M04 partial（结构已实现，专业写作质量=not_run）
  AC-M05 partial（派发/接纳/消费/needs_reviewer 已实现；真实独立模型执行收据=not_run）

Actual commands, environment, inputs and outputs:
  环境：本机 macOS（arm64），Python 3.12，命令使用仓库 .venv；
  PYTHONPATH=src；分支 impl/t03-content-production；无网络与真实 Provider 调用。
  1) 定向测试（每切片）
     PYTHONPATH=src <venv>/bin/python -m pytest -q \
       tests/rebuild/test_compose_v2_phases.py \
       tests/rebuild/test_collaboration_binding.py \
       tests/rebuild/test_content_preproduction_review.py \
       tests/rebuild/test_content_mapping_claims.py \
       tests/rebuild/test_speech_projection.py \
       tests/rebuild/test_variant_requests.py
     结果：55 passed（切片 5 收口时 6 文件合计；另有多次单文件运行）。
  2) 回归与静态检查
     PYTHONPATH=src <venv>/bin/python -m pytest -q tests/rebuild \
       -m 'not render and not browser'
     <venv>/bin/python -m ruff check src/deck_master tests/rebuild
     git diff --check
     结果见下文 §3。
  3) 合成输入：全部为仓库内合成 fixture（tests/rebuild 内构造的 Page/Narrative/
     Plan/材料文本），未使用客户材料、未调用外部模型、未生成 runs。

Evidence layer for each claim:
  - 本卡全部结论为 L1（正式 service 入口的合成运行：dispatch / start / accept /
    export / inputs_update）；没有任何 L2（真实 Host）、L3（专业内容审查）、
    L4（用户认可）、L5（听众）或 L6（文件工程）证据。
  - schema/合同层为 L0（task.v1 / 契约镜像逐字一致，包边界测试保持通过）。
  - 内容方法（四阶段、映射纪律、因果示例修正）目前只是仓库文本，需 T08 才能证明其
    在真实写作中的效果。

Failing examples and repair performed:
  - narrative 阶段的可选 Plan 无法由 Host 提供自身 Ref（对象尚未落库）→ 运行时在
    同一结果内用已存 Narrative Ref 补全 plan.narrative_ref，并拒绝指向其他 Narrative
    的 plan（反例已测）。
  - Page 级 source locator 校验原抛出 ContentPlanError，对提交方不是“输入非法”语义
    → 在 compose.v2 接纳路径转换为 EnvelopeError（路径含 payload 位置），并保留原因。
  - 内容时间预算最初只按页数/单一秒数推断 → 改为讲述/停顿/练习/问答分项相加并与
    声明总时长比较，超限返回“给出真实取舍”的下一步（AC-M03 反例已测）。
  - _input_compose_task 一度被改成需要 store 的签名，破坏既有调用方（Studio 摘要测试
    与 content_ops）→ 恢复旧签名并新增 revision_compose_task 选择器，旧路径逐字不变。
  - variant 子请求首版要求“第二版必须带新授权”，与顺序子请求合同不符且会让声明在
    replace 后失效 → 改为第二版沿用当前 request.variant 携带的声明（同一 group），
    仍拒绝第三份、重复 variant_id 和换 group 标签。
  - 早期实现的响应 dict 里把 schema 写成集合字面量导致 CAS 提交序列化失败 → 已修复
    并由测试覆盖（提交前 schema 校验）。

Preserved state / calls / unaffected pages:
  - 旧 compose.v1：路径逐字未改（test_compose_v2_phases::test_legacy_project_keeps_compose_v1
    断言 protocol_version=compose.v1 且无 binding）。
  - 未迁移项目：content_phase_status 返回 inactive，continue/compose/blueprint/host
    任务不接门禁、不加字段。
  - 已迁移但已有 Page 的旧项目：不因 continue 被拉入新 Narrative 周期
    （_phased_content_active 只在无 Page 或已进入 phased 流程时为真）。
  - 所有拒绝路径都在提交前完成校验，Document 当前指针与页面字节保持不变
    （测试断言 pages 未变、outputs 未清空、narrative 未设置）。
  - 未改动：create 默认 writer、T02 协作写路径语义、PPTX 编译、四 Skill 壳与安装、
    CLI/HTTP 适配器（T07/T04 范围）。

Not run / blocked evidence and concrete next step:
  - 真实 Host 会话（L2）：未运行；需要 T08 的 12 会话协议。
  - 真实独立模型/人类审查收据（L3）：未运行；本卡只实现收据可核对的谓词与拒绝面，
    可信适配器由 T07 提供，T08 用真实审阅关闭。
  - 内容质量与返修效果（L4/L5）：未运行（本卡只在方法文件与示例中固化纪律）。
  - 真实口播/时长实测、PPTX 备注回读（L6）：T06。
  - host_self 降级与 fidelity_only 的真实用户决定：本卡只用合成决定验证谓词。

Scope of this change; next dependent card:
  - 不翻转 create 默认 writer、不对旧项目启用新生产路径（联合集成另做）；
    不做入口级 eligibility enforcement（T04：消费 qualify_for_production /
    derive_requirements / binding 字段）；不做 PPTX notes 编译（T06）；不做
    Skill 安装与统一入口（T07）。T05 依赖本卡的代表内容与页面职责产物。
```

## 1. 切片与提交

| 切片 | 提交 | 主要落点 | 行为变化 |
| --- | --- | --- | --- |
| 1 | `2447aa09` | `content_production.py`（新）、`content_plan.py`、`tasks.py`、`service.py`、`task.v1.schema.json`、`method_resources.py` | compose.v2 分阶段派发/接纳、变体写集合与拒绝面、adopt_proposal、schema 版本与 phase 方法 |
| 2 | `46b38ddc` | `collaboration_binding.py`（新）、`test_collaboration_binding.py` | binding 构造与固定 digest 公式、门禁帮助函数、需求派生、host/blueprint 派发接入 |
| 3 | `64a3630c` | `content_review.py`（新）、`editing.py`、`service.py`、`tasks.py`、三份 references | preproduction 派发/接纳/消费、packet（AC-M05）、独立执行收据与 needs_reviewer、四阶段方法 |
| 4 | `689564a8` | `content_impact.py`（新）、`content_plan.py`、`test_content_mapping_claims.py` | 逐页时间预算与超限取舍、事实源变更影响分析并接入 inputs_update |
| 5 | `53b7c714` | `variant_requests.py`（新）、`exports.py`、`collaboration.py` | 口播政策投影、live/read 顺序子请求与拒绝面、versioned export 的 variant 元数据 |
| 6 | 本文档 | `docs/reports/content-collaboration-v1.2/t03-content-production.md` | 证据收口 |

说明：切片 1 的提交同时包含切片 2 需要的 binding 基础设施（`collaboration_binding.py`），原因是 phased 派发与门禁共享同一对象；切片 2 的提交补齐门禁覆盖与合同测试。

## 2. 关键行为（实现即合同）

### 2.1 compose.v2 变体写集合（CONTRACTS §11.5）

| variant | 写入 | 明确拒绝 |
| --- | --- | --- |
| framing | framing Narrative 提案 Ref + Task/result receipt；当前语义指针不动 | argument Narrative、Page/图像/SVG/PPT、旧信封槽位（`pages`/`notes`/`content_plan`…） |
| narrative | argument Narrative 提案 Ref（+ 可选 planned Plan 提案 Ref） | 非 argument 提案、绑定其他 Narrative 的 plan、bound plan 的 page_links |
| page_copy | 全部 Page + 完整 page_order + Runtime 生成的 page_links + bound Plan，一次指针切换；清理 outputs | 空 pages、page_order 与 pages 不一致、越界页面、映射缺 atom/节点/locator、成员或页序变化超出 scope |
| speech | 指定 Page 的 speaker_notes + content_mapping.speech_segments；重绑 page_links；失效 outputs 与口播审阅 | 修改 customer_visible/visual_spec/internal_only、非固定 Page Ref、kind 与派发不符、缺估时、口播未覆盖 |
| input_revision | changed_layers + proposal + diff；复用既有 content_update 单次切换路径 | 未知层、越界层、无 proposal 的层、input_digest 不符、越界页面、空 summary |

`adoption_policy=proposal_only/candidate_only` 时结果只留在 `Task.result_refs`；`collaboration.adopt_proposal` 只在有效、已接受且范围覆盖的决定内把提案提升为当前指针（不生成确认、不授权制作；页面候选仍走既有 candidate 语义）。

### 2.2 binding 与 digest（与 T04 的接口）

```text
build_binding(store, document, *, phase, executor_type, write_scope, adoption_policy,
              request=None, authorization_ref=None, decision_refs=(), basis=None) -> dict
eligibility_digest = sha256_bytes(canonical_json_bytes({
    "phase": phase,
    "write_scope": <规范化 scope JSON>,      # page_ids/layers 排序；Ref 走 canonical_json_bytes
    "basis": [<按 dependency_slices.slice_key 排序的 slice sha256>],
}))
```

门禁接入点：`open_compose_task`（phased 派发）、`revision_compose_task`、`open_host_task`、`open_blueprint_task` 经由 `collaboration_binding.stamp_task` 构造 binding 并调用 `models.require_task_binding`；低于 collaboration.v1 的项目不接门禁、不加字段。接纳侧只做结构复核（`binding_errors`），请求/范围/预算的入口级 enforcement 属 T04。

### 2.3 前置审查（CONTRACTS §6.3）

- `build_review_packet` 内含材料全文 extract、任务事实、完整 Narrative、完整 Plan、每页 customer_visible/speaker_notes/content_mapping（AC-M05）。
- `independent_model_or_human`：independent_host 需受信适配器的执行收据（subjects 摘要匹配、执行者不同于作者任务）；人类需身份收据；能力缺失时 `needs_reviewer` + 审阅稿。
- `host_self`：仅在 quality_profile 绑定的降级决定仍有效时成立；`fidelity_only` 仅在确认稿映射（`content_plan.v2 mode=imported_mapping`）时成立；降级不影响 `professional_review_required_for_delivery`。
- 消费接口：`preproduction_status` / `qualify_for_production`（units、blocking findings、needs_reviewer、reason_codes）。

### 2.4 映射、预算与影响（AC-M03/M04）

- Page `content_mapping` 在 page_copy 接纳路径强制：每个可见 atom 恰好一条映射、节点存在于当前 Narrative、locator 存在于存储的来源版本、`narrative_ref` 指向当前 Narrative。
- `timing_budget` 分离讲述/停顿/练习/问答并相加，与声明总时长比较；`check_time_budget` 超限时返回“给出真实删留/增页/改用途取舍”，全部数值标 estimate（实测只在 Review 证据里）。
- `analyze_input_change` 在材料/任务事实变化后先给出受影响 claim、受影响 Page（含 atom）与未受影响页，并复用叙事未决项与 review findings 通道；`inputs_update` 把它写进修订任务指令。

### 2.5 口播政策与两版（AC-M02）

- default `live` 只是兼容值（cues 推荐、非必需）；显式 `live` 默认 cues 且必需；`verbatim` 仅显式请求或已委派的 plan 政策；`read_alone` 默认 none；`mixed` 无主用途时返回 read-primary + cues 推荐并要求决定；`none` 不是删除指令。
- 两版：原指令在有效授权 constraints 里声明 `variant_ids`；组 id 由 Runtime 从该授权派生（换标签不能开新组）；第一版替换当前 request，第二版沿用当前 `request.variant` 的声明并必须是另一个变体；重复变体、第三份、不同 Narrative 均拒绝；每次导出在 manifest 冻结 group/variant/label + Narrative/Plan refs，第一版字节与哈希不变。

## 3. 实际执行的测试命令与结果

环境：macOS arm64；Python 3.12（仓库 `.venv`）；`PYTHONPATH=src`；无网络、无真实 Provider、无浏览器。

| 命令 | 结果 |
| --- | --- |
| `pytest -q tests/rebuild/test_compose_v2_phases.py` | 20 passed |
| `pytest -q tests/rebuild/test_collaboration_binding.py` | 16 passed |
| `pytest -q tests/rebuild/test_content_preproduction_review.py` | 12 passed |
| `pytest -q tests/rebuild/test_content_mapping_claims.py` | 9 passed |
| `pytest -q tests/rebuild/test_speech_projection.py` | 7 passed |
| `pytest -q tests/rebuild/test_variant_requests.py` | 5 passed |
| `pytest -q tests/rebuild -m 'not render and not browser'` | **1499 passed, 455 deselected**（收口运行，全绿） |
| `ruff check src/deck_master tests/rebuild` | All checks passed |
| `git diff --check` | 无输出（无空白/冲突标记） |

### 3.1 全量回归

- 基线（T02 main `293579f1`）：任务卡要求 1430+ passed 保持全绿。本卡收口运行为 **1499 passed, 455 deselected**（0 failed），较本卡新增 69 个用例。
- 记录一次中途运行：切片 4 结束时同一命令曾出现 `test_workbench_services.py` 与本地端口/服务相关的 10 failed + 4 errors；该文件单独重跑 19 passed，收口运行未复现。这里如实记录，不当作产品通过证据。
- 三处真实回归均由本卡改动引起并已修复：契约镜像未同步（`test_package_boundary::test_spec_contracts_match_packaged_contracts_byte_for_byte`）、`_input_compose_task` 私有签名变化（`test_studio_delivery_browser`）、`content_effects` 调用点未同步（`test_action_targets`/`test_content_candidates`，同一 `_input_compose_task` 签名问题）。

## 4. AC-M01–M05 状态

| AC | 状态 | 证据 | 缺口/下一步 |
| --- | --- | --- | --- |
| AC-M01 | **partial（结构+方法 L1，内容质量 not_run）** | Narrative `authority`/来源定位/限定节点与 blocker 的结构与语义校验（`models.validate_narrative_semantics`）；plan 的页职责/来源/取舍 issue（`validate_content_plan_semantics`）与 source locator 存在性（`content_plan.validate_source_links`）；`content_impact` 在来源/事实变化后先给受影响 claim/Page；四阶段方法与时序纪律写入 `references/content-methods.md`；无依据因果的示例修正在 `references/content-examples.md`（正反例+两版可接受修法）；反例测试见 `test_content_mapping_claims.py` | 真实写作质量、是否套销售叙事、是否公平说明真实替代、返修是否实质：属 T08 评价（`not_run`）。本卡未运行任何真实 Host 写作会话 |
| AC-M02 | **pass at L1** | `test_speech_projection.py`（live/default 仅推荐、显式 live 必需、read_alone→none、mixed 无主用途→推荐+需决定、verbatim 仅显式/已委派、none 不删用户备注、缺 notes 才派发口播）；`test_variant_requests.py`（两版共享 Narrative、各自 Plan/Page/导出、单一 current、第一版导出字节不变、第三份/重复变体/换组拒绝）；`test_compose_v2_phases.py`（speech 变体写集合与拒绝） | 真实逐字稿可讲性、两版用途验收与实际讲述/阅读效果：T06/T08（`not_run`） |
| AC-M03 | **pass at L1** | `content_plan.timing_budget`/`check_time_budget` 分离讲述/停顿/练习/问答并相加，`test_content_mapping_claims.py` 断言 600+100>480 时 `allows=False`、`over_by` 具体、`next_action=present_a_real_keep_drop_tradeoff`，且 `estimated=True/measured=False` | 真实计时与讲者是否被迫跳过内容：T08（`not_run`）。Q1 8 分钟/6 分 20 秒讲述的合成算术在本卡中以“分项相加”形式固化，未声称实测 |
| AC-M04 | **partial（结构 L1，专业写作质量 not_run）** | page_copy 要求完整 Page 集合 + 完整 page_order + 映射全覆盖（atom/节点/locator）+ bound Plan 一次切换；plan page_roles 的 `transition_to_next`/`timing_seconds` 与章节覆盖结构校验；`test_mapping_must_cover_atoms_nodes_and_sources` 覆盖缺 atom、幽灵节点、未知 locator 的拒绝 | “所有必要节点均有可见表达”“图表标签/单位/范围/来源完整”“无重复页无增量”仍需专业内容审查（L3）与 T08 评价；本卡只保证结构可检查、拒绝不可信输入 |
| AC-M05 | **partial（派发/接纳/消费 L1，真实独立审查 not_run）** | `test_review_packet_carries_materials_task_and_the_complete_manuscript`（材料全文+任务事实+完整 Narrative/Plan/Page 正文与口播）；`test_dispatched_review_task_references_the_packet`（任务引用 packet 并列出 required units，executor_type=external_reviewer）；`test_missing_reviewer_capability_returns_needs_reviewer_with_the_draft`；`test_self_declared_independence_is_refused`、`test_the_author_cannot_be_the_independent_reviewer`、`test_human_review_needs_a_verifiable_receipt`（伪造/自填拒绝）；`test_host_self_needs_an_explicit_effective_downgrade_decision`（降级需绑定决定且不放宽人类政策）；`test_fidelity_only_requires_a_confirmed_manuscript_mapping`；`test_blocking_findings_keep_production_blocked` | 真实独立模型执行收据与人类身份通道（T07 适配器）、四条路径（新论证 full_deck/确认稿/探索稿/只读审查）的真实审查：`not_run`。只读审查的项目外路径属 T04 |

## 5. 发现的问题与修复

1. **可选 Plan 的 Narrative 绑定不可由 Host 自证**：Host 无法提供自己正在提交对象的 Ref → 运行时在同一结果内补全并要求目标一致；指向其他 Narrative 的 plan 拒绝。
2. **locator 校验的异常类型语义错位**：提交方应看到“输入非法（exit 2）”，改为 `EnvelopeError` 并保留原因与位置。
3. **`_input_compose_task` 私有签名变化引发真实回归**（Studio 任务摘要、content_ops）：恢复旧签名 + `revision_compose_task` 选择器；旧路径逐字不变。
4. **契约镜像未同步**（`test_package_boundary`）：`task.v1.schema.json` 同步到 `docs/specs/deck-master-rebuild-v1/contracts/`（逐字一致）。
5. **时间预算曾可由页数推断**：改为分项相加 + 声明总时长比较，超限必须给真实取舍；estimate/measured 显式区分。
6. **variant 第二版的声明继承**：首版实现要求新授权，会让顺序子请求在 replace 后失去声明；改为沿用当前 `request.variant` 的声明（组不变、变体互斥），同时保留“第三份/换组/重复变体”拒绝。
7. **响应对象写成集合字面量**导致 CAS 序列化失败：修复并纳入测试覆盖。
8. **未迁移/已有页面的项目不应被拉入新流程**：`_phased_content_active` 限定 phased 流程入口；全量回归确认旧路径不变。

## 6. 未完成 / not_run 清单与下一步

| 项 | 状态 | 下一步（责任卡） |
| --- | --- | --- |
| 真实 Host 会话与真实写作（L2） | not_run | T08 按 ACCEPTANCE §4 运行 12 会话 |
| 独立模型执行收据与人类身份通道（L3） | not_run | T07 提供受信适配器；T08 用真实审阅关闭 |
| 真实内容质量、返修成本与主线重建归因（L4） | not_run | T08 Owner 试用 |
| 目标听众理解验证（L5） | not_run | T08 §5.3 |
| 真实计时、PPTX 备注回读与文件工程（L6） | not_run | 计时 T08；备注 T06 |
| 入口级 eligibility enforcement（所有写操作/派发/采纳/交付） | 本卡未做 | T04 消费 `derive_requirements` / `qualify_for_production` / binding 字段 |
| create 默认 writer 翻转、旧项目启用新生产路径 | 本卡未做 | 联合集成步骤（T04/T07 后） |
| 只读审查的项目外持久化路径 | 本卡未做 | T04（`persistence=none`） |

## 7. 与 T04 的接口点确认

- **`collaboration_binding.build_binding` 签名**：`build_binding(store, document, *, phase, executor_type, write_scope, adoption_policy, request=None, authorization_ref=None, decision_refs=(), basis=None) -> dict`；新增只读帮助：`binding_errors(document, task)`、`require_binding(document, task)`、`stamp_task(...)`、`derive_requirements(store, document, *, phase, speech_mode=None, write_scope=None)`、`phase_decision_topics(phase, *, speech_mode=None)`、`decision_refs_for`、`containment_gaps`、`delegation_containment`。
- **digest 公式**（冻结，两侧必须一致）：`sha256_bytes(canonical_json_bytes({"phase": phase, "write_scope": 规范化 scope, "basis": [按 slice_key 排序的切片 sha256]}))`；规范化 scope 排序集合字段、Ref/对象字段走 `models.canonical_json_bytes`。测试 `test_collaboration_binding.test_eligibility_digest_matches_the_fixed_formula` 独立重算该公式。
- **门禁接入位置**：`models.require_task_binding`（结构+当前请求/记录归属）由 `collaboration_binding.stamp_task` 在 `open_compose_task`/`revision_compose_task`/`open_host_task`/`open_blueprint_task` 调用；accept 侧 `content_production.accept_compose_v2` 复核 variant 与 `eligibility_digest`，`content_review.validate_preproduction_result` 复核审查身份与依赖。T04 可在同一批入口补 `eligibility.evaluate`，不需再改 binding 结构。
- **需求派生不完全**：`derive_requirements` 覆盖内容阶段（direction/讨论、verbatim 的 speech、production 的 execute 授权与额度、delivery 范围）与 speech 政策；预算扣减、撤回/晚到、入口清单枚举等仍属 T04。本卡只保证 binding 正确携带与门禁结构校验，不宣称已拦截全部入口。

## 8. 证据边界

- 除 §3 列出的命令外未执行其它验证；未运行真实生图、PPTX 编译、浏览器或真实 Host。
- 本卡不含客户材料、不含生成 runs、不含 tokens；全部 fixture 为仓库内合成内容。
- 未 push、未合并、未开 PR；提交只在本地区块链。
