# 验收映射：生成工作台 v3

状态：设计与开发验收分开。**以下87条生产行为AC全部未实施、未验证，不能标通过。** 本轮设计验收D01–D08如下分层记录，部分交互仍只有规格定义；原型使用合成数据和模拟执行不关闭任何生产AC。

来源：[PLAN](PLAN.md)、[代码基线](CODE-BASELINE.md)、[DX-SPEC](DX-SPEC.md)、[ENGINEERING-SPEC](ENGINEERING-SPEC.md)、[12张开发卡](packages/README.md)。行为正文逐条摘自卡片；每条唯一最终owner为其W卡。其它卡可引用证据，但不得另设同一AC的最终owner或重复计完成数。

## 验证层与证据规则

| 层 | 能证明什么 | 最低证据 |
|---|---|---|
| core | 模型/事务/幂等/失效/质量逻辑 | 固定commit、fixture、命令/结果、前后对象或revision hash、关键负例 |
| http | 真实本地服务的输入输出、鉴权与下载边界 | 路由/请求/响应及状态码，服务commit，错误/越界场景；隐去凭证 |
| browser | 页面呈现、实际操作、键盘/焦点/坐标/恢复 | 1280×800和1440×900对应截图/trace；输入、观察、结果；标明真实服务或模拟 |
| real Host | Codex等实际宿主接手和调用/返回关系 | 会话/执行引用、冻结请求、Attempt及真实调用事实、产物hash、实际阅图结论；不得伪造回执 |
| packaging | 最终代码在正常安装中的资源与交付一致性 | 最终commit与候选manifest、wheel/sdist清单/hash、隔离安装、离线资源和回退/包校验 |

同一条AC列多层时，各层均需覆盖。可控时钟可检验30分钟逻辑，不要求真实等待30分钟；这不能替代宿主接手的真实证据。行为层通过不自动证明视觉满意，真实阅图记录要指出页面、版本与结论。
证据记录建议使用 `evidence/<AC-ID>/` 并附索引JSON或Markdown；这是未来路径约定，本次没有创建生产证据。每条至少记录：ID、owner、实现commit、环境、输入、执行时间、验证层、结论、证据路径及未覆盖事项。

### 真实证据的语义与顺序

`evidence.observer` 的 core_frozen 只证明冻结拟用输入，host_reported 只证明Host申报，tool_observed/provider_receipt 才能根据其实际覆盖证明工具观察/供应商回执。标签必须有相应采集来源与证据引用，不能由Host自行改标签升级。W02-AC07真实绑定通过前，W05只展示冻结/申报/未知及证据边界；W07-AC07真实单页试作/采用/失效通过后才进入W08。

风格效果按事实保持、所选风格改善、未选维度退化、实际调用数分别判断；集成样本先记录返工轮次、手修PPT页数及Host等待两段时间基线，无同口径对照不宣称改善。

### UI规范与默认切换闸门

[UI-SPEC](UI-SPEC.md) 是W03/W05/W06/W07/W11/W12交互验收依据。查看原型只能关闭对应设计项，不关闭真实服务AC。SVG/PPT摘要依照代码基线：原生形状/文本声明、工程readback与字体事实、专业/桌面编辑记录各自呈现；没有OCR/图像文本叠加层/PPT光栅计数不补造。

W02真实冻结→提交→输出绑定为提示词强语义退出闸门；W07真实固定参考图纠偏→候选采用→局部失效为W08前置。默认入口切换须M2真实证据（含W08效果与W10恢复）、最终安装候选及回退演练齐全，并遵循既有发布授权；M1只读或原型完成不能替代。

### 开发入口与可复现证据

[DX-SPEC](DX-SPEC.md) §2–7约束W02/W03/W06/W07/W10/W11/W12及全包交付：新workbench/operations/requests与协议能力在实现前均为提案；脚本从真实回包取得运行时ID，operation身份在发送前持久保存。沿用deck-master及退出码0/2/3/4/5，Host经CLI、HTTP写仅同源浏览器session；自动端口不是5050。脚本/JSON样例/--help/恢复文档均应由最终代码执行验证，不能凭文字关闭AC。

W02须提供canonical_json_bytes编码及完整schema hash向量、唯一call ledger映射和协议能力兼容负例；W03提供临时registry/确定性项目工厂与Quickstart；W06提供operations原ID查询/重放和三类完整错误JSON；W07/W10提供候选/故障恢复脚本；W11提供真实快照三用途导出示例；W12用已有Python Playwright运行安装候选的资源/下载CI检查，真实Host单列。每项证据记录实际命令、退出码/HTTP状态、输入输出、来源commit及脚本路径。实施依赖仍无环；W01-AC01 完整压力需要 W07 后回访，同一 owner 保留 open，不能把首轮切片等同全部 AC 通过。W02 先修结果回执恢复，W06 后续扩展。

### 工程实施规格与固定门槛

[ENGINEERING-SPEC](ENGINEERING-SPEC.md)将五处工程约束固定到现有AC：W06的operation digest/result/revision原子事实与跨崩溃重放；W07的生成basis/目标指针/project CAS分离；W03/W05/W10的项目侧独立UI draft journal与ACK后跨端口恢复；W06的原始Unicode code point [start,end)与JS映射/excerpt；W01/W04/W10的300页×5候选×3Attempt固定压力。warm summary p95≤250ms、30页首屏≤2s、图像并发≤6/解码≤2、缓存60缩略图/4大图、20分钟heap末5分钟相对中段增幅≤20%，均为未验证实施门槛，首轮不达标修复而非改门槛。

launcher/registry原子生命周期、既有Host头/X-Deck-Token/Origin/请求体/路径/hash/XSS/SVG旧防线须对新路由回归；不新增cookie/只读token模型、页hold、incarnation或心跳调度。auto与trial共存、固定refs比较；个人UI journal不写业务revision、不驱动生产/质量/导出、不被历史恢复回滚。未同步浏览器缓冲不能自动跨origin，恢复文件须显式导入。W11 metadata canary仍由W11现有AC独占归属，工程规格仅规定细节。

## 本轮设计验收（不等于产品实施验收）

| ID | 唯一最终owner | 设计完成条件 | 应提供的设计证据 | 状态 |
|---|---|---|---|---|
| D01 | 主Agent | 定义独立Web入口职责、打开时机、用法、用/不用差异，明确Host与核心边界 | PLAN第1节；初次/再次/无Host场景路径；不依赖旧审阅定义的论证 | 设计完成；PLAN §1及入口路径已复核 |
| D02 | 主Agent | 五主模块及复用单页工作台职责、默认状态与主动作完整 | PLAN第3节、各模块设计图/原型定位；首屏“现在做什么”走查 | 设计完成；五模块及主动作经R2/R4走查 |
| D03 | 主Agent | 24页合成方案可点击，网格/连续/并排及缺图/偏离/旧PPT状态可演示 | 原型文件、两视口截图、浏览器操作trace；样本和模拟明确标记 | 合成原型通过；双视口、24页，见R4结果 |
| D04 | 主Agent | 从新建/材料→内容→请求→图→SVG→PPT→交付，以及纠偏/恢复路径完整 | PLAN第4节；原型主线及异常分支走查，逐步下一动作清楚 | 规格完成、原型部分覆盖；三条主线和六状态可走查，真实上传/下载/执行未接入 |
| D05 | 主Agent | 系统模板、预备prompt、用户草稿、实际提交四类信息分开；unknown不伪造 | 原型prompt状态截图；GenerationRequest/Attempt分工说明；未记录分支 | 设计及合成状态通过；真实请求绑定仍待W02 |
| D06 | 主Agent | project/chapter/page/artifact与whole/point/rect/text条件清楚，意见保存不等于执行 | 契约示例、标注范围交互及画布/非画布定位演示；不自动迁移旧选区 | 规格完成、原型部分覆盖；整页/框选已演示，点/文本范围尚无可操作样板 |
| D07 | 主Agent | 12包与87AC逐项对应、唯一owner、依赖/恢复/回退与验证层完整 | packages/README、W01–W12、本文件及编号/链接校验结果 | 设计一致性通过；12包/87AC唯一owner，生产均未实施 |
| D08 | 主Agent | AutoPlan和四轮独立复核的输入/输出/修订结论可追溯，缺失覆盖如实注明 | 实际评审文件及轮次索引；问题→修订映射；未解决事项与真实状态 | 评审记录完成；AutoPlan+R1–R4，CEO外部覆盖缺口及detector未运行已披露 |

设计证据集中于[四轮评审索引](reviews/README.md)、[原型走查](WALKTHROUGH.md)、[R4独立结果](reviews/round4-evidence/result.json)和[开发包一致性检查](reviews/delivery-check.json)。D04/D06保留部分覆盖标识，不宣称八项全部通过。设计状态只能据本轮真实证据填写；D通过不代表W通过。尤其D03使用模拟原型不意味着W04浏览器真实服务已通过，D08的文字记录不能代替未执行的独立复核。

## 生产行为验收（全部未实施、未验证）

### W01 · 链路读模型

来源：[W01](packages/W01.md)。最终owner：**W01**。

| AC | 行为条件（卡片原文） | 唯一owner | 验证层 | 证据要求 | 状态 |
|---|---|---|---|---|---|
| W01-AC01 | 24页混合阶段摘要保留顺序/page_id及未生成/当前/依据变化/历史/未知，不拿原图冒充PPT预览；按ENGINEERING-SPEC§6在300页×5候选×3Attempt压力下warm loopback summary p95≤250ms，详情按需读取，不在摘要展开全部候选/Attempt。 | W01 | core/http | 24页状态投影；300×5×3 manifest及warm summary≥100次原始采样/p95≤250ms；按需详情 | 未实施 / 未验证 |
| W01-AC02 | 读取历史 revision 后背景出现新结果，历史页、prompt引用及PPT所属快照保持不变；读取不产生新revision。 | W01 | core/http | 读前后revision计数/指针摘要；指定revision响应；后台更新前后同对象hash | 未实施 / 未验证 |
| W01-AC03 | 无 submitted_prompt 的旧图显示未记录；prepared 与 submitted 可分别读取，不能用重算文本填充 submitted。 | W01 | core/http | 旧项目缺submitted样本；prepared/submitted分别读取响应；不伪造断言 | 未实施 / 未验证 |
| W01-AC04 | 整稿PPT明确依赖有序页面集，页预览明确所属整稿/检查快照；确证不足时标推导或未知。 | W01 | core/http | 有序页面集合与PPT/预览引用快照；known/derived/unknown断言 | 未实施 / 未验证 |
| W01-AC05 | 单个对象损坏不让整稿白屏；该层返回局部错误和恢复入口，已知的其他页仍可读。 | W01 | core/http | 损坏单对象故障注入；局部错误响应；其它页可读的断言 | 未实施 / 未验证 |
| W01-AC06 | 旧/api/view字段兼容；新GET保留loopback Host检查、注册项目/路径与hash白名单，拒绝不存在/跨项目revision或对象且不泄露路径。只读不新增token/cookie要求；保留文本数据化与SVG隔离，新旧安全负例均通过。 | W01 | core/http/browser | 旧字段兼容；新GET Host/项目/路径/hash负例；只读无新token；XSS/SVG安全回归 | 未实施 / 未验证 |

### W02 · 过程产物与实际请求

来源：[W02](packages/W02.md)。最终owner：**W02**。

| AC | 行为条件（卡片原文） | 唯一owner | 验证层 | 证据要求 | 状态 |
|---|---|---|---|---|---|
| W02-AC01 | 新compose返回内容整合和大纲，页目标与Page/材料版本可导航；缺依据显式未解决，不生成假引用。 | W02 | core/http | 新compose信封、ContentPlan/来源引用对象、缺依据负例；schema校验 | 未实施 / 未验证 |
| W02-AC02 | 旧项目无ContentPlan仍能看稿；由Page推导的目录有推导标识，不写回伪造大纲。按DX-SPEC§4/§6验证新旧UI/core/Host/reader/writer组合，旧格式不原地迁移，新任务不静默降级。 | W02 | core/http | 旧Document读降级/推导标签/无写入；新旧UI-core-Host及reader-writer兼容矩阵与旧格式拒绝 | 未实施 / 未验证 |
| W02-AC03 | GenerationRequest冻结后不可改；核心按DX-SPEC§7 canonical_json_bytes返回input_hash，编码及完整请求向量可复现且CLI/HTTP一致。Host提交有差异时Attempt保留文本/差异及observer证据，不改冻结input、不将不匹配输入结果直接作为候选采用；host_reported非独立验证，core_frozen不代表已发送。 | W02 | core/http | 编码与完整schema hash向量；真实序列化字节；CLI/HTTP一致；冻结不可变/observer边界负例 | 未实施 / 未验证 |
| W02-AC04 | 每次attempt记录参考图及角色、参数与其观察来源；仅tool_observed/provider_receipt可据实证明相应实际提交事实。model/seed/参数未知显示未知，不从默认配置倒填，也不接受Host仅修改observer标签升级证据。 | W02 | core/http | 实际参考/参数证据来源；伪高observer标签拒绝；未知参数不倒填 | 未实施 / 未验证 |
| W02-AC05 | 实际新重试（不含同operation传输重放）产生新attempt并绑定既有call allowance/begin/settle；不另建调用账。第一次unknown/consumed事实不覆盖、不视为not_sent自动分配额度，结果分别对应尝试不串图。 | W02 | core | request-attempt-call allowance唯一账对照；unknown/consumed与结果绑定；无自动扣额重试断言 | 未实施 / 未验证 |
| W02-AC06 | 新任务完成后result_refs持久可读，旧缺口明示；protocol_version/required_capabilities与Host supported_protocols/capabilities在调用前校验，不支持则按typed error拒绝新协议写入。缺必需回执的结果拒绝采用但用量事实保留，既有退出码不变。 | W02 | core/http | 协议/能力组合及调用前拒绝；typed error/CLI退出码/HTTP状态；result_refs与缺回执用量保留 | 未实施 / 未验证 |
| W02-AC07 | 真实Host完成request→submit→output绑定：冻结hash、可核对工具提交/返回或供应商回执、Attempt和原图hash对应；交付可运行CLI脚本从真实回包取ID并复核唯一调用账。Host申报/静态信封不通过；通过后W05才启用相符强语义，新CLI在实现前仍为提案。 | W02 | core/real Host | 可运行CLI脚本与真实回包ID；request hash→工具观察/回执→attempt/output绑定；调用账与Host单方申报负例 | 未实施 / 未验证 |

### W03 · 独立入口与工作台壳

来源：[W03](packages/W03.md)。最终owner：**W03**。

| AC | 行为条件（卡片原文） | 唯一owner | 验证层 | 证据要求 | 状态 |
|---|---|---|---|---|---|
| W03-AC01 | 按UI-SPEC§1–2覆盖无项目/新空项目/已有原图/回访/待办直达；名称、用途与受众、保存位置必填可见，空材料不宣称可生成。create可登记唯一待交接compose但不执行模型；补材料沿inputs协调和旧任务失效规则，“整理内容”交接最新eligible compose，不重复开任务，验证创建→补材料→交接的任务ID/数量/状态。交付无项目可起的独立轻量workbench launcher、锁内原子registry与隔离Quickstart，真实输出URL/版本/项目/模式；last activity读UI-state不频繁改registry，新启动器仍为待实现提案。 | W03 | core/http/browser | 创建→补材料→交接任务ID/数量/状态且无重复；无项目launcher与隔离Quickstart；registry并发锁/原子写；last activity来自UI-state；进入状态trace | 未实施 / 未验证 |
| W03-AC02 | 目录选择/手填经权限/格式验证，取消不变当前；动态loopback端口与冲突行为正确，服务复用核对role/instance/project或registry/version，陈旧PID/错误端口身份不复用。launcher与项目独立退出/重启，原子运行元文件不误删新实例；不固定5050、不扫描或用file.name冒充路径。 | W03 | core/http/browser | 动态端口/角色身份/陈旧PID/并发启动；launcher与项目独立退出重启；运行元文件实例保护 | 未实施 / 未验证 |
| W03-AC03 | 五区导航、项目名、当前页/层/版本可辨，首次已有图以“看整稿原图”为唯一高权重主动作；待办直达后才提升该待办动作。深链/回访恢复原位置，过旧基准提示不强制跳走。 | W03 | browser | 初始唯一主动作、待办直达与返回截图；深链/恢复trace | 未实施 / 未验证 |
| W03-AC04 | 没有Host时可看和保存草稿；执行入口说明待交接，不显示模型已启动。 | W03 | browser | 无Host模式录屏/trace；草稿重载保持；没有伪running状态的截图 | 未实施 / 未验证 |
| W03-AC05 | 两个项目同page_id的草稿/位置不串；项目独立draft journal以自身ETag/sequence保存，历史只读持续标识。只在项目ACK后承诺跨端口自动恢复；未ACK仅origin缓冲及恢复文件。journal不增Document业务revision、不影响生产/候选CAS，历史恢复不回滚个人草稿。 | W03 | core/http/browser | 两项目隔离；journal ETag/sequence；ACK后实际换端口及未ACK反例；Document revision/CAS不变 | 未实施 / 未验证 |
| W03-AC06 | 按UI-SPEC§9在1280×800/1440×900保留可读内容和主动作；1024–1279限制多页校准，窄于768保留阅读/意见列表；焦点/Esc/表格键盘可用。交付确定性合成项目工厂及已有Python Playwright可运行验证，合成与真实Host证据分开。 | W03 | core/browser | 确定性合成工厂与Python Playwright可运行入口；两视口/窄屏/焦点/Esc/表格键盘trace | 未实施 / 未验证 |
| W03-AC07 | 按ENGINEERING-SPEC§7保留新旧GET的Host检查与POST的Origin+实例/项目X-Deck-Token、2MB请求体限制，无新cookie/读token模型或Host绕Origin通道。注册/路径/symlink/hash/跨项目、HTML及SVG脚本负例回归；旧格式不原地迁移，旧view不提前切换。 | W03 | core/http/browser | Host/Origin/X-Deck-Token实例归属/2MB/路径/symlink/hash/跨项目/HTML/SVG新旧路由安全矩阵 | 未实施 / 未验证 |

### W04 · 24页整稿画廊与制作矩阵

来源：[W04](packages/W04.md)。最终owner：**W04**。

| AC | 行为条件（卡片原文） | 唯一owner | 验证层 | 证据要求 | 状态 |
|---|---|---|---|---|---|
| W04-AC01 | 24页样本含2页偏离、缺图和失效PPT，用户30秒定位未制作/偏离页；记录真实观察而非自称达标。 | W04 | browser | 24页合成样本清单；首次用户定位计时与行为观察；偏离/缺失页截图 | 未实施 / 未验证 |
| W04-AC02 | 联系表/连续/并排显示同一固定层与版本；SVG/PPT缺失有实情占位，不混入原图。 | W04 | http/browser | 同层切换trace及请求对象hash；缺图占位截图；无类型冒充断言 | 未实施 / 未验证 |
| W04-AC03 | 切章节/筛选后选择保留，并提示筛选外选中N页；重排后仍选同page_id。 | W04 | browser | 跨章节/筛选/重排选择操作trace；筛选外数量与page_id核对 | 未实施 / 未验证 |
| W04-AC04 | 连续阅读回详情再返回保持位置；箭头/Enter/Escape可完成切页/聚焦/返回。 | W04 | browser | 连续阅读位置数值；进入/退出详情、键盘导航与恢复trace | 未实施 / 未验证 |
| W04-AC05 | 并排不裁内容，可开关同步缩放；混合模式若启用则每页标实际产物类型且非默认。 | W04 | browser | 2–4页并排截图；同步缩放开关与不裁剪核对；混合模式类型标签 | 未实施 / 未验证 |
| W04-AC06 | 按ENGINEERING-SPEC§6固定300页×5候选×3Attempt压力及30页样例，warm首屏可操作≤2s；图像≤6 in flight/≤2 decode，内存缓存≤60缩略图/4大图并释放资源。新图后台派生/旧图渐进、project+hash+variant命中，冷热分栏及环境实测；首轮不达标修复不改门槛。 | W04 | core/http/browser | 固定300×5×3与30页manifest；两视口warm≤2s；6/2并发、60/4缓存采样及释放；冷热缩略图 | 未实施 / 未验证 |
| W04-AC07 | 1280/1440两尺寸下页标题、产物层、状态和动作可辨，状态同时用文字/图标，不仅颜色。 | W04 | browser | 两视口全部模式截图；文字/图标状态检查及键盘主操作 | 未实施 / 未验证 |

### W05 · 单页链路与提示词工作台

来源：[W05](packages/W05.md)。最终owner：**W05**。

| AC | 行为条件（卡片原文） | 唯一owner | 验证层 | 证据要求 | 状态 |
|---|---|---|---|---|---|
| W05-AC01 | 从原图最多3次明确点击找到对应逐页稿及提交记录；evidence.observer为host_reported时写“Host申报”，仅可核实证据支持的实际提交使用强语义；不可得时找到未记录说明。 | W05 | browser/real Host | 三次以内定位trace；host_reported/独立观察/未记录分支；关联W02-AC07真实证据 | 未实施 / 未验证 |
| W05-AC02 | prepared、actual、草稿同时存在时文案、只读/可编辑和版本明确；显示core_frozen/host_reported/tool_observed/provider_receipt含义，冻结不等于提交、申报不等于独立验证；改草稿不改原图/历史。 | W05 | core/browser | 四observer语义截图；prepared/actual/draft隔离；历史hash不变断言 | 未实施 / 未验证 |
| W05-AC03 | 按UI-SPEC§3/6固定页/层/版本，同页比较的新结果不替换对象；候选画面主栏是当前采用与所选候选，参考图辅助呈现，候选切换连同依据/按钮目标一起切；单页SVG预览不冒充assemble后按页PPT预览。 | W05 | http/browser | 固定current/candidate/ref与切候选的依据绑定trace；SVG/PPT阶段区别截图 | 未实施 / 未验证 |
| W05-AC04 | 模型/参数/参考图未知时显示未知；不能由项目默认值填成当时实参。 | W05 | core/browser | 旧参数未知fixture；UI未知标签；当前默认参数不同的负例 | 未实施 / 未验证 |
| W05-AC05 | 老prompt不能可靠分段保留全文/选段，建议标推测并供原文核对；文本选段复用ENGINEERING-SPEC§5原始Unicode code point范围，不归一CRLF/组合字、不直接用JS UTF-16 offset，不把图片伪造成文本层。 | W05 | core/browser | 原文选段/推测标签；原始code point与UTF-16映射、CRLF/组合字例；无伪图片文字层 | 未实施 / 未验证 |
| W05-AC06 | 草稿分未保存/仅origin缓冲/项目保存中/已ACK/待核实；项目journal为恢复主副本，ETag冲突保留双方。只有ACK草稿自动跨端口恢复；离线未同步提供下载恢复文件及新origin显式导入，校验项目/基准/hash不自动提交。配额/服务失败不报已保存，pending payload与后写draft分离。 | W05 | core/http/browser | journal ACK/ETag冲突/未知双稿；不同端口与离线未同步；下载→新origin导入及hash/基准负例 | 未实施 / 未验证 |
| W05-AC07 | 缺图/仅正文/历史/失败均有下一动作；SVG/PPT摘要按证据显示editability、text_runs/native_shapes、字体与专业/桌面编辑评估。无raster计数或OCR文字层不补造；SVG推导image数明确标来源，未经实际桌面编辑不写已验证。 | W05 | core/http/browser | artifact/readback/trace/字体/review原始字段→UI对照；unknown/未评估；无OCR/raster误称检查 | 未实施 / 未验证 |

### W06 · 标注、变更计划与最小交接闭环

来源：[W06](packages/W06.md)。最终owner：**W06**。

| AC | 行为条件（卡片原文） | 唯一owner | 验证层 | 证据要求 | 状态 |
|---|---|---|---|---|---|
| W06-AC01 | 按UI-SPEC§7默认阅读拖动不建意见；按层开放整页/点/框/文本，标注与缩放平移互斥，Esc取消范围，框可删/重画。scope条件正确；缩放/letterbox/滚动坐标准确，意见编号回原版本，多区域保留不迁移。 | W06 | core/browser | 阅读/标注/缩放互斥trace；框删重画/Esc/回原版本；坐标与scope校验 | 未实施 / 未验证 |
| W06-AC02 | 保存意见仅持久化，加入计划才预览，不执行/不失效当前；图片无伪OCR选取。文本绑定原始UTF-8文本ref/locator/hash，以Unicode code point [start,end)定位，保留CRLF、不规范化；JS映射UTF-16、服务核验excerpt，emoji/组合字/错误摘录测试。键盘整页/百分比范围可用，错误保留输入。 | W06 | core/http/browser | 保存不执行；Python/JS坐标向量含emoji/ZWJ/组合字/CRLF/excerpt拒绝；键盘范围/输入保留 | 未实施 / 未验证 |
| W06-AC03 | plan经CLI/HTTP共享Service返回精确页/层/基准/调用上限及下游影响且不执行；commit前基准/payload变化必须重算不能扩大。可运行脚本从项目真实回包取revision/ref再生成有效输入，不用占位ID/hash。 | W06 | core/http | 真实回包revision/ref→有效输入→plan脚本；CLI/HTTP相同影响；基准/payload变化拒绝与无调用 | 未实施 / 未验证 |
| W06-AC04 | 批量失败零业务提交，成功全入库；operation UUID持久/项目去重/无TTL。按ENGINEERING-SPEC§2将request_digest/result_ref/revision与业务变更同次原子提交，锁内先查重，索引可重建；pointer前后崩溃和插入后续写入仍同ID同payload返回原结果，异payload拒绝，不再建任务/扣额。 | W06 | core/http | receipt/result/revision同提交；锁内并发；pointer/索引前后kill；后续写入旧ID重放；索引删除重建与零重复任务/额度 | 未实施 / 未验证 |
| W06-AC05 | 按UI-SPEC§5保存后持久交接面板可从待办/运行返回；核心生成摘要、真实ID的deck-master-handoff.v1块及安全CLI读取入口。复制仅已复制未开始、Codex仅预填；Host经CLI真实start/execution_ref后才显示接手，部分返回非整组完成。 | W06 | core/http/browser/real Host | 真实ID交接数据块/安全CLI入口；持久面板copy/start/partial状态及真实execution_ref | 未实施 / 未验证 |
| W06-AC06 | 响应未知暂停新业务提交，operations从已提交事实核实/重放原ID，索引丢失可重建；查询超时不换ID，not_found仅同payload安全重放。pending副本与后写draft分离，项目journal ACK状态不冒充业务提交；未同步跨origin靠恢复文件，CLI/HTTP typed error及docs_ref一致。 | W06 | core/http/browser | 已提交历史核实/索引重建；pending与后写draft分离；journal ACK非业务成功；恢复文件/typed错误 | 未实施 / 未验证 |
| W06-AC07 | 取消已确认后晚到结果不能覆盖当前；超过30分钟提供核实/取消再交接，绝不自动重复调用。 | W06 | core/http/browser | 可控时钟超30分钟、取消确认/晚到测试；不自动二次调用证明 | 未实施 / 未验证 |
| W06-AC08 | 真实本地服务完成标注→计划→提交→复制→真实Host接手；交付CLI可运行脚本、同源浏览器HTTP示例及三类完整故障JSON/恢复步骤，沿用退出码0/2/3/4/5和正确HTTP状态。模拟单独标，不开放无Origin脚本写入口。 | W06 | core/http/browser/real Host | 真实最小链/CLI脚本/同源浏览器；conflict、payload conflict、保存未知完整JSON及恢复；退出码/HTTP状态 | 未实施 / 未验证 |

### W07 · 阶段重跑、候选与采用

来源：[W07](packages/W07.md)。最终owner：**W07**。

| AC | 行为条件（卡片原文） | 唯一owner | 验证层 | 证据要求 | 状态 |
|---|---|---|---|---|---|
| W07-AC01 | 试作返回候选不改当前采用内容槽（Page/原图/SVG/预览/整稿输出引用）；任务/调用/候选事实可推进管理revision；两主栏/参考图、切候选时依据/Attempt/时间/按钮目标一致。比较固定refs期间auto continue可合法产生当前结果，提示更新而不漂移比较；不设置页级hold/租约，不以试作阻塞全项目生产。 | W07 | core/http/browser | 固定current/candidate比较；切候选绑定；auto合法前进且无hold，trial不阻塞生产 | 未实施 / 未验证 |
| W07-AC02 | 采用候选原图后P08当前原图变更，P08下游与整稿失效；其它页原图/SVG保留，旧产物仍可历史查看。 | W07 | core/http | adopt事务前后每页产物ref矩阵；仅目标下游及整稿失效断言 | 未实施 / 未验证 |
| W07-AC03 | 仅SVG修复保留Page事实、原图和actual prompt；生成新SVG后先做单页SVG预览/检查，再整稿assemble并取得按页PPT预览；不产生图像调用或假单页PPT预览。 | W07 | core/http | 仅SVG请求/调用差异；单页SVG检查→整稿assemble→按页PPT预览链 | 未实施 / 未验证 |
| W07-AC04 | 按ENGINEERING-SPEC§3分别验证generation_basis、adoption_target指针和project CAS；无关页更新只重plan/new operation，不判候选过期或重新调用。目标指针/真正依据改变说明各自原因，旧计划禁用直接采用并保留固定比较。单页/批量同Service，任一冲突零采用、保留选择，子集经用户新计划提交。 | W07 | core/http/browser | 无关页更新仅新plan且调用数不增；basis/target/CAS三个原因；单项/批量零采用与用户子集重计划 | 未实施 / 未验证 |
| W07-AC05 | 逆序/重复/取消晚到归属正确，晚到只保留调用事实不覆盖。删页后历史恢复保持稳定page_id但新工作用新task_id，原terminal状态及基准ref继续拒绝旧结果，不添加incarnation或复活旧任务。 | W07 | core | 逆序/重复/取消晚到；删页→同page_id恢复→新task_id；原terminal与base ref继续拒绝旧结果 | 未实施 / 未验证 |
| W07-AC06 | 整稿编译缺当前有效SVG或质量门禁不满足时明确拒绝；候选采用和已查看都不能当pass。 | W07 | core/http | 缺依赖/门禁失败执行拒绝响应；采用/已查看不改变quality pass断言 | 未实施 / 未验证 |
| W07-AC07 | 进入W08前真实完成固定参考图+短要求纠偏：图像ref冻结→实际Host提交→候选→比较→采用。可运行脚本从真实回包取ID：无并发时采用前当前采用内容槽不变（管理revision可前进），采用后仅目标下游/整稿失效、未改页ref不变；auto交错时current变更须归属auto，trial只落候选，固定比较不漂移且旧采用计划不能覆盖。另做SVG重建/仅修SVG真实往返，留hash与阅图证据，mock不关闭。 | W07 | core/real Host | 无并发current不变及auto/trial交错来源/固定ref；真实参考图进入调用与可运行脚本回包ID；候选采用前后ref矩阵；真实SVG链及人工阅图 | 未实施 / 未验证 |
| W07-AC08 | 无UI的既有continue自动生产行为不变；试作不把全项目永久停在人工采用。 | W07 | core/real Host | 无Web既有continue回归；自动生产与人工试作隔离记录 | 未实施 / 未验证 |

### W08 · 跨页风格校准

来源：[W08](packages/W08.md)。最终owner：**W08**。

| AC | 行为条件（卡片原文） | 唯一owner | 验证层 | 证据要求 | 状态 |
|---|---|---|---|---|---|
| W08-AC01 | 简单路径只需固定P07参考原图、P08目标页及一句短要求，就可到试作影响计划；不强制展开prompt或维度表。参考版本持续可见，后台更新不漂移；历史prompt缺失诚实标未知。 | W08 | http/browser | 参考图+短要求默认路径trace；高级区未展开仍可规划；缺prompt诚实标未知 | 未实施 / 未验证 |
| W08-AC02 | 高级维度/prompt对照按需展开；只选色板/文字层级时P08事实、数字、标题、论点保持，构图单独选，不能默认复制P07布局/内容；简单路径可随时展开核对并编辑。 | W08 | core/browser | 按需高级对照trace；所选风格与目标事实/未选构图保持的diff核验 | 未实施 / 未验证 |
| W08-AC03 | 提示词无法可靠分段时可选原文或请求Host提取建议，推测不伪装为实际生成来源。 | W08 | browser | 旧prompt原文选段路径与Host提取建议区分；推测/真实来源标签 | 未实施 / 未验证 |
| W08-AC04 | “极简/高密度”等互斥约束显式列冲突，用户取舍形成新版本及diff；不静默丢弃目标约束。 | W08 | core/browser | 互斥约束样本；用户选择→Recipe新版本/diff；约束无静默丢失 | 未实施 / 未验证 |
| W08-AC05 | 默认先试1页，试作提交/返回本身不替换当前采用；auto可独立推进，固定比较保持并提示新基准，旧计划不得覆盖。无并发时当前采用内容槽不变（管理revision可前进）；比较采用后用户显式勾选余页扩展，调用上限和作用域固定。 | W08 | core/http/browser | 无并发current不变，auto交错只更新其合法current、trial候选固定；先试1页与后扩范围的两个ChangeSet；trial无副作用/调用上限断言 | 未实施 / 未验证 |
| W08-AC06 | 扩展前P09基准变化时单独提示冲突，不替换新内容；未选页及参考页完全不改。 | W08 | core/http/browser | P09变化冲突响应；参考页/未选页ref不变；重新计划trace | 未实施 / 未验证 |
| W08-AC07 | 一次真实P07→P08试作采用→P09扩展留存请求/原图/采用证据，按固定样本分别评价事实保持、所选风格改善、未选维度是否退化及实际调用数；原图并排人工阅图并记录不满意结果，不以prompt相似度或笼统“更好”替代判断。 | W08 | core/real Host | 真实图/请求/采用；事实保持、所选风格改善、未选维度退化、实际调用数逐项记录及人工阅图 | 未实施 / 未验证 |

### W09 · 内容与来源调整

来源：[W09](packages/W09.md)。最终owner：**W09**。

| AC | 行为条件（卡片原文） | 唯一owner | 验证层 | 证据要求 | 状态 |
|---|---|---|---|---|---|
| W09-AC01 | 材料上传/提取完成与Host已读取并判断影响分别显示；材料或受众/用途/既有决定更新尚未采用时明确待协调，不要求重复确认已提供事实。 | W09 | core/http/browser | 材料及受众/用途更新，已给事实不重复确认；材料上传/提取/读取/影响判断独立事实响应与UI状态截图 | 未实施 / 未验证 |
| W09-AC02 | 从正文来源可到确切材料版本及页码/段落；只到材料级时诚实说明，不虚构精确定位。 | W09 | core/browser | 来源材料version/locator跳转trace；仅材料级引用和缺失样本 | 未实施 / 未验证 |
| W09-AC03 | 鼠标与键盘均可重排，焦点/选择跟随稳定page_id，未改页产物保持；移除前显示影响，完成后定位邻页并使相关未完任务失效，历史页与材料不删除，整稿PPT不冒充最新。 | W09 | core/http/browser | 鼠标/键盘重排焦点与移除影响确认；重排/删页前后page_id/产物/task/整稿ref矩阵；历史可读证明 | 未实施 / 未验证 |
| W09-AC04 | merge/split返回新身份和来源关系；显式选定多页交Host跨页改写时保留原page_id及来源，未选页ref不变。旧选区/意见保留旧基准不自动迁移，用户知道新页或新版待处理。 | W09 | core/http/browser | 明确范围跨页改写保留身份、来源和未选页ref；merge/split信封、新page_id/来源关系；旧标注未迁移截图 | 未实施 / 未验证 |
| W09-AC05 | 仅正文项目可直接编辑标题/正文，保存后刷新及切页内容准确，草稿按项目/页/基准隔离，错误/未知保存保留输入并复用原operation核实。改P12事实只使实际受影响页/层待更新；原图是否需重做由显式计划决定，不能把保留旧图说成已适用。 | W09 | core/http/browser | 仅正文编辑→保存→刷新/切页准确，项目/页/基准草稿隔离；修改P12后的影响计划及各层ref矩阵；旧原图适用性与显式重做选择 | 未实施 / 未验证 |
| W09-AC06 | 材料或受众/用途变化由Host提交影响依据并保留既定决定；无影响须具体unchanged_reason，不按时间/字数判断，不默认整套重制或重复确认已提供事实；输入对齐不依赖界面已查看。 | W09 | core/http | 受众/用途影响依据、既定决定保留及避免无依据整套重制；unchanged_reason必需校验；输入对齐状态由Host结果更新证明 | 未实施 / 未验证 |
| W09-AC07 | 真实材料替换→影响判断→局部稿更新证明未改页保持；同组用例覆盖改受众/用途、保留既定决定及避免无依据整套重制。失败和输入变更晚到结果不能覆盖新稿，真实Host与合成用例分别留证。 | W09 | real Host | 真实材料替换与受众/用途更新用例，合成与Host分栏；真实材料替换及input_revision结果；未改页ref保持、迟到拒绝证据 | 未实施 / 未验证 |

### W10 · 完整运行台与恢复

来源：[W10](packages/W10.md)。最终owner：**W10**。

| AC | 行为条件（卡片原文） | 唯一owner | 验证层 | 证据要求 | 状态 |
|---|---|---|---|---|---|
| W10-AC01 | 修改组显示原请求、作用页、任务及所有结果，逆序返回不串归属；复用W02 requests/attempts和W06 operations/handoff查询，真实ID贯穿CLI/HTTP，不新建调用账或第二套查询真相。 | W10 | core/http/browser | request/attempt/operation真实ID查询脚本；唯一调用账；同组逆序结果与全生命周期trace | 未实施 / 未验证 |
| W10-AC02 | 只把缺事实/待交接/候选待决定/冲突/未看结果列为人的待办；正常运行不是催用户处理的todo。 | W10 | browser | 缺事实/待交接/候选/冲突/未看结果及运行样本待办截图 | 未实施 / 未验证 |
| W10-AC03 | 复制/预填不显示已发送或处理中；真实execution_ref及接手时间与task_start一致。 | W10 | http/browser | copy/deeplink/task_start前后截图；接手时间与execution_ref核对 | 未实施 / 未验证 |
| W10-AC04 | 刷新遵守活动3秒/闲置15秒/隐藏暂停/focus立即/最长30秒退避，单请求在途且不触发continue。按ENGINEERING-SPEC§6固定压力运行20分钟，末5分钟heap相对第6–10分钟中段增幅≤20%；环境/原始采样留证，首轮失败修复不放宽。 | W10 | http/browser | 既定刷新请求时间线；300×5×3的20分钟heap原始样本，6–10/16–20分钟中位数增幅≤20% | 未实施 / 未验证 |
| W10-AC05 | 30分钟未返回可查原任务/取消后重交，未确认取消不重复派发；unknown不当not_sent、不自动重新分配额度，晚到事实保留但不覆盖。可运行恢复脚本从真实回包取ID，故障注入与真实Host记录分开。 | W10 | core/http/browser | 可运行恢复脚本；超时/取消未知/晚到故障；unknown未变not_sent、无自动分配额度/重复派发 | 未实施 / 未验证 |
| W10-AC06 | 部分结果可逐项看和选择；重试明确哪些未完成、哪些已采用，不重复已成功外部调用。 | W10 | core/http/browser | 部分结果与已采用/未完混合样本；重试作用域与调用计数 | 未实施 / 未验证 |
| W10-AC07 | 刷新/崩溃/断网恢复滚动/缩放/选择/比较及草稿；项目ACK草稿由journal跨端口读取，未同步保留origin缓冲并可下载/新origin导入，不虚称自动恢复。保存未知查原operation已提交事实，UI journal不回滚或覆盖业务/调用历史。 | W10 | core/http/browser | 刷新/断线/崩溃与实际跨端口；ACK/未同步恢复文件分支；原operation核实且业务/调用历史不变 | 未实施 / 未验证 |
| W10-AC08 | 无任务有当前可做动作；错误含对象/原因/动作及离线docs_ref，CLI/HTTP共享typed error与既有退出码。continue正常awaiting_host退出3、状态读取HTTP200不当失败；完整错误JSON与可运行恢复步骤随卡交付。 | W10 | core/http/browser | 完整typed错误JSON、既有退出码/HTTP状态及离线docs_ref；可运行恢复；awaiting_host不误报失败 | 未实施 / 未验证 |

### W11 · 版本与文件交付

来源：[W11](packages/W11.md)。最终owner：**W11**。

| AC | 行为条件（卡片原文） | 唯一owner | 验证层 | 证据要求 | 状态 |
|---|---|---|---|---|---|
| W11-AC01 | 历史选版先只读查看/固定比较；确认恢复前显示源版本、当前版、受影响页/产物和运行任务，取消不写入，确认后创建新版本，冲突保留双方。当前执行/调用事实及user_stop不回滚。 | W11 | core/http/browser | 选版→查看/比较→确认恢复，取消/冲突保留；历史读前后无写入；restore新revision；调用事实/user_stop不回滚断言 | 未实施 / 未验证 |
| W11-AC02 | 导出开始后背景结果到达，包中所有页/PPT/报告仍属于冻结revision，manifest可核验hash。扩展export --revision/engineering及HTTP同Service，脚本从view/history真实回包取版本与导出ID，不用示意值。 | W11 | core/http/packaging | 从真实版本/导出ID的CLI/HTTP脚本；导出中后台更新；冻结manifest与文件hash | 未实施 / 未验证 |
| W11-AC03 | review不含绝对路径、私密原材料/完整prompt/认证信息；engineering清楚说明内部内容并能恢复项目。 按ENGINEERING-SPEC导出检查PNG文本/EXIF/XMP、SVG注释/metadata、PPTX属性/备注/关系中的隐私canary，生成清理副本、不改不可变原件、不盲删正常可读内容。 | W11 | core/packaging | review/engineering解包清单与敏感数据扫描；隔离恢复记录 | 未实施 / 未验证 |
| W11-AC04 | delivery必须使用所选快照的有效检查及输入对齐事实；不pass或该快照inputs未协调时拒绝，并定位未完成页/层/维度。历史快照与当前稿持续区分，旧PPT不能冒充新稿。 | W11 | core/http/browser | 指定快照有效检查/inputs阻断；历史与当前不同pass样本；定位与失效说明 | 未实施 / 未验证 |
| W11-AC05 | 三类包、版本/文件名与所选快照一致；UI-SPEC§8导出成功显示文件及版本清单，失败保留拒绝维度。可编辑性/工程/专业/桌面证据分开，图像元素不宣称可编辑文字；无PPT的审阅包列缺项不造PPT。 | W11 | core/browser/packaging | 三类下载包/manifest/所选快照；独立能力/工程/专业/桌面摘要截图与无PPT分支 | 未实施 / 未验证 |
| W11-AC06 | 恶意路径、跨项目/失效导出ID下载拒绝；正常Python Playwright同源浏览器下载的hash与manifest一致，下载断开重取同冻结导出。Host/脚本使用CLI导出，不新增绕Origin的HTTP写token。 | W11 | core/http/browser | CLI导出和Python Playwright同源下载；越界/跨项目/失效ID；断线同导出重取/hash | 未实施 / 未验证 |
| W11-AC07 | review语义变化有兼容说明、engineering内部材料提示与CLI处理；随卡交付可运行三用途导出/下载/隔离恢复脚本及--help/JSON/错误退出码验证，示例由真实服务回包取ID，不用占位文件。 兼容脚本覆盖隐私元数据清理副本与原件hash不变。 | W11 | core/http/browser/packaging | 三用途可运行导出/下载/隔离恢复脚本；review差异/engineering材料说明；help/JSON/退出码与HTTP状态 | 未实施 / 未验证 |

### W12 · 集成、安装候选与切换准备

来源：[W12](packages/W12.md)。最终owner：**W12**。

| AC | 行为条件（卡片原文） | 唯一owner | 验证层 | 证据要求 | 状态 |
|---|---|---|---|---|---|
| W12-AC01 | 最终提交重建wheel/sdist隔离安装；HTML/ESModules/CSS/字体/license/图标/Skill全随包，不引用checkout/CDN；安装包实际执行DX-SPEC Quickstart及逐包CLI/JSON/错误/恢复脚本，保持deck-master唯一命令面与既有退出码。 | W12 | core/http/packaging | 最终构建/安装manifest；逐包Quickstart/help/JSON/错误恢复脚本运行；唯一CLI/退出码/资源检查 | 未实施 / 未验证 |
| W12-AC02 | 按UI-SPEC§1–11在1280×800/1440×900覆盖进入状态、主动作及全链路、模式互斥/双稿/焦点/窄屏；已有Python Playwright执行真实本地服务，离线资源和下载检查可在CI运行，不新增Node构建工具，合成验证与真实Host分栏。 | W12 | http/browser/packaging | 已安装真实服务Python Playwright/CI执行；两视口全链/离线资源/下载；合成与Host分栏 | 未实施 / 未验证 |
| W12-AC03 | 30页真实项目完成两轮视觉修改、一次跨页风格复用、一次仅SVG修复和一次材料输入更新；实际阅图确认内容/页正确，并记录返工轮次（区分生图/SVG）、手修PPT页数、Host等待时间的首次基线，不虚构改善。 | W12 | real Host | 30页真实链及人工阅图；首批返工轮次/手修页数/两段Host等待时间基线，未知明确标记 | 未实施 / 未验证 |
| W12-AC04 | 87AC均有环境/commit/层级/结果证据，阻断零；特别核验W02真实冻结→提交→绑定退出闸门、W07真实参考图纠偏/候选采用/局部失效、W08真实跨页效果、W10恢复。原型/Host申报不能代关闭，默认切换前M2真实证据必须齐全。 | W12 | core/http/browser/real Host/packaging | 87AC索引与W02/W07/W08/W10真实闸门审计；M2退出证据清单 | 未实施 / 未验证 |
| W12-AC05 | 最终安装候选复验ENGINEERING-SPEC§6同一300页×5候选×3Attempt manifest与固定门槛；引用W01/W04/W10 owner原始证据并留安装后HAR/内存/环境，不以100页记录替代。无30张base64原图塞首屏。 | W12 | http/browser | 同一300×5×3 manifest的最终安装HAR/内存/SLO及环境，引用原owner证据 | 未实施 / 未验证 |
| W12-AC06 | 正常安装重走批量修改/整稿/输入更新，旧候选不验新修复。按DX-SPEC记录支持环境、文档起点、步骤耗时/求助、首个理解结果；安装/下载/Host耗时分栏，≤5分钟未测不宣传。真实返工/手修/等待同口径，无对照只报测量不报提升。 | W12 | browser/real Host/packaging | 最终候选正常流程；支持环境/文档起点/耗时/求助/首个理解结果；安装/下载/Host及真实指标分栏 | 未实施 / 未验证 |
| W12-AC07 | 临时registry/项目/安装目录演练旧入口、停新写和恢复已验证安装；最低writer/项目格式可查，旧UI回退不等于旧writer可写。项目/候选/调用历史不丢，不碰真实项目或实际HOME安装。 | W12 | core/browser/packaging | 临时registry/项目/安装回退；最低writer/格式记录；真实HOME未修改与历史完整性 | 未实施 / 未验证 |
| W12-AC08 | 三类导出与所看版本一致，离线包可核验；验证切换前置清单含M2真实证据、最终候选与隔离切换/回退演练，无发布授权时不改变默认入口。实际默认切换另按既有G5/T25授权执行并单独记录，未执行发布不阻塞安装候选验收，准备完成不称已发布。 | W12 | browser/real Host/packaging | 三用途包hash；发布前置清单；隔离切换/回退；无授权未改默认；实际发布状态单列 | 未实施 / 未验证 |

## 汇总与关闭条件

生产AC：87条，12个唯一卡owner；本次已实施0条、已验证0条、通过0条。D01–D08共8项，由主Agent根据设计交付填写状态。

只有相关实现、必需层级证据和独立复核结论齐全时，才可逐条更新生产状态。W12汇总发现此前AC失效应重新打开责任卡，不能以集成测试总体通过覆盖缺失证明。任何真实Host/正常安装/人工阅图尚缺的条目保持未验证。

## 本线程执行状态

完整顺序和分段依赖以 packages/README.md 及执行索引为准。implementation-ready / core-verified / slice-merged 不等于 accepted；一条 AC 的所有要求与列出的证据层齐全才通过。W01-AC01 延后补证，编号与 owner 不转移；管理 revision 与采用内容槽的区分已同步 W07/W08 正文。
