# 08｜运行时衔接、低输入交互与任务权限

## 8.1 为什么不能只改 SKILL.md

当前阶段契约中有必答问题，QuestionResolver 对没有当前有效答案的问题执行退出阻断。[R03][R16]
因此“不要重复问用户”必须同时更新：问题定义、答案来源、新鲜度依赖、验证逻辑、handoff、next-step、Skill 与 AGENTS 文档。只简化提示词但保留旧强制问题，不满足本包目标。

## 8.2 问题所有权

在既有问题契约中新增 `answer_authority`、`answer_schema`、`dependency_refs` 和 `confirmation_policy` 等兼容扩展。

| 类型 | 例子 | 可接受的完成方式 |
|---|---|---|
| user_only | 真实交付批准、未授权资料范围、实质方案范围取舍 | 用户明确决定及可追溯引用；不能由 Agent 假填 |
| source_derived | 已有受众、现有系统、已写在材料中的页数要求 | 提取对应来源与版本；实质冲突另开用户决定 |
| agent_proposed | 核心主张、反方疑问、证据顺序、默认页面安排 | Agent 产出具体答案和依据，通过内容检查；关键方向按策略确认 |
| runtime_computed | 工具就绪、来源哈希、页面数、已授权范围是否有效 | Runtime 实测/计算，不问用户 |

`planner.primary_thesis`、`planner.counter_question`、`planner.proof_order` 不应继续要求用户先写答案。`brief.evidence_gap` 应由读取和研究归纳。目标决策未明确且会影响方向时仍需问用户，但先提出有依据的推荐。

用户回答“没有禁词/不包含某范围”对对应的布尔/集合问题可以是有效答案。不能用全局 vague token 规则把所有“没有/否”一律当含糊；也不能把“随便/都可以”当作对外承诺授权。按 answer_schema 验证。

## 8.3 复用与新鲜度

同一个决定只对它实际依赖的内容失效。新增无关来源、重渲染、改变一页颜色，不触发重新访谈全部业务问题。决定复用记录 reused_from 与本次依赖检查，不伪造用户新确认。

关键材料冲突或决策目标改变时，必须给出“哪个旧决定受影响、为什么、推荐如何改”，而不是重复完整访谈。若目标和风格已有明确确认，新建过程中可直接继承；不机械强制三次人工停顿。

## 8.4 阶段内动作协议

复用现有 HandoffRuntime 管理跨阶段，扩展阶段内 `next_action` 投影。必要字段：action_id、kind、stage_id、actor_type、input_refs+hashes、output_refs、required_schema、authorization_ref、scope、acceptance_command、resume_command、reason。

新增动作种类可以包括：`agent_context_extract`、`agent_research`、`agent_solution_design`、`agent_narrative_plan`、`agent_page_content`、`agent_diagram_view`、`agent_semantic_review`、`agent_targeted_repair`。这些是已有阶段内任务，不是新的公开 Skill 或另一个全局 Run 状态机。

Runtime 无内置模型：命令返回 Agent 动作后，宿主读取当前任务、调用实际可用工具、形成结果，执行 acceptance，再继续现有 autopilot。Shell 命令返回 awaiting_agent_execution 不等于必须用户说“继续”。不能假定 CLI 自己能调用宿主 Web/ImageGen。

## 8.5 接受动作的原子性与冲突

提交结果必须匹配当前 run、action_id、预期输入指纹和授权范围。相同 action+相同 result hash 幂等；同 action 不同结果作为冲突保留，不能直接覆盖。旧输入结果迟到时标为 superseded/stale，不能覆盖新决定。

使用现有 per-run 锁和写入辅助扩展：先验证全部输出，在 staging 写文件，成功后提交一份引用清单/提交标记，使 resolver 只读取完整已提交结果。中断时保留旧版本、可恢复或清理未提交 staging。不引入通用事务平台，但必须测跨文件半写入和并发导入。

用户停止后不启动新动作；正在形成的迟到结果可留档，不自动推进/批准/导出。工具临时失败只重试当前动作，不重跑已完成内容。

## 8.6 允许停止的条件

仅当：用户停止；必需工具或输入不可用；必须用户决定且无既有授权；达到修复/研究预算；无法在授权范围内修复的契约/证据冲突；最终文件等待当前版本批准。

禁止因为“轮到另一个 deck-* Skill”“需要 Agent 写 JSON”“已有材料还没读”就停下来要求用户推动。

## 8.7 最小 Review Desk 接入

复用现有页面显示：本次任务就绪、材料未读范围、需要用户决定的真实问题、推荐主线、内容审查问题、返修进度、当前版本批准/失效原因。不要新增独立聊天面板或重做全部设计系统。

CLI、Skill 与 Review Desk 必须读取相同状态投影。read-only diagnosis 不写生产文件、不导入结果、不自动发起研究。
