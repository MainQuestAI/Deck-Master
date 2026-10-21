# PR127 对 Deck Master Web UI 的影响定位

2026-10-20｜源码、规格与资源包交叉分析｜只读分析，未修改产品代码。

**结论：需要安排一轮有边界的 Web UI 增量。PR127 本身没有直接修改前端，也没有证据表明原页面必然失效；但它增强的方法资源和内容能力，当前界面不能充分解释和呈现。优先补任务方法依据与恢复提示，再补论证主线、证据关系和实质审阅；资源选择器与案例浏览后置。**

## 1. 本次分析的准确基线

- 已读取关联聊天“回拉 PR127 并查看剩余任务”。其中另一个开发会话正在推进资源内化、Host 接入和验收；本报告不将其未提交工作当作完成功能。
- 线上 PR127 在本次首尾查询均为 Draft / OPEN，分析固定于 `12bffbd72631ad60ada6d456b99e95c3e6b2bd0e`，base 为 `09f0213d07fc718dc4d41a52bb69c4595fcb1ac8`。
- 当前主工作区 HEAD 为 `92e9f567eaf506f004cac1ef68f44f314739631a`，早于 PR 基线，且有用户未提交文件。未拉取覆盖、未更改这些文件。
- 主工作区与 PR 基线间已有协作面板、完整稿导入、范围控制、交付等更新。因此以下“已有/缺口”主要按 PR 基线及固定 PR HEAD 判断，而非仅凭旧主工作区。
- 固定差异共 28 个文件；`resources/static/` 下无改动，`service.py`、`cli.py`、`collaboration_api.py` 在此 PR 快照也无改动。资源与运行协议基础变更不能自动等同于 Web 功能上线。
- 检查了资源包的总体、迁移、Runtime、验收、Gemini 裁决和阅读边界，以及方法选择、语体、叙事、页内写作、内容到设计、方法审阅指南。本文不是对全部 52 个种子的内容质量验收。

## 2. 开发任务与资源线，对前端分别意味着什么

| 资源/任务线 | 目标和当前证据 | 对 Web UI 的实际影响 |
|---|---|---|
| WP-A 方法与案例 | 10 方法族、7 指南、6 案例、12 校准例、3 模板等是目标范围；固定 HEAD 的 catalog 仍是 14 个既有 reference | 不必把目录映射成十个菜单。应让用户看清增强后的主线、理由、取舍、条件和正文 |
| WP-B 选择与冻结 | 已有 Python 选择、依赖展开、最终阶段冻结、旧 manifest 保留、打包映射 | Web 需要能解释本次任务采用哪些资源、资源是否可用；若允许用户选择，还需 Host-facing 接口和能力声明 |
| WP-C 真实效果验证 | 经营诊断、方案选择、教学三类新旧完整稿成对验证；固定快照未证明完成 | 不应先做“质量提升百分比”或方法评分。界面应支持阅读具体结果与审阅意见；实验台可保持内部 |
| M01–M10 | 问题界定、分析、论证、解释、选型、不确定性、综合、叙事、教学、压缩 | 内容工作区应表达这些操作的产物，不要求用户填满十套分析表 |
| 叙事/语体/写作指南 | 多种可组合路径；高管、工程、研究、教学表达；完整正文 | 更中性的用途提示、主线阅读/比较、按受众和阅读方式表达；不是四条固定流程 |
| 内容到设计 | 保留比较、机制、条件，允许拆页等候选 | 单页设计交接可补“必须保留的关系和条件”，复用现有局改与候选机制 |
| 方法审阅/数字检查 | 审真实观点与依据；算术只证明给定公式的计算 | 质量记录应能定位原句、来源、影响与修改建议；算术通过不能成为商业判断通过 |
| 研究原文 | 是来源与采用裁决，不是默认运行上下文 | 无需进入客户材料库或前端主导航 |

资源包明确“不新建 UI 审批台”“不建立第二套内容状态机或业务证据库”。实现应复用 Narrative、ContentPlan、Page、Review、Task 及现有决定/候选。[总体规格][bundle00] [运行规格][bundle03] [迁移表][bundle02]

## 3. 可直接进入后续规划的功能项

优先级是本报告的建议，不是 PR127 已承诺实现的前端范围。P0 表示建议随 RC5 接入核对的可解释性与恢复，不表示已复现崩溃。

### UI-01｜任务的方法依据与恢复提示（P0，直接关联）

**用户价值：**用户能理解任务为什么继续不了，以及该核实哪个任务，而不是只有“待接手”或一段原始 JSON。

**当前证据：**`service.task_summary` 已返回 `method_manifest`、`method_basis_status`、`method_basis_issues`、派发与当前 release。但 Run Desk 的 `task_row/detail` 投影没有这些专用字段，任务详情也没有专用资源展示。另一入口“下一工作单”可展开原始工作单记录，因此不是完全无法查询，而是缺少日常可读解释。[工作单][service] [任务投影][runbackend] [任务 UI][runui]

**建议：**在“任务详情”加折叠的“本次方法依据”，显示人类可读名称、方法/示例/模板/数据/脚本类别及可用状态。技术 ID、版本、hash 放详情。对缺失/不匹配给出受影响资源与既有恢复入口；旧任务严格展示其冻结依据。

**后端配套：**增加有界读投影，复用现有 resolver，保留固定 revision 的含义。派发时冻结事实与现在安装的可用性要分别标注；不能用当前 catalog 把旧版本资源名称/属性伪装成历史事实。旧任务无记录时显示“未记录”。

**验收要点：**升级后旧任务 hash 不匹配、资源缺失、历史版本、未记录、恢复后新任务均有正确提示。浏览器读取/展开不启动模型；“已返回资源字节”不能显示成“已应用方法/质量通过”。若原任务还有未结调用，按现有结算/接续规则处理，不加一键自动重跑。

### UI-02｜可读的论证主线与方向比较（P1，已有能力的呈现缺口）

**用户价值：**在写成多页稿之前，用户能看清这份稿想回答什么、为什么这样组织、还有哪些真实替代。

**当前证据：**Narrative 合同已有 `communication_job`、`nodes/edges`、`issues`、`alternatives`。当前“内容与来源”主要呈现用途、受众、材料、章节及页面目标；协作面板显示决定摘要与 JSON，尚未看到完整的 Narrative 阅读与方向比较面。[Narrative 合同][narrative] [内容工作区][contents]

**建议：**在现有内容工作区增加“论证主线”阅读区：受众问题、核心回答、关键理由与条件、未决问题、真实备选及代价；有不同方向产物时做并列比较，采用仍复用现有 direction 决定和 proposal adoption。先做文本阅读，不必建设自由图编辑器。

**后端配套：**提供固定版本和待选 proposal 的可读投影，绑定真实 source/ref。注意 `alternatives` 可以是业务方案替代，不能一律冒充“叙事候选”；七种叙事路径是建议资源，不是运行时已有的七个候选对象。

**验收要点：**尚无 Page 的 plan_only 也能读到完整成果；已确认方向的 write_only/speech_only 不重新打开方向选择；采用方向不扩大原请求范围。没有两条真实候选就不强凑比较。

### UI-03｜正文、论点与证据联动（P1，已有追溯能力的延伸）

**用户价值：**点击关键判断就能分辨来源事实、计算、推断和建议，并看见必要条件。

**当前证据：**单页已有来源入口和材料定位，引用详情仍部分为 JSON；Narrative 已有 authority、source_links、qualification 等，Page 也有 content_mapping。当前单页阅读没有把这些连接成面向正文的论证链。[单页来源][page] [Narrative 合同][narrative]

**建议：**在单页来源抽屉中加入“此结论的依据与条件”，使用已有可定位正文对象；有映射时联动，没有映射时明确未记录。方法示范独立标识，不能出现在“客户事实来源”里。

**后端配套：**把 Page visible_links、Narrative 节点、固定 source locator 聚合为同版本读模型；不新建证据库，不根据正文猜测来源。

**验收要点：**事实/推断/建议准确区分，跳转保留版本；E04 等案例数据不变成客户 source_id；导入稿缺 Narrative 时仍可正常读稿，不伪造论证关系。

### UI-04｜实质审阅意见定位与局改交接（P1，已有质量记录的增强）

**用户价值：**看到哪里有问题、为什么影响结论，并在明确范围内安排修改。

**当前证据：**质量记录已经展示 observations、finding.message、expected、actual，底层身份与依据可展开；交付页也区分工程、专业与接受状态。因此不用重建质量中心。缺口在于对论证、因果、取舍、教学问题的可定位阅读与修订交接。[质量记录 UI][reviews]

**建议：**复用现有 finding，优先展示原句/对象、问题、影响、建议、适用版本；支持跳转正文和生成现有局改计划。分类用于导航，不作为强制检查清单。保留实际审阅者、范围和未验证项。

**后端配套：**先核对现有 Review 合同对定位与建议的表达，能复用就复用；缺少字段时再做最小扩展。共享算术脚本若未绑定真实项目结果，不在 UI 显示“数字已校验”；将来接入也应单列输入、公式和结果。

**验收要点：**“相关不等于唯一根因”“方案缺真实替代”“教学缺迁移”等问题能定位实际正文；只读审阅不修改稿件；用户选择局改后只覆盖既定范围。算术 PASS 不提升专业审阅/交付状态。

### UI-05｜任务用途与表达偏好（P2；文案调整可先做）

**用户价值：**教学、研究、工程评审能自然进入流程，且用户不用先学习方法编号。

**当前证据：**新建项目已经有约定产物和阅读方式；口播稿也已有单页阅读入口，不应再登记为全新功能。用途提示仍是“这份方案要帮助听众作出什么判断？”，内容区用“汇报用途/汇报受众”。[新建项目][launcher] [内容工作区][contents]

**建议：**先将提示覆盖“理解、判断、选择或学会什么”。可提供少量可选示例，后续再考虑表达偏好。四种写作侧重允许混合，不增加四个业务流程或不同事实标准。

**后端配套：**优先复用已有 brief、audience、presentation_mode 和 Narrative.communication_job。不要未经合同设计新增永久 writing_profile 枚举或把选择藏在不可解析的 notes JSON 中。

**验收要点：**教学不被要求填预算 CTA；研究允许没有行动建议；阅读方式和已确认范围继续生效。

### UI-06｜高级方法选择与案例预览（P2，可选能力）

**用户价值：**有经验的用户可针对“解释不清”“方案缺比较”等问题微调下一任务的方法，也可理解示范怎么写。

**当前证据：**固定 HEAD 只有 Python 侧 `selected_resource_ids`；HTTP collaboration 的 continue 字段集合仍为空，前端发送空请求。不能仅加下拉框就声称接通。当前 catalog 也没有面向人类的 title/summary 字段。[选择实现][select] [API 白名单][api]

**建议：**默认由 Host 按任务选择；可在下次任务准备时展开高级面板，以业务问题/方法名称为入口，自动展示必要依赖。示例预览注明“合成教学示范”，不提供默认导入客户材料的动作。

**后端配套：**先等 WP-B 明确实际派发和只读目录接口，并提供能力探测。任何 UI 选择都必须到最终 phase/scope freeze，仍是调用输入，最后写现有 manifest；不新增持久 MethodPlan/审批状态。展示元数据来自统一目录，不在 JS 复制第二套适用性规则。

**验收要点：**M04+E04 及依赖实际进入新任务；不适用资源拒绝；已存任务不原地加卡；同一任务读取不被 UI 选择悄悄改变。无对应服务能力时不显示可操作选择器。

### UI-07｜内容到设计的语义保真说明（P2，后续延伸）

**用户价值：**设计结果保留关键比较、机制假设和限定，不为版面好看损害内容。

**建议：**在单页设计/提示词详情内展示本页需要保留的语义关系与条件，有信息才显示。装不下时给出拆页/分组等现有候选或局改入口；正文变更回到 Content 范围。

**依赖与验收：**复用固定 Page、design context 和授权边界；不能把方法名称硬映射成唯一版式，不能将理论示例里的布局当成画布规则。这一项不需要随资源打包立即上线。[设计指南][visual]

## 4. 推荐实施顺序与边界

**第一段：完成 PR127 核心任务，同时锁定 Web 接口。** 继续 WP-A/B 和原定验收；核对方法目录的语义类、冻结 manifest、资源错误以及 writer 兼容提示是否能被 UI 读取。前端不自行解析本地技能目录，也不把返回字节当成质量证明。

**第二段：独立安排 Web 增量，先 UI-01 + UI-02 + UI-04，按需把 UI-03 的基础追溯一起接入。** 它们直接帮助用户理解、判断和修订新能力的产物。不是 PR127 范围必须立刻扩大到完整前端重构。

**第三段：再做 UI-05/06/07。** 用三类真实成对稿确认哪些信息最有用，再决定选择器、案例预览和设计交接的细节。

建议回归至少覆盖：旧任务跨版本恢复；M04+E04 新任务；只有大纲的完成态；确认稿局改；speech_only；design_only；review_only；固定历史版本；示例与客户来源隔离；旧核心拒写新 writer 边界。浏览器、Host 实际执行、成稿质量分别记录。

不建议新增：十个方法导航页、方法勾选即通过的评分、新的审批台、单独的 MethodPlan 状态机、自动客户案例回流、自动强制重写确认稿。资源包也不要求这些产品功能。

## 5. 结论的证明范围

本次证明的是固定源码与规格上的接口和呈现缺口。没有运行浏览器、真实 Host、模型生成或安装验收；因此不声称某一现网画面已复现故障，也不声称新增方法已经提升成稿质量。历史记忆仅用于定位已有 UI 工作，本报告的具体判断已按本次固定源码核对。

关联开发会话会继续变化。接手实现时应重新核对 PR 最新 HEAD，尤其是 Host-facing 选择接口，避免与正在进行的 WP-B 重复开发。

[service]: https://github.com/MainQuestAI/Deck-Master/blob/12bffbd72631ad60ada6d456b99e95c3e6b2bd0e/src/deck_master/service.py#L565
[runbackend]: https://github.com/MainQuestAI/Deck-Master/blob/12bffbd72631ad60ada6d456b99e95c3e6b2bd0e/src/deck_master/run_desk.py#L131
[runui]: https://github.com/MainQuestAI/Deck-Master/blob/12bffbd72631ad60ada6d456b99e95c3e6b2bd0e/src/deck_master/resources/static/v2/run-desk.js#L152
[contents]: https://github.com/MainQuestAI/Deck-Master/blob/12bffbd72631ad60ada6d456b99e95c3e6b2bd0e/src/deck_master/resources/static/v2/content-sources.js#L31
[narrative]: https://github.com/MainQuestAI/Deck-Master/blob/12bffbd72631ad60ada6d456b99e95c3e6b2bd0e/src/deck_master/resources/contracts/narrative.v1.schema.json#L58
[page]: https://github.com/MainQuestAI/Deck-Master/blob/12bffbd72631ad60ada6d456b99e95c3e6b2bd0e/src/deck_master/resources/static/v2/page-workbench.js#L49
[reviews]: https://github.com/MainQuestAI/Deck-Master/blob/12bffbd72631ad60ada6d456b99e95c3e6b2bd0e/src/deck_master/resources/static/v2/views.js#L23
[launcher]: https://github.com/MainQuestAI/Deck-Master/blob/12bffbd72631ad60ada6d456b99e95c3e6b2bd0e/src/deck_master/resources/static/v2/launcher-ui.js#L106
[select]: https://github.com/MainQuestAI/Deck-Master/blob/12bffbd72631ad60ada6d456b99e95c3e6b2bd0e/src/deck_master/resource_catalog.py#L122
[api]: https://github.com/MainQuestAI/Deck-Master/blob/12bffbd72631ad60ada6d456b99e95c3e6b2bd0e/src/deck_master/collaboration_api.py#L26
[bundle00]: /Users/dingcheng/.codex/worktrees/pr127-rc5-continuation/inputs/deck-master-content-methods-spec-v1.1/00-iteration-spec.md
[bundle02]: /Users/dingcheng/.codex/worktrees/pr127-rc5-continuation/inputs/deck-master-content-methods-spec-v1.1/02-resource-catalog-and-migration.md
[bundle03]: /Users/dingcheng/.codex/worktrees/pr127-rc5-continuation/inputs/deck-master-content-methods-spec-v1.1/03-runtime-and-scripts-spec.md
[visual]: /Users/dingcheng/.codex/worktrees/pr127-rc5-continuation/inputs/deck-master-content-methods-spec-v1.1/resource-seeds/skills/deck-master/references/content-to-visual.md
