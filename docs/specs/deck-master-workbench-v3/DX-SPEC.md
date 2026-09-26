# 开发与 Host 接入规格

这份文件定义开发包必须交付的入口和示例。除明确标“当前可运行”外，v3 新命令和新接口均为**待实现提案**，不能复制后声称已支持。CLI 只有 `deck-master` 一个命令面，各子命令与 HTTP 复用相同 Service。

## 1. 当前可运行：先看设计原型

在本仓库根目录，Python 标准库足够启动合成原型，无安装和模型密钥：

```bash
python3 -m http.server 8766 --bind 127.0.0.1 --directory docs/specs/deck-master-workbench-v3/prototype
```

浏览器打开 `http://127.0.0.1:8766/`。停止用 Ctrl+C。若端口已占用改为8767，并对应打开8767。第一项有用结果是看24页样本的同层联系表，再点第8页查看链路。这里不是安装后的真实工作台。

当前核心源码安装沿用根 README 的 Python3.11/3.12 与 `pip install -e ".[dev]"`。`deck-master view --project <dir> --json` 当前只返回服务状态；W01 的显式 --revision/--summary/--page-id --lineage 才读取 Document（实施前仍为提案）；`view --open`启动或复用单项目服务。当前 `view --no-open`不能被文档冒称全局启动器。`continue`返回awaiting_host并以3退出可以是正常等待，不是生成失败。

## 2. W03 首次成功与默认配置（提案）

W03提供新的 `deck-master workbench` 子命令：无项目时打开项目入口，可用 `--project <dir>`直接打开已验证项目；新入口默认打开 `/v2/`，旧 `view --open`在切换授权前仍打开旧入口；`workbench --ui legacy`打开旧UI，`--no-open`只启动并输出URL；`--port 0`自动分配端口，可显式传可用loopback端口；`--registry <file>`支持隔离测试与多工作区，默认用户配置目录中独立的项目注册表。registry只记用户选择，不递归发现项目。不新增第二CLI可执行文件。

正式W03 Quickstart须随卡交付，顺序为：安装当前候选→`deck-master workbench`→打开随包的明确合成只读样例。输出必须含URL、服务版本、项目ID/入口模式。安装、打开样例与真实Host生成分别计时。目标：有支持的Python、从安装文档第一步到理解样例全稿≤5分钟；网络下载时间和前置安装单列。目标未实测，不能宣传首张真实AI图在5分钟内返回。

| 设置 | 默认 | 覆盖 | 不可绕过 |
|---|---|---|---|
| 浏览器 | 自动打开 | workbench --no-open | 无 |
| 端口 | 自动可用端口 | workbench --port | 只能loopback；冲突报告不抢占 |
| 项目注册表 | 用户配置目录 | workbench --registry | 显式注册，canonical path校验 |
| 已开项目服务 | 健康检查后复用 | 换项目/独立registry | 验证服务身份，不凭端口存活复用 |
| 轮询 | 活动3s/闲置15s/失败最多30s | 首版无用户设置 | 隐藏暂停，单请求在途 |
| 任务超时 | 30min进入待核实 | 首版不开放UI缩短 | 不自动重发外部调用 |
| 生产门控 | 共享核心决定 | 无绕过开关 | 版本/取消保护、质量、文件边界 |

## 3. CLI / HTTP 对照（提案）

下表新命令均需在对应卡实现并测试 `--help`、JSON与错误退出码。所有write参数采用 `--project`、`--base-revision`、`--operation-id`；基准读取用 `--revision`；页面用 `--page-id`。不要让前端直接写对象目录。

| 能力 | CLI | HTTP | 卡 |
|---|---|---|---|
| 固定版本与链路 | 扩展 view --revision R；新增 view --page-id p8 --lineage | GET /api/view?revision=R；GET /api/pages/p8/lineage?revision=R | W01/W05 |
| 变更预览 | 新增 changes plan --input changes.json | POST /api/changes/plan | W06 |
| 提交计划 | changes commit --plan-id P --base-revision R --operation-id O | POST /api/changes/commit | W06 |
| 核实写入 | operations show --operation-id O | GET /api/operations/O | W06 |
| 保存意见 | annotations save --input notes.json --base-revision R --operation-id O | POST /api/annotations/batch | W06 |
| 候选读取/采用 | candidates show --candidate-id C；candidates adopt --input adoption.json --base-revision R --operation-id O | GET /api/candidates/C；POST /api/candidates/adopt | W07 |
| 任务接手/状态/取消 | 复用 task start/status/cancel | 任务投影/取消路由复用共享Service | W06/W10 |
| 请求与调用观察 | requests show --request-id Q；attempts show --attempt-id A | GET /api/requests/Q；GET /api/attempts/A | W02/W10 |
| 交接文本 | changes handoff --change-id X | GET /api/changes/X/handoff | W06 |
| 固定版本导出 | 扩展 export --revision R --purpose review/delivery/engineering | POST /api/exports，固定purpose+revision；GET白名单文件 | W11 |

候选采用统一集合payload（单项为长度1），避免单页/批量两套事务规则；原PLAN的 `/api/candidates/{id}/adopt`为兼容别名时也必须进入相同Service。

```json
{
  "schema_version": "change_intent.v1",
  "project_id": "sample-project",
  "base_revision": "R18",
  "targets": [{"page_id": "p8", "page_ref": "sha256:example", "layer": "original_image"}],
  "intent": "match_reference_style",
  "reference": {"page_id": "p7", "artifact_ref": "sha256:example-reference"},
  "instruction": "采用第7页色板，保留第8页标题、事实和数字",
  "max_calls": 1
}
```

以上是结构示例，hash占位明确无效。W06必须随卡提供真正由临时样例生成的 `changes.json` 与可复制脚本：读取项目revision/ref→写文件→plan→commit→核实operation；示例从回包读取ID，不写固定假ID。暂不为本地应用新建SDK。

## 4. Host最小协议与真实示例（W02）

复用现有任务接手、call allocate/begin/settle和task accept流程；新GenerationRequest/Attempt需要与现有call事实明确映射，不能创建两本互相矛盾的调用账。

任务描述新增 `protocol_version` 与 `required_capabilities`；Host在task start声明 `supported_protocols` / `capabilities`。服务在开始外部调用前校验，不依赖Host名字或Skill文案猜能力。首次手工交接不要求常驻连接；无声明时显示未知且拒绝本任务的新协议写入，旧协议任务仍按原规则处理。

| 组合 | 读取 | 写入 |
|---|---|---|
| 新UI/新核心/兼容Host | 完整新记录 | 按能力允许 |
| 新UI/新核心/旧Host | 可看历史与草稿 | 新任务缺能力明确拒绝，提供升级Skill/手工接入说明 |
| 旧UI/新核心 | 旧deck_view字段保留 | 保持已有命令契约；涉及新对象的任务不能静默降级 |
| 新UI/旧核心 | 启动检查给出版本不兼容 | 禁写并引导匹配安装，不到执行一半才报错 |
| 旧格式项目 | 显示兼容信息 | 禁止原地迁移 |

新Host完整样例必须随W02出现：continue取实际任务→能力校验/start→冻结请求输入→call begin绑定request与attempt→调用工具→settle记录观察者/回执/unknown→task accept绑定输出→view反查。每一步给机器JSON与对应状态；重复接手/提交使用同operation返回同一结果；中断发生在调用之后但回执之前时保留unknown，不再次扣用量后自动重试。

图片改写请求的prompt/参考图必须在调用前冻结；返回时申报不同输入只保留差异事实并拒绝将结果当作匹配候选。由用户修改后建立新请求。Host自报与工具观察并存，不把自报升级为供应商证明。公开Skill的步骤与core协议在同一包版本中验证。

## 5. 错误契约与恢复

沿用现有 `error.code/message/field/next_action` 和退出码0/2/3/4/5，兼容新增 `cause`、对象ID、`retryable`、`operation_state`及仓库内文档锚点 `docs_ref`。HTTP与CLI都投影同一typed error，前端不解析自然语言猜状态。HTTP错误使用4xx/5xx，不用200伪装；正常awaiting_host的状态读取仍是200。

| 情况 | code提案或复用 | 用户可见问题/原因/动作 | CLI / HTTP |
|---|---|---|---|
| 基准变化 | conflict（复用） | 基准R18已变化为R19；保留草稿，读取新版并重新计划 | 5 / 409 |
| 同operation不同内容 | operation_payload_conflict | 此ID已用于另一要求；查原操作，若为新要求则新ID | 5 / 409 |
| 保存响应丢失 | 客户端save_unconfirmed | 不知道服务是否提交；保留待核实payload，用原ID查询 | 网络状态，不能捏造服务端失败 |
| Host协议不匹配 | host_protocol_unsupported | 缺少冻结请求能力；更新公共Skill或使用支持协议的Host | 2 / 422 |
| 工具缺失 | needs_tool（复用） | 命名实际缺少工具及所需阶段；修复后继续 | 3 / 422 |
| 交付不满足 | input_reconciliation_pending等共享code | 命名当版未通过维度和对应页；定位解决后再导出 | 3 / 409 |
| 未知操作ID | operation_not_found | 当前未查询到；原请求可用同ID/同payload安全重放，不另起ID | 2 / 404 |

`docs_ref`只指向离线可读帮助锚点，不杜撰外站。三个主要故障完整JSON样例随W06交付并测试前端与CLI一致；每个新code均纳入恢复文档。错误详情不得输出密钥、材料全文或任意本机路径。

## 6. 文档与升级归属

根索引顺序：先看合成原型→产品方案/UI-SPEC→CODE-BASELINE→正在实施的包→对应contracts→验证入口。用户操作和Host协议分开；本轮设计规格不是已安装软件说明。

- W02：新Host协议、一次完整真实绑定记录、兼容矩阵与唯一Skill同步。
- W03：安装/启动/项目打开Quickstart、配置表、只读样例。
- W06–W10：新增CLI/HTTP成对示例、恢复与错误锚点、当包验证命令。
- W11：review内容兼容变化、engineering敏感材料说明、固定版本导出/下载示例。
- W12：最终安装包逐条执行上述文档；旧包不能验新修复。

只读兼容不触发迁移；显式升级写入记录project format与最低writer版本，不静默回填旧请求。回退旧UI不等于回退旧writer，新数据保留，用匹配核心查看；恢复历史产生新revision。W02须测试旧reader/旧writer与新任务的组合，W12演练安装回退。

开发体验测量使用本地手工记录即可：支持环境、文档起点、每步耗时、求助次数、首个理解的有用结果。合成演示、自动脚本耗时与真实Host耗时分栏。不新增遥测平台、云账户、自动升级器、社区运营或定时监控任务。


## 7. 请求摘要、交接样例与可复现验证

W02新增 `requests freeze --input request.json --operation-id O`，由核心返回request_id和input_hash；外部Host不能自行指定高可信hash。`task call begin`扩展 `--request-id Q`（新协议必填），返回attempt_id并绑定原call allowance；`task call settle`扩展 `--attempt-id A --report observation.json`；结果仍走 `task accept`。不要采用外部评审建议的第二套 `deck` 命令或改既有退出码。

input_hash复用models.canonical_json_bytes：UTF-8、ensure_ascii=False、sort_keys=True、紧凑逗号/冒号、allow_nan=False后SHA256，无尾部换行。hash覆盖完整冻结input对象（schema、准确prompt、Page/design/template refs、参考内容hash及角色、拟用参数和限制）；不含自身hash、生成后的request_id/时间戳/Attempt。核心返回序列化input，Host不得自作Unicode/空白归一。实际文本不同作为观察差异保留，不能当作匹配候选直接采用。

由当前核心函数计算的序列化测试向量（编码向量，非完整请求schema）：

```json
{"parameters":{},"prompt":"保留事实","references":[],"schema_version":"generation_input.v1"}
```

精确UTF-8且无换行，SHA256为 `d2153cf3ffe6fd547e61bfaa909086e85f8e517e84563a443a108a85d240fa06`。W02补完整请求schema向量及跨CLI/HTTP一致测试。

交接格式由核心生成，显示人类摘要，下面是版本化数据块：

````text
请处理第8页的一个原图试作。以固定第7页图片为参考，保留第8页事实。
这是一项待接手请求；先读取当前任务和冻结输入，不要直接重写项目文件。

```deck-master-handoff.v1
{"project_id":"sample-project","change_id":"example-change","task_ids":["example-task"],"request_ids":["example-request"],"base_revision":"R18","required_protocol":"generation.v1"}
```
````

以上ID均是示意。W06真实生成时使用项目实际ID和当前任务输出，附一条由核心安全引用的正式CLI读取入口；材料内容不能注入命令。Host通过CLI共享Service写入，HTTP写接口只面向同源浏览器session；不为脚本公开跳过Origin的token接口。

operation_id由发起端在发送前生成UUIDv4并持久保存，核心仅接受合法长度/字符且按项目命名空间去重；操作记录与项目历史同寿命，不设自动TTL。重复同payload返回原结果，不重复执行；同ID异payload拒绝。查询超时不生成新ID。调用后unknown不等于not_sent，不自动重新分配调用额度。

服务发现复用 `.deckmaster/view.json`与服务身份健康检查，未响应/错误版本不作为健康复用。当前源码是自动端口，不是固定5050；无依据新增launchd约束。开发registry和样例项目用临时目录，禁止测试触碰用户真实项目/HOME安装。

浏览器测试采用已在dev依赖中的Python Playwright；不增加Node构建工具。W03–W08提供确定性合成项目工厂供pytest/浏览器共用，原型样本与真实Host验证分开。W12浏览器资源/下载检查纳入CI环境可执行门禁；真实Host单列人工记录，不用fixture替代。

术语：revision只指项目快照；object_ref/hash指不可变对象版本；page_id是稳定页面身份；request_id是冻结生成意图；attempt_id是一次外部调用尝试；candidate_id是待采用结果；operation_id是一次本地事务重放身份。prompt的input_hash不是项目revision，也不是供应商回执ID。

W01 CLI 兼容决定：无读取选项保留原 view 服务状态；读取与 --open 互斥，--lineage 必须带 --page-id。HTTP 所有相关读路由共用 revision 验证，不存在或异项目快照不得退回 current。
