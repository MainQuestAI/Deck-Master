# N4｜工作上下文减负与操作历史增量查询

## 0. 任务状态与执行基线

| 项目 | 本卡规定 |
| --- | --- |
| 计划版本 | `1.0.0rc4` 候选迭代；版本号最终由发布任务统一确定 |
| 状态 | 开发输入，尚未实现、尚未验收 |
| 审查基线 | `MainQuestAI/Deck-Master@a08bc68c1cbbbc806205104c2bb01f3f096305f0` |
| 目标 | 在保持完整业务上下文、固定版本、原图核对及操作恢复语义的前提下，减少方法正文重复传输、来源重复解析和历史重复查询 |
| 前置依赖 | N1 的操作回执与查询接口固定；N3 的 Task 方法清单及映射规则固定 |
| 可提前工作 | 在隔离目录建立计数探针、构造合成历史、记录 v1 响应、梳理只读入口；不提前改变正式返回结构或业务事务 |
| 实现核验 | 需要 Codex 核验开发时的当前 SHA、N1/N3 实际接口、文件位置、测试命令、安装包行为及本卡全部验收结果 |

本卡包含两个子工作：**N4A：上下文读取与传输；N4B：操作历史查询。** 可以分别实现、分别提交，在共同验收完成前不得将 N4 标记为完成。本卡所列新增接口、协议和计数上限都是开发要求，不能引用为当前已具备的能力。

## 1. 业务目标与完成定义

Agent 继续工作时，应能取得实际 Task 所需的完整方法、材料、Page、原图、设计限制及恢复事实；同一份方法或来源正文不应在一次新协议响应中重复出现。已经在当前会话上下文中可用的相同资源，可以经明确协商按引用传递；缓存不存在、版本变化或进入新会话时，仍能取得真实完整原文。

查询一项操作是否已提交时，应以 N1 统一回执解析为准。历史较长的项目，在同一服务进程、相同已验证历史下重复查询，避免反复解析全部 Document；出现新提交时，只解析新增部分。索引缺失、伪造、损坏或落后时，不得产生“已提交”或“不存在”的错误结论。

完成 N4 必须同时满足：

1. 原有 Host 未声明新读取能力时，其现有 v1 行为和业务协议仍可用。
2. 新协议全文模式中，同一资源正文只返回一份，全部消费关系通过明确引用表达。
3. 紧凑模式不能制造“已读”“已应用”或专业审查证据，不能降低原图、内容或范围要求。
4. N1 的 `committed / not_found / unknown` 判定与原始回执在启用、禁用和重建索引时保持相同。
5. 有可复核的计数、响应样本、对照测试和兼容记录；不以未经测量的 token、费用或耗时百分比作为完成依据。

## 2. 事实依据与问题边界

以下为审查基线中已读取的实现，开发前需要 Codex 核验当前对应位置。

| 事实 | 源代码证据 | 本卡处理方式 |
| --- | --- | --- |
| `read_skill_methods` 将相同 `dispatch_items` 同时放入 `dispatch.methods` 和顶层 `methods`，JSON 序列化时重复输出正文 | `src/deck_master/method_resources.py:315–337` | v2 用单一资源表和引用表达；不静默改变 v1 |
| 一份工作单遍历派发版本的全部 sources，读取每个 extract 并展开到 `source_reading` | `src/deck_master/service.py:542–552` | 单次响应共享读取上下文；正文去重、可协商按引用读取；保留全部来源清单及实际必读要求 |
| 多份 pending Task 已共享 dispatch Document，但未共享全部来源解析 | `src/deck_master/service.py:397–405、477–488` | 在现有批量投影处补资源收集器，不另建生产编排 |
| `read_task_methods` 的 Task 查找对命中对象可能重复调用 JSON 读取 | `src/deck_master/method_resources.py:154–173` | 统一一次解码后的 Task 查找；不扩展为全仓通用缓存重构 |
| `committed_record` 每次从 current 扫描完整 committed ancestry | `src/deck_master/operations.py:58–90`；`snapshots.py:67–89` | 在 N1 resolver 内提供可丢弃的进程内查询索引 |
| 现有 `publish_index` 写入索引，但查询并未以其加速；部分回执查询命中后再次遍历历史 | `src/deck_master/operations.py:92–123`；`store.py:413–437` | 去除二次遍历，严格区分原始回执与派生索引 |

审查时的隔离计数轨迹包含 20 页、160 个 Task 引用、20 个 Review 引用。历史规模为 100、500、1,000 个 revision 时，每次查询全新 operation ID，分别发生 100、500、1,000 次 snapshot JSON 读取；重复查询没有减少该计数。这是查询机制的合成证据，不是客户性能结果。

### 2.1 非目标

- 不改写 SVG→PPT 渲染器，不引入新 harness、数据库、任务引擎或全仓分层重构。
- 不通过减少来源、删掉 Page 正文、压缩原图、降低审查维度来获取性能收益。
- 不改变授权、预算、任务 claim、call settlement、read-set、CAS、late-result 或质量门的规则。
- 不重算旧操作的 digest，不把旧日志升级成原子提交证据，不把 `unknown` 解释为可以重试。
- 不把 Host 自述缓存命中、返回 hash、文件下载或角色名当作方法已读、方法已应用或独立审查证据。
- 不承诺所有 CLI 冷启动查询都为常数时间；在当前未签名的文件式历史结构下，冷启动信任建立需要实际验证历史。

## 3. 前置接口与职责归属

### 3.1 与 N1 对齐

N1 固定内部纯查询接口：

```python
operations.resolve_operation(store, operation_id, *, head_revision=None)
```

返回至少包含 `state=committed|not_found|unknown`、固定的 `head_revision`；命中时带 `receipt_format`、`stored_kind`、`committed_revision_id` 及原始 `record/result`。具体字段结构以 N1 冻结合同为准。N4 不另建同义 resolver，不新增第四种业务终态。

必须保留 N1 规定：

- 只有 Document 内的 `operation_commit` 或 `operation_receipt` 可以成为原子提交事实。
- 找到旧 `input_update` 提交但没有原子回执时，resolver 返回 `unknown(reason=legacy_receipt_only)`；兼容旧日志的责任仍属于 N1 adapter。
- `inputs.update` 与 `content.inputs` 的 family、请求规范和 digest 不因索引而合并；相同 ID 的跨 family 冲突仍由 N1 处理。
- `not_found` 只证明该固定 head 的 canonical ancestry 中不存在此 ID，不能等同“该 ID 可以首次提交”。旧普通输入 no-op 可能只有 legacy 日志而没有带该 ID 的 revision；即使 N4 负缓存命中，N1 adapter 仍必须在取得首写资格前检查该日志的重放与 ID 占用。该兼容分支不把日志升级成原子提交事实，不增加 resolver 第四态。
- 旧 `operations/<id>.json` 可能是旧操作唯一剩余的回执，不得被泛用索引覆盖、清理或改格式。
- `committed_record/recover/show` 的外部兼容 wrapper 继续存在，但最终调用同一 resolver；不能为缓存再恢复一次历史。

N4 的职责是提供候选定位与完整覆盖信息，最终状态仍由 N1 的 canonical decoder 决定。索引命中后，原始回执按 N1 规则核验并原样返回。纯 resolver 不进行素材读取、模型调用或持久索引发布。

### 3.2 与 N3 对齐

N3 固定 `method_resources.resolve_task_methods(task)` 为 Task 方法读取的唯一入口，并保留 `method_ids_for(kind, intent, phase, review_units)` 的职责映射。新 Task 的 `method_manifest`、旧 Task 的冻结映射和 `basis_changed` 判断均由 N3 负责。

N4 只消费该入口返回的有序清单、真实文件 hash 和 basis 状态：

- 不因角色默认方法而给已有 Task 追加方法，不因紧凑传输删去 calibration 或原图重建方法。
- 不改 `method_release.methods_sha256` 的公式、顺序或含义。
- 旧 Task 无 manifest 时，继续使用 N3 的冻结 RC3 兼容规则。无法证明一致时，返回真实 `basis_changed`，不替旧 Task 换用新方法。
- N3 若因业务持久字段新增 writer floor，遵循总方案统一安排；**N4 本身不新增持久 writer floor**。

## 4. N4A：读取协议与兼容设计

### 4.1 必须增加只读响应协议版本

新增 `work_context.v2`，用于方法和工作单资源去重后的读取响应。它是**读取与传输协议**，不是新的 Task 执行协议。

理由：v1 中的 `methods[].content`、`dispatch.methods[].content` 和 `source_reading[].text` 是现有调用方可以直接消费的位置。将其删除或替换为引用属于响应语义变化，不能继续无声返回同名 v1 schema。

兼容规则：

| 调用方请求 | Runtime 行为 |
| --- | --- |
| 未传 `read_protocol` | 返回当前 v1 响应；默认行为不变 |
| 显式 `read_protocol=work_context.v2`，Runtime 支持 | 返回 v2；`body_mode` 默认 `full` |
| 显式请求不支持的读取版本或模式 | 返回结构化 `read_protocol_unsupported` 或 `invalid_input`；列明支持版本，不自动降级 |
| 新 Host 连接旧 Runtime | 先读取能力；未声明支持 v2 时主动使用 v1，不靠试错解释缺字段 |
| 旧 Host 读取持有 N3 新 writer floor 的项目 | 按 N3 的现有前向写边界处理；N4 不修改该限制 |

`capabilities.describe` 增加独立的 `read_protocols` 声明。禁止把 `work_context.v2` 写入持久 Task 的 `protocol_version`、业务 `required_capabilities`，或以读取请求推进项目版本。

新增只读响应合同的真源固定为 `src/deck_master/resources/contracts/work-context.v2.schema.json`，唯一 spec 镜像为 `docs/specs/deck-master-next-iteration-20261019/contracts/work-context.v2.schema.json`。两者保持 byte-for-byte 一致；不再建立 rc4 或其他同职责镜像目录。该 schema 不进入 Document，不参与业务内容 hash。

将新读取合同注册到 `models.SCHEMA_FILES`，并在 `tests/rebuild/test_package_boundary.py::test_spec_contracts_match_packaged_contracts_byte_for_byte` 的 spec 目录列表中加入本轮唯一目录；保留“每个活动合同恰好一份 spec 镜像、与打包字节一致”的现有断言。N3 的 `task.v1.schema.json` 仍只同步其原 `docs/specs/deck-master-rebuild-v1/contracts/` 镜像，不复制到本轮目录。文件位置与实际注册方式实施前由 Codex 核验。

### 4.2 入口范围

在现有入口增加可选读取参数，保持旧调用签名有效：

- `method_resources.read_skill_methods(...)`、`read_task_methods(...)`：接受 `read_protocol`、`body_mode`、`cache_offer`。
- `deck-master methods --project … --task-id …`：增加对应可选参数；可用 `--cache-offer <json>` 传结构化声明，不把大段 JSON 拼进 shell。
- `service.task_summary` 和 `_pending_host_tasks`：内部接受同一只读投影选项及资源收集器，默认仍为 v1。
- create/continue 的 pending-task 返回投影可显式协商 v2；**在创建、继续、派发等任何副作用之前校验版本与参数**。unsupported 请求不得先派发后报错。
- 其他工作台 summary、run-desk、固定版本读取及 HTTP 路由只在确有消费者需要时接入同一 projector；不为 N4 建立第二套工作单系统。

本卡不要求新增顶层 CLI 命令。新增或调整的公开读取入口应登记到现有入口覆盖表；旧入口仍调用同一业务函数，只改变经协商的只读投影。

### 4.3 v2 响应结构

v2 至少表达下列结构。字段最终由实现者与 N1/N3 合同对齐，但同义字段不得并行保留两套：

| 区域 | 必要内容 |
| --- | --- |
| 响应身份 | `schema_version=work_context.v2`、project identity、当前控制 revision、选定/派发 revision、Task identity、读取模式 |
| Task 工作单 | 原 Task 的 kind/intent/status/instruction/scope、`produced_against`、binding、dispatch 方法版本、当前方法版本及 basis 状态 |
| 方法清单 | N3 返回的有序 `id/relative_path/sha256`，每项指向单一 `body_ref`；角色入口说明与 Task 方法分别列引用 |
| 来源清单 | 全部原来源身份、版本、extract ref、原始文件 ref/原始 hash、source locator、外部使用限制及可用性；不只列已被 Page 引用的来源 |
| 正文资源表 | `bodies` 按内容身份保存方法 UTF-8 原文或来源 extract；同一正文内容只出现一次，别名和用途保留在清单中 |
| Page 与视觉依据 | 完整 Page/notes/内容约束、scope、精确 immutable 原图 ref、尺寸、SVG/PPT 比对对象、设计/字体/物理尺寸约束；必要时通过同一资源表无损引用 |
| 取回状态 | 每个资源是 `returned`、`omitted_by_cache_offer`、`manifest_only` 或 `unavailable`；列出未返回资源的精确取回入口及缺口 |
| 证据边界 | Runtime 本次返回了哪些字节；Host 应用状态默认 `not_recorded`，不得从缓存状态推导 |

`body_ref` 的身份至少包括资源类型和实际 bytes 的 SHA256。相同正文对应不同方法路径、source ID 或用途时，保留所有清单项，仅共享正文。不得只按文件名、source ID、页面编号、修改时间或方法版本字符串去重。

正文 hash 按真实 bytes 计算；读取方法继续保持 UTF-8 和原有换行字节语义。二进制原图不嵌入文本摘要，保留原有 hash 验证和完整文件读取入口。原始文件/图片引用必须属于原工作单的精确版本与授权范围，不能临时改取 current 的同名文件。

### 4.4 三种正文模式

| 模式 | 适用与行为 |
| --- | --- |
| `full` | v2 默认。返回本次请求所需的完整正文，每份最多一次；适合首次进入、恢复、新会话和无法证明本地缓存存在的 Host |
| `delta` | 仅在 Runtime 与 Host 已明确支持时使用。相同内容可按 `cache_offer` 省略，但正文省略只代表传输优化，不代表已读或已应用 |
| `manifest` | 显式只看资源目录。响应标记 `context_ready=false` 并列出尚未取回的必读资源；不能把该响应当作可直接执行生产的完整上下文 |

`cache_offer` 只接受精确资源身份及当前 Host 会话/上下文代次，不接受客户端声明“通过审查”“已授权”“已经消费”。它不能扩大可读取来源，也不能使不存在的资源变为可用。

重复传输的可用性由 Host adapter 管理：若 Host 暴露真实会话/上下文代次，用它隔离缓存；若无法观察该信息，默认按冷上下文处理并返回全文。上下文压缩、进程重启或新会话后，adapter 必须清空旧 offer。不得自行创造一个持久 session ID 来假设模型始终记得原文。

即使收到匹配 hash 的 offer，Runtime 也只能记录 `omitted_by_cache_offer`；Host 必须实际能读取对应 bytes，否则重新请求 `full`。一次下载回执或旧会话的“已返回”不能替代当前上下文的可用性判断。用户或 Host 随时可以显式要求全文。

### 4.5 原文取回与恢复

来源正文优先复用现有固定版本入口：`content source` 及对应 Python/HTTP reader，并传递 source ID、派发 revision 和 extract hash。方法正文由 N3 的 resolver 选择准确路径，再由当前 `methods --read` 或 v2 `full` 读取。

- 首次全文：不得依赖缓存预热；所需全部方法和来源均可完整返回。
- 来源更新：extract hash 或原文件 hash 变化即新资源；旧正文不能替代新版本。
- 方法变化：返回 N3 的 `basis_changed`；新方法可供检查，但不能把旧 Task 的 dispatch hash 改为新 hash。
- 跨会话/恢复：默认 `full`；即使 bytes 相同，也不生成“此前已读”的消费事实。
- 必需资源缺失或损坏：保留可读部分和具体缺口，`context_ready=false`；不得返回成功空正文，不得改取其他版本。
- `context_ready` 只指本响应约定的资源是否已完整提供或需要额外取回，不等于生产资格、任务可采纳或质量通过。

### 4.6 单次响应共享读取

引入小范围、请求级的资源收集器，复用已读取的 immutable JSON 和 bytes。生命周期限于一次响应，不跨 current 控制变化复用可变业务状态。

工作单投影先固定 current/dispatch 身份，再收集 Task、方法、来源和 Page 依赖。相同 `(project identity, immutable ref path, sha256)` 在该响应内最多解码一次。v2 批量返回多个 Task 时，共享来源正文和方法正文；Task 的独立状态、范围、允许动作和原图依据不能合并。

可以提取公共 decoder 和精确 Task 查找函数；不能把所有业务模块引入统一泛型缓存框架。v1 可在内部复用一次解码而保持原有输出结构，其历史重复字段只在 v2 消除。

## 5. N4B：可验证的操作查询索引

### 5.1 信任模型

**提交事实仍是 current 可达祖先中的原始 Document 与其原子回执。索引是可丢弃的查询提示。** 磁盘索引的 checksum、mtime 或“完整”标记不能独立证明某 operation 不存在；攻击者或错误程序可能同时修改索引内容和 checksum。

索引分为两层：

1. **进程内已验证覆盖表**：本进程从 canonical ancestry 实际建立，含固定 head、已覆盖 revision、parent、项目身份、原始 snapshot 签名及 operation 定位信息。
2. **可选磁盘提示**：只用于候选寻址或减少非必要工作，不授予 `committed/not_found` 的可信状态。需要时使用独立派生路径，例如 `.deckmaster/cache/operation-lookup.v1.json`，禁止覆盖 `operations/<id>.json`。

resolver 只更新进程内缓存，不产生持久写入。可选磁盘提示发布必须放在既有提交后 best-effort hook 或既有允许发布缓存的 adapter 中，不能藏在严格只读查询中；发布失败不改变已提交事实或业务响应。

进程内缓存必须有明确容量上限及按项目淘汰策略。默认上限由实现时的内存测量确定并在 PR 中记录；淘汰只能丢弃派生缓存，不能裁剪正式历史。覆盖表被部分淘汰后不再具备负查询完整性，必须重建或退回 canonical 查询。

### 5.2 冷启动建表

1. 读取并固定 head；需要当前 CAS 的业务写路径沿用 N1 已持有的项目锁。
2. 从该 head 按真实 `parent_revision_id` 向祖先遍历，不枚举 revisions 目录来判断已提交。
3. 每份 snapshot 按 shared snapshot reader 校验标识、所属项目、路径/符号链接、数据形状及引用；记录实际解码后的 parent、operation ID、kind 和回执位置。
4. 记录文件签名与实际 bytes digest。可信覆盖只能来自本进程读取到的 canonical 内容，不能直接采用磁盘索引里的 operation 字段。
5. 查询命中时，调用 N1 decoder 验证原始回执与 result 的 ID、project、revision、base 和 digest；保留原 `record/result`。
6. 只有完整扫描到有效历史根、未发生损坏/缺失/身份错误/环、且 head 仍符合查询约定，才能为未命中返回 `not_found`。

冷启动允许 O(H) snapshot 解析。已有磁盘提示但没有本进程可信覆盖时，负查询仍必须建立完整覆盖；不能为追求冷启动数字跳过这一条件。有效正查询可以在已证明的祖先前缀上结束，不必扫描命中点之前的更旧记录；该前缀不能因此用于全历史负缓存。

### 5.3 同 head 热态查询

进程内覆盖表按“项目真实身份、读取根、固定 head”隔离；同名项目、复制目录或不同服务不能共用 trust。

查询前检查 current，以及已覆盖 snapshot 的路径与签名。签名至少包含设备、inode、大小、纳秒 mtime/ctime；复用仓库既有安全路径处理。标准本地文件系统不能提供这些可靠事实时，回退重新读 bytes/解析，不据弱签名返回负结论。

在全部签名未变、覆盖完整、head 匹配时：

- 正查询：按定位结果直接读取并验证原始回执及 result；必要时重新读取命中的 Document，最多一次，禁止再走第二遍历史。
- 负查询：可以从进程内已验证完整覆盖中返回 `not_found`；保留其 `head_revision`，不得声称覆盖了后来的 current。
- `unknown`：永远不负缓存，不持久化为“未找到”，不得触发新业务操作。

本轮优化目标是减少**历史 JSON 解码次数**。为检测外部文件变化，每次仍可能有 O(H) stat；不能将其宣传为完整查询 O(1)。若后续需要跨进程、常数时间可信负查询，应单独设计可认证的提交索引，不在本卡引入新的持久历史格式。

### 5.4 新 head 的增量路径

若新 current 是已验证 head 的后代，先验证旧覆盖的签名，再只读取新增祖先段，直到连接到旧 head。将新增 Δ 份 canonical snapshot 解析结果合并进覆盖表，并重新固定本次 head。

若无法连接、旧 snapshot 发生变化、覆盖不完整、项目身份不同或发现环：失效相关覆盖，回退 canonical 查询；不能拼接两个看似相近的缓存。重复 operation ID、冲突回执等异常交由 N1 decoder 按原规则报告 `unknown/conflict`，不能“最后一条获胜”。

非 operation 类提交仍是祖先链的一部分，必须计入覆盖和增量检查；不能只索引存在回执的 revision 而跳过中间链路。

### 5.5 多进程与 current 变化

- 各进程独立建立可信覆盖。其他进程写入的磁盘提示对本进程仍是不可信提示。
- 写操作调用 resolver 时，必须沿用 N1 的项目锁、原请求 ID、纯请求 digest 和后续 CAS；缓存不能使锁外判断代替锁内判断。
- 只读查询固定一个 head，返回前验证 head 未违背本次请求约定；查询中推进 current 时，允许一次有界重读，仍变化则返回可恢复的 current-changed/unknown 语义，而不是返回针对旧 head 的“当前不存在”。
- 显式 `head_revision` 按 N1 的固定版本约定处理，未经验证的旧/current 字符串不得绕过 ancestry 校验。面向当前写入的调用不可把旧 head 的负结果带到新 head 使用。
- 不长期持有项目锁进行全量索引发布、源码读取或外部操作。需要冷扫描时，保留正确性优先的现有事务边界，并记录真实锁持有时间供后续评估。

### 5.6 异常恢复矩阵

| 情况 | 规定行为 |
| --- | --- |
| 磁盘提示不存在、损坏、伪造、指向 orphan/其他项目 | 丢弃提示，走 canonical 查询；只有实际历史证明后才返回状态 |
| canonical ancestry 有损坏 snapshot、缺失父节点、符号链接、foreign parent 或环 | 不能作为“扫描结束”；未能建立结论时返回 N1 `unknown` 或其原结构化错误 |
| 存在无关 orphan 文件，但 current 完整历史中确无该操作 | 忽略 orphan；完整历史核验后可以返回 `not_found` |
| 命中原子回执但 result 缺失、hash 或 revision 不一致 | 返回 N1 的不可验证结果，不能从缓存复制一份旧 result 假装成功 |
| 找到旧 input_update 提交，只有旧日志回执 | 返回 `legacy_receipt_only` 对应 unknown，由 N1 legacy adapter 处理；索引不覆盖日志 |
| 查询 current 在处理中发生变化 | 有界重读或明确报告变化；不返回可用于新 head 的旧负结论 |
| 索引发布失败 | 保持已确认的业务结果；可保留现有缓存不可用提示，不能导致第二次提交 |

## 6. 验收标准

本卡共有 **14 项独立 AC**。N4A 对应 01–07，N4B 对应 08–14；所有 AC 的最终状态与证据由本卡 Owner 统一归档。

| AC | Given / When / Then |
| --- | --- |
| **AC-N4-01｜旧 Host 与协商** | **Given** 现有 v1 Host fixture 和相同项目/Task；**When** 不传读取参数，或显式请求不支持的版本；**Then** 前者保持既有字段/内容/业务行为，后者明确拒绝且 current、Task、call、scope 均不变。Runtime 能力声明与实际支持相同；旧 Runtime 由新 Host 主动回退 v1。 |
| **AC-N4-02｜正文只出现一次** | **Given** 同一方法被角色入口和 Task 引用、同一来源被至少两个 pending Task 引用；**When** 返回 v2 `full` 并实际 JSON 序列化；**Then** 各唯一方法/source extract 的完整正文在 `bodies` 只出现一次，其他位置只有合法引用；每个消费关系、source ID 和方法顺序仍保留。不得只检查 Python 对象是同一引用。 |
| **AC-N4-03｜首次、变化与跨会话** | **Given** 首次会话、同代次匹配缓存、来源/方法 bytes 变化、新会话/上下文代次、不可观察会话信息五组输入；**When** 分别请求 `full/delta`；**Then** 首次和冷上下文提供全文，匹配缓存仅标记传输省略，变化资源不被旧 hash 命中，任何组均可再次完整取回；不得产生方法已应用或独立审查声明。 |
| **AC-N4-04｜N3 清单与旧 Task** | **Given** 新 manifest Task、旧 RC3 Task、方法 basis_changed 和不存在方法四组；**When** 经三种模式读取；**Then** 方法 ID、顺序、path/hash、dispatch release 与 N3 resolver 完全一致，不能补角色默认文件、不能改旧 Task hash；缺失/不匹配保留真实状态和恢复入口。 |
| **AC-N4-05｜完整 Page、原图与来源** | **Given** compose、reconstruct、page_visual、final 四类真实结构 fixture，含完整 Page/notes、多来源、原图、内容/字体/物理尺寸要求；**When** 用 v2 `full` 和 legacy v1 读取并解引用比较；**Then** 所有业务必需字段语义相等、原图 ref/hash/尺寸不变、来源清单完整；`manifest` 不声称完整可执行，资源损坏不以空正文或另一版本补位。 |
| **AC-N4-06｜请求级读取计数** | **Given** 多 Task 共享同一派发 Document 和若干 immutable extract；**When** 一次构建 v2 批量工作上下文；**Then** 每一唯一方法 bytes/source extract JSON/Task 对象在该请求最多实际解码一次；记录真实 reader 计数和序列化字节数。Page 原图核验调用不得因减少计数被省略。 |
| **AC-N4-07｜业务与只读等价** | **Given** 四个 Skill 入口及恢复入口的固定控制快照；**When** 对同一 Task 分别使用 v1、v2全文、完整解引用后的delta；**Then** eligibility、completion、允许的结果类型和采纳结论一致。读取不产生新的Document/Task/授权/调用/消费回执；可选磁盘缓存发布不发生在严格只读 resolver 内。 |
| **AC-N4-08｜冷扫描正确性** | **Given** 100、500、1,000 revision 合成有效轨迹，既有原子回执、无回执提交和不存在 ID；**When** 新进程无可信缓存查询；**Then** 与禁用索引的 N1 canonical resolver 三态及原结果一致。完整负查询每个 reachable snapshot 最多解析一次，不出现 Store→operations 二次全链扫描。 |
| **AC-N4-09｜同 head 热查询** | **Given** 已验证完整覆盖、相同 head 且所有文件签名未变；**When** 至少连续十次查询同一已有 ID 和十个不存在 ID；**Then** 负查询历史 snapshot JSON 解析为 0，正查询每次最多重新解析命中 Document 1 次，原始回执/result仍按N1核验；记录stat与解码次数，不以跳过检查达标。 |
| **AC-N4-10｜增量 Δ** | **Given** 已验证 H 个 revision 后再追加 Δ=1、10 的合法提交，含无回执提交；**When** 当前进程查询新 head；**Then** 新增部分最多解析 Δ 份 snapshot，加上正命中所需的至多1份，旧历史不再全量JSON解析；结果与canonical resolver一致，旧head负缓存不用于新head。 |
| **AC-N4-11｜索引伪造与重建** | **Given** 丢失/截断/伪造磁盘提示、伪造“完整”标记、重算checksum、替换operation映射以及既有legacy日志；**When** 查询和重建；**Then** 不能据提示形成假commit或假missing，必须从canonical确认，旧operations日志字节不变；缓存发布失败不重复业务提交。 |
| **AC-N4-12｜历史损坏与孤儿对象** | **Given** orphan、foreign project、symlink、父snapshot缺失/损坏、循环父链、命中result损坏、热态snapshot被替换；**When** 正/负查询；**Then** 无关orphan不被提升为历史，无法证明的链返回unknown/原结构化错误；损坏不能被当作历史根；热缓存失效且不返回旧假结论。 |
| **AC-N4-13｜并发与固定 head** | **Given** 两个进程各自缓存，同ID竞争提交，以及读取时另一进程推进current；**When** 查询/恢复/CAS执行；**Then** 只有合法CAS获胜，输方保持N1原语义，负结果明确绑定已验证head；不能在新head复用旧not_found，也不能导入其他进程提示作为trust。 |
| **AC-N4-14｜N1回执、未知态与副作用** | **Given** inputs.update/content.inputs/Task acceptance 的新旧回执、跨family同ID、legacy_receipt_only、完整旧log-only no-op日志及日志丢损；**When** 启用/禁用/重建索引后执行N1回放对照，包含canonical负缓存命中；**Then** 原digest、stored_kind、response、conflict/unknown结论一致，unknown不负缓存；旧log-only no-op的重放和ID占用仍经N1 adapter检查，不能凭not_found跳过；可核验恢复不重新读来源、不占额度、不重新派发、不改current。 |

## 7. 实施顺序与测试要求

### 7.1 建议实施顺序

1. 在 N1/N3 接口固定前，只建立 v1 响应快照、合成历史、正文重复计数、read/parse 计数器；计数器不修改业务返回值。
2. N3 合入后实现请求级资源收集器和 v2 `full`，先证明完整内容等价与正文只出现一次。
3. 再接入明确协商、`delta/manifest` 及冷上下文回退；将可观察的“返回/未返回”与不可推断的“已应用”分开。
4. N1 合入后，把旧查询 wrapper 收敛到 resolver；先去掉二次全链扫描，再增加进程内完整覆盖和增量索引。
5. 验证索引失效、伪造、损坏、并发与未知态；可选磁盘提示只有在证明确有收益且不增加信任歧义后实现，不作为额外发布前置条件。
6. 运行本卡定向验收及受影响的既有回归；通过后由总验收任务运行跨任务集成和安装包检查。

### 7.2 必须保留的测试证据

- 同一固定 fixture 的 v1/v2 序列化响应，以及解引用后的业务字段比较结果。
- 实际 JSON 中的全文重复次数，不能用引用相等替代；方法和来源计数分别报告。
- 冷态/热态/增量的 snapshot bytes读取、JSON解析、stat和回执/result读取次数；耗时作为观察值，不设置未经校准的毫秒门槛。
- AC-N4-11/12/13 的故障注入数据、操作前后指针与原回执 hash、状态结果。
- N1 三态与 legacy adapter 对照、N3方法映射对照、新旧Host对照。
- 全部产物标明 `SYNTHETIC_ENGINEERING`，注明源 SHA、实际运行 SHA、Python/平台、cache模式和限制；不可写成真实客户效果验证。

### 7.3 测试修复约束

不能为使测试通过而删除旧 Host 兼容断言、放松 snapshot 可达性、把 expected unknown 改为 not_found、减少 required_sources、替换原图，或将“返回字节”断言升级成“已应用”。计数上限只约束同一读取机制，不允许通过把解析移到未计数的 helper 或其他线程隐藏工作量。

## 8. 预期交付与交接

开发 PR 必须包含：

1. v2 只读协议/schema、能力协商、兼容说明和一个可完整阅读的响应示例。
2. N3 resolver 到资源收集器的唯一调用关系，方法/来源全文与引用的取回路径。
3. N1 resolver 的索引实现、失效条件、negative cache可信条件和postcommit派生缓存边界说明。
4. 14项AC结果表、原始计数记录、对照样本、故障注入结果及未完成项；每项只认当前实现对应的证据。
5. 给 N5/总验收的使用说明：如何强制v1、v2全文、关闭缓存、重新建立进程内覆盖，如何识别unknown及basis_changed。

本卡不要求清理全部大文件或消除所有模块依赖环。允许的提取范围以本卡实际复用的 decoder、Task 方法解析、请求级资源收集与操作查找为限。最终成功标准是 **内容完整、入口兼容、恢复结论不变，同时减少已经量化的重复传输和重复解析**。
