# Deck Master 受控协作流程：旧新对照与根因审计

> 审查状态更新（2026-10-12）：本文件保留首轮诊断/建议，不是用户已批准的产品方案。用户指出 Skill 体系、逐字稿、逐页稿、说服方法和效果评估论证不足；尤其“一个公开主 Skill”已重新开放讨论。请先读 [审查包入口](../skill-flow-review-20261012/README.md)，以其中的问题清单和待决事项审查本方案。

日期：2026-10-12。状态：**方案阶段；未修改产品代码、Skill、测试、安装或客户项目。**

配套文件：[修复方案](repair-plan.md)、[固定版本源码索引](source-index.md)、[隔离探针结果](evidence.json)、[可复现命令](reproduce.md)。

## 1. 结论

当前新建流程存在产品层面的退化：在用户没有确认内容方向、视觉设计、信息密度及生产范围时，Host 可以自行填写任务、提交整套正文，核心随即派发生图，最终由同一个 Host 自审并进入工程交付。运行时对“对象是否真实、版本是否一致、结果是否完整”的控制较强，对“当前到底被授权做什么、哪些业务决定尚未形成”的控制不足。

退化分四步发生，不能归因于一次菜单隐藏，也不能归因于 PR105：

1. **前置确认先被改为自动推进。** `25a27e31`（2026-09-15）把 Brief、Planner、Sourcing 三个阶段的 `approval_required` 从 true 改为 false，并移除部分来源权威、时效及许可问题；其中清理固定模块、无关前置有合理性，但未建立区分“普通执行取舍”和“方案方向决策”的替代控制。
2. **主控职责被压入正文任务。** `2ce3004b`（2026-09-16）将新建路由改为 create/compose；`1c2bb80c` 同日加入“有 Page、无 blueprint 即派发生图”，没有等价承接需求缺口、方案确认及风格选择条件。
3. **旧控制模块和入口被删除。** `abb84a19`（2026-09-22）退役旧运行代码；`ba8cebf5`（2026-09-26）删除 18 个 companion Skill 和阶段合同。任务字段、方法文件、输入更新得到替代，但用户决定的结构、确认有效性和阶段退出控制没有等价落点。
4. **后续治理强化了后半段。** 新 ContentPlan、冻结生成请求、候选、风格试作、回执、逐页审阅和交付核对完善了生产追溯与修改安全，却没有把首次策划与设计纳入同一受控流程。风格修改可以“先试后扩”，首次制作仍直接生成。

恢复目标是：让系统持续承担任务理解、内容策划、信息设计、制作、审阅和交付的主控责任，让用户决定和授权成为运行依据。仅增加几句提问、恢复旧 Skill 名称、恢复固定问卷，都不足以达成目标。

## 2. 对照基线与证据边界

| 基线 | SHA / 来源 | 用途 |
|---|---|---|
| O0：取消前置确认前 | `4d44c7ee92632622a13d3770025ccac5ea49b982`（`25a27e31^`） | 读取原阶段合同，避免把已放宽版本误当原设计 |
| O1：重建前最后旧入口 | `d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf`（`2ce3004b^`） | 对照旧主控、问答、决定、风格、交付的实际实现 |
| 早期主控修复 | `d05c336f`、`d8dc6808`、`199f1d6c`、`799bab3f` | 核对唯一主控、阻断传播、fixture/production 区分、回写和交付 |
| N：当前 main | `af9fd7a6b4d08f753d2f16536a03f386384f49d2` | 所有当前代码结论和探针基线 |
| 真实使用 | Codex 聊天 `01a12dfa-b87b-7a90-9abc-ce5c7a9595fb` | 已读取执行记录：未经前期方向确认直接制作；用户反馈内容偏离、视觉/密度/版式未确认 |

主目录原有 README 修改、docs/work-items 与 output/evidence 产物保留。首轮只新增本报告目录，未提交或推送。后续文档专用 Draft PR 纳入本报告与审查问题包；安装仍未切换。

本轮另只读核对日常安装：release 为 `af9fd7a6b4d0-66edd87fed03`，source_sha 与 N 相同、source_dirty=false；安装版 13 个 Skill 文件与当前源码逐字节一致。因此本次缺口不能用“加载了旧 Skill”解释。

证据标记：**代码确认**表示当前或历史路径已阅读；**探针确认**表示本轮隔离合成项目实际运行；**用户反馈**是本次真实使用评价；**待验证**不得升级为通过。旧版未在本轮完整复跑，不能据文件存在声称旧版全部好用。

特别更正：旧 `session_builder` 自己写明“实际多轮交互可后续接入”；旧 Brief 编译器仍用关键词和句子提取；旧 `validate_entry` 不直接执行 required_decisions；高密度和完整稿导入另有快捷路由。旧版不是可直接回滚到的完整答案。[E05–E07、E11]

## 3. 18 个旧 Skill 的职责去向

| 旧入口 | 当前去向 | 审计结论 |
|---|---|---|
| deck-init | create、sources、Store | 项目与材料持久化保留；强制 workspace/setup 前置有意退役 |
| deck-brief | compose 的 content-methods | 需求理解方法部分保留；缺口对象、阶段退出和确认交接未迁移 |
| deck-planner | compose + ContentPlan | 页目标与出处可追溯；没有独立的制作前方案决策阶段 |
| deck-sourcing | sources、ContentPlan、allowed assets | 原件、版本、定位与外发许可保留；来源选用理由与关键缺口处置未完整迁移 |
| deck-producer | compose / blueprint / reconstruct | 正文和制作能力保留；没有统一生产授权基线 |
| deck-builder | pipeline / compiler | 保留，当前由本地核心编译 |
| deck-builder-high-density | blueprint → SVG → PPT | 原图及原生编辑链保留；原风格选择阻断未接入新建路径 |
| deck-quality | Review 六维 | 审阅和逐 finding 返修保留；前期内容审查缺口仍可能拖到全套制作后 |
| deck-review | export / handoff-check / check_summary | 工程核对保留；最终用户决定及入口一致性不足 |
| deck-autopilot | 主 Skill 的 continue 循环 | 连续执行保留；交互/授权/只审/局部返修等执行边界未等价建模 |
| deck-doctor | doctor --step | 依赖诊断保留；不承担产品方向就绪判定 |
| deck-setup | install activate | 安装和入口绑定保留 |
| deck-upgrade | activate / rollback | 同版本 CLI/Skill 与回滚保留 |
| deck-learn | 明确不再提供；意见保存在项目 | 长期学习有意退役；项目内复盘仍应有明确交付位置 |
| ppt-deck-pro-max | 主链路 Host 制作 | 外部生产入口退役，能力改由主链路承担 |
| ppt-library | 显式 sources / assets | 强制库依赖退役；资料复用仍有需求，但不能恢复强制库绑定 |
| ppt-master | compiler / pipeline | 主编译器替代；不应恢复旧私有 backend 准入 |
| ppt-quality-gate | Review / readback | 审阅职责部分替代；外部审查作为有条件要求尚需明确运行契约 |

这里的“部分替代”不是入口名称问题，而是缺少相应输入、产出、责任人、有效性和推进条件。[E20–E22、E29–E30、E33]

## 4. 全流程控制对照（30 项）

状态：**保留/替代**、**部分迁移**、**缺失**、**旁路/不一致**、**合理退役**。下表按职责覆盖，不按旧文件数量计数。

| ID | 职责或控制 | 旧实现与限制 | 当前实现 | 判定与恢复要求 | 证据 |
|---|---|---|---|---|---|
| C01 | 用户任务与执行范围 | stage route、interactive/repair/review-only；多条旧路由并存 | task 含 brief/受众/场景；continue 默认沿生产推进 | 部分迁移：持久化“本次只策划/只审/局部改/制作到何处”，不能从“继续”扩大范围 | E04、E11、E12、E21 |
| C02 | 材料读取与边界 | context/material inventory、workspace | discover_sources、源文件快照、hash、extract | 保留/替代：继续保留；补来源在本次叙事中的用途，避免历史测试稿自动成为当前要求 | E11–E14、E24 |
| C03 | 缺失需求的访谈 | 问题列表 + QuestionResolver；旧会话构建本身非完整交互 | 对话问答仅由 Host 识别，缺口不是运行状态 | 缺失：阻塞问题需可记录、可恢复、可消解；只问影响当前决定的缺口 | E02、E06、E12、E25 |
| C04 | 决定与假设分开 | DecisionLog 含 user/approved_document/agent_assumption/policy、指纹 | existing_decisions 是字符串数组；输入版本有保护 | 部分迁移：每项决定的来源、适用范围、依据和状态丢失；不能把 Host 扩写 brief 当用户选择 | E03、E13、E25 |
| C05 | 内容策划前置 | brief、claim map、narrative/page tasks；规则 Planner 有机械生成缺陷 | 同一次 compose 交正文和 ContentPlan | 缺失：必须有制作前的可讨论内容方案；其结构记录不等于用户确认 | E01、E07、E12、E14 |
| C06 | 关键论据缺口处置 | evidence gap/claim map；曾有固定模块和过度要求 | 版本化 source_links、unresolved_facts；核心验证引用存在 | 部分迁移：未区分会推翻主张的缺口与可标注的小缺口；不能仅登记缺口后继续宣称已解决 | E02、E14、E16；P01 |
| C07 | 选料与复用决策 | sourcing strategy、authority/freshness/permission；25a 部分移除 | 文件选入与媒体 allowed assets；正文事实适用性主要靠 Host | 部分迁移：保留许可强约束，恢复关键证据选用理由、过时冲突处理；不恢复全局许可问卷 | E01、E24、25a diff |
| C08 | 视觉设计方向 | high-density ensure_style_lock，生产无选择则阻断；style_id 仍由调用者声明 | create 固化默认 design_context，直接可生成 | 缺失：默认配置只证明可渲染；需显式设计提案、已有规范适用性及用户选择依据 | E08、E12–E13；P01 |
| C09 | 内容密度与版式系统 | style 有 grid/density_rules/chart/table language；不是用户偏好自动证明 | 字号、颜色、layout_notes、Page.visual_spec；风格修改含 density/composition | 部分迁移：缺少首次制作的密度、图文比例、页型规则及代表页校准 | E08、E13、E22、E24 |
| C10 | 完整正文是制作权威 | PagePackage/content lock | Page v2、visible atoms、prompt 投影、readback | 保留/替代：不能回到正文缩写或图片替代正文；在这层之前恢复策划 | E12、E15、E24 |
| C11 | 样页通过后扩展 | 风格锁存在，但未证明旧版有完整样页协作闭环 | styles trial/adopt/expand 有严格绑定；新建 continue 不经过它 | 旁路：将同类样页准入用于新建生产，不复制第二套候选系统 | E12、E22；P01 |
| C12 | 连续执行的授权边界 | Preauthorization 有 scope/mode/expiry；旧规则过度禁止自然语言授权 | 主 Skill 连续执行到 ready_for_export；change plan 仅对局部变更限定范围 | 部分迁移：恢复可继承、可撤回的本次执行授权；直接用户指令可以作为依据 | E04、E21、E31、E34 |
| C13 | 人类决定的证据来源 | actor/source_type 存在，但调用者可自报，并非可信身份认证 | Review 可声明人类/独立身份；独立性有类型限制 | 部分迁移：区分可信 UI/原始用户消息和 Host 自报；不能靠新增 approved=true 解决 | E03、E08、E16 |
| C14 | 外部调用范围与额度 | 授权与构建预算分散 | allowance 事务、unknown、局部 max_calls 强；初始 external_call_limit=null | 部分迁移：初次生产也绑定目标页/阶段/次数上限；限额存在不等于本次已授权 | E13、E15、E31；P01 |
| C15 | 停止、取消、晚到与未知调用 | workflow stop + legacy build 状态 | task cancel、user_stop、unknown 阻断、晚到保护、用量账 | 保留：恢复流程必须沿用；阶段授权撤回也要触发相同约束 | E15、E31–E32 |
| C16 | 唯一主控与结果回写 | orchestration check、generation session、handoff | task start/accept、CAS、operation journal、不可变对象 | 保留/加强：职责 Skill 共用核心，不允许各自写另一套状态 | E11–E12、E15 |
| C17 | 依赖准入与阻断传播 | setup/backend/library/workspace 共同准入，曾误伤普通任务 | doctor 按步骤、NeedsTool；工具缺失阻断实际动作 | 保留/替代：按所选动作检查真实依赖；不复活与本任务无关的库/backend 准入 | E30、早期主控提交 |
| C18 | 原图/提示词/转换保真 | style/content locks、receipts、Scene | frozen request、真实调用观察、不可变原图、SVG hash | 保留/加强：加方向控制时不能放宽原图证据与保真 | E15、E24 |
| C19 | 原生可编辑构建与回读 | builder、readback、artifact manifest | compiler/pipeline、实际渲染、原生对象、回读 | 保留/替代：本轮无新渲染验收；既有技术能力不等于用户认可 | E23–E24 |
| C20 | 审阅时机和返修归属 | narrative advice、quality review、owner stage | 逐页三维 + 最终六维；内容完整性主要在最终审阅 | 部分迁移：生产前完成语义/论证评审，主线错误退回策划，不派成视觉修补 | E10、E16、E21 |
| C21 | 独立/专业审查要求 | 外部任务输入指纹、结果回写；并非每条路由都强制独立 | reviewer 类型存在；六维可 host_self；专业条件默认 false | 部分迁移/旁路：按任务约定独立审查，缺失就阻断该交付条件；Host 自审不代替用户认可 | E10、E13、E16–E17；P02、P04、P05 |
| C22 | 最终版本交付授权 | final approval 绑定最终文件 hash 和 readiness | delivery 主要依赖工程 pass；handoff 与 export 条件不一致 | 缺失/不一致：统一准入解释器，区分工程就绪、用户接受及允许交付，批准绑定实际文件 | E09、E17–E19；P02–P05 |
| C23 | 输入变化后的确认失效 | decision 输入指纹、handoff stale | task/source 更新会使任务与审阅失效；没有决定项的独立有效性 | 部分迁移：保留现在的数据失效，再补内容/设计/样页/授权的选择性失效 | E02–E03、E12、E15–E16 |
| C24 | 恢复与续作 | run/decision/handoff 历史 | immutable history、restore 新 revision、草稿与 uncertain receipt 恢复 | 保留/加强：旧批准不可因恢复旧快照而自动复活，调用费用与撤回事实不回滚 | E15、E32 |
| C25 | 用户可见阶段与下一责任人 | stage display、blocking questions、next-step | 页面/候选/生产工作面丰富；主流程无前期用户决定对象 | 缺失：显示当前任务、待决定事项、可做动作及确认版本；取消批准不等于删除产物 | E01–E02、E12、E19 |
| C26 | 反馈与复盘 | deck-learn/workspace learning，有脱敏要求 | 项目意见可留存；长期学习明确退役 | 合理退役 + 项目内补齐：保留本次决策理由和复盘；长期记忆仅用户明确要求时写 | E29 |
| C27 | 安装、版本与方法一致 | companion manifest，曾有断链 | managed release、method_release、CLI/Skill 同源、回滚 | 保留/加强：新增职责方法必须纳入 wheel、安装与冷启动验收 | E20、E33 |
| C28 | workspace/library/backend 强前置 | v0.9.11 强绑定，曾有 library blocked | 普通材料目录即可创建；native compiler | 合理退役：恢复主控不等于恢复旧平台依赖 | E11、E28–E30 |
| C29 | 发布成熟度和真实证据 | fixture/production/RC 分离、外部依赖快照 | package/CI/真实 Host/桌面/业务仍须分层 | 原则保留：恢复行为级验收矩阵；不把旧 RC 数字、未发布文件数当当前事实 | E26、早期主控提交 |
| C30 | 退役验收与职责追踪 | 旧阶段合同明确职责，实际有捷径 | old-files 台账大量统一指向 tests/rebuild；Flow Quality 验收未覆盖缺失意图/设计时必须停 | 缺失：每项重要职责要有唯一当前 owner、替代路径、正反例和真实会话证据 | E01、E26–E29 |

## 5. 已确认的重点问题

### F01 / P1：前期协作被压成一次正文生成（C01、C03–C06）

`open_compose_task` 指示 Host 自行推导受众问题并写完整 Page。返回的工作单不包含独立的内容方案待确认状态；`ContentPlan` 与完整稿同次采用。Agent 可以选定主线后自行沿该主线检查一致性。运行时有来源结构验证，没有用户方向一致性的前置判定。

### F02 / P1：首次视觉设计和信息密度没有生产准入（C08–C11）

创建时允许默认样式；continue 从 Page 直接派发 blueprint。后续 styles 流程的确认与先试后扩没有覆盖新建。默认设计快照解决各消费者默认值不一致，但不能承担用户设计选择。

### F03 / P1：执行授权和决定有效性缺少运行对象（C04、C12–C14、C23、C25）

“请整理方案”“只先规划”“先试两页”“按这个模板全套做”应产生不同允许动作。当前大部分差异由聊天约束 Host，生产状态本身没有足够字段表达。已有 decisions 字符串无法回答谁决定、针对什么版本、哪些页、何时失效。初次生成默认调用限额为空；局部修改反而有固定目标和 max_calls。

### F04 / P1：交付认可缺失且入口判定不一致（C21–C22）

六维工程通过可以全部来自 host_self；policy 默认不要求专业复核。即使 policy=true，当前导出条件允许 `kind=professional_use` 的 host_self 记录满足要求；条件使用 `status != fail`，未要求明确 pass。另一方面，handoff-check(delivery) 不检查该 policy；final-readiness 也只投影工程结果。单个入口加强仍可能被另一入口绕开。

这不是把所有专业审阅都解释成人工：现有 spec 03.3 对该 policy 的定义明确指向用户要求的人类专业复核，实际谓词弱于该定义。[E35]

### F05 / P2：内容评审的独立性、时机和证据解释不足（C06–C07、C20–C21）

源码能验证 locator 存在、来源版本正确和 observations 非空，无法据此证明论证成立或用户意图已确认。关键语义缺口目前缺少正式处置状态。不是所有 unresolved_facts 都应阻断：例如尚无成效数据但明确不承诺收益的页面可以成立；涉及核心主张的缺口必须先改主张、补证或请用户取舍。

### F06 / P1（治理）：能力退役验收未覆盖产品职责（C30）

“引用归零、方法同字节、单测通过”证明安装和工程替代，没有证明用户在主线、风格、密度、生产范围和交付上的控制权仍然成立。现有 AC-17 从已给受众和决定的任务出发，没有覆盖这些信息缺失、冲突或改变时的协作行为。

## 6. 本轮探针与验证边界

| 探针 | 实际结果 | 能证明什么 | 不能证明什么 |
|---|---|---|---|
| P01 | v3 create/start/accept/continue：decisions=[]、default style、限额 null，仍派发 blueprint | 新建路径没有用户方向/设计确认前置 | 未做生图；合成正文不证明业务质量 |
| P02 | 六维 host_self 工程记录使实际 delivery gate 放行 | 默认交付条件未要求用户/独立认可 | 合成产物不是实际可用 PPT 验收 |
| P03 | policy=true 时 export gate 阻断，handoff-check(delivery) 返回 verified | 两入口对同一要求解释不一致 | handoff 仍标 engineering；不能说它声称人工批准 |
| P04 | policy=true 加 host_self professional_use pass 后放行 | 该条件不等于人类确认 | 未证明外部身份伪造攻击 |
| P05 | PPT-only professional_use=not_evaluated 记录仍满足可选 gate | `status != fail` 与主体筛选可组合产生弱判定 | 使用 fixture store 插入；未验证 UI/公开 review 提交是否可构造相同记录 |

P01 使用现有 ContentPlan 合成 fixture 和真实核心服务调用。P02–P05 使用现有 export 合成 fixture，补齐占位角色仅为隔离政策判定；不把这些角色当真实图像、渲染或桌面证据。所有临时项目在 TemporaryDirectory 中自动清理；没有真实图片调用和客户项目写入。

源码证据与探针原始结果在 source-index.md、evidence.json。本轮没有运行全套 CI、浏览器、真实 ImageGen 或 PowerPoint 桌面检查；方案完成不代表修复完成。

收尾验证：reproduce.md 中 P01–P05 命令已整体执行成功，P05 的 Review 形状额外通过现有 schema；30 项职责、28 项验收的编号覆盖、Markdown 围栏和本地链接已检查。原有 tracked diff 的 SHA256 前后一致。

## 7. 不应原样恢复的旧设计

- 不恢复关键词/规则 Planner、固定痛点/风险/CTA、所有任务必须有决策对象、固定最低密度等内容模板化机制。
- 不恢复每阶段点击批准、把自然语言授权一概视为无效、用“ok/没有”等词表决定回答是否有效。用户可以明确委派判断；系统应记录委派范围。
- 不恢复强制 PPT Library、私有 backend、workspace/setup 或外部认证作为普通材料新建的统一前置。
- 不把旧文件中的 actor、approved、external reviewer 字符串当可信人类证据；旧实现同样存在声明与真实确认的距离。
- 不因旧学习模块曾存在，就自动写长期记忆或扫描工作区。
- 不整体回滚 PR105 或新核心。现有不可变对象、原图证据、输入失效、候选和恢复是修复基础。

需要恢复的是具有具体运行后果的职责，而不是旧系统的全部对象、名称和阻塞条件。实施方案见 repair-plan.md。
