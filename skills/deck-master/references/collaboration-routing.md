# 同一 Runtime 的职责、范围与恢复

四 Skill 是专业职责，不是四套状态机、四个身份或四份内容方法。先读用户真实指令、已有决定、当前 request、scope、eligibility 与 completion，再开展本次职责。决定采用、范围授权、文件认可分别记录；普通“继续”不补成决定或增额。

## 四种入口

- **点名**：使用点名职责；明确只写/只审/只试样页时保持原范围。名称与现有 request 冲突，返回具体冲突与建议责任，不重建项目或扩大 scope。
- **自然路由**：按所求产物选职责。策划/正文/口播→Content；方案/限定样页→Design；只读检查→Review；整套作品/跨职责/不明确→Master。Runtime intent 只有 full_deck/content_only/design_trial/review_only/edit，resume 是操作。
- **Master 连续调用**：同一项目、当前有效决定/授权、固定 artifact basis、相同 source/对象 ID，交给对应职责；只接纳该职责允许的产物。Content 独立完成、Design 方案/样页结束、Review 报告结束都不能自动变成全套制作。
- **恢复后调用**：重新解析 Host Skill entry 到当前 release，读 Runtime 当前 request、暂停/撤回、scope、任务与调用账和 completion，再读取当前工作单方法 bytes/hash。不要从聊天“上次已批”推权限；同一次已完成调用不重发，unknown 先核实。

用同版 Python 的 `method_resources.read_skill_methods(skill, entry_mode=..., project=..., task_id=..., text=...)` 返回方法和只读上下文。自然路由传原始 text；Master 调用与恢复传真实项目；存在 Task 时必须传真实 task_id，优先消费 Task 的派发方法和当前 basis 状态。basis_changed 不能冒称旧 Task 已消费新方法，须经正式 Runtime 解决过期任务。

返回的 `consumption=runtime_returned_bytes` 只证明读取；实际 Host 应另记执行身份、所用方法 SHA、具体判断/产物、范围及结果。没有真实工具/模型/人类执行不得补写 executed/pass；合成 Runtime 检查是 L1，非真实模型、native 或人类验收。

## 内容独立完成

以 `content_production.completion_status(store, document)` 的 `state, content_intent, effective_scope, outputs, checks, missing, responsible_role, next_action` 为准；此纯投影不写 current。`state=completed` 正常返回请求的内容产物，不要求全项目 work_complete 或为继续而补设计授权。

plan_only 返回 Narrative/Plan；write_only 返回完整逐页正文和约定检查；speech_only 返回 notes/segments/整稿投影及估时，固定稿可用 imported_mapping 而不补 Narrative；content_full 返回完整内容包及约定口播。必要独立审查缺失则 needs_reviewer，稿件仍可读。权限拒绝/零图像调用并不等于正常完成。

每个子意图以独立 Task/检查点接纳，不把理解、论证、全文和审查挤成一次不可检查的全稿覆盖。只改口播不改屏幕正文；read_alone 默认 none，live 默认 cues，明确逐字才 verbatim。

## 设计、审查与完整制作

Design 消费固定 Page/Plan或合法确认稿、recipe、内容关系和声明范围；缺正文依据交 Content，不能补造“已确认论证”。Design 方案或样页候选完成即返回；样页采用与范围扩展是两个决定。

Review 严格只读走外部报告路径，不建生产项目或把报告写回源。source 可以是固定项目、单文件或明确文件集，report/scratch 必须在源外。没有审阅能力返回具体 needs_reviewer/needs_tool，不阻止返回可读报告。报告的事实引用不提升证据等级；换 Skill 名不改变作者 lineage 或独立性。

full_deck 的授权 Producer 使用工作单准确方法及 capability：generation.v1 的 freeze→begin→真实调用→settle→accept；changes/stage/candidate/recipe/icon 依实际工作单，不虚构协议能力。全部写入通过 Runtime，采用 candidate 不重复计生图费。已发调用的 consumed/unknown 在取消/过期拒收后仍保留；不要写本地对象修复资格。

首次形成可读 Page 可通过同版 `view --open --ui v2` 打开真实 Studio；内容完成不会因此获得制作范围。没有浏览器报告实际原因和可用地址。不要把自动打开或拷贝交接视为执行。

## 变更、两用途版本与实际交付

材料/受众/用途改变通过 inputs update；局改明确 page/field/layer；当前 CAS、原始 instruction evidence 与 dependency basis 由同一 service 校验。恢复历史内容不恢复已撤回授权、暂停或费用。

顺序双版本只按原声明两版：固定第一份 revision/export 后，start_request.input.variant_transition.kind=next_variant，source 显式指向第一份。第二版创建独立 Plan/Page/output，共享固定 Narrative/来源；不复制预算或用换 label 增第三版。edit_variant 指向要改的版本，限定页/字段，当前 control 生效；其他固定版本原文件保持原样。不能用 history restore 全项目替代窄 edit。

交付核对准备交给用户的实际文件、实际 notes_policy、选定 artifact revision 与 current control。export/handoff/readiness 消费同一 delivery_eligibility；sanitized/notes-excluded 文件需核对自身 hash，不能借原 artifact 批准。工程、协作、专业/人类、native/桌面分列；历史 Desktop 工程记录不是当前人类桌面验收。

## 单任务变更回执与完整输入读取

先通过 `deck-master capabilities` 确认 `task_response_protocols` 支持
`task_receipt.v1`，再在 `task start`、`task accept` 或 `task cancel` 上指定
`--response-protocol task_receipt.v1`。Python service 使用同名
`response_protocol` 参数；HTTP `/api/cancel` 可传同名 JSON 字段。
未指定时保留旧版回执，不静默改变旧 Host 的输入。

紧凑回执只报告本次 Task 身份、状态、execution、版本和结果引用，不展开其他待办
的材料或方法正文；`context_ready=false` 不能被解释为已经读取生产输入。
领取后按回执的 `task_id` 显式读取完整上下文：

```bash
deck-master methods --project <project> --task-id <task-id> --read --read-protocol work_context.v2 --body-mode full
```

核对该完整读取中的当前性、冻结方法、scope 和实际 execution，再执行工作。
接受结果后的回执不等于下一任务派发：需要继续时调用现有 `continue`，或按 Task
目录选择明确任务后读取。精确重放保留原提交 revision/result_refs，同时报告当前
revision；不要把旧提交回执当作当前项目或当前审查通过。无效协议在写入前拒绝，
选择紧凑格式不改变权限、取消、晚到、调用结算或来源校验。
