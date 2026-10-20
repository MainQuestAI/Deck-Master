# 验收与验证分层

下列为开发验收定义；原规划的 NOT_RUN 快照保留在 traceability.json，实施实际结果单独记在 [execution-ledger.json](execution-ledger.json)，不能用规格状态覆盖运行证据。测试名称可按实际模块组织，但每项行为必须有可复核结果。预计用例数量不作为完成标准。

| AC | 最终负责卡 | 情景 | 可判定通过条件 | 验证层 |
|---|---|---|---|---|
| AC01 | WU00 | 最终 PR127 基线 | 记录最终 head、集成 base、合并情况和负责会话收口依据；不能把当前 Draft 快照直接标为完成。 | inspection |
| AC02 | WU00 | 检查与包证据 | required CI 绑定最终 head；包证据绑定准确源码；差异或环境失败有原证据和适用性结论，不挪用旧全绿。 | inspection |
| AC03 | WU00 | 接口漂移 | 逐项比对本 Spec 的现有/拟新增接口，已有同等能力移为复用，并更新对应任务和验收映射。 | inspection |
| AC04 | WU00 | 工作区隔离 | 实施分支包含最终基线；主工作区用户修改、历史 run、PR127 工作树均未被覆盖。 | inspection |
| AC05 | WU01 | 无副作用读取 | 六类项目读接口执行前后 Document、Task、调用账本和 writer floor 相同；读取不会发起 Host。 | integration |
| AC06 | WU01 | 引用与项目边界 | 不属于项目或所选快照引用链的 SHA/Task/Review 被拒绝；不允许磁盘存在即被读取。 | integration |
| AC07 | WU01 | 版本与分页 | 翻页固定同一 revision；非法/重复参数拒绝；后台 current 变化不替换子对象。 | integration |
| AC08 | WU01 | 局部损坏 | 单条资源/来源/Review 引用损坏返回可定位 issue，完好稿件仍可读；absent 与 unreadable 有区别。schema 断言 readable=false 仅含真实 Ref/issues 或 data=null，不可强制或伪造业务字段；SnapshotRead absent/unreadable 的 data=null，ready 不接受 null，Review 不可读不变成空问题或通过。 | integration |
| AC09 | WU01 | 老合同与能力 | 旧无 manifest/mapping/Review v2 字段的项目可读；新能力缺失局部降级；不开新持久字段。 | integration |
| AC10 | WU01 | 显示边界 | 不可信文本/Markdown 不执行 HTML/JS；元信息列表不读取全部资源正文；迟到回包不覆盖新对象。 | browser |
| AC11 | WU02 | 冻结清单 | 新任务显示与其 manifest 一致的顺序/数量/hash；旧任务无清单显示未记录，不套当前默认。 | integration+browser |
| AC12 | WU02 | 历史与当前可用性 | 历史派发依据与现在安装检查分列；名称/类别未验证时回退，不把当前 metadata 冒充历史。 | browser |
| AC13 | WU02 | 资源变化恢复 | 模拟缺文件和 hash 漂移，分别展示具体对象/原因并进入现有核实入口；不改旧 manifest。 | integration+browser |
| AC14 | WU02 | 未知调用 | 有未结调用时不能自动分配额度或重试；只展开/核实不触发 continue、cancel 或外部执行。 | integration+browser |
| AC15 | WU02 | 状态诚实 | 字节可用/已返回只表示读取事实，不能显示已应用、专业通过或已认可。 | browser |
| AC16 | WU03 | 零 Page 策划稿 | plan_only 零 Page 仍完整阅读 Narrative 与精确关联的固定 Plan/planned_roles，未产出 Page 的 page_ref=null；不同方向关联不同 Plan，缺失/不可读不回退到另一方当前计划；导入稿无 Narrative 时继续读正文，不自动建主线。 | browser |
| AC17 | WU03 | 主线真实展示 | 核心回答、节点关系、条件、问题及业务 alternatives 与原对象一致，不制造摘要或候选。 | integration+browser |
| AC18 | WU03 | 候选分类与比较 | 当前/本请求待选/历史分类正确；两份不同、可读、合法可达 Narrative Ref 可比较，支持 current+candidate，不要求多个 proposal；同 Ref/非法/不可读/不可达拒绝，历史比较禁止写入，后台变化不改左右稿及关联 Plan。 | integration+browser |
| AC19 | WU03 | 采用准入 | can_record_direction_decision 与 can_adopt 分开；无决定时 needs_decision=true、不可采用但可在准入通过后记录；有效覆盖决定复用。只有 argument、合法对象、有效决定和覆盖 scope 等实际采用谓词全部成立才允许采用；framing、历史及策略拒绝保持不可写。 | integration+browser |
| AC20 | WU03 | 两步事务恢复 | 决定成功后采用失败/断线保留已记录决定与两份独立 UUID/payload，明确部分完成；使用决定返回 revision 重新评估采用，不沿用旧 base。中间并发写入不静默改 base，不重复记录决定；unknown 先 lookup，拒绝不得放松事务。 | integration+browser |
| AC21 | WU03 | 采用范围 | 采用结果仅更新实际允许的引用并保留历史；不隐式派发 Page/原图任务或增加额度。 | integration |
| AC22 | WU03 | 只写/口播边界 | write_only 和 speech_only 的确认主线不被本轮入口重开；允许只读查看，不自动替换方向。 | integration+browser |
| AC23 | WU04 | 原子定位 | 段落/条目/表格单元通过实际 atom 映射联动来源；鼠标和键盘可用，正文选字不被破坏。 | browser |
| AC24 | WU04 | 旧论证绑定 | Page 绑定旧 Narrative 时读旧对象并说明差异，不跳到当前新主线；原 locator 与 source_version 不变。 | integration+browser |
| AC25 | WU04 | 映射缺失 | 未映射、原子失效、来源损坏分别显示具体情况，不能猜引用或高亮；仍可读稿与页面级来源。 | integration+browser |
| AC26 | WU04 | 示例隔离 | 方法案例和客户来源的展示及点击路径分开；E04 数字不被 UI 登记为业务 source_id。 | integration+browser |
| AC27 | WU04 | 返回与深链 | 刷新及从 finding/主线/来源来回切换后保留 project、revision、page、atom 和返回位置；finding 链接绑定 review_sha256、finding_id、原 source_index，过滤/排序仍定位非首条原对象，越界/身份不符不得默认首项。 | browser |
| AC28 | WU05 | Review 兼容 | v1/v2 均按真实合同读取 finding_id、impact、resolution；只对 v1 未要求的 v2 扩展字段显示未记录，缺必填 ID 不新增兼容。不同固定 Review 的同名 finding 不混淆；needs_review/not_evaluated/not_applicable 不变成通过。 | integration+browser |
| AC29 | WU05 | 真实问题定位 | 准确定位有效 page/element；整稿问题和失效位置降级到真实页面/范围，不跳到新版猜测文本。 | browser |
| AC30 | WU05 | 精确修订草稿 | 准备修改仅保存个人草稿；确认计划后才走原 plan/commit，scope/page/ref 与选中 finding 一致。 | integration+browser |
| AC31 | WU05 | 只审与分层 | review_only 不自动修稿；speech/design/source 问题不统一改写正文，不得越过 request/授权范围。 | integration+browser |
| AC32 | WU05 | 结果与解决状态 | 修稿返回/采用不自动把旧 finding 标 fixed；算术通过和资源加载不改变专业审阅或交付判定。 | integration+browser |
| AC33 | WU05 | 错误与回执 | 局改 stale base、提交回包丢失和 scope 拒绝后保留草稿/原 UUID；按已有 lookup 恢复，不重复派发。 | integration+browser |
| AC34 | WU06 | 多用途入口 | 新建和内容区使用中性用途文案；教学、研究、工程评审不强制预算或行动建议。 | browser |
| AC35 | WU06 | 保持输入与产物 | 示例提示不覆盖已有 brief，不改变 intent、阅读方式或口播规则；未指定字段不伪装用户确认。 | browser |
| AC36 | WU06 | 设计要求来源 | 内容交接来自同版本 content_requirements；frozen_task 与 derived_from_snapshot 清楚区分。 | integration+browser |
| AC37 | WU06 | 保留必要语义 | 限定条件、角色/原子关系可读；缺项不补造；页面装不下只提出原内容流程，不自动删正文。 | browser |
| AC38 | WU06 | 纯设计范围 | 查看/交接设计要求不改变 Page 正文、页集合和页序，也不启动生图。 | integration+browser |
| AC39 | WU07 | 同一目录选择 | 目录与适用性来自同一服务 resolver；未知/越权 ID 拒绝，无 JS 私有规则或任意路径读取。目录可读但无新阶段返回 200，browse_status 与 dispatch_status=cannot_dispatch 及原因独立；不得用空 phase 绕过范围校验，未评估选择不能伪装 validated。 | integration |
| AC40 | WU07 | 真实依赖预览 | M04+E04 展开准确默认/显式/依赖和字节；不加载无关全库；角色/阶段变化后重新校验。 | integration+browser |
| AC41 | WU07 | 冻结任务保护 | 已有待办仍可 200 浏览目录并显示依据固定、existing_task_frozen；网页选择/复制不修改旧任务、不新增业务状态或带参派发。preparation_only 恒 true，即使 new_content_task_possible 也不产生派发许可；GET/预览不写入、消耗或提高 writer floor。 | integration+browser |
| AC42 | WU07 | 正文安全预览 | input/after/walkthrough 可读，before 按需；script 不执行，data 不作指令，示例不作客户事实；过大正文明确失败。 | integration+browser |
| AC43 | WU07 | 准备稿与漂移 | 刷新可恢复个人 ID 选择；目录/字节/上下文指纹与 expected_basis 不符返回 409 并禁用旧复制，重新核对成功才恢复，不丢选择。无新阶段本身不是 409，原因与独立浏览明确；不可评估选择 copy_allowed=false，部分资源损坏与全局不可用分别处理。 | integration+browser |
| AC44 | WU07 | 实际使用回读 | 复制仍是未应用；真实 Host 重新核对后派发，新任务 manifest 才能证明所选资源实际进入任务。 | host+integration |
| AC45 | WU08 | 三类场景链路 | 经营诊断、方案比较、教学三套具来源的 Runtime 项目完成主线/依据/审阅阅读及允许的交接路径；fixture 与真实 Host 分开标记。 | browser+host |
| AC46 | WU08 | 视口与可访问性 | 1280×800、1440×900、390×844 无页面级横溢；键盘完成主要动作，焦点恢复、状态文字及长内容可读。 | browser |
| AC47 | WU08 | 独立安装 | 由最终实现 SHA 构建 wheel/sdist，在隔离 managed 环境运行同一浏览器关键路径；不借用 checkout/HOME 的资源。 | installed |
| AC48 | WU08 | 兼容与回退 | 老项目读取、当前 writer 拒写、历史版本/旧任务恢复保持；移除新 UI 不重写业务对象，不降低 writer 边界。 | integration+installed |
| AC49 | WU08 | 准确版本收口 | 最终 head 必需检查、受影响运行回归与未验证项均记录；包/报告准确绑定 SHA，未产生的证据保持 NOT_RUN。 | inspection |
| AC50 | WU08 | 分层交付回执 | 工程、浏览器、安装、实际 Host、专业阅读、人类体验分别记录；没有人类确认不宣称人类认可或正式发布。 | inspection |

## 分层执行方案

1. **纯读和HTTP集成：**构造固定项目和对象，测试真实Store/resolver/API；比较业务对象与调用账本前后，验证无副作用。优先覆盖跨项目/跨revision、局部损坏、旧合同、方向采用两步部分完成。
2. **浏览器：**使用实际服务和打包静态文件，不用mock接口替代通过声明。覆盖真实点击、刷新、后退、两个窗口并发、断线、键盘、窄屏；截图与交互日志绑定版本。
3. **Runtime范围：**在可公开测试项目执行真实plan/commit、task accept、候选/方向采用，检查只改指定页/层。外部模型可由受控测试Host提供固定输出以验证事务，但必须标识为fixture。
4. **实际Host：**至少一条真实“方法准备→制作工具重新核对→派发→读取冻结manifest→返回内容”的链路；三类场景的成稿质量与UI工程分别报告。可复用RC5真实稿作为阅读输入，但只有真正经过本轮Runtime操作的部分才能算本轮E2E。
5. **独立安装：**最终源码构建wheel/sdist并隔离安装；从安装命令启动工作台，在不借用checkout资源的环境验证A/B主路径。既有HOME保持。
6. **人类体验/专业认可：**交付可打开的工作台与场景说明，记录用户实际反馈。未发生时NOT_RUN，不由工程测试代填。

## 场景包

| 场景 | 核心观察 | 最少覆盖 |
|---|---|---|
| 经营诊断 | 材料事实、关联、因果假设不混淆 | 主线→原句→来源→具体审阅问题 |
| 方案选择 | 两个真实方向/业务替代的区别，选择代价可见 | 固定比较→决定→采用→返回新版本 |
| 教学讲解 | 无商业CTA也能读完整稿，练习与反馈各自保留 | 用途→主线→页稿→审阅定位 |
| 老任务升级 | 原依据不被新库改签 | 缺失/字节变化→核实→正式接续 |
| 只改口播/只设计/只审 | 允许层之外字节不变 | 原request与实际提交/采用核对 |
| 导入稿无映射 | 没有映射不造成全页不可用 | 页面级来源、清楚空态、无伪造论证 |

## 记录格式

每个执行条目至少包含 `ac_id / candidate_sha / environment / command_or_steps / result / evidence_refs / limitations`。结果为 PASS、FAIL、BLOCKED 或 NOT_RUN。证据可为JUnit、JSON回执、浏览器trace、截图、精确前后对象hash；不只给一句“测试通过”。

状态总结分开输出：`spec_validation`、`core_api`、`browser`、`installed`、`actual_host`、`professional_review`、`human_acceptance`。当前规格包检查只填第一项，不自动提升其余项。

受影响的既有测试族至少检查：RC5资源/Host选择、RC4 context、RC3 four skills与scope、compose phases、Review policy、content ops、operation recovery、Studio navigation和安装静态资源。按实际改动选命令；完成后只有新失败或新疑点才扩大/重复。
