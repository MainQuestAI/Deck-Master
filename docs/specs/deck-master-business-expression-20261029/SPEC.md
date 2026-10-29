# 商业表达能力迭代总方案

> 状态：开发输入草案；本次仅整理文档。逐卡入口与唯一执行状态见 [README](README.md)。

本轮大版本聚焦 DeckMaster 的商业内容加工能力：从讲述者的具体任务出发，理解需求和产品边界，提炼能够展开的业务框架，并使它贯穿正文、场景、讲稿和演示提纲。排版与新输出引擎安排到大版本之后。

建议沿现有 Narrative、内容计划、页面、讲稿、提案采用、内容审查和输入修订体系增量开发。先验证内容效果，再扩充协议与作者工作流。整个大版本分为 I0 至 I3 四个内部迭代，共 D00 至 D08 九张主开发卡，另保留一张有条件启动的表格材料入口卡。

# 基线与证据边界

设计依据为 2026-10-29 的产品讨论与 Space 方案。本次重新 fetch 并核对远端 main 为 `ce4ef8b204dd5033019364ce44979adac7f4243b`，与原方案相同。已静态复核方法选择与冻结、阶段指令、依赖切片、影响分析和审查派发。原讨论中的合成探针是历史观察，本次未重跑，也未执行真实 Host 内容生成或专业作者评审。具体核对见 [BASELINE.md](BASELINE.md)。

下述 Narrative.v2 与能力命名属于待 D00 验证后、D01 冻结的设计提议，尚未成为运行合同。样本规模和数值门槛是候选目标，费用与评审安排尚未冻结。功能开发尚未开始。

核心结论有三项。

1. 既有方法投入可以复用。当前有 67 条注册资源，其中 10 张编号方法卡为 M01 至 M10；资源选择、依赖展开、冻结和读取已经实现。[S24]

2. 当前缺口集中在商业任务主导、业务框架的明确承载、方法调用与成果之间的对应，以及策略改变后的内容重组。已有机制不能简单等同于这些效果已经稳定成立。

3. 本轮应把方法库接成作者可用、成果可审查的内容加工过程。继续增加方法数量、另建语义系统或先改排版，都不能优先解决这个问题。

基线来源：[主线提交][S01]、[方法选择与冻结][S02]、[内容阶段指令][S03]。

# 产品目标与范围

## 本轮核心目标

帮助解决方案作者针对不同商业任务，从需求与真实产品能力中提炼有价值的业务主张和组织框架，完成有明确取舍、可以展开、符合技术边界的商业表达。

首次提案与竞标作为首批完整场景。同一份会员系统材料，应当能够因任务不同形成不同主线：首次提案突出业务改善、改善机制和具体使用；竞标突出需求理解、业务回应及有事实支持的适配与差异。场景标签只提供线索，实际取舍由本次已经形成的共识、需要争取的判断和作者指令决定。

“钱、事、酒、账”作为业务提炼能力的标杆。它要求框架可以从简洁名称展开回需求、能力、场景、边界和演示。没有原始案例材料时，不推定四个词的具体审核规则，也不把它当成已经建立的测试样本或所有项目的标准答案。

## 同一材料应当怎样产生不同 deck

以下是行为设计示例，不代表当前项目已经验证这些输出，也不替代真实会员系统需求和能力材料。

| 判断 | 首次提案 | 竞标 |
| --- | --- | --- |
| 作者本次要讲清什么 | 会员经营能改善哪些具体业务环节，系统怎样参与，人员怎样使用 | 我们如何理解本次需求，方案如何回应，哪些适配与差异有事实支持 |
| 默认已知 | 不默认客户已经理解会员管理的业务意义 | 以招标要求和前期共识为准，避免重复已经达成一致的基础介绍 |
| 展开重点 | 现状中的具体问题、能力介入点、业务动作与改善机制、使用场景 | 关键需求与约束、方案响应方式、真实能力和交付安排、关键取舍 |
| 应当减少的内容 | 无关竞品比较、内部技术堆叠、没有实际依据的收益数字 | 无必要的品类教育、无法回应招标要求的泛化价值页 |
| 框架成立的要求 | 每个主题可以展开成具体业务动作，并说明为什么可能带来改善 | 每个主题能回应一组真实需求，说明如何做到以及相关边界 |
| 仍须保留的约束 | 不能把人工辅助写成已经自动完成，也不能把机制推导写成已实现收益 | 没有对手材料就说明自身适配，不能凭空声称优于某个竞争方案 |

两种任务共享事实与产品能力，却可以有不同的中心主张、内容分组、页序和省略项。系统必须能解释这次为什么这样组织。如果任务标签发生变化但开场、重点和正文几乎未变，仅换了“价值”“优势”等标题，则视为核心能力没有成立。

## 必须交付的内容能力

- 商业任务驱动的策略提案：本次作者要表达什么、争取什么判断、已经有哪些共识、重点与取舍是什么。

- 可展开的业务框架：允许以业务名词命名，但有定义、关系、需求与能力对应、场景和必要边界。

- 框架贯穿成品：概览、章节、正文、案例、口播及随页演示提示有一致主线。

- 策略改写：作者改变商业任务或重点时，系统能说明影响，重组内容并保留仍然有效的部分。

- 可读作者交付：即使只完成策划，也能带走固定版本的策略、框架和计划；完整稿则附正文、既有讲稿与演示提纲。

## 本轮范围边界

本轮复用既有生成和渲染链路。新 HTML 引擎、企业 PPT 母版无损编辑、Office 原生图表、全面视觉改版、自动操作外部 demo、通用多分支版本平台、跨 Host 自动执行平台安排到后续。

涉及内容正确性或版本一致性的既有渲染缺陷仍按必要回归处理，但不以新增版式或视觉风格作为本轮成果。

# 现有代码核对

以下为固定基线的设计映射；本次已复核的调用点见 BASELINE，其余实现细节在对应卡开工时核验。

| 领域 | 当前已经具备 | 本轮实际增量 |
| --- | --- | --- |
| 作者任务 | Document.task 已有 brief、audience、scenario、existing_decisions；CLI 和输入更新能够传入场景 | 把原始任务提炼成明确策略，成为方法选择、框架和内容取舍的依据 |
| 内容语义 | Narrative.v1 保存 communication_job、中心节点、关系、限定、问题和业务选项 | 增量承载讲述者策略和可展开业务框架，继续维持单一语义来源 |
| 分阶段生产 | framing、argument、page_copy、speech 与 input_revision 已有独立职责 | 在已有阶段中落实策略、框架、展开、贯穿与重组，不再建立平行流水线 |
| 候选与采用 | 有真实 Narrative 候选阅读、比较、方向决定及固定提案采用 | 比较业务组织方式和取舍，选定框架形成不可变正式提案后采用 |
| 内容对应 | Plan 页职责引用 Narrative 节点；页面可见内容和讲稿也有节点及来源映射 | 用既有节点对应传递框架，增加覆盖与贯穿检查 |
| 内容审查 | 已有零页面大纲审查和完整稿件前审，含身份、固定材料、发现及修复链 | 在现有审查单位中加入策略适配、业务框架展开和全文统领检查 |
| 变更与恢复 | 有输入修订、作用域、版本、原子采用、失联恢复及迟到结果保护 | 增加商业任务与框架的语义影响，避免把来源未变解释为内容无影响 |
| 讲稿与交付 | 已有 cues/verbatim、估时、独立讲稿 JSON/TXT 及备注导出 | 补作者策略与框架交付视图；演示提纲沿计划和讲稿派生 |

依据：[任务输入合同][S04]、[Narrative 合同][S05]、[内容生产][S03]、[计划映射][S06]、[作者主线界面][S07]、[大纲审查][S08]、[完整内容前审][S09]、[现有导出][S10]。

## 六个决定本轮开发重点的发现

第一，任务入口和方法指引仍偏向受众变化。framing 指令要求建立受众变化目标；M01 首先询问读者应能回答什么；M08 从受众卡点选叙事。商业任务虽然可以放进自由文本，但没有稳定成为主导策略。应联动修改入口、方法、阶段指令和审查要求，不能只换输入提示语。[S03]、[S11]、[S12]

第二，默认 framing 和 argument 读取 source-reading、content-methods、content-examples、method-selection，并不自动选入 M01 至 M10。Host 可以显式选择，Skill 也要求自主判断，因此不能说用户必须手选卡。缺的是稳定的任务驱动选择及成果对应。[S02]、[S13]

第三，方法库内容已接近本轮目标。M02 要求尝试两种有意义的拆解；M07 要求从事实形成上位判断并反向核验；M08 有真正的候选路径比较；M10 有语义取舍。这些应复用并校准。[S14]、[S15]、[S12]、[S16]

第四，业务主题与事实命题需要分开。M07 当前要求去掉只有分类名称的节点，适合论证组织；业务框架却可以使用“钱、事、酒、账”这样的名词。新版本应要求名词背后有定义、关系和内容映射，避免强制把每个主题改成长句结论，也避免允许空口号过关。[S15]

第五，标准 outline 和 preproduction 审查调度没有传入 selected_resource_ids。前审确实存在，并且读取完整材料和稿件；但若要按本次业务框架检查具体方法成果，需要接通正式审查选卡入口。不能在已冻结任务上私加方法。[S08]、[S25]

第六，现有影响分析主要根据变化来源推导节点和页面。只改变合法 task.scenario 的合成探针，会记录任务变化与 has_impact=true，但 affected_pages 为空、其他页进入 unaffected_pages。这不证明 Host 不会重写，却说明该投影不能直接承担策略切换的语义影响判断。新策略的依赖还必须覆盖实际使用的场景与既定共识。[S17]、[S18]

另一个纯函数探针表明，单个“会员系统赋能业务升级”中心节点、零关系和空候选可以通过结构校验。这不是结构校验的代码漏洞；它说明业务提炼是否成立仍须进行语义审查，不能由图连通、字段齐全或工程通过替代。[S19]

# 方法卡如何进入新框架

## 方法改造清单

| 方法 | 本轮用途 | 改造方式 |
| --- | --- | --- |
| M01 受众与问题界定 | 识别作者商业任务、主张、已有共识和目标 | 重点修订：讲述者任务先行，受众视角用于表达校准 |
| M02 结构化分析 | 拆需求、业务对象、过程、责任与关键矛盾 | 扩展无数字的业务结构提炼，保留不同切法与回查 |
| M03 主张与理据 | 约束能力、差异、承诺和推导 | 复用；内部核验不自动变成满页证明 |
| M04 作用机制 | 解释怎样改善、为什么改善、使用条件 | 首次提案按需重点使用；机制说明不等同收益承诺 |
| M05 选项与价值 | 同条件说明适配、差异和方案取舍 | 区分竞标表达与中立选型，不编造竞争对手资料 |
| M06 不确定性 | 处理会改变方案的关键假设与交付边界 | 按需使用，不让首次提案默认变风险报告 |
| M07 综合与抽象 | 提炼业务框架，并展开回真实方案 | 核心扩展：业务主题与事实命题分开，增加反向展开 |
| M08 叙事与比较 | 按商业策略组织开场、顺序、取舍和演示 | 重点修订：任务主导，受众校准，候选必须实质不同 |
| M09 示范与迁移 | 在需要时说明具体场景怎样使用 | 按需使用，不把商业提案统一改成培训 |
| M10 语义压缩 | 保留、合并、下放和删除内容 | 复用并连接本次任务，评实际内容而非字数 |

本轮不新增同义 M11 或另建“商业方法百科”。四个 Skill 继续共用一份 canonical 方法来源。Humanizer 作为可选表达修订资源，不承担策略或业务抽象的主要职责。

## 调用机制

方法选择发生在正式任务冻结之前，分清初始入口与后续阶段。

1. Host 驱动创建时，先用无 Task 的方法入口读取选用指引，基于已给出的 brief、场景和必要材料选择资源，再传入 create 的 selected_resource_ids。

2. 纯 Web 新建、尚无 Host 策略判断时，新版业务策划任务使用最小 framing 起步组合，至少包含更新后的 M01 与必要来源/协议规则。framing 只需识别商业任务、表达目标、已知边界和未决点，产出供后续判断的提案；不提前要求形成成熟业务框架，也不代表策略已经生效。初始入口不宣称已经完成智能组合选择。

3. argument 派发前，由 Host 根据已有 framing 提案、商业任务和具体难点，以合法的 deck-content 职责选择、读取 M02、M04、M07、M08 等。竞标需要时加入 M03、M05；M06、M09、M10 按实际任务使用。组合是可解释建议，不能固定全卡必跑。

4. outline 和完整前审派发前，根据被审对象和待检问题独立选择最少必要资源。评审可查看作者的应用说明，但不只读取作者自述，也不机械继承全部作者卡。

5. Runtime 继续校验角色、阶段、范围、依赖和资源 hash，冻结任务。冻结后不追加文件；改变依据继续沿既有正式退役与重派机制。

现有 create 会立即派发并冻结首个任务，不能写成“创建后再给首个任务追加卡”。新版起步包必须由新任务能力或合同版本在 freeze 时明确选择；当前 method_ids_for 不能识别商业策划能力，不能直接替换全局 framing 默认，也不能只靠界面文案区分。旧 Task 继续读取各自原 manifest。首版不以新增 prepare 状态机为前提；如果后续实测证明必须先导入快照再选首批资源，另行设计正式两步协议。[S02]、[S20]

Host 是执行环境，不等于始终以 deck-master 职责读取资源。M02 至 M07 当前只允许相应内容/审查职责，M01 至 M10 均不在 speech 阶段范围。业务场景、演示顺序和组织方式在 argument/plan 中形成，speech 根据已采用结构写讲稿；纯口播修改继续保持局部范围。[S24]、[S26]

审查选卡必须打通 outline/preproduction dispatch、native review 及其调用入口到冻结任务的参数传递。调度方可以在派发前读取只读待审 packet/status，再按实际审查单位和版本选择。复用 pending/recovery Task 时沿用其原 manifest，改变选择须正式退役重派。独立性继续由独立执行及 receipt 机制保障。[S25]、[S27]

方法应用说明应回答“用来处理哪个问题，改变了哪个主张、框架部分、取舍或正文”。只保存指向冻结 Task 和实际结果位置的轻量引用，不复制卡全文或新增平行方法账本。资源可读、已选择、Host 已接手、已有成果、已被专业审查是不同事实；任何一项都不能自动推出下一项。

## 文档与上下文减负

当前 framing/argument 默认四文件合计 41,565 bytes，其中 content-examples 为 19,036 bytes。这是原始 UTF-8 字节量，不是 token 或耗时测量。

先验证按任务选用方法与案例的内容效果，再调整新版任务的默认上下文：协议和来源规则保留一处权威说明，必要时选择相关案例；没有匹配案例时不强制携带。案例的 input、after、walkthrough 仍按 catalog 展开完整依赖，不只统计入口文件。不能只从一个 selector 移除 content-examples 就视为完成，还要核对角色入口和方法中的重复引用。旧任务保留原 manifest 和来源版本；不通过删除旧依赖来实现减负。

验收报告实际返回字节、调用数、时长与内容效果。不预先承诺降低 50% 或提高某个百分比质量。

# 实现框架与版本决策

## 单一语义来源

新增 Narrative.v2，保留既有中心节点、节点关系、来源、限定、未决项、maturity 和前版本引用。原始作者指令继续保存在 Document.task 的既有字段。Narrative 保存对指令形成的策略提案，并绑定这些输入依据。

最小增量分为三部分。

**商业策略。** 保存本次业务任务、作者目标、已有共识、本次主张所指中心节点、重点、主动省略及解释/支撑责任。场景允许 custom；不把所有任务强制归为首次提案或竞标。

**可展开框架。** 保存拆解依据、业务主题名称及含义、主题关系、需求/能力/场景/约束节点引用、内容的主线/支撑/省略安排和已知缺口。原始事实继续由节点与来源承载，不再复制需求、能力和材料全文。

**方法作用引用。** 仅指向已冻结方法及实际产物位置，帮助作者与评审判断方法是否产生作用。生成者的自述不能充当独立审查通过。

Plan 已有节点引用，Page 与讲稿已有对应，可派生主题覆盖哪些页；初版不必为重复保存主题 ID 而全面升级 Plan 和 Page。

## 最小协议增量

保留 compose.v2 的阶段和结果信封、ContentPlan.v2 和 Page.v2。新增 Narrative.v2、新协商能力及对应 writer floor。建议能力名 business-framing.v1，最终命名与注册需要 Codex 核验。

当前 compose.v2 的 Narrative payload 仅要求 object，具体内容由接收器校验，因此无需仅因产品大版本而升 compose.v3。新任务冻结必须支持 v2 的要求：旧 Host 缺能力不得承接，声明支持却返回旧结构也必须拒绝。[S21]

所有严格读取点同时更新，包括 models 版本派发、content_production 接收与采用、content_insight、内容审查、依赖消费和可读导出。不能只加 schema 文件。

旧项目读取不补造商业策略、旧 Task 不补签新方法、新语义首次持久化才提高 writer floor。失败、取消和回退保留此前已采用版本。

## 候选与采用

framing 界定任务并记录作者已有方向，业务框架探索与实质比较主要在 argument 阶段完成，避免在最小起步包中提前要求成熟框架。作者已有框架时直接校验、展开，不强制制造替代候选。

选择完成后，argument 形成包含确定框架的不可变 Narrative 提案，再通过既有 direction 决定与采用机制写入。已有有效委托可以减少重复确认，但不能修改旧对象的 selected_frame_id 后继续沿用旧 Ref 和旧决定。

零页面策划还要区分“已有完成的提案”和“已采用为当前版本”。当前 plan_only 可以在产出 Narrative 和 planned Plan 提案后完成并关闭原请求；不能在已关闭请求上追加决定。[S30] 作者选择“采用并审查此策划”时，复用现有 start_request 发起只覆盖 narrative、plan、review 的后续请求，引用现成结果，不重新生成。有效 direction 决定须覆盖所采用的两个具体 Ref 及相应 projection；先采用 Narrative，再以最新 revision 采用与它绑定的 planned Plan，随后进入 outline review。两次采用之间重新检查决定有效性；若第二步失败，保留可恢复结果且不派发 outline，不混入旧 Plan。[S08]、[S28]、[S29]

导出候选本身不要求先采用；作者包标明未采用/未审查状态，也不通过导出暗中创建请求或采用内容。

原 Space 方案记录的合成服务级核对曾走通“旧 plan_only 完成关闭—新有界请求—采用 Narrative—采用匹配 Plan—outline 读取两者”，全程保持零 Page，未新增生成 Task。这支持复用现有后端路径；新版 Narrative.v2 适配及作者界面的实际体验仍需要 Codex 核验。

现有 live/read 双版本共享固定 Narrative，首提与竞标不能伪装成这两种版本。配对评测使用同源独立任务；项目内策略变化走正式输入修订与新 Narrative 提案。[S22]

## 内容与演示的归属

随页演示提纲从有序 Plan 页职责、Narrative 场景与能力节点、已有 Page 讲稿提示派生。策划阶段只有计划职责时，输出拟展示场景和要说明的内容；有正文后才附对应口播与随页提示。它不成为第三份可独立编辑的内容真源，也不负责实际操作外部系统。

需要展示的能力未确认时，标记为拟展示或待确认，不能因写出了提纲就声称 demo 可运行。作者包和客户包明确分开；内部策略、取舍说明、方法应用和材料定位默认留在作者用途。

# 迭代顺序与交付关口

| 内部迭代 | 开发卡 | 主要交付 | 进入下一阶段的条件 |
| --- | --- | --- | --- |
| I0 内容验证 | D00 | 固定材料与任务、小样对照、现有最佳流程基线 | 新方法在预先定义的策略与业务组织问题上有可识别改善，且没有新增关键事实错误 |
| I1 策略与框架 | D01、D02、D03，D06 第一部分 | 作者能输入任务，阅读、比较、修正并采用一套可展开框架 | 真正形成可用策划结果，不能只交 schema、方法文档或后台 JSON |
| I2 全文贯穿与改写 | D04、D05，D06 第二部分 | 框架进入正文、场景与讲稿；策略改变产生影响说明和内容重组 | 完整内容-only 流程可交付，原版本保留，范围不扩张 |
| I3 作者完整流程与发布 | D06 收口、D07、D08 | 固定版本作者包、真实状态与接续、留出效果和兼容报告 | 核心内容指标、边界与工程回归共同满足候选发布门槛 |

D08 的评估设计从 D00 开始，不能等到 I3 才定义“什么算好”。D06 随 I1/I2 提供最小可用界面，I3 做整体收口。D01/D02 在对象和调用边界冻结后可以并行；D03 依赖两者。D04 在框架采用闭合后展开正文，D05 在新依赖语义就绪后实现重编。D07 只消费真实对象，不反向承担内容生成。

不在源码探查阶段承诺固定周数或总代码量。实施估算以各卡的契约影响、真实 Host 小样、兼容回归和人工评审投入为依据。每个内部迭代的出口是可检查的作者成果。

# 验收设计与候选门槛

## 规模和比较口径

建议准备 12 个输入材料包，6 个用于开发，6 个用于留出；在 D00 固定分组并隔离留出材料与任务。每包分别定义首次提案与竞标两个任务，共 24 个任务条件。配对任务共享材料，不作为 24 个独立业务样本解释。

I0 先选 2 个开发材料包，两种任务各做当前基线与新方法小样，单轮为 8 份输出。完整开发集允许迭代，逐次记录真实调用和修改。

最终留出集是 6 包、12 个任务条件。基线与新版各独立生成 2 次，共 48 份输出，即 24 组可比较的结果对。只生成内容和必要作者材料，不为效果评测默认生成 48 套视觉成品。具体模型与费用额度在执行前冻结。

基线使用当前最佳合法流程，不能故意不选卡、不给任务目标或削弱提示。模型、资料、任务、人工投入与调用预算保持可比，额外计算成本单独报告。评审隐藏基线/新版和方法名称，但必须知道原始任务、需求、能力和技术边界。

## 评分与失败规则

每个维度采用 0 至 3 级锚点：0 为明显不成立或偏离；1 为存在方向但需实质重构；2 为作者小改可用；3 为业务具体、结构有解释力且可直接展开。维度为策略适配、业务框架、反向展开、内容取舍、全文贯穿；事实与技术边界作为单独硬检查。

严重失败包括：编造已实现能力或竞争事实；扭曲关键需求与约束；框架无法映射实际内容；两种商业任务只换措辞；作者明确限定范围被突破；旧结果或其他候选内容混入当前产物。严重失败不能由平均分或美观分抵消。

建议候选发布门槛如下。这些是待评审冻结的产品目标，不是本轮已测结果，也不是普遍效果承诺。

- 24 份新版留出输出均无上述严重失败，尤其是关键需求、能力、技术边界和版本混用错误。

- 至少 20 份新版输出，在五个内容维度上均达到 2 级以上。

- 24 组配对中，至少 16 组获得专业评审多数判定“新版整体更好”；首次提案和竞标分别至少 8 组，避免只改善一个任务。

- 没有一类核心任务在策略适配或保真上形成系统性退步；失败逐项保留并说明。

- 讲述者实际采用情况、实质性重构投入及目标信息传达作为辅助指标，报告分母和方法，不换算为中标率提升。

由至少两位熟悉解决方案工作的评审独立评价；分歧由第三位结合原始任务裁决。若尚无业务作者或真实材料，先报告合成和模型层面的验证状态，不宣称完成专业商业验收。

# 文档与执行交接

本套件以本文件作为活动总方案；task-cards/ 保存逐卡实施与验收定义，execution-index.json 保存唯一执行状态及验收状态，BASELINE.md 保存本次核对依据。方法内容仍在原 canonical references；运行合同仍在 resources/contracts。开发卡引用权威定义，不把同一合同复制到多份说明中。

每张开发卡关闭时记录：固定提交、真实变更文件、已执行的工程检查、内容样本与评审、未执行项、剩余风险。资源工程通过、结构探针通过、模型审查和业务作者认可分开记录。

提交顺序按依赖推进：先 D00 的基线与案例，再 D01/D02 的合同与调用，随后 D03 的框架与采用，D04/D05 的全文和策略改写，最后 D06/D07 的流程收口及 D08 的候选发布记录。每个内部迭代保留可运行、可阅读的成果，不把所有 UI 和真实内容验证推迟到最后。

对执行型 AI 的首条任务应是：重新核验 main 与本方案基线差异，定位既有机制，完成 D00 的材料、任务、预算和验收设计；依据小样结果决定 D01 的具体落点。方法文本、schema、引用数或测试通过数量本身不构成本轮内容价值验收。

# 固定代码依据

主要核对入口：[任务输入][S04]、[Narrative][S05]、[内容生产][S03]、[方法选择与冻结][S02]、[方法目录][S24]、[角色与依赖检查][S26]、[大纲审查][S08]、[完整内容审查派发][S25]、[原生审查调度][S27]、[影响分析][S17]、[依赖切片][S18]、[作者主线界面][S07]、[现有导出][S10]。

[S01]: https://github.com/MainQuestAI/Deck-Master/commit/ce4ef8b204dd5033019364ce44979adac7f4243b
[S02]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/method_resources.py#L117-L298
[S03]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/content_production.py#L144-L284
[S04]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/resources/contracts/document.v1.schema.json#L33-L89
[S05]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/resources/contracts/narrative.v1.schema.json#L58-L324
[S06]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/resources/contracts/content-plan-input.v2.schema.json#L22-L147
[S07]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/resources/static/v2/insight-reading.js#L24-L111
[S08]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/outline_review.py#L13-L128
[S09]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/content_review.py#L219-L283
[S10]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/exports.py#L252-L378
[S11]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/skills/deck-master/references/methods/M01-framing.md#L12-L32
[S12]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/skills/deck-master/references/methods/M08-narrative.md#L12-L37
[S13]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/skills/deck-content/SKILL.md
[S14]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/skills/deck-master/references/methods/M02-structured-analysis.md#L12-L35
[S15]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/skills/deck-master/references/methods/M07-synthesis.md#L12-L35
[S16]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/skills/deck-master/references/methods/M10-compression.md#L12-L35
[S17]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/content_impact.py#L127-L172
[S18]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/dependency_slices.py#L18-L58
[S19]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/models.py#L438-L511
[S20]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/service.py#L155-L202
[S21]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/resources/contracts/compose-result.v2.schema.json#L62-L114
[S22]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/variant_requests.py#L1-L25
[S23]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/resources/static/v2/material-uploads.js#L1-L12
[S24]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/skills/deck-master/resource-catalog.json
[S25]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/content_review.py#L451-L502
[S26]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/resource_catalog.py#L122-L153
[S27]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/native_review.py#L344-L407
[S28]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/collaboration.py#L519-L609
[S29]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/content_production.py#L1809-L1927
[S30]: https://github.com/MainQuestAI/Deck-Master/blob/ce4ef8b204dd5033019364ce44979adac7f4243b/src/deck_master/content_production.py#L699-L716

以上固定来源用于定位本轮判断。实施时的最新代码、具体调用路径、测试与专业效果仍需要 Codex 核验。
