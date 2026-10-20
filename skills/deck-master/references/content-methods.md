# 公共内容方法｜从任务与资料写成专业完整稿

这份方法用于判断和实际写作，不是每次必须填满的字段表。正式正文保存在 Page，配以合理页序和能支撑表达的图示要求。`compose.v1` 另记录下面的 ContentPlan，保存整理依据和页目标；其中不重复正文。

## 新项目的过程记录（compose.v1）

仅当工作单声明 `protocol_version=compose.v1` 时必需；旧任务保持原信封。先 `task start --supported-protocol compose.v1 --capability content_plan --capability versioned_source_links`，项目、任务、execution_ref 仍取本次工作单与实际执行身份。

在 compose 信封顶层增加 `content_plan`，按运行时 `content-plan-input.v1.schema.json`：

- `input_summary`：材料如何整合、哪些判断还缺依据。
- `chapters`：稳定 `chapter_id`、标题及有序 `goal_ids`；每个目标只属于一个章节。
- `goals`：稳定 `goal_id`、实际 `page_id`、本页用途、`source_links`、`unresolved_facts`；必须覆盖采用后的每个 Page。
- 来源链接包含真实 `source_id`、`source_version`（原文件 SHA256 和 extract ref）以及 extract 中存在的 `locator`；复制工作单 `content_plan_contract.sources` 的版本，不把旧材料或页标题冒充来源。图像材料的定位存在，也不自动证明 Host 已阅图。
- 全局 `unresolved_facts` 记录剩余缺口。某页没有来源链接时，必须说明该页缺少什么依据；不能伪造出处来通过结构检查。

核心在同一次正文提交中生成不可变计划版本、绑定 Page refs，并保存 Task.result_refs。输入修订时保留未删除页的 goal_id；source/version/locator 有误或 Host 不支持协议时不采用正文。历史计划通过 ref 和固定 Document revision 定位，页标题推导的旧稿目录只供阅读、不会回填。

可以在 `view --content-plan --revision …` 或按页 lineage 中核对；可运行的合成流程在 `examples/workbench/w02_content_plan.py`，不是专业内容验收证据。

## 内容方法导航与边界

基础动作是理解交流任务、找到材料中的判断依据、组织理解顺序、写完整正文。方法按实际缺口选择，不逐项填十张表，也不扩大已确认方向或当前 scope。

- [method-selection](method-selection.md)：选择与停止条件；M01–M10 分别承载界定、分析、论证、机制、选项、压测、综合、叙事、教学与压缩操作。
- [page-writing](page-writing.md)：完整可见正文、表格、图内文字与必要限定；制作注释放 internal_only，理解必需的信息不藏 notes。
- [narrative-patterns](narrative-patterns.md) 与 [writing-profiles](writing-profiles.md)：候选顺序和表达侧重；不强制结论标题、商业 CTA 或固定信息密度。
- [content-examples](content-examples.md)：短例与六套完整案例索引；全部合成，不是当前客户事实或产品实测结果。
- [method-review](method-review.md) 与 [content-calibration](content-calibration.md)：按实际来源和正文查论证与推进。Content 在允许范围内完成返修；Review 保持只读。

以上链接是导航，不授权绕过冻结清单直接读取。需要额外资源时通过 Runtime 正式选择/重派发，保存准确字节和当前范围。普通数字检查只证明算式一致；工程通过、模型审阅与人类认可分开记录。

## 分阶段生产（compose.v2）

工作单声明 `protocol_version=compose.v2` 时，任务只做它这一个阶段，结果按 `compose_result.v2` 变体提交。不要用空 Page 冒充策划，也不要把整份 Page 塞进 framing。

| phase | 你要产出 | 明确不做 |
| --- | --- | --- |
| `framing` | `payload.narrative`：`maturity=framing`。材料用途/权威/冲突、受众已知与目标变化、具体缺口与候选方向 | 完整 Page、图像、SVG、PPT、替用户做决定 |
| `argument` | `payload.narrative`：`maturity=argument`，中心节点 + 连通结构 + 证据/限定/未决项；可选 `payload.plan`（`content_plan.v2`、`mode=planned`） | 完整逐页稿、外部生成、声称已获确认 |
| `page_copy` | `payload.pages`（完整 Page v2，含 `content_mapping`）、`payload.page_order`、`payload.plan_input`（`content_plan_input.v2`） | 改写 Narrative/来源/全局设计、超出范围的页面 |
| `speech` | `payload.updates`：固定 Page Ref 的 `speaker_notes` 与覆盖全部口播的 `speech_segments` | 改动上屏正文、页序、视觉配置 |
| `input_revision` | `payload.changed_layers`、每个变化层的实质 `proposals`、`payload.diff`（`input_digest`、`summary`、`changed_page_ids`） | 范围外差异、无 proposal 的层、半写成功 |

`adoption_policy=proposal_only` 时结果只是提案：当前 Narrative/Plan/Page 指针不动，等有效决定覆盖后才由 Runtime 采用。

### 阶段内的方法顺序

1. **辨材料用途与权威**（framing）：正式要求 / 可核对事实 / 历史参考 / 能力说明 / 用户设想 / 模型建议分开；冲突不靠“较新的文件对”解决。目标写成受众变化：谁在什么场景、已知什么、用后要能判断或做什么。
2. **建立论证或讲解结构**（argument）：按任务选方法——培训用目标行为与概念/步骤/边界/练习反馈；分析汇报用问题/方法/观察/解释/限制/结论；决策建议用真实选项/判断标准/证据/代价/推荐条件；独立阅读用检索结构/定义/完整解释/前提/可定位来源。每个核心结论标明支持它的事实或适用规则、限定挂在哪个结论上。
3. **写出实质全文**（page_copy）：先有形（章节与页职责、节点映射、预算），再有文。每页一项可说明的沟通职责；删掉它丢掉什么、上一页留下什么问题、下一页为什么必要。正文写全图表标题、数值、单位、轴标签、注释与必要来源，不用“此处放结论”。
4. **批判与返修**：写成后按页自查限定是否跟着结论、口播是否讲得完、下一页是否必要；发现问题按依赖范围返修，删字或缩小字号不是修复。

### claim → source → page 映射纪律

- 每个需要事实支撑的可见 atom 在 `content_mapping.visible_links` 里指向它承载的 `narrative_node_ids`，并带真实 `source_links`（`source_id` + `source_version` + 存在的 `locator`）。定位存在只证明可查，不证明支持。
- `authority=reported_fact/calculation` 的节点必须有可核对来源定位或明确 blocker；`inference/hypothesis/target` 不得冒充事实。
- 限定不能只留在备注：承担该主张的页面正文必须能看到必要限定。
- 口播段用 `speech_segments` 覆盖 `speaker_notes` 的全部码点，标 `kind`（cue/verbatim）与 `estimated_seconds`（估计值，实测另记）。

### 前置内容审查（preproduction）

新论证的整套生产在进入真实视觉生产前需要内容审查，对象是任务适配、论证、证据边界、页面覆盖、推进与用途预算。默认要求 `independent_model_or_human`：独立模型必须有可核对的独立执行收据，人类必须有身份证据；作者自审（host_self）只有在用户明确接受降级且记录了范围与原因时才成立，且不影响交付前的人类专业复核政策。能力不存在时如实返回 `needs_reviewer` 并交出可审阅稿，不要伪造收据。

### 完整稿与浅稿的区别

对照 content-examples 四类完整页例，按用途写全单元格、条件、责任、异常、动作与含义。每个实质页能说明“删掉会丢什么、下一页回答什么”；有用途的总结和教学复习可保留。矩阵各格不能都写“高效”，侧栏解释差异/例外/含义，不仅换词复述主图。

Narrative、Plan 与 Page 表达同一主线，保留事实到来源与 atom/notes 的映射。无收益数据时标假设和测量办法；必要限定在正文，notes 不藏核心论证，制作说明放 internal_only。预算不是加字或缩字的授权。

前审实际读取材料与全稿，按 content-calibration 六组正反例查浅稿。返修记录具体 Page/atom、原句、改句及受影响页；只补 evidence ID、observation 或“更专业”不算改稿。原始稿、首次 Owner 稿与返修分开，不能用精修覆盖首次失败。

### 从完整分析到当前页稿

argument 写出中心解释/判断、实质支持和相应限定，不能只列章节标签。page_copy 在已有论证上完成全部客户可见内容：表头和每个单元格、案例原值与动作、流程触发/责任/异常/交接、指标分子分母/期间/单位/用途。选用表格、bullets、nodes/edges 或段落承载真实关系；图的箭头和表格归属也是内容，不留“此处放图/结论”给设计补写。

把每个事实与限定接到真实 source/version/locator，再接到承担它的 Narrative node 和 Page atom；可见来源只是其中帮助读者核对的简洁部分。Plan 记录当前页职责、独特贡献、映射和承接，不再复制正文。检查“删掉这一页会丢什么、下一页回答什么”，合并没有贡献的重复页；结尾回顾和培训重复如果帮助完成任务，应保留。一个实质页的主图与侧栏分别承担关系和解释/例外，不能只换词复述。

按 `content.visible_atoms` 的真实 atom_id 覆盖所有标题、正文、表格列/单元格、节点标签、脚注等，不能用显示页码或自造 block ID 代替；导航 atom 可空映射，不能给它编事实来源。来源定位存在不等于来源支持主张，前审需实际核对。变更正文时更新该页关系映射和受影响 notes；不越过本次 Scope 重写其他页。把相关但越界的问题列为 scope gap。

### 篇幅、讲述与阅读边界

- Plan 的 `page_budget.exact` 和 `max` 仅来自用户或有效委派，`target` 是可解释调整的软目标；“约 15 页”不变成恰好 15 页，也不为填上限补无用页。
- `time_budget` 分开口播、互动与总时长；逐页估计说明假设并相加，不能把页数乘固定值宣称实测。内容放不下时去重复、重组必要表达或在授权内拆页；硬上限冲突用 Plan 本地 issue/tradeoff 指明取舍，不删核心限定、不缩成不可读小字、不临时跳过必要内容假装通过。
- 沿用有效 `speech_policy`：现场讲解未另定时 cues；独立阅读默认 none；明确逐字稿才 verbatim。provided 原注按本次指令保留，none 不强制新增 notes。speaker-only 只写固定 Page Ref 的口播/段映射，不顺便改正文、页序或视觉。
- live cues 补讲述提醒与停顿，不能藏上屏必须知道的事实/限定。read_alone 的必要论据、比较和限制完整可见；mixed 分别说明现场讲述与独立阅读的用法/投影，版本化保存需要的差异，不把同一稀疏现场页直接说成阅读稿。只在用户明确要求时长时做合理篇幅估算并标明；真人试讲计时仅在另行明确要求时适用，不能把估计写成实测。
- speaker_notes 是口播真源，`speech_segments` 按 Unicode codepoint 半开区间覆盖全部文本并标 cue/verbatim 与估时；讲稿导出或 PPTX notes 必须实际生成、按 page_id 回读后才能声明交付。Page 有 notes 不等于文件已带备注。

已确认全文沿 fidelity：保留原稿主线、页面职责、必要表格和限定，`imported_mapping` 可没有 Narrative，未知映射如实记录；不为填合同字段补造论证/确认。已有用途和“不需要讲稿”等决定继续适用，不重新问一轮受众/口播。改变受众、中心主张或说服结构才回新论证流程，并先核对授权范围。
