# 既有对象的精确扩展输入

本文件是对现有对象的字段增量设计，不是独立的另一套事实库。具体已有 Schema 的版本/额外字段规则需要 Codex 核验；禁止跳过迁移直接覆盖旧文件。

## Narrative Plan 目标 v3

结构草案见 `narrative-plan.v3.schema.json`（含合成样例 `examples/narrative_plan.json` 与自检反例）；与本表冲突时以本表语义为准，Q0 冻结时统一。

| 字段 | 类型/约束 | 语义 |
|---|---|---|
| schema_version | 固定目标版本 | 与读写适配一起升级 |
| run_id / based_on | 同现有Run及输入引用集合 | 绑定当前Context/claim/solution与相关决定 |
| solution_ref / solution_sha256 | 安全引用 / 64位SHA-256 | 方案模型单一来源 |
| candidates | 非空数组 | 各项含 id、core_thesis、decision_intent、argument_sequence、evidence_refs、tradeoffs、recommendation_reason |
| recommended_candidate_id | candidates中存在的ID | Agent推荐，不等于用户批准 |
| selected_candidate_id | ID或null | 只有批准/已有明确方向适用时才填 |
| selection_decision_ref | 有选择时必填 | 指向既有DecisionLog/Handoff中的当前决定 |
| issue_tree | 数组 | id、parent_id、question、hypothesis、claim_refs；不得形成循环 |
| beats | 非空数组 | 保留已有beat_id/order/role；新增page_job、conclusion、claim_refs、evidence_refs、solution_refs、business_implication、required_components、content_budget、visual_intent、dependencies |
| coverage | 对象 | required_objectives、covered_objectives、omitted_with_reason；不是十章模板全选 |

`page_tasks` 从 beats 派生；Agent 不可绕过 narrative 单独重排 page_tasks。新MBB记录 source_narrative_ref/hash 和相同 selected id，不允许另建冲突选择。旧MBB未迁移时走旧适配，不强行套新对象。

## Page Package 的增量

优先在已有受控嵌套对象承接：`provenance` 增加当前 narrative/solution/claim 输入引用，`visual_spec` 增加 view_ref/view_hash/strategy，`quality_intent` 增加 page_job/decision_impact，内容块记录稳定 block_id、statement_type、claim_refs、必要限定和数据派生引用。

`statement_type` 至少支持 factual、design_proposal、working_assumption、derived_value、structural。factual 与 derived_value 按来源/推导规则验收；structural 不强求业务证据。若现有 schema 不允许这些字段，升级 Page Package 版本并保留v1 adapter，不能放入会被丢弃的 internal_only 非法字段。

Content Lock 在当前Package形成后冻结精确文字、数字和重要限定；切换Builder不重写业务含义。

## Question/Decision 增量

`answer_authority` = user_only / source_derived / agent_proposed / runtime_computed。
`answer_schema` 定义字符串/布尔/集合/结构对象与最低语义要求；不能全靠全局 vague_tokens。
`dependency_refs` 指向真正影响该决定的来源、内容或产物；`confirmation_policy` = user_explicit / reuse_current / validated_proposal / runtime_verified。

Decision 仍写既有日志，增加 answer_origin、source_refs、derived_by_action、reused_from、validated_dependency_fingerprint。Agent来源必须诚实标记；user_explicit必须指向可追溯用户决定，不能靠字符串值伪造。

## Next Action 增量

action_id、stage_id、kind、actor_type、input_refs[{ref,hash}]、input_fingerprint、output_contract、allowed_output_refs、authorization_ref、scope{page_ids,object_refs,allowed_changes}、acceptance_command、resume_command、reason。

输出位置由Runtime确定。任意result里的路径不构成写权限。接收动作校验输入版本、授权、schema、跨对象语义和当前状态后，才提交一组完整产物并产生typed event。当前 action 是投影；现有 handoff/decision/approval仍是各自权威。

## Benchmark 与 Learning 增量

benchmark结果在既有report内增加comparison_arm、baseline/candidate_sha、input_fingerprints、host_profile、budget、attempts、first_draft_ref/hash、human_active_seconds、user_authored_chars、clarification_rounds、avoidable_questions、retention、rubric_scores和missing_data_reason。完整attempts不能按成功过滤。

learning统计以asset/run/reviewed_revision最终决定去重；accepted_count、rejected_count、acceptance_rate、sample_count、delivered_count独立。pattern_card含problem_scope、solution_mechanism、user_feedback_reason、applicability、exclusions、source_run_refs、allowed_reuse_scope。数据缺失保持unknown，不补造精准率或跨客户事实。
