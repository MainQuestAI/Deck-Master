# UI 重构问题映射与基线核查

核验时间：**2026-10-24 01:10:28 +08:00**（2026-10-23 17:10:28 UTC）。仓库 remote 实查为 `https://github.com/MainQuestAI/Deck-Master.git`。本轮为只读核查；未改 Issue、PR、安装或客户项目。

**结论：28 项选定问题均为 open。** 其中 20 项与页面结构、动作、候选、恢复、性能直接相关，8 项是设计/审查契约依赖。不能只改组件外观后宣称这些问题已解决。尤其是 **#182 当前待办分类 → #132 整体布局验收**、**#181 规范版本可读 → #141 样页入口联验** 两条前置关系必须保留。

## 基线与证据范围

| 对象 | 当前实查事实 | 方案如何使用 |
|---|---|---|
| 远端 main | `afcc23d1654a6ce24583677c4de9d4a80f0f89bd` | 来自本轮 `git ls-remote`，作为当前公开源码身份，不等于本机激活安装身份。 |
| 本地 checkout HEAD | `92e9f567eaf506f004cac1ef68f44f314739631a` | 与远端 main 不同；不可拿本地旧实现状态代表现有安装或远端 main。 |
| [修复基准 PR #184](https://github.com/MainQuestAI/Deck-Master/pull/184) | open、非 draft、未合并；head `7bbf204658dfc39f53fa34352543168e7eee1e65` | 只含文档目录，51 项 Issue、31 张卡均 planned。复用关闭责任与依赖，不重建第二套 Issue owner。 |
| 实施方案固定版本 | `55adc97c5bb5f16ae7fcff7c33c43969fae9ce97` | Issue 正文引用该方案版本；PR 当前 head 增加同步回读记录。本文任务卡链接固定到当前 PR head。 |
| [性能 PR #147](https://github.com/MainQuestAI/Deck-Master/pull/147) | open、draft、未合并；head `ad2f278cd637f29b5665fcf71d7064098faf617b` | 单飞轮询已有局部修复与测量记录，但缩略图/匹配安装仍有关闭条件；本轮不复述为当前性能实测。 |
| [新增 #186](https://github.com/MainQuestAI/Deck-Master/issues/186) | open，更新时间 2026-10-23 08:30:48 UTC | 不在 #184 的 51 项中，作为检查/返修连续性的新增相邻依赖，实施前追加明确责任。 |

本轮使用 GitHub connector 的 search 定位，再对全部 28 项逐项 fetch_issue 读取状态和正文；search 返回的 state 为 null，未据此推断 open。PR 通过 fetch_pr 读取 metadata，任务内容通过固定 head 的 tasks.json 读取；文件树通过 list_pr_changed_filenames 核查。没有仅凭历史记忆认定关闭状态。机器清单见 [issue-map.json](issue-map.json)，含每项更新时间、设计处理、前置、验收条文和固定来源。

### PR184 实施入口仍有两条开放审查

当前两条线程均 `is_resolved=false`、`is_outdated=false`。它们不阻碍本轮设计研究，但应在实际修复启动前补入计划：

1. [RP-00 窄补丁来源可检索性](https://github.com/MainQuestAI/Deck-Master/pull/184#discussion_r4351506006)：审查要求为 #138/#139 的两个窄补丁提供持久 ref、PR 或精确 diff。本轮核对了线程状态，未重新复现审查者关于补丁不可达的检查，不把审查意见写成新实测。
2. [RP-04 所有可恢复写入覆盖](https://github.com/MainQuestAI/Deck-Master/pull/184#discussion_r4351506025)：任务卡尚未列出 `annotations.save` 与 `styles.references.import`，应加入精确重放与暂停门禁矩阵，不只测试卡内原有操作。本轮未执行这些产品写入。

## 责任分界

- **UI 可直接改**：对象组织、导航、阅读宽度、行动顺序、按钮与链接语义、按需详情、准确消费已有字段、浏览与选择分离。#143、#172、#181 仍须真实 API 和浏览器回读，不能只有示例页。
- **UI 与行为共同改**：#132、#133、#136、#141、#170、#171、#173、#182。视觉方案先固定交互合同；真实状态、范围、消费链随后接通。设计稿不承诺后端已支持。
- **能力/契约是前置**：候选资格、采用隔离、精确重放、职责终态、设计约束和检查范围。UI 提供可理解的状态，但不伪造成功或绕过门禁。
- **性能单列验收**：#140/#142/#183 的读取、轮询、回执工作量。加载反馈与视觉压缩有帮助，但不代替固定负载性能测量。

以下 A/B 名称沿用 2026-09-30 增量定义：A 是 UI 实现，B 是能力补齐；其旧任务卡用作模块/接口归属参照，不把历史“待实施”文字重新当作今天的完成状态。RP-xx 是本轮修复基准的唯一 Issue 关闭责任。

## 1. 页面结构、行动与可读性

| Issue / 实查状态 | 用户痛点 | 本轮设计处理 | 既有责任与 A/B 映射 | 前置 / 关闭边界 |
|---|---|---|---|---|
| [#132](https://github.com/MainQuestAI/Deck-Master/issues/132) · open | 长模块、材料和资源目录挤走正文、进度和下一步。 | 稳定工作面导航；正文为阅读主区；材料、方法和意见按对象进入抽屉；首屏只突出当前行动。 | [RP-22](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-22.md)；A03/A04/A05/A08；B01 | 当前待办、计划编辑与方法准备先准确，再验布局。 |
| [#133](https://github.com/MainQuestAI/Deck-Master/issues/133) · open | 编辑器显示 DOM 对象字符串，章节、页目标、来源不可直接编辑。 | 章节—计划页—来源结构化编辑；预览变更；表单字段与稳定对象对应。 | [RP-10](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-10.md)；A05；B03 | 正确挂载控件并保存回读；不得只删除异常字符串。 |
| [#143](https://github.com/MainQuestAI/Deck-Master/issues/143) · open | 主线绑定、文字映射、来源关联用同一个缺失标签，表达互相矛盾。 | 分开列主线关系、文字映射、来源链接；来源抽屉只陈述各自事实。 | [RP-10](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-10.md)；A04/A05；B01 | 同版本 API 与 UI 一致；无来源不能写已核实。 |
| [#170](https://github.com/MainQuestAI/Deck-Master/issues/170) · open | 界面选口播，但实际准备范围没有 speech。 | 用核心注册表生成审阅范围；选择摘要、实际 context、复制文本逐项相同。 | [RP-18](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-18.md)；A05/A07；B02 | 现核心已有 speech-only；修复前端映射，不另造审阅能力。 |
| [#171](https://github.com/MainQuestAI/Deck-Master/issues/171) · open | 复制只给资源 ID 和不可恢复摘要，丢职责、阶段、范围。 | 复制前展示可读交接摘要：职责、阶段、页范围、版本、资源和缺项。 | [RP-18](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-18.md)；A05/A07；B02 | 后端输出可恢复上下文；真实剪贴板→reader 验证；复制不等于执行。 |
| [#172](https://github.com/MainQuestAI/Deck-Master/issues/172) · open | 没有新阶段时，仍可读的方法目录被隐藏。 | 浏览始终可发现；可选择、可复制、可派发独立表达，不用隐藏名称表示禁用。 | [RP-18](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-18.md)；A05；B02 | 保留 selectable/copy_allowed 与目录权限，不能把浏览变成派发。 |
| [#181](https://github.com/MainQuestAI/Deck-Master/issues/181) · open | 已存 V3 初始设计规范被过滤，方向看似丢失。 | 混合版本规范目录、详情和历史可读；历史与当前方向明确区分；不支持动作仍保留阅读。 | [RP-09](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-09.md)；A06；B02/B06 | 版本/用途适配必须覆盖搜索、分页、固定 revision；不只去掉过滤。 |
| [#182](https://github.com/MainQuestAI/Deck-Master/issues/182) · open | 历史失败和接续任务被当当前待办，同名对象难辨认。 | 待办按当前阻塞、可行动、历史、关系未知分组；任务显示阶段、时间、页范围和当前关系。 | [RP-08](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-08.md)；A03/A07；B01 | 三个入口共享当前性投影；21 stale+1 current 场景不能推荐错对象。 |

## 2. 制作、候选、恢复与交付

| Issue / 实查状态 | 用户痛点 | 本轮设计处理 | 既有责任与 A/B 映射 | 前置 / 关闭边界 |
|---|---|---|---|---|
| [#136](https://github.com/MainQuestAI/Deck-Master/issues/136) · open | 正文完成后看得到产物层，看不到可执行的推进动作。 | 每层显示当前产物及一个适用的下一动作；在抽屉中核对范围、依据和影响后提交。 | [RP-21](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-21.md)；A04/A06/A07；B01/B02/B06 | 真实资格、固定范围、冻结输入与执行链一致。 |
| [#139](https://github.com/MainQuestAI/Deck-Master/issues/139) · open | 候选已生成，固定参考读取不匹配使比较打不开。 | 基准/候选清晰并列；读取失败保留对象身份与就近重试，不误报没有结果。 | [RP-00](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-00.md)；A06；B03/B04 | V3 读取原始参考字节；V1/V2 保持预览语义；需正规化窄补丁。 |
| [#141](https://github.com/MainQuestAI/Deck-Master/issues/141) · open | 首次试作缺少方向、确认状态、继承范围与设计依据。 | 当前方向摘要与固定依据置于试作上下文；区分已有方案、当前选定方向、未核验样页。 | [RP-21](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-21.md)；A06；B06 | 先完成 #181；策略、资产、原图审查均须真实消费，不新增逐页审批。 |
| [#148](https://github.com/MainQuestAI/Deck-Master/issues/148) · open | 纠正旧稿的零调用候选，被旧稿的制作前审阻断。 | 区分改正文和开始制作；依据真实资格呈现可用动作与具体原因。 | [RP-02](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-02.md)；A05；B02/B03 | 修正资格与职责链；不得只启用按钮。 |
| [#149](https://github.com/MainQuestAI/Deck-Master/issues/149) · open | 未采用旁支导致当前稿审查与交接被无关阻塞。 | 候选有独立待决定状态；当前稿状态和旁支状态分别展示。 | [RP-03](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-03.md)；A06/A07；B03/B04 | 当前采用依赖与旁支隔离；真正采用后才按依赖失效。 |
| [#150](https://github.com/MainQuestAI/Deck-Master/issues/150) · open | 成功操作响应丢失后，精确恢复又被暂停门禁阻断。 | 未知结果显示“正在核对原操作”；保留草稿和原操作身份，提供结果回读。 | [RP-04](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-04.md)；A05/A07；B02/B04/B05 | 相同操作返回原回执，新操作仍受门禁；补齐两条 review 指出遗漏写入。 |
| [#169](https://github.com/MainQuestAI/Deck-Master/issues/169) · open | 纯设计方案已完成仍误索要下一生产授权。 | 完成摘要显示本次范围、产物、停止原因；后续动作按已有授权呈现。 | [RP-06](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-06.md)；A03/A06/A07；B01/B02 | 职责终态须由请求与产物事实定义，完成不等于采用。 |
| [#173](https://github.com/MainQuestAI/Deck-Master/issues/173) · open | 上传成功、选用资产、实际生产消费被混为完成。 | 资产行显示已登记、已绑定、已消费的事实；支持能力和限制在使用入口就近说明。 | [RP-19](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-19.md)；A05/A06；B06 | Logo/图片/字体/PPTX 模板分别验真实字节消费；不把文本抽取称母版复用。 |
| [#186](https://github.com/MainQuestAI/Deck-Master/issues/186) · open | 新报告原发现未连续传给返修与定向复核，通用 pass 掩盖未闭合 F1。 | 问题列表固定报告+产物身份，逐项显示已修、开放、接受差异、未核查；检查范围明确。 | 待追加责任；A04/A07；B01/B03（需追加责任） | 新 Issue 不在 PR184；沿用标准报告、绑定和 import，不新增审批体系。 |

## 3. 性能独立项

| Issue / 实查状态 | 用户痛点 | 本轮设计处理 | 既有责任与 A/B 映射 | 前置 / 关闭边界 |
|---|---|---|---|---|
| [#140](https://github.com/MainQuestAI/Deck-Master/issues/140) · open | 加载长时间停滞，导航意图与仍显示的旧页不一致。 | 即时标明目标工作面；局部加载、更新时间、失败就近重试；旧数据明确标为上一成功结果。 | [RP-25](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-25.md)；A02/A07/A08；B07 | 轻量读取及取消/晚到保护；性能目标须固定负载复测。 |
| [#142](https://github.com/MainQuestAI/Deck-Master/issues/142) · open | 重复昂贵读取与请求重叠影响空闲 CPU，缩略图仍有残项。 | 状态刷新不抢阅读焦点；离开工作面停止相关读取；按需加载缩略图。 | [RP-25](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-25.md)；A08；B07 | PR147 单飞改动正规化、缩略图与匹配安装复验；CSS不能关闭。 |
| [#183](https://github.com/MainQuestAI/Deck-Master/issues/183) · open | 单任务回执携带所有待办正文与重复材料。 | 前端消费紧凑结果与当前任务事实，完整上下文在需要时读取。 | [RP-07](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-07.md)；A07/A08；B01/B07 | 协议兼容与同负载字节/CPU测量；不能归因整机温升或通过删权威材料减负。 |

## 4. 相邻的设计与审查契约依赖

| Issue / 实查状态 | 用户痛点 | 本轮设计处理 | 既有责任与 A/B 映射 | 前置 / 关闭边界 |
|---|---|---|---|---|
| [#162](https://github.com/MainQuestAI/Deck-Master/issues/162) · open | 正文表格被机械固化成成品版式，自主设计与约定排版混用。 | 展示本轮策略、必须保持项与可自由设计范围；正文组织不直接冒充布局约定。 | [RP-17](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-17.md)；A06；B06 | RP-17 定义策略及消费语义后接入 UI。 |
| [#164](https://github.com/MainQuestAI/Deck-Master/issues/164) · open | 原图阶段缺表达质量与固定关系检查，不能等 SVG 才发现。 | 样页标明检查层次与开放问题；原图可读可比较，已知关系错误不能标可扩页依据。 | [RP-20](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-20.md)；A06/A07；B06 | 真实原图阶段审查能力、固定 basis 与关系验证。 |
| [#165](https://github.com/MainQuestAI/Deck-Master/issues/165) · open | 项目级方向与页级要求互相冲突，生成输入仍并存。 | 准备摘要显示继承来源和逐页覆盖；冲突定位到字段与对象后修正。 | [RP-17](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-17.md)；A06；B06 | 权威策略合并/冲突检测；单纯提示文案不解决输入矛盾。 |
| [#166](https://github.com/MainQuestAI/Deck-Master/issues/166) · open | 新设计缺少视觉结构却仍可派发。 | 以信息关系、布局意图、自由范围等可读字段展示方案完整性。 | [RP-17](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-17.md)；A06；B06 | 最小完整性校验进活动合同；避免以UI必填替代合同。 |
| [#174](https://github.com/MainQuestAI/Deck-Master/issues/174) · open | 内部证据被默认上屏，客户文案与追溯混在一起。 | 主阅读区显示受众正文；来源和核验说明进依据抽屉，必要客户限定仍保留。 | [RP-16](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-16.md)；A04/A05；B03 | 正文策略与实际 prompt/产物消费一同修复；不能仅CSS隐藏。 |
| [#178](https://github.com/MainQuestAI/Deck-Master/issues/178) · open | 独立前审输入未携带当前请求与适用决定。 | 检查详情说明本次审查目的、固定范围与适用决定，减少用通用 pass 替代具体验收。 | [RP-14](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-14.md)；A07；B01/B03 | 审查 packet 真实展开请求与决定；UI只能消费不能臆造。 |
| [#179](https://github.com/MainQuestAI/Deck-Master/issues/179) · open | 内容前审不能发现内部语域上屏，检查通过含义过宽。 | 将受众表达与来源追溯分层；检查结果按维度与范围显示。 | [RP-16](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-16.md)；A04/A07；B03 | 补实际审查维度及反例，不用换标签提升检查能力。 |
| [#180](https://github.com/MainQuestAI/Deck-Master/issues/180) · open | 未定义字段被当必须上屏要求，UI可能继续放大歧义。 | 内容属性与必需限定有明确业务说明；非上屏元数据留在依据详情。 | [RP-15](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/task-cards/RP-15.md)；A05/A06；B03/B06 | 活动合同定义字段语义、兼容旧记录、准确投影。 |

## 设计稿与后续真实实现的共同验收

| 场景 | 设计/交互验收要求 | 真实实现另需证明 |
|---|---|---|
| 当前总览 | 首屏可识别当前对象、进度和下一动作；同名任务未打开前可分辨；历史失败在历史中可读。 | #182：历史失败、真正失败、接续任务、未知调用、未闭合问题、21 stale+1 current 候选的推荐逐项正确；总览/任务/选择对象共用事实。 |
| 内容与页序 | 章节导航、逐页稿、材料、方法各有稳定入口；长材料不会把正文推出首屏；行操作在对象末列；编辑不混入阅读。 | #133/#143：无计划、有计划零成稿、多页成稿均正确；编辑→预览→保存→重开一致，取消不写，未编辑字段保留，revision 冲突不覆盖。 |
| 单页阅读与编辑 | 阅读/编辑/标注互斥；正文完整可连续读；依据按需展开；抽屉有标题、焦点回归、明确保存反馈与草稿保护。 | #132：跨工作面/后台更新/固定历史不丢草稿；保存只代表保存；来源状态与同版本 API 一致。 |
| 风格与样页 | 方向、适用页、固定依据、继承项、自由范围可读；历史规范可读但不冒充当前；试作入口可发现。 | #181/#141/#173：V1/V2/V3 混合、固定 revision、资产字节、冻结输入和实际调用一致；无旧原图仍可读 V3 initial_design。 |
| 候选比较 | 基准左、候选右，固定两端版本；正文用文本差异；画布完整；窄屏先基准后候选；采用与保留清楚分离。 | #139/#148/#149：参考字节正确；试作当前稿不变；采用后仅真实依赖失效；无效/冲突不能静默覆盖；旧版本兼容。 |
| 等待与恢复 | 加载目标、上次更新时间、失败原因、就近重试明确；不把旧页当新页；未知写入显示核对中。 | #140/#150：响应丢失用原 operation 查回执；不重复付费/写入；取消/晚到不覆盖新对象；所有可恢复写入覆盖。 |
| 方法与交接 | 浏览、选择、准备、复制、实际接手分开；选择摘要能读出职责/阶段/范围，不要求读 hash。 | #170/#171/#172：真实 context、默认方法、复制字节、reader 一致；无新阶段仍可读；复制不创建任务或权限。 |
| 检查与交付 | 每个 pass 标明检查对象与范围；原问题逐项有状态；正式槽位、外部文件、原生验证分开。 | #164/#186：原图表达检查实际发生；原报告 finding 集合连续；未满足 F1 不被其他范围 pass 掩盖；外部合格文件不因槽位空被判质量失败。 |

视口延续 1280×800、1440×900 与实际窄侧栏；390px 样例可补充响应式观察，不能冒充完整现场验收。每项记录静态/合成、真实浏览器、原生调用、匹配安装、交付层次。本轮设计输出不关闭其中任何工程或真实业务验收。

## 对完整重构方案的直接输入

1. **首屏先有可信的当前事实。** 总览不能靠设计层自行过滤旧失败；RP-08 的统一分类作为状态合同，UI 控制呈现层级。
2. **“少按钮”对应明确归属。** 导航用可识别链接/列表选择，写入用有轮廓或实心按钮，次要动作归对象菜单；隐去的是重复入口，保留能力与状态。
3. **抽屉用于上下文工作。** 材料、来源、方法、编辑和操作预览沿用稳定页面上下文；完整比较和整稿阅读仍有足够主画布，不把一切塞入小抽屉。
4. **功能状态不得混成一个完成。** 保存、准备、复制、接手、返回、采用、检查、交付分别使用事实和反馈；UI 文案与后台响应一起验。
5. **设计重构与能力修复衔接，不互相代替。** 可先推进组件、布局、只读适配；RP-22 的完整关闭必须等其 RP-08/RP-10/RP-18 依赖和真实浏览器证据。
6. **性能预算在实际负载建立。** #140 中 <1 秒导航反馈、<3 秒可操作主工作面只是 Issue 提议目标，不是已批准 SLA；记录冷/热、项目规模、历史量及至少三次热切换，结果达不到时仍要有清晰恢复。

## 来源

- [PR184 文档基准](https://github.com/MainQuestAI/Deck-Master/pull/184)、[固定任务数据](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/tasks.json)、[共同兼容与验收](https://github.com/MainQuestAI/Deck-Master/blob/7bbf204658dfc39f53fa34352543168e7eee1e65/docs/work-items/wi-issue-repair-20261023/ACCEPTANCE.md)。
- 当前仓库 `DESIGN.md`、`docs/specs/deck-master-webui-v4-20260930/A-UI-SPEC.md`、`B-CAPABILITIES-SPEC.md`、`CONSOLIDATION.md`。仅读取；历史进度数字不用于断言当前状态。
- 上表每项 Issue 及固定任务卡；机器清单保留逐项核验时间。除 28 项选定问题外，其余 #132–#183 性能/Skill 专项继续由 PR184 原卡负责，未硬套为本轮 UI 需求，也未声称全部逐项实时核验。
