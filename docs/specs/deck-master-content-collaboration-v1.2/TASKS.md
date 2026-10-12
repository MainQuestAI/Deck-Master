# 开发任务卡 T00–T08

本文件是实施顺序与交付清单，**不是本轮开始改产品的指令**。收到后续实施任务后执行；每卡只关闭其指定 AC。原 PR106 的 R1–R6 已由这些任务替代，不同时维护两套实施完成状态。

所有拟新增模块/字段/命令名以 [CONTRACTS.md](CONTRACTS.md) 为准；当前基线的代码和测试路径用于定位。新增测试文件名是推荐落点，可按仓库组织调整，但 AC ID 与唯一 owner 不得丢失。

## 1. 卡片与验收责任

| 卡片 | 主要交付 | 依赖 | 唯一负责关闭的验收 |
| --- | --- | --- | --- |
| T00 | 固定基线、四材料包、专业产物原型与正反评价锚点 | 无 | AC-B01–B03 |
| T01 | 严格 professional 谓词、统一交付解释、修正错误正例 | 无，可与T00并行 | AC-P01–P03 |
| T02 | 内容/协作/审查协议、唯一权威与兼容迁移 | T00 | AC-C01–C04 |
| T03 | 分阶段内容生产、Writer方法、前置审查与返修 | T02 | AC-M01–M05 |
| T04 | 请求路由、统一 eligibility、范围/预算/晚到控制 | T02 | AC-R01–R07 |
| T05 | 无旧蓝图的初始设计、覆盖与限定样页 | T03/T04 | AC-D01–D03 |
| T06 | cues/verbatim 投影、PPTX备注、编译依赖与回读 | T02/T03 | AC-N01–N04 |
| T07 | CLI/Studio/聊天统一、四Skill安装与恢复 | T01–T06 | AC-H01–H03 |
| T08 | 真实Host、用户、听众、文件证据与发布判定 | T07 | AC-U01–U05 |

依赖表示可关闭条件。独立的设计与脚手架可以提前准备，但不能在依赖不满足时启用生产旁路。T04 的纯解释器可以先 shadow 对比；新写入项目的正式 enforcement 必须一次覆盖完整操作清单，不能让“逐步接入口”成为发布时的可绕过窗口。

每卡结果提交到同一验收索引，至少包含实施 SHA、输入/输出哈希、实际执行环境、命令和返回值、AC结论、限制及失败修复。仓库中的证据只能包含合成或获许可的脱敏材料；实际客户资料不因验收需要而公开。

## T00｜先验证可审查产物，再冻结字段

**目的**：证明前期工作能产出值得用户判断的内容和决定卡，防止先完成通用 gate 再给坏内容填表。

**输入**：本包、PR106固定审计、Q1–Q4、当前 AGENTS 与 main/PR head。

**实施工作**：

1. 核实远端 base/head、工作树与实际已安装 release；比较本包关键源码路径是否变化。保留来源/环境差异，不覆盖用户修改。
2. 将 EXAMPLES 的固定源文本、任务答案、变更事件与预期行为保存成可重用合成输入。Q4 分开普通单元fixture与真实工程产物；不得用伪图片/PPT给Host或工程验收兜底。
3. 在不先新增 Runtime 合同的情况下，产出理解稿、Narrative全文投影、页面职责/预算、完整逐页稿、cues/verbatim分支、设计可行性和决定卡。
4. 培训/决策/研究三类各准备正确候选、F0/F1反例与具体修订；验证事实、规则、推论、提案的边界。
5. 两位独立评价者先单独判断“哪里错误、依据何在、下一步是否可做”，再裁决分歧。不要求只有一种措辞；所有明确关键反例必须被发现，正确限定不能被误删。
6. 若规范字段无法容纳必要产物，先修改本包相应条款；不把产物压缩成现有字段以便进入T02。

**交付**：固定样例manifest、完整原型、评价差异与裁决、更新后的输入/输出边界、基线记录。推荐证据目录为 `docs/reports/content-collaboration-v1.2/`，仅在实施时建立。

**退出**：AC-B01–B03 全部满足；特别是“只看字段齐不齐”的原型不得进入合同冻结。此关证明可审查性，不证明真实制作或用户效果。

## T01｜单独修复人类专业交付语义

**目的**：修复现有合同已明确、且不依赖 Skill 选型的缺陷。

**主要落点**：`src/deck_master/exports.py`、`handoff.py`、`review.py`、`cli.py`、Studio交付投影；`tests/rebuild/test_export.py`及handoff/readiness测试。

**实施工作**：

1. 提取统一 delivery 专业证据判断；禁止 `status != fail` 和 `kind==professional_use OR human` 作为放行条件。
2. 原开关true时要求正确kind、final阶段、显式pass、相符人类身份与证据、精确当前文件与必要依赖、无有效阻断项。独立模型不是人类。
3. 导出、handoff、final-readiness返回同一政策结果和缺口；工程通过仍单独展示。保留符合条件的审阅用途导出。
4. 修改 `_review` 测试helper，调用者显式指定 reviewer/执行证据/观察；删去 `seed="human"` 仅改变名称却仍生成host_self的错误正例。
5. 经正式提交入口建立身份、状态、kind、版本、缺依赖、空观察、旧pass被新fail覆盖的正负矩阵。最初可用受信适配器的隔离协议fixture验证谓词；这只能是L1，不能假称真实人类已阅文件。

**分阶段边界**：T01-min可先修错误谓词和三入口一致；当真实身份通道未具备时，强人类政策应返回具体缺口，不以自报actor补正例。T02/T07补齐正式receipt协议与适配器，T07/T08完成实际通道集成。实现者不能为独立交付T01而削弱最终身份条件。

**退出**：AC-P01–P03；引用正例的实际证明层。T01不负责证明内容有效，也不把默认false改成全用户强制人工审阅。

## T02｜最小合同与迁移

**目的**：建立专业产物、决定、授权与旧能力的唯一权威对应。

**主要落点**：`resources/contracts/`、`models.py`、`content_plan.py`、`store.py`、`operations.py`、`editing.py`；新增专业对象/协作解析模块；`tests/rebuild/test_models.py`（若仓库测试组织不同使用相应语义校验测试）、`test_store_transactions.py`、`test_content_plan.py`及新迁移测试。

**实施工作**：

1. 按CONTRACTS注册Narrative、ContentPlan新版本、compose分阶段协议、Review扩展、Decision/Authorization与唯一collaboration区；复用Ref/CAS/journal，不创建独立批准数据库。
2. 明确Narrative语义、Plan页面映射/预算、Document实际页序、Page正文/notes、recipe有效设计的唯一写入点。字段齐全与语义质量分别验证。
3. 实现决定来源/可信等级，禁止客户端提交assurance升级；Host转述、默认值、导入未知、已确认文档、委派、真实用户事件可区分。
4. 实现registered依赖切片与权威投影；所有必须依赖由service补全，不能让调用者省略。不要把全部collaboration hash塞进content_identity。
5. 实现迁移describe/apply与writer边界。读取旧项目不改字节，apply单事务，不造历史批准；旧任务晚到仍结算但不能接纳为新结果。
6. 内容restore保留当前权限、暂停/撤回、费用和minimum_writer。未知调用不能清零。

**退出**：AC-C01–C04；把版本矩阵与原子边界的测试结果交给T04/T07。完整行为不得仅依靠schema通过。

## T03｜专业内容与写作，不再一次压平

**目的**：从材料形成适用的论证、可讲/可读的完整稿件和可检查的映射。

**主要落点**：`service.py`的compose dispatch、`tasks.py`结果接纳、`content_plan.py`、`content_ops.py`、`method_resources.py`、`review.py`；`skills/deck-master/references/content-methods.md`、`source-reading.md`、`content-examples.md`及新的Content职责方法。公开Skill壳与安装集成归T07。

**实施工作**：

1. 按Task phase/compose协议分开理解、论证与篇幅、完整逐页写作、仅口播、input revision。framing任务不得以完整Page结果直接进入生产。
2. Content方法明确：先辨材料用途/权威与冲突，建立受众变化目标；按任务使用论证、说明、步骤或数据解读方法；写出实质全文，再批判和返修。
3. 输出Narrative与Plan后给用户真实方案卡：中心任务、证据边界、取舍、每页职责、预算和风险；已获委派的选择记录来源而不重复请求。
4. `write_only`、`speech_only`、`content_full`分别约束写集合；确认稿采用后不得强迫重建方向。用户只问稿件时按时返回稿件，不进入生图。
5. 将content preproduction review前移。独立审查输入包含材料、任务与完整稿件；检查员不得只审作者摘要。不能满足默认独立要求时返回needs_reviewer与审阅稿；只凭明确降级决定使用host_self。
6. 建立claim→证据→Page/atom、notes→Page/argument映射检查；事实源变更后先做影响分析。设计为密度提出改动须交回内容owner。
7. 修正含无依据因果的示例。“直接减少往返”必须有适用条件或作为待验假设；不把所有材料套销售叙事。

**退出**：AC-M01–M05。至少展示一次关键论据反例被具体返修，而非只添加一条review observation。

## T04｜所有执行入口共用资格与范围

**目的**：让用户的本次范围、决定、委派与停止事实真正控制生产。

**主要落点**：拟新增`eligibility.py`/协作service；`service.py`、`tasks.py`、`changes.py`、`candidates.py`、`styles.py`、`content_ops.py`、`editing.py`、`pipeline.py`、`exports.py`与各HTTP/CLI适配器。

**实施工作**：

1. 列举所有公开业务写操作、派发、领取、reserve/begin、accept/adopt、compile、restore、policy更新和delivery；建立“入口→同一service→必检action”的清单。
2. 先实现纯eligibility解释器，返回具体产物、缺决定、责任与恢复方式；不会因查询而创建任务/花额度。
3. 新请求与旧后台请求隔离。只试样页、局改、仅写讲稿、review_only不能借旧full_deck授权扩张；明确并行委派才允许后台推进。
4. execute grant绑定固定页集合/层/最大调用/候选数；delegate可在约束内具体化，但子授权预算不复制。每次外部调用继续用已有allowance账本。
5. reserve、begin、结果接纳和采用分别检查当前控制。最后一次合法调用消耗完预算后可接纳其结果；预算耗尽只阻止新增消费，撤回才阻止该授权下尚未采用的结果。
6. user_stop、请求pause、task cancel、authorization revoke语义分开。普通continue不扩大范围、不清除拒绝、不复活撤回；旧结果只记录事实。
7. 以当前control+选定artifact snapshot判断历史delivery/restore；旧文件和旧宽松policy不能绕过新撤回。
8. 接纳在同一CAS中验证真实write set；违反scope不能部分改Page。结算已发生调用的事实与采用产物分开，不能以拒收为由丢掉成本。
9. 严格只读审查可在项目外生成报告，不为登记Review而写源项目；通常的项目审阅记录由明确任务范围允许，二者都不自动返修。

**退出**：AC-R01–R07。所有入口的正负行为及失败后“原稿保持、调用如实、下一步具体”均有证据。只测continue不能关闭此卡。

## T05｜初始设计与代表样页

**目的**：无需先生成旧蓝图，即能在本次授权范围内形成设计依据。

**主要落点**：`styles.py`、`visual_styles.py`、style proposal/recipe合同、`changes.py`、`candidates.py`、设计方法与`style-calibration.md`。

**实施工作**：

1. 把初始设计作为现有style proposal的新明确来源：绑定真实代表Page与关系/密度目标，无target旧图时仍合法；不能伪造原图或拿自己的SVG预览充原始blueprint。
2. 在Plan阶段允许无外部调用的版式可行性；在试样阶段消费完整代表页的固定正文。
3. 覆盖清单记录已校准与未校准的高密度、机制、数据或架构页型。数量由风险决定，不固定每稿两三页。
4. 1页请求只做1页；2页已授权请求可完成2个candidate，不在中间伪造采用。默认候选不自动覆盖当前产物。
5. 采用候选、接受palette/density/layout等维度、授权余下页三件事分别绑定。可由一条明确用户指令同时满足，不可由“颜色可以”推导全套。
6. 新密度/页型出现后追加局部校准；已有模板且当前适用可以复用，不反复做品牌问卷。

**退出**：AC-D01–D03。至少有Q4-A的无旧图测试、真实代表内容样页及范围外拒绝证据。文案写“先样页”但create继续全套仍失败。

## T06｜讲稿能进入实际交付

**目的**：让口播生产、页面映射与PPTX备注形成闭环；仅存一个speaker_notes字段不算完成。

**主要落点**：`pipeline.py`、`compiler/api.py`、`compiler/native.py`、输出依赖/trace/readback；Page相关方法和导出投影。保持现有native SVG编译路线，不重做编译器。

**实施工作**：

1. 按speech policy生成/展示cues或verbatim；完整口播文档由有序Page notes投影。scope只含讲稿时不强制创建PPT。
2. 范围含口播并生成PPTX时，默认把逐页notes写入对应PPTX备注，并交付只读整稿投影；用户明确不要嵌入时记录该选择。
3. 编译输入加入page_id与对应notes，保持SVG几何与可见正文权威；备注不能混入幻灯片可见文本或内部prompt。
4. 编译digest与readback覆盖notes。仅备注修改使整稿PPTX与文件级审查过期，不默认重生blueprint；视觉不变的页预览可复用。
5. 重排按稳定page_id重新配对；拆并有明确notes迁移/重写；未知映射阻塞编译或请求处理，不能静默串页/丢失。
6. 尊重用户提供的既有notes。read_alone/none意味着本次不新增口播，不等于允许删除原备注。

**退出**：AC-N01–N04，必须读取实际PPTX notes内容并核对页映射；再在目标桌面/阅读环境检查可用性。不只测试Python入参或Page JSON。

## T07｜统一入口、四Skill与安装

**目的**：使实现的专业职责和控制能在用户实际使用的入口被发现并稳定调用。

**主要落点**：`cli.py`、`launcher.py`、`registry.py`、`resources/static/v2/`、`install.py`、`method_resources.py`、四个`skills/*/SKILL.md`、共享references、`AGENTS.md`、`docs/agent-task-index.md`、`docs/agent-recovery-playbook.md`及现行规范边界。

**实施工作**：

1. CLI/Studio/Host统一create默认与request路由、协作投影、错误返回、下一动作。保持同一个service，不持久化UI自己的批准状态。
2. 用户界面显示实际理解/稿件/样页/差异；停顿卡提供推荐、备选、范围、决定后影响及拒绝/撤回路径。ID/hash放在必要详情，不把实现词汇塞进正常创作流程。
3. 按DESIGN.md及现行OpenDesign规范扩展现有工作面。真实浏览器验证普通、缺口、拒绝、并发冲突、过期结果、窄屏/键盘状态，不能只交静态页面。
4. 实现真实Host能力协商与source receipts。默认traceable如实标来源；verified_user/独立执行能力不足明确阻塞其对应要求。不得把同Host CLI、TTY、hash或普通本地按钮宣称为安全隔离。
5. 四Skill分别有方法、输入、退出产物和下一责任；共享规则只保留一处，命令合同不复制四份。安装后点名调用、自然路由、Master调用、续作调用都能完成独立任务。
6. 更新安装清单与canonical资源、method release/digest、doctor/capability输出，防止源码有新方法但安装包仍旧。
7. 把Flow Quality v1.1中“单一公开Skill、不新增前置协作对象”等与本增量冲突的活动约定明确标为由本包替代；归档旧语义，不能悄悄保留两份活动规范。
8. 修正candidates-and-stages中Page trial不支持的过时说明，保留已有能力和历史用户项目。

**退出**：AC-H01–H03。必须从真实安装路径运行；源码checkout通过不能代替HOME安装切换验收。安装变更按实际用户授权实施，不因PR文档已合成自动执行。

## T08｜真实使用闭环与发布证据

**目的**：证明系统能在既定任务下承担主线、写作和制作，而非只是把失误变成有确认记录的失误。

**实施工作**：

1. 运行ACCEPTANCE规定的12个真实Host比较会话：4个核心任务各main/candidate一对，加模糊启动与篇幅冲突各一对重复。保留全部结果，失败不得只重跑最好的一次。
2. 使用非生产、可核对的两个代表性任务进行Owner试用：现场用途与独立阅读各一项。固定目标和原材料，记录用户如何指出问题、是否被迫补写中心主张/章节逻辑、迭代时间和实际返修。
3. 每项至少3名未参与写稿的目标类似受众完成陌生情境任务。若无人选/无使用许可，记录not_run；模型扮演用户不能补齐。
4. 至少一次完整现场讲述计时，检查关键限制与练习不因时长被省略；阅读用途无需作者补充即可理解。
5. 完成实际样页/整稿/PPTX notes/正文回读与编辑性证据；对工程与内容分别裁决。
6. 汇总各AC状态和F0/F1/F2/F3。任何未关闭F0、归因于系统误解的主线重建F1、影响约定用途的F2或必要not_run，都不能宣布发布通过。
7. 若失败，回到对应owner修订方法/实现，保留首稿失败和费用，定向复测；不得把用户后来改目标算作旧稿失败，也不得把系统后来修好抹成首稿一直可用。

**退出**：AC-U01–U05；输出可审查的发布建议和剩余风险。小样本结果只证明这轮质性验证，不推导普遍效果或ROI。合并、发布、安装切换与真实客户生产仍是分别授权的动作。

## 2. 每卡提交模板

```text
Task: Txx
Implementation commit / source baseline:
Changed paths and resulting behavior:
AC IDs and status:
Actual commands, environment, inputs and outputs:
Evidence layer for each claim:
Failing examples and repair performed:
Preserved state / calls / unaffected pages:
Not run / blocked evidence and concrete next step:
Scope of this change; next dependent card:
```

不要把“测试全绿”写成业务认可；不要写未实际执行的命令结果；不要把未完成的卡标done后将关键AC无owner地移入“后续优化”。
