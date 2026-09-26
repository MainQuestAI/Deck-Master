# 工程实施规格：生成工作台 v3

状态：**确定的实施方案，尚未实现、尚未验证**。基线为 d1c7c4600cb0fc781070116ed8cc8a1ff6b8b7ca。本文件细化 [PLAN](PLAN.md)、[UI-SPEC](UI-SPEC.md)、[DX-SPEC](DX-SPEC.md) 的事务、候选、恢复与性能边界；不改变 87 条 AC 的数量或唯一归属，不替代真实 Host 或安装验收。

## 1. 核心复用与事实边界

| 现有代码 | 已有机制 | 本轮要扩展的部分 |
|---|---|---|
| src/deck_master/store.py:225、251、305、348 | advisory file lock、不可变对象/Document、最后原子替换 current.json、文件 fsync | 操作提交事实随业务 revision 可恢复；统一索引重建；必要目录 fsync 与故障注入 |
| src/deck_master/service.py:957、984、1135、1154、1290 | inputs_update 请求摘要、锁内再次查重、预写 operation receipt；沿已提交历史判断 receipt 有效 | 从输入更新推广为共享提交原语，不再依赖独立 receipt 文件是唯一证据 |
| src/deck_master/tasks.py:90、275、824、936、1149 | OperationJournal、结果幂等、外部调用事实先结算再内容采用 | 把新操作结果索引与已提交事实关联，补指针切换后旁写失败恢复；原 call allowance/begin/settle 仍是唯一调用账 |
| src/deck_master/models.py:61、381、394、411；tasks.py:305 | canonical_json_bytes、revision parent 链、content_identity、compute_input_digest、作用页新鲜度校验 | 区分生成适用依据、采用目标指针、项目 CAS，不能把 revision 变化直接判为生成结果过期 |
| src/deck_master/web.py:82、92、106、109、142、205、308 | loopback Host 检查、Origin+X-Deck-Token 写保护、请求体上限、对象白名单、SVG sandbox CSP、服务身份检查 | 新路由全部保留同一防线；轻量 launcher、UI journal、缩略图和新接口沿用公共底层 |
| tests/rebuild/test_web.py:242、259、274 | 同源 token、路径与 hash 拒绝、用户文本作为数据、SVG 隔离回归 | 新 GET/POST、草稿导入、缩略图、候选与导出执行相同负例 |

现有 Store 在 current 正好指向该 operation 时可识别重放，但这不等于已具备跨后续写入的完整通用重放。当前 task journal 的旁写与 inputs receipt 的预写方式也不等于本规格已落地。新增代码仍在 src/deck_master/；活动契约只在 resources/contracts/，不新建数据库、模型执行器、调用账或第二个 CLI 命令面。

## 2. 操作事实、原子提交与崩溃重放

最终 owner：W06-AC04、W06-AC06；W07 采用及 W10 恢复复用。一次本地业务事务使用一个 operation_id；外部调用仍遵循既有 call allowance/Attempt 事实，不在写锁内等待 Host/工具。

### 2.1 一个可恢复提交事实

新操作采用以下不可变关系，字段名是需实现的契约，不是当前已有接口：

- 请求摘要 request_digest：以 canonical_json_bytes 对协议版本、operation kind、project_id、base_revision、完整业务 payload 及固定对象引用做 SHA256；排除 session token、传输时间和 operation_id。字符/空白不隐式规范化。合法同一 operation_id 只允许这一请求摘要。
- OperationCommit 对象：operation_id、kind、request_digest、base_revision、committed_revision_id、result_ref。result_ref 指向可原样重放的稳定业务结果，包括实际创建的对象/任务 ID 和结果引用；不含短期 token、瞬时健康状态。committed_revision_id 预分配，仅为身份字符串，避免对象 hash 的循环引用。
- 该业务 Document 的 change 引用 OperationCommit；任务创建/采用/失效、operation digest、result_ref 与 revision 由同一次 current.json 指针切换变为可达。不存在“业务已经提交，但需要第二次成功写 journal 才知道结果”的窗口。
- .deckmaster/operations/ 仅作可重建查询索引，复用现有 operation 目录与类型分派。索引必须标到已提交 revision；丢失、损坏、落后或提前存在均不能改变业务事实。已提交 parent 链中的 OperationCommit 才是新协议的提交依据。记录随项目历史保留，无自动 TTL。

### 2.2 写入与恢复顺序

1. 在锁外只做无副作用校验/不可变输入暂存；涉及外部材料的快照输入一旦确定必须绑定内容 hash。不得在查重前再次调用模型或分配新额度。
2. 进入现有 Store._locked 后读取 current；先查询并验证 operation 索引及历史可达性，必要时从 current 沿 parent 重建。**锁内查重早于新 base/CAS、取消或业务执行判断**：同摘要已提交则返回原 result_ref，即使后来有其它写入；异摘要返回 operation_payload_conflict。原操作成功后的取消不把其历史成功改为未执行。
3. 未提交时才检验项目 CAS、明确的目标指针及 read_set、取消/终止状态与门禁。所有候选采用目标先完整预检；有一项失败则本组零提交。
4. 创建业务对象、稳定结果对象及 OperationCommit；保存同一业务 revision，然后原子替换 current。复用 _atomic_write_bytes，补所需父目录 fsync 及故障注入点，不以文件存在当已提交。
5. 指针成功后才更新派生索引并响应。索引写入失败可以记录可恢复错误，不能撤销已提交业务或让重试再次执行。响应丢失时 operations 查询从已提交事实恢复同一结果。

| 中断位置 | 重启/原 ID 重放行为 |
|---|---|
| 对象或 receipt 已落盘、current 尚未切换 | 对象是未提交孤立物，不报告成功；base 仍匹配才按原请求完成一次事务。若已有其他事务前进则返回 conflict，不盲盖新内容 |
| current 已切换、operation 索引尚未写 | 沿已提交历史找到 OperationCommit，重建索引，返回原结果，不再建任务/采用/扣额 |
| operation 索引已写、HTTP/CLI 响应丢失 | 验证索引对应已提交事实后原样返回结果 |
| 成功后多个无关事务前进，再重放旧 ID | 查重优先于当前 base 检验，返回当时结果与 committed_revision_id，不把 current 回退、不执行第二次 |
| 同时两请求同 ID 同 payload | 锁内唯一成功提交；另一请求返回同一结果 |
| 同时两请求同 ID 异 payload | 一个可能提交；另一个固定返回 operation_payload_conflict，无部分副作用 |

旧 inputs/task journal 保留兼容读取及现有语义；仅在能验证已提交历史时导入索引，不猜缺失摘要、不静默重放未知旧记录。通用 primitive 接入既有服务后，不允许新接口再旁建独立“已完成”文件作为另一真相。调用事实结算仍先于内容采用且不可回滚；候选拒绝也不能删除已有用量。

验证必须覆盖 pointer 前/后、索引前/后进程中止、索引删除重建、插入多个后续写入、同 ID 并发、异 payload、取消后晚到；分别记录 current/ref/任务数/调用额度。进程故障注入不能被描述为已证明任意硬件断电恢复。

## 3. 生成依据与采用并发条件分开

最终 owner：W07-AC01、W07-AC04、W07-AC05；W01/W05 投影同一判断，W06 负责 plan 与 commit。

| 维度 | 固定内容 | 比较时机与含义 |
|---|---|---|
| generation_basis | request input_hash、目标 Page/content ref、实际使用的材料/要求语义 digest、design/template refs、固定参考图 hash/角色、stage 与限制 | 冻结时记录；结果回来验证输入一致与来源，判断是否仍适用于目标事实。复用 task_inputs_current 的作用页/输入语义检查，不使用全项目 revision 等价替代 |
| adoption_target | 每个 page_id、目标 stage、计划时该槽 current ref（可为空）、必要的下游依赖/页成员资格 | 采用锁内逐项比较。目标已有新结果、已删页或其它必要依赖改变，旧计划不能直接覆盖 |
| project_cas | 最新采用 plan 的 base_revision | 最后业务事务仍用 Store 项目 CAS；只要 current 变化便重新 plan。此条件失败不自动把候选标成生成依据过期 |

无关页、任务管理或 UI 关注变化不改变当前候选的生成依据。其它页合法完成造成项目 revision 前进时，保留候选及固定比较，重新预览采用影响并生成新 plan/new operation_id；**不重生图、不重新扣额度**。UI 显示“采用计划需更新”，不是“图片已失效”。目标 Page/实际生成依据改变才显示“生成依据已变化”，需新的请求或明确重新处理；不得自动把旧请求重标为新依据。

固定参考图指向历史不可变 ref：参考页后来有新图，不会悄悄替换该参考。target pointer 已变但 generation_basis 仍相同时，仍可查看候选；用户重 plan 明确新的当前结果后才可采用，不自动覆盖。单页和集合采用共用 Service，全量预检再全有/全无提交。

auto 与 trial 共存：用户比较固定 refs 时，既有 continue 可合法继续自动生产并产生当前结果。trial 不设置页级 hold/租约，不暂停整项目；采用发生 CAS/目标指针冲突按上述规则重 plan。无 UI 的生产行为保持。取消/删除使原 task terminal；通过历史恢复同一稳定 page_id 后新工作创建新 task_id，以 terminal 状态、原基准 ref 和新计划阻止旧任务复活，不增加 incarnation 字段。晚到返回保留调用事实但不能覆盖当前。30 分钟沿用“待核实/用户取消后新交接”，不新增心跳调度器。

## 4. 项目 UI draft journal 与跨端口恢复

最终 owner：W03-AC05、W05-AC06、W06-AC06、W10-AC07。W03 提供最小 journal，W05 接草稿，W06 同步待核实 operation 身份；不产生 W03 反向依赖 W06。

- 权威的**草稿恢复副本**位于已注册项目 .deckmaster/workbench/drafts/；它只是可独立清理的个人 UI 恢复数据，不是正文、请求、任务、调用、质量或导出真相。正式“保存意见/提交计划”才进入第 2 节业务事务。journal 保存不生成 Document revision、不改变生产 content_identity/候选 CAS，也不驱动任务。
- 每条记录包含 draft_id、project_id、scope/目标身份、base_ref 或原始文本 ref、完整 content/定位、updated_sequence、内容 digest、ETag、以及独立的 pending_operation_id/pending_payload_digest（若有）。该 pending 部分是客户端请求副本，不能当业务提交成功记录；后写草稿与待核实 payload 保持两个版本。
- 复用核心原子写、路径校验与短期文件锁；journal 使用自己的 ETag/sequence 并发保护，不使用项目业务 revision CAS。服务先原子持久化，再返回 saved_sequence/ETag。并发旧 ETag 以冲突返回，保留本机/服务端两稿，不静默覆盖；索引可由 journal 记录重建。
- 浏览器只作当前 origin 的临时缓冲，按 project/目标/base/draft_id 隔离；输入即时进入缓冲，在线空闲 600ms debounce 保存，失焦/显式保存时 flush。写失败或未收到持久 ACK 不能显示“已保存到项目”。不因每次按键生成业务 revision。
- 项目服务在新动态端口启动时，从项目 journal 加载已确认草稿。**只有原端口收到项目保存 ACK 的内容，才承诺自动跨端口恢复**。旧 origin 的 localStorage/IndexedDB 无法被新 origin 自动读取；尚未同步、离线或 ACK 未知均显示实际状态。
- 离线未同步内容提供显式下载/导入的恢复文件，包含版本、project_id、draft_id、基准 ref、文本/意见/位置、pending payload 与 digest，不含 token、绝对路径、执行命令或外部资源。文件标“个人草稿，可能含内部提示词”。新端口导入先校验 schema/大小/hash/project/基准；冲突保留为独立草稿，绝不自动提交、采用或重放调用。
- 项目尚未打开/路径不可写时只提供浏览器缓冲与恢复文件，不承诺项目已保存。历史 restore 不回滚个人 journal。工程包可以明确排除个人草稿；跨机器恢复若需要草稿由用户单独导入恢复文件，不能把同机 journal 承诺扩成自动跨机器同步。

journal 暂不可达不阻止已加载内容阅读；写入故障保留缓冲和下载入口。清理此 UI 数据不应改变任何 current、任务、产物或调用记录。回滚 UI 不删除已保存草稿。跨端口验证必须包含 ACK 成功、离线未 ACK、保存响应丢失、ETag 并发冲突及下载→新 origin 导入五类，不能只在同一端口刷新。

## 5. 文本范围的唯一坐标规则

最终 owner：W06-AC02，W05-AC05复用。range 绑定原始存储文本对象 ref、字段 locator、text_sha256、start/end 与 excerpt。定位原始 UTF-8 解码后的文本字段，**按 Unicode code point 的左闭右开区间 [start, end)**；不是 UTF-8 字节、JavaScript UTF-16 code unit 或字形数量。0 ≤ start < end ≤ code point 长度。

不隐式做 NFC/NFD、换行、空白或标点规范化；CRLF 原样为两个 code point。JSON 中转义的换行读取为原文本控制字符，不把序列化 JSON 引号/反斜杠算进范围。text_sha256 对该字段原样 UTF-8 字节计算。服务以 Python 字符串切片核验 excerpt 与 text_sha256/ref 完全一致，不匹配就返回可恢复校验错误，不以模糊搜索静默换位置。

JavaScript 显式建立 source code point ↔ UTF-16 DOM/编辑器 offset 映射，使用原始文本缓冲维护 CRLF；不能直接把 selectionStart/end 当契约坐标。DOM/textarea 显示归一造成的差异必须通过映射处理，不能在读写时悄悄改源文本。拒绝落在 surrogate pair 中间的非法边界。测试包含中文、非 BMP emoji、ZWJ emoji、组合音标、CRLF/LF混合、重复摘录、源版本变化与错误 excerpt。

坐标测试向量：JSON文本值`"A🙂e\u0301\r\n中"`解码后有7个code point、8个UTF-16 code unit；code point边界到UTF-16边界映射为`[0,1,3,4,5,6,7,8]`，范围`[1,4)`的excerpt为`"🙂e\u0301"`，CRLF占`[4,6)`。不能先把组合字转成单一é或CRLF转LF再计算。

真实正文/prompt可以文本选取；原图没有 OCR 文字层。SVG 首版通过安全 img 显示，若已有稳定 element ID 及能可靠换算的静态几何命中映射，可把意见关联该 ID+固定 artifact ref；映射不安全/缺失时退回 rect。几何映射只作数据，不执行 SVG 内脚本；不建设 iframe 脚本 bridge、不注入 SVG DOM、不凭视觉猜文本范围。旧范围永久指向旧 ref；转到新版本必须显式新建意见。

## 6. 固定压力模型与 SLO

最终 owner：W01-AC01（summary）、W04-AC06（首屏/图像/缓存）、W10-AC04（持续运行 heap）。以下是实施门槛，**不是本轮已测成绩**；首轮未达标修复实现，不能改门槛。W12复用各 owner 的证据而不重新分配归属。

确定性压力项目：300 个稳定 page_id，每页 5 个候选，每候选关联 3 个 Attempt，即 1500 候选/4500 Attempt，包含成功/失败/取消/unknown及混合层历史。记录种子、素材尺寸/字节数和总对象数；不用空对象省略真实解析负担。只读/性能 fixture 不伪装真实 Host 生成证据。

| 测量 | 固定要求 | 口径 |
|---|---|---|
| loopback warm summary | p95 ≤250ms | /api/view/summary，5次预热后至少100次，客户端请求开始至JSON解析完成；压力项目并有正常后台状态更新。摘要不展开1500候选/4500 Attempt正文 |
| 30页首屏可操作 | ≤2s | 30页样例从页面导航开始，到首个可见区域缩略图完成、页/层/状态可读且选择/打开可响应；预热本地服务/缩略图缓存，两视口。压力项目的首个30页窗口另按同口径验证 |
| 图像网络并发 | ≤6 in flight | 每个工作台实例共享队列；离开视口取消或忽略过期响应，不为每张卡各开独立池 |
| 图像解码并发 | ≤2 | 缩略图和大图共用有界队列，完成/取消释放资源 |
| UI 内存图像缓存 | 最多60张缩略图、4张大图 | 包含当前可见/固定比较及预取；LRU按project_id+content hash+variant键。释放Object URL/ImageBitmap，DOM虚拟化移除离屏引用；HTTP磁盘缓存另计 |
| 20分钟持续浏览 | 末5分钟 heap相对稳定中段增幅≤20% | 同一20分钟脚本循环滚动/换层/开页/切候选/返回并轮询；以第6–10分钟采样中位数作中段，第16–20分钟中位数作末段，(末段−中段)/中段≤0.20。采样方法一致，不在末段单独强制GC美化 |

基准报告必含commit、macOS/硬件/内存、Python/browser版本、视口、数据manifest、后台负载、测量工具/脚本与原始采样。warm排除进程安装/首启及外部Host调用，但不能排除JSON读取/解析；冷启动、旧图首次缩略生成单独记录耗时和占位体验，不与warm混算或称达标。

W01摘要按revision和实际依赖缓存，详情/Attempt按页按需读取；缓存失效由真实版本变化驱动，不复用跨项目未校验数据。W03先提供最小fixture工厂，W04完成压力图集/图像队列，W10用同一manifest补20分钟运行，依赖仍无环。

缩略图是派生缓存：新原图入库后由有界本地后台工作队列生成，旧项目按访问优先逐步生成；不阻塞原图采用、不改immutable原图、不新增Host调用/调度器。cache key为project_id+原内容hash+variant（尺寸/格式/算法版本），命中须校验归属；缺缩略图显示明确加载状态，只加载视口所需内容，禁止首屏塞30张base64原图。缓存命中/未命中与冷热测量分开记录。

## 7. launcher、项目服务与旧安全防线

最终 owner：W03-AC01/02/07、W01-AC06，W05/W06/W07新资源和写接口继承。

launcher为独立轻量registry服务，无项目也能启动；不把一个假项目当入口。继续通过deck-master workbench（提案）启动，不新增CLI可执行文件。registry只记显式注册的canonical path及最少展示资料，独立文件锁+原子写；同样抽取/复用核心原子文件工具，不创建数据库。last activity从项目UI-state读取，用户浏览不频繁重写registry。

launcher运行元文件与registry数据分开，含role=launcher、registry identity、instance_id、pid、动态loopback端口、协议/包版本与启动身份。项目服务保留.deckmaster/view.json并增加对应instance/project身份。新服务就绪后才发布元文件；复用先健康核对role/instance/project或registry/version，不能只看PID/端口存活。端口0由绑定过程自动分配；冲突不抢占。token留在服务实例/session中，不写入registry或恢复文件。

CLI结束后detached服务可继续工作；launcher退出只停止launcher，不杀死已开的独立项目服务。项目服务退出也不删除registry或业务数据。进程正常退出只移除匹配自身instance的运行元文件；崩溃留下旧元文件时下次健康检查拒绝复用并重启。启动失败输出真实错误，不把半启动状态登记为可用。验证需覆盖并发启动、launcher无项目、只停入口、只停项目、端口重用到错误服务和陈旧PID；无常驻心跳调度或额外launchd前提。

所有新GET复用现有Host请求头检查，只允许该实例的loopback Host；只读不新增必须读取token或cookie的模型。所有新POST沿用该实例X-Deck-Token+精确Origin+Host校验，按service instance及其project/registry作用域绑定；旧实例/另一项目token无效。Host走CLI共享Service，不增加无Origin token通道。保留当前2,000,000字节JSON请求体上限；超大导入在解析前拒绝且保留用户输入，不通过扩大限制掩盖问题。

回归最少包括：错误/外部Host、跨Origin/缺token/错实例token、过大/畸形JSON、未注册目录、绝对/../路径、symlink组件、跨项目ref/候选/导出ID、hash不符、标题/prompt/标注恶意HTML、SVG script/onload/外链。用户字符串通过textContent等数据通道；SVG保持安全img与独立sandbox CSP，不用富HTML绕开。/api/file、缩略图、恢复文件和导出下载只使用经验证对象/派生ID白名单，不能接受任意路径。既有tests/rebuild/test_web.py安全测试必须继续通过并覆盖新路由。

## 8. 审阅导出的 metadata canary

由W11-AC03/AC07承接；W11卡与其AC由主Agent同步，本轮不改其owner。review应检查可外发文件本体及PNG文本/EXIF、SVG metadata/属性/外链、PPT core/custom properties、notes、relationships等可隐藏内部数据的位置；在测试源注入唯一的内部路径/prompt/凭证canary，解包/解析后断言审阅输出无该canary。

通过生成清理副本处理元数据，不改immutable原件、不把合法可读正文/正常链接/可见来源盲删。扫描发现不明可执行/私密内容时给出位置与拒绝原因，不凭字符串模糊匹配删整页。engineering默认不携带认证信息，个人UI journal可排除且清单明确。此检查与专业质量/可编辑性分别记录，不能以文件可下载代替内容审查。

## 9. 开发包归属与验证交付

| 规格 | 唯一最终AC | 需提供证据 |
|---|---|---|
| summary性能/兼容与GET安全 | W01-AC01/06 | 压力manifest、warm采样、固定版本/跨项目/安全负例 |
| 独立入口/生命周期 | W03-AC01/02 | 无项目启动、并发启动/错误身份/退出重启与registry原子写 |
| UI journal及跨端口恢复基础 | W03-AC05 | 无业务revision变化；journal ETag/ACK、实际换端口与未ACK反例 |
| 旧写保护 | W03-AC07 | Host/Origin/token/请求体/路径/XSS/SVG新旧路由矩阵 |
| 画廊性能与图像缓存 | W04-AC06 | 两视口首屏≤2s、6/2并发、60/4缓存与冷热缩略图 |
| 草稿状态/文件恢复 | W05-AC06 | ACK与未同步状态、ETag冲突、恢复文件下载/新origin导入 |
| Unicode文本范围 | W06-AC02 | Python/JS同向量，emoji/组合字/CRLF/excerpt负例 |
| 幂等原子事实/跨崩溃重放 | W06-AC04/06 | pointer与索引前后故障、后续写入、并发与索引重建 |
| basis与采用CAS | W07-AC04/05 | 无关页更新仅重plan、target变化、不变调用数、auto/trial及取消删除恢复 |
| 长时间刷新/内存与恢复 | W10-AC04/07 | 20分钟原始heap、刷新时序、journal/operation不同真相的恢复矩阵 |

开发卡“示例与验证交付”中的脚本必须实际复现这些条件；本轮只提供确定规格，未生成或执行生产实现测试。所有代码、安全、性能、真实Host和安装证据保持对应层级，未执行仍标未验证。

## 本线程执行澄清

W02 先在原 Store 提交路径补 task accept 的 digest/稳定结果恢复基础，W06 扩展本规格§2全部行为与最终验收。trial 禁止更换采用内容槽；任务/调用/候选事实正常提交管理 revision，故 project CAS 可能改变。Candidate 是已提交业务对象而非独立 Document 历史；固定 revision 读取校验当前已提交 parent 可达性。W01 先交读模型核心切片，§6完整 300×5×3 验收在 W07 契约/工厂形成后由 W01 回访完成，阈值与 owner 不变。
