# 讨论记录、历史沿革与证据范围

## 来源分级

A：固定 Git 源码/仓库文档，可由任何仓库读者复核。B：本地实际运行记录，脚本可复现，但有合成 fixture 边界。C：用户当前反馈与聊天记录摘要。D：历史记忆检索，用于定位；未经仓库核对的内容不当作当前事实。

公开仓库只纳入与产品诊断相关的摘要与源码链接，不上传完整私聊、客户材料、真实项目输出、访问凭据或个人路径。本包不是所有聊天的逐字归档。外部评审无需访问私有记忆即可审查技术结论；真实用户体验强度仍依赖 C 类证据，不能从代码推导满意度。

## 时间线与相互冲突的要求

| 时间 / 版本 | 记录与原意 | 对本轮的意义 / 限制 |
|---|---|---|
| 2026-06-17 | 用户要求先定义独立 Deck Master 的产品级 Skill 体系；历史能力包只是可引用资产 | 历史记忆 D；当前归档 [产品架构](../../archive/pre-rebuild/specs-legacy/deck-master-skill-system-product-architecture.md) 可查 A。不要把旧供应商/包结构当永久约束 |
| 2026-06-22 | [v1.0 交互 Spec](../../archive/pre-rebuild/specs-legacy/deck-master-v1.0-skill-suite-interaction-spec.md) 明确数量可以增加，职责要清楚；有输入路由、Workspace、运维、阶段交接 | A。原路径 docs/specs/… 已归档；Spec 的 Implementation Status 是当时声明，不是本轮复验 |
| 历史讨论摘要 | 用户反对单纯压到 3 个入口；要求按原始材料、研究报告、已规划页面、现有文件等输入定位；讨论 init 与 setup 的区别 | D：检索到带角色标记的聊天文本；不把其中助手推荐的 9/14 个 Skill 当用户批准 |
| 2026-06-23 | 用户曾叫停过快进入页面生产，要求回到 planner 开启专家访谈 | D：历史事件摘要及用户片段已读；说明问题曾出现，不证明现版本相同实现原因 |
| 后续旧 Skill OS v1.1 | [审批与自动推进策略](../../archive/pre-rebuild/specs-legacy/skill-os-runtime-v1.1/07-approval-autopilot-policy.md) 规定 interactive/preauthorized 等；方向变化、最终文件有停止条件 | A。旧严格最终审批/自然语言规则与本轮减少重复确认诉求存在张力，不机械恢复 |
| 25a27e31（09-15） | Brief/Planner/Sourcing 前置从人工变自动，部分来源问题移除 | A：首轮源码索引及差异；删除无关前置具有合理部分，但替代控制不完整 |
| 2ce3004b、1c2bb80c（09-16） | 新入口改 create/compose；Page 无 blueprint 即派发 | A；首次策划和设计没有等价承接 |
| abb84a19（09-22） | 旧源代码退役 | A；引用归零不等于专业职责验收 |
| ba8cebf5（09-26） | 18 companion Skill / 阶段合同退役；一个公开入口 | A；菜单隐藏与运行控制退化有关联，但不能认定唯一原因 |
| PR105 合并后当前 main | 页面、候选、回执、风格修改等生产管理得到增强 | A；PR105 不是前期协作退化的起点，技术修复不等于内容质量验收 |
| 2026-10-12 真实使用 | 由材料直接产出整套方案；用户认为内容歪、缺少访谈、视觉/密度/版式未确认 | C；这是用户效果评价，未做标准化盲评 |
| 本轮首份方案 | 比较 18 Skill、30 职责，记录 6 问题、5 探针，提出 6 包/28 AC | A+B 的缺陷证据加候选方案；用户认为内容方法与 Skill 关系仍未讲清 |
| 本 PR | 重新开放 Skill 体系选型，补问题与内容/评价讨论，交第三方模型审查 | 文档准备，不是修复验收 |

历史记忆定位 URI（外部评审可跳过）：
- `viking://user/default/memories/events/2026/06/17/deck_master_skill_system_redesign.md`
- `viking://user/default/memories/events/2026/06/23/skill_suite_redesign_workshop.md`
- `viking://user/default/memories/events/2026/06/23/老板叫停_回到_deck-planner_进入专家访谈.md`
- `viking://user/default/memories/entities/Deck-Master 项目/Deck_Master_v1_Skill_Suite_Interaction_Spec_2026-06-22.md`

记忆摘要中存在对助手建议和用户要求的混合叙述，本轮以实际角色片段、仓库归档和当前用户指令分别标记，不整体照录为决策。

## 真实试用案例：匿名摘要

输入包含正式要求、当前实现、旧测试版本参考。Agent 阅读材料后自行扩写 brief、组织完整稿和页面，随后进入图像蓝图、SVG 和原生 PPT；工程记录与导出不能证明前期共识。用户中途纠正了“方案内容”和“演示完成状态”混写的问题，之后又指出整体没有访谈和设计对齐。

上一轮已阅读该任务执行记录。本次重新读取其最近一轮，确认 Agent 自述正文/结构/SVG 由同一会话完成，蓝图调用 ImageGen，工具未给出底层精确型号；此自述不等于底层模型身份的独立证明。公开包不包含业务素材或私聊全文。

可支持的结论：用户未获得所需的策划/设计协作体验，当前路径允许这种直接生产。不可支持的结论：每个模型都会如此、单一 Skill 必然劣于多 Skill、旧版一定更好、视觉已全面验收、已有客观说服力提升数据。

## 首轮技术证据如何复核

[源码索引](../controlled-collaboration-audit-20261012/source-index.md) E01–E35 固定新旧 SHA；[原始探针结果](../controlled-collaboration-audit-20261012/evidence.json) 与 [复现方法](../controlled-collaboration-audit-20261012/reproduce.md) 配套。

P01 证明无方向/设计决定也可派发 blueprint；P02 证明默认 self-review 放行；P03 比较 export/handoff policy；P04 证明 professional_use 的 host_self 可满足条件；P05 以 fixture 插入 not_evaluated 记录测试谓词。P05 没有证明公开 UI 提交可构造同样对象。探针没有真实生图和桌面验收。

本次文档发布对 evidence.json 仅把个人绝对路径换成仓库相对路径，并添加说明；其他探针事实不变。首轮方案加了未批准提示，不悄悄把旧结论改写成用户同意的新方案。
