# RC3-04 R4 独立固定代码复核

**结论：PASS_LIMITED_FIXED_CODE_REVIEW。未发现 must-fix。** 本结论仅覆盖下列固定代码、测试迁移、只读证据校验和有限探针，不代表整卡验收或最终 CI 通过。原 8223df8 CI 的 90 FAIL / 342 PASS / 4 ERROR 继续作为失败原件保留；后续安装步骤当时未执行，不改称通过。

## 固定身份与只读证明

- HEAD：`02a6d44da85cf4ecde9d84d4587f648587c41597`
- tree：`8a12383ab597dbd061ad53de6f5186c5343d19d4`
- parent：`8223df80be654c9a89a44cd97cf770fa01bf4383`
- source：`/workspace/work/rc3/reviews/rc3-04-r4-code-snapshot-02a6d44`
- 专属 Python：`/workspace/work/rc3/reviews/env-04-r4-02a6d44/bin/python`
- 实际导入的 `deck_master`、`content_production`、`eligibility` 均来自此 snapshot 的 `src/deck_master/`，版本 `1.0.0rc3`。采集和有限 SDK 检查使用 absolute Python、`-I -B`；工具环境激活后仍使用该 absolute Python。
- 3935 份完整 tracked 文件的内容 SHA256、mode，以及 HEAD/tree/status/Python/version/module origins，在本次检查前后完全相同；前后 status 均为空。`source-before.json` 与 `source-after.json` 同 SHA256：`52ba9d424064d79539608f6e6a92a63d48576e88a0815411fbff1d88ae3ff85b`。详见 `source-unchanged.json`。
- 未编辑 source、安装目录、旧 snapshot、旧原件、Git 或用户 HOME；未运行 broad、安装包验收、真实模型、真实图像、05、PowerPoint 桌面或人类验收。探针项目仅位于外置短 TMPDIR；报告不复制 Store、registry、认证 key 或 HMAC。

## 产品改动复核

完整 parent→HEAD 非 docs 差异恰为 34 个文件，其中 5 个产品文件、29 个测试/示例/helper。已逐文件读取差异及 R4 handoff。

| 改动 | 复核结论与证据 |
| --- | --- |
| C1：`gallery.js`、`content-sources.js`、`overview.js` | v2 使用实际 `page_ids` 分章，不把 `goal_id=null` 当同一个目标；v1 goal→page 分支保留。v2 outline 从完整 `plan.input` clone，只修改实际章名、对应 role 的 `intended_takeaway` 和 `source_links`；budget、time、speech、issues、tradeoff、page order、其余 role/mapping/qualification 字段保留。原 v1 summary/unresolved 编辑分支保留；v2 对无对应字段的旧 summary/局部未决事项只读展示，不伪造 v1 保存。source-link 的投影三字段与活动 v2 contract 完整一致。执行原文件的精确源码片段，9 项新旧正例/clone/多章边界通过；这些是逻辑探针，不冒称浏览器或 DOM 验收。 |
| C2：`content_production.py` | 只在没有 Page 变化/删除时读取独立 `diff.unchanged_reason`；缺省时保留原 summary fallback，显式非法值拒绝，字符串仅去掉边界空白。采用和 proposal-only 回执均保留独立理由；理由不会产生授权、已读、来源已核验或费用事实。实际 SDK 验证 summary/reason 区别、原 Page/output 保留、5 种非法值无写拒绝、exact replay、summary fallback、内部换行/Unicode 保真、proposal-only 无采用及重放、越范围理由仍被公共 eligibility 更早拒绝。 |
| C3：`eligibility.py` | 仅在只读 `preproduction_state` 边界捕获 `ModelError`/`StoreError`；返回 `unreadable`、`satisfied=false`、全部 required units 缺口和原件保留提示，没有跳过坏 Task、修坏对象或伪造 pass。实际坏 Task 的项目读取仍可用；`production.resolve_page_rendering_design` 继续抛原严格 generation-lineage 错误，produce/delivery 继续拒绝且全树不变。delivery 例先遇已有 decision 缺口，未将其冒称独立证实新的 unreadable 判据。自编负对照验证非预期 `RuntimeError` 不被吞掉；额外验证两种预期异常均明确返回缺证。 |

`content_production.py` 除 `_accept_input_revision` 外的所有顶层 AST、`eligibility.py` 除 `preproduction_state` 外的所有顶层 AST，均与 parent 相同。245 份其余 tracked runtime/tools/pyproject 文件逐字节相等；其中严格 `production.py`、方法路由、控制/费用/授权、安装/版本/build hook 没有本轮改动。23 份 Skill/方法资源、68 份活动 contracts、37AC/13CQ ledger 也均逐字节相等。见 `static-audit.json`、`remaining-runtime-byte-reuse.json`。

原 F1–F9、严格 03 lineage、方法/权限合同不因此重新全矩阵执行；复用依据是其完整源文件或未改函数的准确字节/AST，加上本次实际受影响负对照。此处不是重发旧验证的全量通过声明。

## 测试/示例迁移与原义

24 份 browser 测试原有 1379 条 `assert`/`expect` AST，现有 1401 条。没有原 test 函数删除。原断言仅 5 条被明确的同义 contract 迁移替换：

1. `test_pr103_complete_browser.py` 两条历史选项旧文案改为实际精确“正在阅读的历史版本”；同时保留原 `option[value=A/B]` 身份并加强 selected value、URL revision。原 source/current/export/restore/CAS 身份断言均保留。显示全部历史记录在实际 route 重挂载后重新明确选择，没有改默认历史筛选产品规则。
2. `test_studio_content_browser.py` 三条旧 v1 `input_summary`、`goals[].purpose`、`goals[].source_links` 持久化断言，迁移为实际 v2 章名、`page_roles[].intended_takeaway`、`page_roles[].source_links`；新增未编辑 budget/time/speech/issues/tradeoff/order/其余 role 保留断言。原取消、preview、真实 commit、source version/locator、stale/CAS、Page/task 不变和只读断言继续存在。

此外，示例 w12 的 1 条 digest 验证从尚未展开 row 改为实际点击“查看文件与哈希”后，在真实完整性 dialog 验证同一下载文件的完整 digest，再关闭 dialog；其余 ZIP 每文件 digest/notes/privacy/安装资源字节断言保留。示例 w11 新增的仅是固定 p1 output 的明确 L1 host-attested `export.delivery` 授权与 `delivery_acceptance` decision，0 call/0 candidate，未将旧工程/host_self 记录升级为真实人类授权或专业审查。

其他迁移均核查为当前协议的显式具名 Request/方向/Grant/capability，或仅将证据落点从 checkout/output 移到 `tmp_path`/明确外置 env：

- A 的 content/candidate 浏览器 helper 通过真实服务建立当前请求，枚举当前 Page，0 外部调用；4 或 34 local-candidate ceiling 由相应测试规模明确指定。原业务断言未删除。两候选晚回包用实际 `expect_response.finished()` 与 `expect_request` 先确保旧请求完成/新请求被 hold，未放宽超时。
- B 的 style 授权在首次页面载入前明确准备，按实际 p02/p30、0/1/2 calls 的测试分别给 scope；不强制 enable 控件。任务/版本只读测试明确使用历史 snapshot，原 Page 内容保留，不伪造现代 Task binding。需要写当前正文的用例单独具名 p01、0 call scope；没有全局 autouse 授权。
- C/Classic 的完整计划编辑与范围改动使用真实方向 decision + 0 call editorial grant；范围输入、精确节点/Unicode、取消/commit、错误与全树不变断言保留。artifact 迁移不隐藏产品自身写入。
- `test_content_ops.v2_revision_envelope` 只额外转交 authored `unchanged_reason`；实际 Task 的协议/必需 capability 被真实 claim 消费，未造 native、provider、independent 或 professional PASS。
- 全部 timeout 调用及 timeout keyword 数值 AST 与 parent 相同。新增 `style_navigation_page` 的缺 Playwright/Chromium 条件与其原 `workbench_page` fixture 完全相同；无按失败结果 skip、xfail 或新增 autouse。实际缺工具条件不被解释为产品通过。

三个独立 SDK helper 身份检查实际读取归一化的当前 grant/decision：具名 page ids、动作、层、0 call/候选上限、host_attested assurance、空 verified receipt 均符合上述声明；0-call style 没有被伪造为前审满足，已有 fidelity fixture 的 review 仍是明确 `host_self`、independence=false、无 identity receipt。

## 原失败和安全证据对账

直接从 canonical browser log 独立解析到 94 个 summary 事件，准确为 90 FAILED + 4 ERROR。其 `(outcome,test_id)` multiset 同时等于原库存和新映射；93 个 distinct test ID 的函数均仍存在。单个 batch lost-response 的 FAIL 与 teardown ERROR 继续作为两个事件、一个业务 test ID 保留，未增加关闭场景数量。每项映射引用的冻结 worker handoff hash 均验证一致。

两份安全 manifest 验证通过：5 份 CI 失败原件副本和 13 份 focused 副本，共 18 份 / 1,416,720 bytes，分别与原件逐字节、声明 SHA256/size 相等；2 份明确 derived 映射/源清单也核 hash。copy allowlist 没有 Store、registry、认证 key、venv、安装包或客户材料。旧失败未编辑。详见 `static-audit.json` 与 `canonical-events-crosscheck.json`。

## 本次实际执行与边界

- **17 个 distinct SDK 检查最终实际通过**：本轮执行先 13 PASS + 1 reviewer 错误异常类型预期，随后只补该单条并完成拒绝后全树不变检查，1 PASS；另 3 个具名 helper 身份检查最终 3 PASS。不是单次 17 项全量重跑或 broad PASS。
- 其中 7 个来自当前固定提交的 C2/C3 新测试，10 个由本 reviewer 编写。没有为这次 review 修改产品或仓库测试。
- **9 个精确原 JS 源码片段逻辑探针 PASS**：gallery/content/overview 的 v1/v2 分章、v2 完整 clone 仅改实际字段、深拷贝隔离、v1 兼容。源码片段有独立 SHA256。未启动浏览器，不据此声称视觉/route/DOM 通过。
- `fixture-authority-final.log` 的 6 个 warning 为外置 review pytest root 未注册所导入源测试的 browser/render marks，原文保留；0 skip。
- SDK 全部使用 offline wheelhouse flags、专属 absolute Python，探针 basetemp 在外置短 TMPDIR。没有真实模型/图像 API 调用或人类/桌面效果声称。
- broad、实际安装 UI/recovery、独立受影响行为/UI 复审和新 exact-head CI 由 Root 的其他验证承担。本报告不替代它们；最终是否 merge 须继续按完整链路判断。

## Reviewer 自编错误及基础设施记录

全部错误及修正见 `reviewer-errors.json`，原日志/XML 保留。包括最初 `git ls-files` 中文路径引用处理、静态工具误写 installer 位置、自编 ModelError 构造参数、独立外置测试 import path、越范围被更早 EligibilityBlocked 拒绝时的异常类型预期、gallery 最小页数误用、归一化 record 的 `evidence` 字段误读，以及一次未创建进程的 exec-server transport 中断。所有这些未引起 source 改动；它们是本 reviewer 的采集/探针错误，不改称产品缺陷，也不从证据中删除。

复核现已冻结，停止继续编辑/执行。具体文件身份见 `SHA256SUMS`。
