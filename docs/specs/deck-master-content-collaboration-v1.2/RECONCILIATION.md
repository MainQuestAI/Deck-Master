# 评审整合、裁决与证据

本包整合 PR106 审计、前轮严格只读审查和用户提供的两份外部评审。外部评审 A 为 1537 行文本，B 为 248 行文本。外部评审是意见和证据线索；只有固定源码或可复核执行记录才能成为实现事实。原文不作为本次 PR 附件发布。

## 1. 证据状态

| 标记 | 使用规则 |
| --- | --- |
| 确认成立 | 本轮/前轮读到的固定 SHA 源码、合同，或明确限定范围的探针记录支持 |
| 合理推断 | 实现路径支持风险，但尚未排除真实 Host 行为等条件 |
| 尚未验证 | 没有本轮执行/实际使用证据；不能转述成“已经测试通过” |
| 已过时 | 归档行为或与当前源码冲突的文档，不能作为当前合同 |
| 设计裁决 | 本 spec 选定的拟实施行为；不等同于现有实现或用户验收 |

PR 原探针 P01–P05 使用合成 fixture。B 自述独立复跑了五项探针，本轮未取得其可独立核对的完整执行包，故保留为“评审者报告”，不宣称本轮复跑。P05 的直接 fixture 注入不能证明公开 UI 可达；其错误谓词仍由源码直接支持。

## 2. 分歧裁决

| 议题 | 意见差异或过强结论 | 本版处理及理由 | 落点 |
| --- | --- | --- | --- |
| Skill 4 或 5 个 | A 主张 Master/Content/Design/Review；B 主张 Master/Plan/Design/Review，写作归 Master；前轮审查曾建议独立 Writer | 采用 4 个入口且 Content 包含可独立调用的 write_only/speech_only。写作有独立用户需求，应保留方法与退出产物；不因有独立需求必然再增加一个入口 | SPEC；T03/T07 |
| 单 Skill 的因果 | 不能从入口数量推导内容失败 | 以路由、方法加载、产物和交接验收；若四入口仍为薄包装则 T07 不通过 | SPEC；ACCEPTANCE |
| 内容模型 | A C2 把 Narrative 作为语义权威，F2 又把 central_claim/argument_nodes 放进 ContentPlan | 固定 Narrative 为语义权威；ContentPlan 只引用语义节点，管理页面映射/预算。用户可读论证稿由 Narrative 生成，不复制一份任意改写全文 | CONTRACTS |
| 确认稿导入 | 有意见要求导入后补齐所有策划对象 | 保留 confirmed_manuscript 路由；只生成如实标 derived/imported 的索引，不倒填用户对新 Narrative 的批准 | SPEC；MIGRATION |
| 口播默认 | B 倾向 live/mixed 都完整逐字稿，A 以任务需要为条件 | live 默认 cues，verbatim 由明确要求触发；read_alone 默认 none；默认 live 字段不能自动获得业务效力；mixed 明确主用途和版本 | SPEC；T06 |
| 内容与设计顺序 | 原 repair-plan 线性写完后再设计；其他文档要求前置可行性 | 双循环：先评估论证/篇幅/密度与关系，完整写作后以真实内容试样；确定版本后再生产 | SPEC；EXAMPLES |
| 把 CLI 变确认通道 | B 建议 K2/K5/K6 必须走 CLI 或按钮 | 同一 Host 能运行 CLI，不形成独立身份来源。默认允许可追溯 Host 转述并如实标注；verified_user 要由适配器建立真实事件证据，不能由参数自报 | CONTRACTS；T07 |
| “人类专业”与独立模型 | B 的修复建议包含 independent OR human 放行原开关 | 拒绝。原开关明确要求人类；独立模型仅满足单独的 independent_model_or_human 内容审查配置 | CONTRACTS；T01 |
| 默认外部额度 | “没有额度”说法过强 | 当前任务已有 reserve_allowances；缺的是项目级范围/委派。保留既有额度账本，新增范围约束，不重建计费系统 | CONTRACTS；T04 |
| 前置独立审查 | 是否将所有任务一概强制独立审查 | 新论证 full_deck 默认前置独立审查；确认稿只查忠实性；只读/探索可以交回带缺口稿件。明确用户降级不被伪装为独立通过 | SPEC；ACCEPTANCE |
| 初始样页复用 | “现有 styles 全部目标都需要旧蓝图”过强；“直接复用即可”又不足 | v1 需要已有参考；v2 screenshot 需要目标蓝图。保留 recipe/candidate/allowance，补无初始蓝图入口与覆盖判断；不能把初次设计写成只改函数调用 | CONTRACTS；T05 |
| 所有决定进入全局 digest | A 建议决定进入 content_identity | 采用动作实际依赖切片与 eligibility basis；撤回单独读当前控制事实。无关决定不能让全稿在飞任务都过期 | CONTRACTS |
| 正式交付每次确认 | 初稿方案可能要求最终文件 hash 后再让用户签字 | 分开“授权生成/交付某范围”和“人类已阅这个文件”。已有明确交付委派可复用；不能把事前委派标为人类阅过将来文件 | CONTRACTS |
| 主线重建阈值 | A 提议超过 20% 页职责改变即重建 | 20% 只作预警；以固定输入/目标下的语义重建和用户补写负担判失败。用户后来改变目标单独归因 | ACCEPTANCE |
| 原型与门禁顺序 | 原 R1/R2 先合同和 gate，D01–D06 未定 | 本包给定产品选择、完整样例和 AC；T00 先验证产物可审，再冻结合同。明确谓词缺陷 T01 可独立先行 | TASKS |

## 3. 当前源码支持的关键事实

所有代码链接固定在 `af9fd7a6b4d08f753d2f16536a03f386384f49d2`。行号用于定位，不表示这些函数全部都需要重写。

| 编号 / 状态 | 事实与证据 | 业务含义 / 本版处理 |
| --- | --- | --- |
| E01 确认成立 | [service.py L171–190](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/service.py#L171-L190)、[L280–310](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/service.py#L280-L310)：新建直接 compose，要求完整 Page 与页序 | 先区分任务意图/方向，不能把对象齐全当方向成立 |
| E02 确认成立 | [service.py L724–769](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/service.py#L724-L769)：普通续作排除 trial；有 Page 无 blueprint 可派发 | candidate 不自动采用仍不能约束“只试一页”；用授权范围限制整条路径 |
| E03 确认成立 | [content_plan.py L20–65](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/content_plan.py#L20-L65)、[cli.py L108–109](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/cli.py#L108-L109)、[registry.py L118–136](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/registry.py#L118-L136)：v3 强制 plan，CLI 默认与 Studio 不同；import_draft 特例存在 | 新建入口统一；确认稿豁免重策划仍保留 |
| E04 确认成立 | [content-methods.md L21–83](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/skills/deck-master/references/content-methods.md#L21-L83)：已有受众任务、机制、观点、边界、推进和返修方法，明确反对统一销售故事 | 发展现有方法并观察中间产物；“完全没有专业方法”不成立 |
| E05 确认成立 | [styles.py L56–81](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/styles.py#L56-L81)、[L252–306](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/styles.py#L252-L306)：已有 reference、trial、recipe 与扩展校验，初始设计仍有前提缺口 | 补初始路径和风险覆盖，继续用现有候选体系 |
| E06 确认成立 | [合同 03 L38–44](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-rebuild-v1/specs/03-data-and-state-contracts.md#L38-L44)、[exports.py L106–155](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/exports.py#L106-L155)：人类开关实际谓词允许 status 非 fail 且 kind/actor 二选一 | 收紧 kind、pass、actor、证据、当前依赖；保留低门槛审阅稿 |
| E07 确认成立 | [handoff.py L66–93](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/handoff.py#L66-L93)、[cli.py L814–838](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/cli.py#L814-L838)：工程视图与 export 的政策判断不一致 | 三入口消费同一交付资格，工程事实仍单独展示 |
| E08 确认成立 | [test_export.py L47–64](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/tests/rebuild/test_export.py#L47-L64)、[L244–257](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/tests/rebuild/test_export.py#L244-L257)：seed=human 的 helper 仍生成 host_self | 正样例必须有真正不同的 actor/evidence，不能只改文件名 |
| E09 确认成立 | [review.py L38–52](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/review.py#L38-L52)、[L197–219](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/review.py#L197-L219)：独立性 helper 本身正确；实质 observation 检查有限 | 消费独立性校验并增前置内容证据；结构门禁不能证明逻辑正确 |
| E10 确认成立（静态） | [pipeline.py L301–313](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/pipeline.py#L301-L313)、[compiler/api.py L14–26](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/compiler/api.py#L14-L26)、[native.py L42–147](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/compiler/native.py#L42-L147)：新建原生编译未投影 speaker_notes | 增加真实 PPT 备注与回读；当前未实际生成/打开 PPT 验证，需 Codex 核验 |
| E11 确认成立 | [editing.py L383–403](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/editing.py#L383-L403)、[tasks.py L1335–1365](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/tasks.py#L1335-L1365)：恢复保留当前 policy/调用事实；已有 bounded call 检查 | 新授权沿用此地基；不得另造可回滚的费用/撤回账本 |
| E12 已过时 | [candidates-and-stages.md L7](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/skills/deck-master/references/candidates-and-stages.md#L7) 称不支持 Page trial；[changes.py L92–97](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/changes.py#L92-L97) 已支持 content trial | T07 校正文档，T03 复用能力 |

对“无前期协作导致用户实际内容偏离”的归因是合理推断：机制允许该路径，用户反馈一致，但本轮没有真实原会话和对照实验。该归因通过 T08 的固定输入对比与修稿负担记录检验。

## 4. 原文样例的修正

- A 的 120/54 案例不能从“缺设备条件”直接推出“检索尚未开始”“必须先补问”或“主要往返”。这些是待验证机制，修正版必须写出条件。
- B 的 100/38+平均 1.5 次往返属于另一个合成数据包，不能注入本包 Q1 的 100/38 教学数据。“唯一可见”改成“唯一成规模的重复成本”仍无充分证据。
- A 的 8 页/10 分钟预算区间为 450–690 秒，不能在上限超过 600 秒且未留互动时间时声称可讲。减少页数也不必然缩短讲述时间。
- “把未知版本设必填”可能阻断紧急流转。Q1 将版本可得性与紧急程度分成两个判断轴，并允许记录未知及原因。
- 修正后的示例仍不是效果证据；它们是 T00 校准用候选样例和失败锚点。实际渲染、讲述、用户与听众评价必须独立完成。

## 5. 原方案编号的归属

| 原定位 | 新归属 |
| --- | --- |
| F01/F05、Q01–Q08、D01/D03 | SPEC / T00、T03、T08 |
| F02、D04、R4 | SPEC / CONTRACTS / T05 |
| F03、R1/R2、CC01–CC20 | CONTRACTS / MIGRATION / T02、T04、T07 |
| F04、G4、CC21–CC24 | CONTRACTS / T01、T04 |
| F06、D06、R5 | MIGRATION / T07 |
| D05、R6、CC25–CC28、V01–V12 | ACCEPTANCE / EXAMPLES / T00、T08 |

该表是职责对应，不是对每条旧 CC 字面内容的无条件采纳。新验收以 ACCEPTANCE 的明确 Given/When/Then 和唯一 owner 为准。
