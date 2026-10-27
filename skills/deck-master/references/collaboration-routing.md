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

## 内容交付与使用者审阅

首次交出本次内容时，先让使用者拿到可读稿，再结合实际页面或论证说明推荐的表达及取舍：这样安排解决了受众什么问题，哪些材料或方法使稿件发生了具体变化。不必罗列方法名；只说“已按方法完成”和给文件链接不足以帮助使用者判断稿件。已有方向保持不变，推荐可以是讲解顺序、证据与限定的摆放或操作说明的详略，不为展示决策协作而重开已定业务选项。

有值得使用者判断的地方，就把审阅引导落在该页、论点或使用情境上，并说明不同反馈会影响哪段内容、取舍或后续动作。使用者应能据此继续讨论，而不必猜从哪里看起；“请审阅，有意见告诉我”没有提供这个入口。正文中给受众的练习题不等于请使用者审稿，作者自查也不等于使用者认可或独立 Review。引导可以融入简短交付说明，不规定问题数量、标题、句式或问号；没有会改变稿件的判断就说明适用边界和正常下一步，不编造待决项，不强制每次追问。

材料足够时先完成已授权内容，不等可选反馈才交稿。即使 Runtime 尚待方向接纳或审查，也交出现有可读稿及上述与稿件有关的说明，同时准确标明未完成的是哪一步、谁能接续。反馈讨论、正式采用和独立审查分别处理；真正改稿仍沿已有范围、决定和写入入口，不把回复意见自动当作扩权或生产许可。

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


## 跨轮恢复与职责接手

发送新工具调用之前，读取当前 request/scope/control、Task.execution_ref 及其冻结
Request/Attempt；当前 Host 身份不等于旧 Task 身份。不要为了“继续”写一个新身份
到旧 Task，或把 selector 中的真实 thread/turn 改成旧轮次。按已核实事实处理：

| 已核实事实 | 接续方式 | 必须保留 |
| --- | --- | --- |
| 当前执行仍是领取者，调用尚未发出 | 按原工作单继续；只有明确未发的 Attempt 才 settle not_sent | 原 Request/Attempt/额度身份 |
| 调用是否发送未知 | 先收集真实观察，保持 unknown，不新建调用 | 真实消耗和未知状态，不自动释放 |
| 已完成输出与原执行及冻结输入一致 | 按原 Task/Attempt 结算并接纳准确原件；精确回执重放不再生图 | 原始输出、观察、费用与采用资格 |
| 新会话不同于领取者，已确认 not_sent | not_sent 只释放额度，不转移领取身份；用现有正式取消/退役、当前范围的计划或 request replacement/reissue 路径获得新 Task，再声明新身份 | 原任务/调用记录；已有适用授权照常核验，不虚构用户改需求 |
| 图片已完成，但真实执行与原 Attempt 不匹配 | 保留原件和实际消耗，拒绝旧 Attempt 冒名绑定；报告当前无已验证跨执行重新关联入口 | 不改 selector、不自签 proof、不自动重生成掩盖缺口 |
| 取消/撤回/过期后迟到 | 仍结算真实已发调用，拒绝采用；让当前责任方处理已有产物 | 停止控制和旧事实都不能回滚 |

只有用户确有范围/需求变动时才用 `start_request` 的 `replace_request_id` 记录该
真实变动；不能伪造新指令来绕过运行中的执行身份。无变动的重新派发须走现有
正式取消/计划/退役入口，若当前状态没有适用入口，就报告具体缺口。

实际交接记录固定 request、scope、当前 revision、Task/Request/Attempt ID，交给
下一执行者的完整 reader、实际产物 Ref、未决调用/审查及下一动作。新会话冷读取
完整方法与材料，确认 scope/currentness 后才领取；只有 reader 返回不证明执行。
返回时将真实采用产生的 revision/result_refs 与原依据对照，不把新会话名字当独立
审查证明。完整会话、实际工具图像和独立接手证据缺失时分别记 NOT_RUN/BLOCKED。
