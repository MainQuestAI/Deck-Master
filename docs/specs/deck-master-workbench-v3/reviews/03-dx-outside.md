# DX外部完整结果

outside_status: completed；已通过格式校验。

```tool-output
# DX 外审结论：5/10

**结论：** 产品层和状态语义已经相当扎实，但开发者契约层明显偏薄。对 Codex Host 集成者和 Python/JS 贡献者来说，本方案回答了"系统应该表现成什么样"，没有回答以下几个动手问题：

- 该敲哪条命令；
- 该发什么 payload；
- 报错后下一步做什么；
- 旧版本碰到新项目会怎样。

CEO 要求的"真实提交证据"和"尽早真实 Host 验证"，恰恰都依赖 Host 集成者能正确接入。目前这条路径没有可照抄的规格。

**不改动的部分：** 用户要求的 UI 设计（参考图简单路径、持久交接、固定候选双栏、显式状态），以及 W01–W12 分包。下面只补 DX 层，不扩成 SaaS 或平台。

---

## 一、问题清单（按严重度）

### P0 / Critical

**1. Host 提交证据协议没有可执行规格**

§2.2 和结尾决议定义了 `core_frozen / host_reported / tool_observed / provider_receipt` 四级证据，但缺少以下内容：
- Host 在"调用前 / 调用后"各自必须做哪一步；
- request hash 的规范化规则，即对哪些字段、按什么序列化方式计算 hash；
- 回执 payload 的 schema；
- 缺少字段时的降级规则。

后果：集成者只能各自猜一种接法。M1b 的退出证据（一次真实的冻结→提交→输出绑定）很可能因为接法不一致而无法复现。

**修正：** 在 W02 卡中补一张时序表，外加一份可直接复制的 JSON 示例：
- 第 1 步 `request freeze`，返回 request_id 和 hash；
- 第 2 步 `attempt start`；
- 第 3 步 `attempt submitted --evidence host_reported --sent-hash …`；
- 第 4 步 `attempt result --outputs …` 或 `attempt fail`。

hash 算法写死（例如 canonical JSON + sha256），并给一个测试向量。

**2. CLI 语法完全缺席**

方案多次说"CLI/Host 可做同样操作"，§6 却只列了 HTTP 路由，而且标注为"提案"。冻结请求、记录 attempt、采用候选、plan/commit、指定版本导出，都没有对应的 CLI 动词、参数和默认值。Host 集成者主要走 CLI，这一块等于空白。

**修正：** 补一张 CLI↔API 对照表，统一采用"名词 + 动词"语法：

| 能力 | CLI 示例 |
|---|---|
| 请求 | `deck request freeze\|show` |
| 尝试 | `deck attempt start\|submitted\|result\|fail` |
| 候选 | `deck candidate list\|adopt` |
| 变更 | `deck changes plan\|commit` |
| 操作核实 | `deck op status <operation_id>` |
| 导出 | `deck export --purpose review\|delivery\|engineering --revision` |

统一约定：
- 全部支持 `--json`；
- 退出码语义固定：0 成功 / 2 用法错误 / 3 基准过期 / 4 门控拒绝 / 5 冲突；
- 默认值写明，例如 `--revision` 默认取 current，`purpose` 没有默认值、必须显式指定。

### P1 / High

**3. 缺统一错误模型**

方案里散落着至少七种拒绝路径：
- 基准过期；
- operation_id 同 ID 不同 payload；
- 门控前置不满足；
- 晚到结果被拒；
- 旧格式只读；
- 目录未注册；
- Host 未连接。

UI 侧要求"原因 + 下一动作"，但 API/CLI 侧没有对应定义。

**修正：** 定义统一的错误 envelope：

```
{code, message, target, base_revision, current_revision, next_actions:[{label, cli, api}]}
```

配套一份稳定错误码表，例如 `STALE_BASE`、`OP_PAYLOAD_MISMATCH`、`GATE_PREREQ_MISSING`、`LATE_RESULT_REJECTED`、`LEGACY_READ_ONLY`、`PATH_NOT_REGISTERED`、`HOST_UNCONFIRMED`。

UI 文案从 `next_actions` 渲染，保证 CLI 和 UI 给出同一个下一步。

**4. 兼容与升级路径不可操作**

W02 写了"新项目明确协议版本；新写不兼容则阻止旧写端"，但没有说明：
- 版本号存在哪里；
- 旧 Skill/CLI 碰到新项目时看到什么报错；
- 用户该跑哪条命令升级。

b79e6a5 已经把 Skill CLI 绑定到具体 release，版本错配是真实会发生的场景。

**修正：**
- 项目元数据中写入 `protocol_version`；
- 旧写端报 `PROTOCOL_TOO_NEW`，并附带升级命令；
- 新增 `deck doctor`，检查 wheel/Skill/项目协议版本是否一致，以及端口和注册目录状态；
- 给出兼容矩阵（旧 CLI × 新项目、新 CLI × 旧项目，各自的读/写行为）。

**5. 本地 HTTP 写鉴权对 Host 不透明**

§6.3 要求校验 Origin 和"会话写能力"，但没说 Host 或脚本写入时走 CLI（进程内）还是 HTTP。集成者如果直接调 HTTP，会撞上 403 却不知道原因。

**修正：** 写明"Host 只经 CLI 写入；HTTP 写接口仅服务于浏览器会话"。如果确实需要脚本走 HTTP，给出 token 获取方式（例如 `deck web token`），并说明 403 对应的错误码。

**6. 交接文本（handoff）没有格式规格**

"复制交接"是无 Host 连接时的主路径，但复制出去的内容长什么样、Host 如何从中解析出 project_id / request_id / operation_id，都没有定义。

**修正：** 交接文本采用固定结构：一段人类可读说明，加一个带版本标记的 fenced 块（内含 ids 和要执行的 CLI 命令）。在 W06 卡中附样例。

### P2 / Medium

**7. 开发环境隔离缺失**

生产 launchd 服务固定占用 5050，而方案明确要求不碰真实 HOME。贡献者本地起 v2 时会和生产服务抢端口、共用 registry。

**修正：** 明确以下约定：
- 环境变量 `DECK_MASTER_HOME`，或参数 `--home`；
- `--port 0` 自动分配端口；
- 开发 registry 与生产隔离；
- 写一段"从 clone 到看到 24 页画廊"的 5 条命令快速上手，放在 README 的醒目位置。

**8. 24 页合成样本不可复现**

这个样本同时是验收基准和原型数据，却没有说明它从哪里来。

**修正：**
- 提供 `tests/fixtures` 生成器，例如 `python -m deck_master.dev.fixture --pages 24 --anomalies drift:2,missing:1,stale_ppt:1`；
- 输出必须确定性；
- 同一个 fixture 同时供 pytest 和浏览器测试使用。

**9. 前端测试工具链未定**

方案用原生 ES Modules、不走构建，默认用 Playwright 做验证，但 pre-merge 只有 pytest。引入 Node 会改变 Python 贡献者的开发环境。

**修正：** 优先采用 pytest-playwright，保持单一工具链。把浏览器测试纳入 pre-merge，或者明确它为什么暂时不进门禁。

**10. 版本概念混用，缺词汇表**

`revision`（项目级）、`base_revision`、对象版本、`artifact_id/版本`、request hash 在文中交替出现。中文 UI 术语与代码标识也没有对应表，比如"原图 / 逐页稿 / 试作 / 采用"分别对应哪个标识。

**修正：** 在 CODE-BASELINE 加一张术语表，列三栏：UI 中文、代码标识、字段名。并规定 `revision` 只用于项目级快照，对象级一律称 `version`。

**11. v2 入口的默认值与回退方式不明确**

"入口显式选择 v2"，但没写是 `deck web --ui v2`，还是直接访问 `/v2/`，也没写旧入口如何回退。多项目下"启动/复用已有服务"时，服务发现依赖什么（pid/端口文件）同样没有说明。

**修正：** 写明 flag、默认值（M2 + W12 之前默认走旧 UI）、服务发现文件的位置，以及冲突时的报错。

**12. operation_id 生命周期不完整**

没有说明 operation_id 由谁生成（客户端还是服务端）、格式、保留期限，以及核实时用什么接口。"保存未知则用原 operation_id 核实"缺一个查询端点。

**修正：** 规定客户端生成 UUIDv7，补 `GET /api/operations/{id}` 和对应的 CLI `deck op status`，并写明保留期限。

### P3 / Low

**13. 文档可查找性差**

结尾有大量追加式的决议条目，与正文重复，后续容易产生漂移。

**修正：** 给决议编号（D-01…），在正文中引用编号。增加一个 `docs/specs/deck-master-workbench-v3/README.md` 作为索引，指向 PLAN、UI-SPEC、CODE-BASELINE、W 卡和 AC 归属表。每张 W 卡固定包含"可复制示例"一节。

**14. 字体授权**

字体授权文件随 wheel 分发这一点，在 W12 中应作为显式的检查项，而不是仅在 §5 顺带提到。

---

## 二、评分依据

| 维度 | 分 | 说明 |
|---|---|---|
| 首次使用路径 | 5 | 用户侧清晰，贡献者和集成者没有快速上手路径 |
| 可行动错误 | 4 | UI 有原则，API/CLI 没有错误模型 |
| API/CLI 语法与默认值 | 3 | 只有路由提案，CLI 空白 |
| 文档可查找 / 可复制 | 5 | 内容完整但密集，缺少示例和索引 |
| 兼容与升级 | 6 | 原则正确（不迁移、只读兼容），但缺少可执行的版本机制 |
| 开发环境 | 5 | 与生产服务的隔离未定义 |
| **综合** | **5/10** | |

补齐 P0/P1（第 1–6 条）后，预计可以到 7.5 分。这些改动全部落在 W02、W06、W03 三张卡的契约附录里，不改变 UI 设计，也不新增模块。

Recommendation: 在进入 W01/W02 实现前，先为 W02/W06 补齐 Host 证据时序与 hash 规则、CLI↔API 对照表和统一错误码/协议版本机制 because M1b 的真实"冻结→提交→输出绑定"证据完全依赖 Host 集成者按同一契约接入，而当前方案只有语义没有可照抄的命令、payload 和错误路径。
```
