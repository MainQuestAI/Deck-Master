# N1｜操作回执恢复与入口边界一致性

## 0. 任务登记

| 项目 | 约定 |
|---|---|
| 唯一 Owner | N1；本卡所有 `AC-N1-*` 均由 N1 负责实现、举证和收口 |
| 建议目标版本 | `1.0.0rc4`；这是规划目标，审查基线仍为 `1.0.0rc3` |
| 固定代码基线 | `MainQuestAI/Deck-Master@a08bc68c1cbbbc806205104c2bb01f3f096305f0` |
| 任务性质 | 修复与兼容性收口；本文是待执行 Spec，不代表代码已修改或验收已通过 |
| 前置条件 | Codex 核对执行时的 base/head SHA、实际分支及本卡涉及模块的新变更；相对固定基线的差异单独记录 |
| 与其他卡的关系 | N1 定义操作事实查询与恢复合同；N4 可加速查询，但不得改变回执、摘要、历史及返回语义 |

**目标结果：一次输入更新即使丢失响应、丢失或损坏派生索引，也能用原请求确认实际提交结果；同一拒绝原因在旧 HTTP 与现有服务入口中能够被程序识别；Python eligibility 读取与 HTTP eligibility 读取遵守同一已提交快照边界。**

## 1. 目标与非目标

### 1.1 目标

1. 为普通 `inputs update` 的新提交建立与 Document 同时落盘的原子回执，覆盖实际输入变化、仅名称变化以及业务无变化三个分支。
2. 恢复先于素材解析、上传文件查验和源文件读取；已提交请求的重放只依据已保存事实，不能再次摄取素材。
3. 兼容普通 CLI/API 的非 UUID operation ID、原有成功响应结构及旧日志摘要；明确允许和拒绝的跨入口重放。
4. 让旧 `/api/inputs/update` 在 pause、scope、decision、输入冲突等情况下返回稳定的结构化错误，保留真实业务原因。
5. 仅修复已定位的 `eligibility.describe()` Python 读取边界，与 `collaboration_api` 的 eligibility action 共用已提交快照解析。

### 1.2 非目标

- 不改写、补造或批量迁移历史 Document、旧摘要及缺失的旧请求绑定。
- 不改输入影响分析、内容协调、任务采用、调用预算、pause/revoke 或最终交付的业务裁决。
- 不增加数据库、服务队列、自动重试模型调用或新的运行审批流程。
- 不统一改造所有 HTTP 路由、所有 service/task/history Python 入口，也不新增独立 SDK 包。
- 不把底层 `Store.load_document()` 全部替换为对外快照查询；事务内原始读取仍保留。
- N4 的缓存优化不是本卡完成的前提；关闭或删除 N4 索引时，本卡必须全部成立。

## 2. 已核验现状与证据

下表只描述固定 SHA。实际执行分支、用户项目、用户安装状态及测试结果仍**需要 Codex 核验**。

| 已核验事实 | 固定源码证据 | 对本卡的意义 |
|---|---|---|
| 普通输入更新只从 `.deckmaster/operations/<id>.json` 恢复，文件不存在即返回未命中 | [service.py L1259-L1283](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/service.py#L1259-L1283) | 新项目也可能落入旧恢复路径 |
| `_recoverable_workbench` 与普通入口使用不同恢复分支 | [service.py L1430-L1495](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/service.py#L1430-L1495) | 需要统一提交事实，保留入口协议差异 |
| 普通更新先写日志再切换 Document，没有随提交保存的原子回执；新 content 输入使用 `operations.commit_locked()` | [service.py L1648-L1654](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/service.py#L1648-L1654) | 派生日志丢失后无法仅从已提交历史确认原请求 |
| 旧普通 no-op 仅写日志，既不创建 revision，也不在历史 change 保存 operation ID | [service.py L1573-L1595](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/service.py#L1573-L1595) | 纯历史 not_found 不足以允许新提交，必须先检查仍在的旧日志 |
| 常规 CLI 使用普通分支；新 `content inputs` 要求 UUIDv4 | [cli.py L599-L616](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/cli.py#L599-L616)、[content_ops.py L391-L397](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/content_ops.py#L391-L397) | 不能用切换一个布尔参数的方式收口，否则会收窄旧 ID 合同 |
| 当前素材规范化可调用 upload resolve/show，而 show 会读取并校验上传文件字节 | [service.py L1359-L1376](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/service.py#L1359-L1376)、[source_uploads.py L38-L51](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/source_uploads.py#L38-L51) | “在 `_read_patch_material()` 前恢复”仍不够，恢复还必须早于上传查验 |
| 通用操作模块已经支持已提交历史回执及可重建索引 | [operations.py L55-L152](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/operations.py#L55-L152)、[store.py L415-L443](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/store.py#L415-L443) | 复用现有存储机制，不另建业务账本 |
| 旧 HTTP 入口存在单独的异常映射，最终还可能返回字符串 error | [web.py L284-L337](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/web.py#L284-L337) | 用薄 adapter 保留明确的拒绝原因，无需重排路由框架 |
| Python `eligibility.describe()` 直接读取 revision 文件；HTTP eligibility action 使用 `load_snapshot()` | [eligibility.py L1843-L1857](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/eligibility.py#L1843-L1857)、[collaboration_api.py L218-L222](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/collaboration_api.py#L218-L222) | 对外 Python 入口需要遵守同一 committed ancestry 边界 |
| `snapshots` 已拒绝非法 ID、孤立/跨项目 revision 和符号链接 | [snapshots.py L35-L145](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/snapshots.py#L35-L145) | 不重新实现第二套 revision 校验器 |

本轮审查中已在临时合成项目确认：普通 `inputs_update()` 提交后删除其 operations JSON，同 payload/ID/base 重试会返回 `input_revision_conflict`；`operations show` 返回 `operation_unverified`，项目内容未被重复改写。这是本卡的缺陷基线，不是修复验收结果。

## 3. 先固定兼容合同

### 3.1 操作族与跨入口重放

| 操作族 | 入口 | 新请求 ID 规则 | 同族跨入口重放 | 不同族同 ID |
|---|---|---|---|---|
| `inputs.update` | CLI `inputs update`、`service.inputs_update()` 普通模式、旧 `POST /api/inputs/update` | 保留既有 `Store` operation ID 语法；不新增 UUID 或 128 字符限制 | **允许**，但解析后的 patch、原 base 和相对路径上下文必须完全一致 | **拒绝**，不转换、不重新提交 |
| `content.inputs` | CLI `content inputs`、`content_ops.inputs()`、`POST /api/content/inputs` | 保留 UUIDv4 | **允许**，使用现有 content 请求摘要与 wrapper 语义 | **拒绝**，即使业务内容看起来相同也不混用 ID |
| 中性查询 | `operations show` 及其现有 HTTP 入口 | 接受能够命名已有操作的安全 ID | 可查询任一族的已提交事实 | 只读查询不改变所属操作族 |

跨入口等价指业务结果、原提交版本、当前版本和错误原因等价；不要求旧扁平成功响应与新 `committed/operation_result` 外壳逐字相同。各族的现有成功外壳必须保留。

表中的严格 base/路径上下文绑定适用于新原子回执。旧普通日志按旧协议判断；原协议摘要没有保存 base 时，不补造该绑定，也不把旧协议原先可回放的请求改成新协议规则。旧日志适配仍执行操作族占用检查。

### 3.2 摘要与历史规则

1. **旧普通日志不改摘要算法。** 仍按已保存的 `request_sha256` 和旧规范化合同识别，不给旧操作补写新摘要、不重新解释已保存历史。
2. **已有及后续 `content.inputs` 保留原摘要。** `operations.request_digest(document, 'content.inputs', base_revision, {'input': patch})` 的协议和内容不改。
3. **普通 `inputs.update` 的新原子回执使用可识别的新请求摘要域：**

   ```json
   {
     "protocol": "inputs-update-request.v1",
     "kind": "inputs.update",
     "project_id": "<已有项目ID>",
     "base_revision": "<客户端原始base>",
     "patch": "<解析后的原始JSON对象，保留数组顺序、字符串、空白及Unicode>",
     "relative_path_base": "<仅存在相对素材路径时，记录无文件系统解析的绝对patch_dir；否则null>"
   }
   ```

   使用现有 `canonical_json_bytes()` 和 SHA256。`patch` 在示意中代表对象，不是转义后的 JSON 字符串。只消除 JSON 对象键顺序差异；不自动 trim 业务字符串、不把省略字段与显式默认值视为同一原请求。

4. 新摘要在任何素材读取前计算。相对路径上下文采用字符串级 `expanduser/abspath`，不得执行 `Path.resolve()`、查验 symlink、调用上传记录解析或读取源字节。原请求使用相对路径时，跨入口必须能够从既有参数及入口上下文确定相同 `patch_dir`；否则是不同绑定。不为此增加旧 HTTP 路由参数，支持等价调用的测试可使用绝对路径原请求。
5. 新普通回执复用现有 `Document.change.operation_receipt.v1`，由 `change.kind=input_update` 与该回执的组合确定摘要域；不混用 task/freeze 回执的摘要算法。`content.inputs` 继续使用其现有 `operation_commit.v1`。
6. `operation_id` 在项目内不得因换入口成为第二次业务请求。不同族、不同 payload、不同 base 或不同相对路径上下文返回冲突；不能把旧回执当成新授权。
7. N1 不增加 writer 名称，不依赖 N3 的 `rc4-content.v1`。新增普通输入提交按既存 `content-ops.v1` 功能 floor 记录最低写入能力；已有更高 floor 只保留不降低。旧历史不回填 floor。

### 3.3 原成功响应

- 普通 `inputs.update` 首次成功仍返回现有扁平结果，保留 `status=updated|unchanged`、`revision_id`、`diff`、`input_alignment`、`pending_tasks` 等原有字段含义，不强制改成 `status=committed` 外壳。
- 普通精确重放返回保存的原核心结果；`revision_id` 始终指原提交。可追加 `current_revision_id`、`replayed=true`、`journal_warning`，不得把旧结果中的 revision 偷换为当前版本。
- 原结果中即使含有当时的 `pending_tasks`，重放也仅返回记录，不再次 dispatch 或 claim；文档应明确先 `continue` 读取当前可执行任务。
- workbench `content.inputs` 保留既有 `committed_revision_id/current_revision_id/operation_result` 外壳。
- 原子回执保存核心结果，不保存后来附加的本机工作台 URL、端口或临时会话信息。

## 4. 实现方案

### 4.1 N1/N4 共用的纯查询边界

在 `operations.py` 内提供以下内部接口；现有 `committed_record()`、`recover()` 和 `show()` 保留为兼容 adapter：

```python
resolve_operation(store, operation_id, *, head_revision=None) -> OperationLookup
```

`OperationLookup` 至少包含：

| 字段 | 语义 |
|---|---|
| `state` | `committed` / `not_found` / `unknown` |
| `head_revision` | 本次查询实际固定的已提交 head |
| `receipt_format` | 原有 `operation_commit.v1` 或 `operation_receipt.v1`；无则 null |
| `stored_kind` | 原记录或 change 中原样保存的 kind，例如 `input_update`、`content.inputs`；adapter 可据此映射操作族，但不能改写原字段 |
| `committed_revision_id` | 有可靠提交时的实际 revision；不得指向孤立文件 |
| `record`、`result` | 验证后的原记录和原结果；不重算、不合成替代值 |
| `reason` | `legacy_receipt_only`、`history_unreadable` 等内部原因，供 adapter 选择公开错误 |

规则：

- 查询固定 head 一次，沿同项目的已提交父链查找。命中对象还须验证项目、operation ID、base/parent、result revision 与实际提交绑定。
- `not_found` 只表示完整验证过的该 head 祖先链中不存在此 ID；历史无法完整验证时是 `unknown`。
- 找到旧 input_update 提交但没有原子回执，返回 `unknown(reason=legacy_receipt_only)`；不能仅凭派生日志将其升级为新协议的 committed 事实。
- 无素材/模型/任务执行、无新 revision、无磁盘索引发布副作用。N4 可以替换内部查询策略，不能改变结果。
- N4 的 hint 不得覆盖 `.deckmaster/operations/<id>.json`。旧日志仍是旧入口的兼容材料，不能被通用 `publish_index()` 写成另一种格式。

#### 旧日志 adapter 与中性查询

纯 resolver 不把日志当作原子提交事实；所有可能把 `not_found` 解释为“允许首次提交”的输入入口，都必须再执行同一个受限 legacy 检查。只读取安全 ID 对应的单个旧日志，并校验格式、ID、kind、结果 revision 是否可达；不能扫描素材或假定任意 JSON 是可信回执。

- **旧提交带 change ID、无原子回执：** resolver 返回 `unknown(legacy_receipt_only)`，adapter 检查原日志。缺失、损坏或不可验证时保持 unknown。
- **旧 no-op 只有日志：** resolver 可以是 `not_found`，但完整日志及可达结果 revision 仍占用该 ID。可用纯旧规范化精确匹配原摘要时，普通入口返回旧 `result`，不增加 revision；跨族写入拒绝。对 task/default/reason 等用纯函数复现原规范化；遇到需要当下文件系统、symlink 或 upload 字节才能重建的旧绑定，返回 `operation_unverified`，不得悄悄重读素材。
- **旧 no-op 日志已完全丢失，且历史没有该 ID：** 无法与从未使用的 ID 区分。不得承诺其可恢复、不得伪造旧结果；中性查询只能报告本次已验证历史中 not_found。新操作准入按当前 base/CAS 与现有规则执行，方法文档须说明此边界仅属于旧日志协议。日志存在但损坏时不能当作缺失，返回 unknown 并保留文件。
- **中性 `operations show`：** 对完整可验证旧日志新增只读兼容投影：`status=legacy_recorded`、`receipt_source=legacy_log`、`request_binding_verification=legacy_only`、`operation_id`、`result_revision_id`、`current_revision_id`、原 `request_sha256` 和 `operation_result`。这个新成功分支不叫原子 committed，不填不存在的 result_ref，不改原普通 replay 外壳；不通过查询授权重复执行，不重写日志或历史。原有原子回执查询结果完全保留。

普通精确旧请求的回放，只能使用能够凭已保存事实及纯规范化证明相同的原摘要。不得为了满足兼容测试，把旧摘要升级为新算法或从已提交素材重新摄取。带旧日志的普通/content 入口与中性查询共用格式及 ID 占用判断；N4 不承担该 adapter。

### 4.2 更新入口执行顺序

按以下顺序改造 `service.inputs_update()`，复用现有内容变更实现：

1. **只校验传输形状和安全 ID。** 检查 patch 是 JSON 对象、base 和 operation ID 的基本合法性。读取固定已提交 head；不创建输入变更，不解析上传源，不读素材。
2. **先查已提交事实。** 调用 `resolve_operation()`。若已提交，按所属族校验纯请求摘要，再直接投影原结果；如果操作族不同则返回类型冲突。新回执的恢复不得依赖 operations 目录存在。
3. **处理旧兼容记录。** `legacy_receipt_only` 以及准备作为新请求处理的 `not_found` 都先走第 4.1 节的受限 adapter；包括完整旧 no-op 日志。无法证明时不得猜新 digest，不得自行更换 ID/base 重做。
4. **仅完整 not_found 且不存在可识别或损坏的旧占用记录时准备新变更。** 执行既有 `_normalize_input_patch()`、上传文件校验、`_read_patch_material()`、源快照保存与影响分析。原有错误、scope 和内容协调规则保留。
5. **提交锁内再次查重。** 取得项目写锁，重新固定当前 head，再调用 resolver 与同一 legacy 占用检查；另一个执行已完成同操作时直接恢复。仅未提交且当前 base 匹配时才执行业务更新。对于被另一个输入更新推进的不同操作，维持 CAS 冲突。
6. **一次提交业务结果与回执。** 预先分配新 revision，构造原核心响应，在同一 `_commit_locked()` 中保存变更与 `operation_receipt`；pointed Document 是唯一提交事实。不得先写“成功”日志再依赖它恢复。
7. **派生索引后置且尽力写入。** current 已切换后，缓存写失败返回核心成功结果及 `journal_warning.code=receipt_cache_unavailable`。不能把已提交改报未提交；不得清理历史来修复索引。
8. **返回保持兼容的结果。** 包装时只增加当前版本、重放标记及非敏感告警。工作台 URL 由现有 CLI 包装层当场获取，不写入原子回执。

#### 无变化与仅展示名称变化

新普通输入操作的三个分支均形成可恢复回执。业务无变化时允许创建**仅记录这次输入操作结果的 revision**，保持 `status=unchanged`；Page、ContentPlan、输入 basis、任务列表、调用事实均不变化，也不新建 Host 任务。仅展示名称变化沿用既有无重新生成行为。旧历史 no-op 不回填 revision。

#### 并发素材读取的边界

进入素材准备前已确认 `not_found` 的新请求，可能与另一执行并发读素材；锁内必须再次查重，最终只有一项提交。已经能够从提交历史识别的重放，不能再读素材。N1 不为避免所有并发读取而在整个文件解析期间持有项目写锁。

### 4.3 旧 HTTP 错误 adapter

实现一个窄的业务异常投影函数，供 `/api/inputs/update` 的异常分支使用；同一已存在异常类型在相关旧入口的适配点可复用。保留路由及成功 payload，避免重排所有 POST 处理。

| 条件 | 旧 HTTP 目标行为 | 普通 CLI 行为 |
|---|---|---|
| `request_paused`、`scope_exceeded`、`decision_needed` 等 `EligibilityBlocked` | HTTP 409；`error.code` 为真实首要 reason；保留 reasons、责任角色、next_action、decision projection 和 revision 信息 | 保留当前退出码；同一个业务 reason 不改成 invalid_input |
| stale base / 不同 payload 或绑定 | HTTP 409；保留 input_update 兼容码 `input_revision_conflict`，细分原因放 `error.cause` | exit 5；不自动换 ID 或 base |
| 同 ID 不同操作族 | HTTP 409；普通入口 `input_revision_conflict` + `cause=operation_type_conflict`；content 入口保留其 operation 冲突族 | exit 5 |
| 已提交旧操作但回执无法核验 | HTTP 409；`operation_unverified`、`operation_state=unknown`、`retryable=false` | exit 4；提示先检查原操作，不提示直接重做 |
| 历史/对象 I/O 无法完成验证 | HTTP 503；`operation_unavailable`、`operation_state=unknown` | exit 4 |
| 请求 JSON/字段错误 | 结构化 `invalid_input`；保持该入口原有 400/422 兼容映射并固定测试，不借本卡统一所有路由状态码 | exit 2 |

错误对象至少有 `code/message/field/next_action`；需要恢复时增加 `operation_id/operation_state/cause`。禁止把业务拒绝降格为裸字符串、`local_io_failed` 或 `request_failed`。公开错误不包含实际 HOME、临时路径、原始 parser traceback；详细异常留本地诊断。

### 4.4 SDK eligibility 快照边界

只修改以下调用链：

- `eligibility.describe(project, action, targets=None, revision=None, context=None)`；
- `collaboration_api.invoke(..., action='eligibility')` 的 artifact/control 读取；
- 为二者复用所需的 `snapshots` 小型 helper。

要求：

1. 当前 control 通过安全的 committed snapshot 读取捕获一次；指定 artifact revision 必须属于该 control head 的同项目父链。
2. `revision is None` 与 `revision == ''` 区别处理；空串、路径、重复 query、非法 ID 不能退回当前。
3. 可在 `load_snapshot()` 增加内部的已验证 head 参数，或增加返回 `(artifact, control)` 的窄 helper。调用者不能传未经验证的任意文件作为 head。保留原函数无新参数时的合同。
4. 当前 head 后续推进，不把两个读取拼成无声明的混合快照；返回实际 artifact/control revision，公开结果仍保留各入口已有外壳。被选历史 artifact 仍受固定当前 control 的 pause/revoke 等规则约束。
5. SDK 抛出同一 `ReadModelError` code；HTTP 保留既有外壳并映射同码。非法、孤立、复制、跨项目和符号链接 revision 均拒绝；不恢复、不初始化、不修改项目。

## 5. 模块落点与开发顺序

| 顺序 | 模块 | 具体工作 |
|---|---|---|
| 1 | `operations.py`、`snapshots.py` | 实现 canonical resolver 与固定 head 读取；先在无 N4 缓存下通过正确性用例 |
| 2 | `service.py` | 分离无 I/O 请求摘要和有 I/O 素材规范化；新普通回执、旧日志 adapter、三种更新分支及锁内查重 |
| 3 | `cli.py`、`web.py`、必要的 `errors.py` | 保留普通成功形状/ID规则；增加窄错误 adapter 与稳定 recovery 字段 |
| 4 | `eligibility.py`、`collaboration_api.py` | 只收口已定位的 eligibility 快照读取差异 |
| 5 | 现有测试和恢复文档 | 回归矩阵、failure injection、更新 Agent recovery 中的真实恢复动作 |

新增辅助函数应承接职责，不复制整个 `inputs_update()`。`operations.recover()` 仍可负责读后重建派生索引，但 pure resolver 本身不能写。N4 只依赖 resolver 合同，不拥有本卡任何 AC。

## 6. 验收标准（均为待执行）

每项唯一 Owner 均为 **N1**。测试必须断言真实业务状态、记录和素材读取次数，不能只断言函数被调用。

| AC ID | Given | When | Then |
|---|---|---|---|
| AC-N1-01 | 新 RC3 项目、普通入口、有效非 UUID ID（含基线允许的超过 128 字符但可落盘 ID） | 完成 task-only 输入更新 | 保持原响应形状；业务与回执在同一 Document 提交；`operations show` 能定位原提交 |
| AC-N1-02 | add/replace 或 upload 输入已经成功提交，随后本机源或 upload staging 被移走/修改，operations 索引被删或损坏 | 原 payload/ID/base 重放 | 从历史恢复原结果和当前版本；`_read_patch_material`、`read_source_snapshot`、upload resolve/show 的调用次数为 0；不重新派发任务 |
| AC-N1-03 | 一次更新分别在对象写、revision 写、pointer 前、pointer 后响应返回前、索引发布处失败 | 原请求恢复 | pointer 前只有旧状态且可重新执行；pointer 后确认原提交；孤立 revision 不算成功；缓存失败返回成功+warning |
| AC-N1-04 | 同族请求从 CLI、Python、旧 HTTP 任一入口先成功 | 换同族入口提交相同原请求，或换不同 payload/base/path context | 精确请求恢复同一提交；变更请求冲突；字符串空白和 Unicode 不被静默归一化；相对路径上下文不一致拒绝 |
| AC-N1-05 | 一个 ID 已属于 inputs.update 或 content.inputs | 通过另一操作族使用该 ID，或中性 operations show 查询 | 跨族写冲突且 current 不变；中性查询可读；content 的原 UUID 与 digest 合同不变 |
| AC-N1-06 | 旧真实变更日志、仅日志 no-op、旧日志损坏/丢失各有 fixture | 原旧请求恢复、跨族写入和中性查询 | 完整日志沿旧规则回放/只读投影且占用ID；无法证明者unknown且不读素材；完全丢失的旧no-op明确不可与never-used区分；不改旧摘要/历史，不被新index覆盖 |
| AC-N1-07 | 业务无变化、仅名称变化和实际输入变化各一例 | 首次请求后精确重放 | 新三分支都有原子回执；no-op/名称变化不增加 Host 任务或改变 Page/basis；精确重放不再增加 revision |
| AC-N1-08 | 两执行同时提交相同 ID/相同请求，以及相同 ID/不同请求 | 在独立进程中竞争项目锁 | 同请求仅一个业务提交，另一方恢复；不同请求仅一个提交，另一方冲突；调用事实和输入协调状态不重复 |
| AC-N1-09 | 同一输入更新分别被 pause、scope、decision、stale base 拒绝，或发生历史 I/O 失败 | 走普通 Python/CLI与旧 HTTP，再对照新 content 入口 | 业务 code/原因一致；旧 HTTP 不丢 decision 信息；正确区分 409/503；公开错误不泄露本机路径 |
| AC-N1-10 | 当前/正常历史/空字符串/非法ID/孤立revision/跨项目复制/符号链接/损坏revision | 分别调用 SDK eligibility.describe 与 HTTP eligibility action | 当前与正常历史裁决等价；坏输入拒绝同一语义码；无当前回退、写入或初始化副作用 |
| AC-N1-11 | 捕获 control 后发生并发推进或暂停，且 N4 索引分别启用、禁用、丢失 | 查询历史 eligibility 与原操作 | 每次响应声明真实固定 artifact/control/head；不混入后来的未选 revision；启停索引不改变结论或摘要 |
| AC-N1-12 | 带 task/freeze/content 操作和旧输入日志的兼容 fixture | 运行定向原有回执/输入/适配器测试 | 原成功外壳、ID、旧摘要与历史字节保持约定；修复证据明确列执行 SHA、命令、用例及未验证边界 |

## 7. 测试复用与执行建议

优先扩展现有测试，新增反例仅补缺口：

- `test_flow_quality.py`：输入更新、名称/no-op、pointer 前后失败和旧日志兼容。
- `test_task_receipt_recovery.py`、`test_workbench_operations.py`、`test_content_ops.py`：原回执、冲突、丢缓存及跨族不回归。
- `test_rc3_collaboration_adapters.py`、`test_eligibility_enforcement.py`：HTTP/CLI/Python 对照与 pause/scope/decision。
- `test_workbench_reads.py`、`test_snapshot_headers.py`、`test_eligibility_resolver.py`：固定 snapshot、孤立/复制/symlink/损坏拒绝。
- 可新增聚焦文件 `test_input_receipt_recovery.py` 与 `test_eligibility_snapshot_boundary.py`，避免把 N1 所有场景堆入一个历史大测试文件。

Codex 先用 `pytest --collect-only` 核对实际测试名，再运行本卡定向集合。验收环境使用临时项目、明确 synthetic 内容及独立 `--basetemp`；不调用真实模型。项目实际 test gate、测试是否通过和运行环境仍**需要 Codex 核验**。完整发布门禁由迭代总验收统一触发，不因本卡增加无差别矩阵。

## 8. 交付物与完成判定

1. 本卡限定模块的代码、合同兼容说明和定向回归测试。
2. `operation-recovery-compatibility.md`：旧/新回执、摘要、同族/跨族、no-op revision、旧log-only丢失的不可恢复边界和错误码矩阵；可放入本轮正式开发文档目录。
3. `operation-recovery-evidence.json`：固定执行 SHA、环境、命令、AC→测试映射、故障点、原提交/当前版本、素材读取计数和未验证项。
4. 更新 `docs/agent-recovery-playbook.md` 与共享输入更新方法：重放原请求、unknown 与 not_found 的区别、旧日志缺失如何停在可解释状态。
5. 与 N4 的接口评审记录：resolver 三态、head、旧原始 record/result、索引不得覆盖 legacy 日志。

完成必须同时满足所有 `AC-N1-*` 与必要的现有回归。文档写完、测试用例存在、API 返回 exit 0 都不能单独宣布完成。本地真实项目与客户素材并未由本卡提供；涉及其状态的任何结论均**需要 Codex 核验**。
