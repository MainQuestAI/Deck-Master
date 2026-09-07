# 02｜目标架构、数据归属与公共内容内核

## 2.1 架构边界

Deck Master = 方法与契约 + 确定性 Runtime + 托管生产工具 + 当前 Run 的证据和产物。
宿主 Agent = 阅读、推理、网页研究、图像理解/生成、执行当前任务及回传结果。
用户 = 提供必要输入、授权和不可替代的业务决定。

不增加第二套 Agent Loop。所谓“公共方案内容内核”，是可复用方法、结构化对象、验证器与已有宿主任务的集合，不是新的自治服务。

## 2.2 保持现有阶段；在阶段内增加专业动作

| 公共阶段 | 本轮新增/升级动作 | 责任主体 |
|---|---|---|
| deck-init | 范围登记、能力执行计划、资料解析安排 | Runtime + Agent |
| deck-brief | 全文抽取、事实/约束/冲突整理、研究缺口任务、Brief 提炼 | Agent 形成内容，Runtime 验收 |
| deck-planner | 方案模型、方案备选、论点证据、候选主线与页计划 | Agent；真实方向由用户裁决或复用已有确认 |
| deck-sourcing | none / real；历史资产检索、来源与适用性判断 | 托管 Library + Agent |
| deck-producer | 页面内容写作、方案视图、原生图形/资产制作、Page Package | Agent + 确定性工具 |
| deck-builder | 标准 PPT Master 或现有 high-density，编译/渲染/回读 | 托管程序 + 宿主视觉工具 |
| deck-quality | 内容、证据、视觉、工程检查；定向返修与复审 | 审查任务 + Runtime |
| deck-review | 当前版本审批、客户安全投影、导出 | 用户/Runtime |
| deck-learn | 按需收集真实修改理由与适用边界 | Runtime + Agent |

不新增一级公开 Skill，不把研究或方案阶段外包给另一个长期状态中心。

## 2.3 事实、设计、页面与投影：唯一所有权

| 对象 | 唯一权威内容 | 不能承担的角色 |
|---|---|---|
| `context_manifest.json` + 它引用的原始/解析文件 | 来源版本、授权范围、可定位片段、可用证据与研究来源 | 不能由生成页面反向制造事实 |
| `claim_map.json` / `claim_evidence_graph.json` | 论点类型、支持/反驳关系、证据状态、推导 | 不决定页面视觉 |
| 新 `solution_model.json` | 业务问题、能力机制、组件、关系、阶段、验收与设计备选 | 不复制原文资料、不管理审批、不代替页面内容 |
| `narrative_plan.json` 目标 v3 | 方案论证主线、候选与所选 ID、页任务与顺序 | 不独立保有另一套来源台账 |
| `page_tasks.json` | narrative 的可执行页面任务投影 | 不可与 narrative 独立改写页面顺序 |
| `page_packages/` | 获准用于生产的精确页面内容、图形任务与绑定 | 不是外部事实来源 |
| 现有 Content Lock | Page Package 和当前批准主线的不可变构建快照 | 不重新设计方案 |
| 现有 `high_density_build/mbb/mbb_plan.json` | 新 Run 下为公共 narrative 的兼容投影 | 不与公共 narrative 双写、也不重复访谈 |
| 新 `diagram_views/` | solution_model 的有范围、有类型的派生视图 | 不自由增删未经登记的业务组件 |
| `workflow/*` | 既有决定、handoff、审批与动作记录 | 新对象不得建立第二份 approval 真相 |

新领域对象只有 Solution Model 和 Diagram View；Execution Plan、Research Task 是操作任务/投影，不是新的事实库。Context Pack 与 External Review 为已有契约升级。

## 2.4 主链依赖，防止内容循环

原始资料 → context_manifest → Brief/claim graph → solution_model → narrative candidates → 已选择并批准的 narrative → page_tasks → page_packages → content_locks → 图形与构建 → 当前语义/视觉/工程审查 → final_readiness → 当前版本批准与导出。

研究结果回到 context_manifest，再使相关判断失效并重算。图形 View 引用 solution_model 与当前页面，不能反向直接改变事实。

重要：新的 storyline 规划不得先要求最终 Page Package 存在。现有高密度“由 Page Package 驱动 MBB”的实现需通过提取方法与兼容适配改变依赖方向，不得为了复用而先制造空包。正式的 Content Lock 在 Page Package 完整后才生成。

## 2.5 标准与高密度的一致性

同一批准 narrative 与 Page Package 可以进入标准或高密度构建。质量要求、论点、数字、限定条件和来源不因 profile 切换而改变。
高密度保留当前 provider 证据、SVG 受支持子集、内容覆盖、PPTX 可编辑性及回读门禁；复用批准内容时生成当前 hash 对应的兼容 receipt，而非伪造旧 receipt。
标准构建必须消费 Page Package 当前内容。若 Q0 发现实际后端只读取旧 preview，需要显式适配并通过文字/图形/来源的真实回读验收，不能仅更新文档宣称已统一。

## 2.6 失效与增量规则

来源变化只失效引用其片段/版本的论点、设计判断和页面；新增无关材料不自动使所有已答问题失效。无法精确判断时先报告保守影响集，不能静默忽略关联。
页面样式改变：只失效该页视觉/工程审查和当前导出批准，不让已确认业务目标失效。正文或数字改变：失效对应内容审查、图文一致性、内容锁与当前批准。方案组件增删：失效所有引用组件/关系的视图和相关页面，并报告影响范围。

首次修改后由 Runtime 产生变更影响投影；局部授权只覆盖选定页面时，发现跨页必须同步的实质修改，应给出具体原因和扩展范围请求。可继续做不超范围的检查，但不能静默修改整套 Deck。

## 2.7 审查事实边界

哈希、一致性、JSON 校验和审查 receipt 证明“在什么输入版本上做过什么检查”，不证明内容客观真实。语义依据由可定位来源与审查观察支持；未完成审查的内容必须保留未审状态。
