# RC3-04 R1 独立源码审查：CHANGES_REQUIRED

审查者：`/root/rc3_04_independent_code_review`。固定候选 HEAD `7a8578baa210a92b92ae98922ff3236edf4d5975`，tree `4b7c5a931998ced2de624ee0ec29ff4a9e023139`，父基线为实际03 main `634d75e4cc48368e53b088e47fa09c675cd2b998`。本结论仅适用于该固定源码与下述定向 L1 轨迹，**不是 RC3-04 PASS、全RC3验收或发布结论**。

发现五项必须修复的问题，均已立即交 Root。Root 的全局编号为 **F1、F2、F3、F4、F6**；本 reviewer 的 local F5 即 global F6。全局 F5 为另一路 UI 发现，本报告未将其写成本 reviewer 的运行结果。以下编号不改变原 AC/CQ 或原范围 audit 的 F1–F5。

## F1｜高：确认稿导入检查 incoming 页集合，却替换整个当前稿

位置：`src/deck_master/project_initialization.py:151`，关联 `prepare_manuscript:126`。

`adopt_manuscript` 只用 incoming `ids` 与 `layers=[page_copy,plan]` 调用 guard；`prepare_manuscript` 随后整份替换 Document.pages/content_plan，清除 Narrative 和所有 outputs，并可改整个 quality profile。实际写集合没有包括被删除页、页序、speech、Narrative 与其他实际被清除的层。

正式 SDK 复现：新建固定两页稿 p1/p2 → start_request 明确 edit 仅 p1，禁止增删/重排，layers 仅 page_copy/plan → import_draft 仅含 p1。结果 accepted、current 页集合由 `[p1,p2]` 变成 `[p1]`，p2 被删除，collaboration 控制记录未变。

证据：`probe_import_scope.py`、`probe-import-scope.log`、`probe-import-scope-result.json`；完整原始 Request、scope、前后 Document 与响应均保留。探针只使用真实 create/start/import services，不使用测试夹具、直接 current 改写或外部调用。

违反 CONTRACTS §2.1、§6.1–6.2、§11.3/11.5 的精确 scope/实际写集合，以及 RC3-04 统一导入要求。关闭条件：计算并校验完整实际写集合，或使用真正有界的保留未选页事务；拒绝范围外删除/改序/层变更，保留合法有界与完整导入正例及 CAS/replay。不能靠一律拒绝确认稿解决。

## F2｜高：来源去重只看当前请求，旧来源可重建 request/credit 边界

位置：`src/deck_master/collaboration.py:403`；关联 `_request_source_key:310` 与 `collaboration_budget.initial_per_page_plan`。

`_stage_request` 只在 current 未 closed 且与新输入 source key 相同时去重；没有从已提交 ancestry 恢复同源请求身份。请求被其他请求替换后，同一原指令可以用不同 operation_id 重新获得新 request_id。

正式 SDK 复现：create 原请求 A → 用明确的新只读指令切换到 B → 以 A 完全相同的来源、意图与 scope，用新 op 替换 B。新请求 accepted，`_request_source_key(original)==_request_source_key(current)`，但 request_id 从 `req-e90ae270f1ee` 变成 `req-0f1534e84d9e`。纯预算 planner 随之将 `req-e90ae270f1ee:initial:p1` 改为 `req-0f1534e84d9e:initial:p1`。

证据：`probe_request_source_replay.py`、`probe-request-source-replay.log`、`probe-request-source-replay-result.json`。这里只证明请求/预算 key 边界被重建；**没有图像执行、消费、退款或实际花费结论**。

违反 CONTRACTS §12 的同来源不同 op 返回原 request_id/不刷新 credit，以及 §3.4–3.5。关闭条件：以 committed history/可重建索引去重并复用原边界；closed/paused/withdrawn 的事实不能因此复活。保留真正新明确指令与已声明不同 variant 的合法新请求/预算。

## F3｜高：input_revision 的 Page 映射未验证真实 source/version/locator

位置：`src/deck_master/content_production.py` 的 `_accept_input_revision` Page/最终映射校验段。与正常 page_copy 的 `_check_mapping_against` 比较，前者只调用 `_require_mapping_links_current`/`check_page`，后两者只验证节点集合与 Page 形状，不核实 SourceLink 的项目来源、版本和 locator。

正式 SDK 复现：create 单页合法 imported_mapping → open_phase_task(input_revision,p1,within_scope) → 按真实工作单协议/capabilities claim → accept 含完整映射的 Page。映射中填写 `source_id=nonexistent-source`、虚构 extract Ref、`locator=L999`；项目 `sources=[]`。结果仍 accepted，虚构 SourceLink 进入 current Page。

证据：`probe_input_revision_sources.py`、`probe-input-revision-source.log`、`probe-input-revision-source-result.json`，包含真实 Task/binding、完整信封、前后 Document 和实际采用 Page。无测试夹具、人工 current 改写或外部调用。

违反 CONTRACTS §11.3 要求的真实 source/版本/定位存在校验及 §11.5 的四层完整验证。关闭条件：四层采用复用完整来源/映射校验，任一层非法时无业务半采用；同时保留合法 fidelity/null Narrative 与空语义链接，不强造历史确认或来源。真实语义支持性仍是专业审查职责，不能将结构存在校验误称语义已证。

## F4｜中：strict evaluate 的 needs_reviewer 被映射为 HTTP200/CLI0

位置：`src/deck_master/collaboration_api.py:175`。

`review.evaluate` 无条件返回 `(response,200,0)`，包括真实 `status=needs_reviewer`。正式共享 adapter 调用外部单文件、persistence=none，无实际 reviewer；返回可读 external_report，但仍 HTTP200/CLI0。

证据：`probe_external_gap_status.py`、`probe-external-gap-status.log`、`probe-external-gap-status-result.json`。这是共享 CLI/HTTP adapter 的直接运行；没有启动 HTTP server 或另跑 CLI 子进程，不将其写成额外浏览器/传输层证据。

违反 CONTRACTS §12 与已冻结入口协议对可恢复 needs_reviewer 的 HTTP409/CLI4 映射。关闭条件：使用固定映射，保留完整可读报告于 result；UI/CLI 不能因非200丢报告。报告生成与未满足专业审查分别呈现。

## local F5 / global F6｜高：导出在初始 guard 后暂停，仍可发布 delivery 文件

位置：`src/deck_master/exports.py:515`（初始判定）、`:522`（另一个 exports.lock）、`:548`（发布）。

当前 export 在取得 exports.lock 之前判定一次 current control；等待锁或制作 bundle 期间 current 可变化。`_bundle/_gate` 虽重读当前 policy/reviews 做工程/专业检查，却不重算 request pause/revoke/scope，也没有将最终发布与 Store current-control 变更串行化。

确定性复现：显式 L1 synthetic 工程夹具初始 shared readiness=ready → 主线程持 exports.lock → 另一线程正式 exports.create(delivery) 完成初始 guard 后等待同锁 → 正式 pause_request 提交暂停 → 释放 exports.lock。等待中的导出返回 exported，实际 `delivery-published-after-pause/deck.pptx` 出现。此后 readiness=blocked；新发起的同类导出对照正确返回 EligibilityBlocked。

证据：`probe_delivery_pause_race.py`、`probe-delivery-pause-race.log`、`probe-delivery-pause-race-result.json` 与实际导出文件。没有 monkeypatch 产品；使用 OS 文件锁争用确认 exporter 到达初始 guard 后的位置。唯一复用 helper 是固定 `tests/rebuild/test_export.py::_passing_deck`，其路径/hash 记录于结果；它显式建立 L1 synthetic 工程 facts，不代表真实文件工程验收、human、模型、renderer 或 desktop。随后 export/pause 是正式 services。

违反 CONTRACTS §6.1 提交前同锁/CAS 重查依赖与授权、§7.1 暂停的控制边界。关闭条件：发布前在与当前控制兼容的原子/串行边界重查；等待/构建期间 pause/revoke/current-policy/basis 变化不得发布失去资格的 delivery。保留合法 current/历史固定文件和 review 导出；不要用全程拒绝导出替代修复。

## 七面审查的范围与结论

| 检查面 | 本次实际检查与限界 |
|---|---|
| S1 默认创建/Entry13/兼容 | 检查 private create/publish、统一 manuscript 路由、registry/legacy/sample 初始化、models/schema/Store 单调 floor 与 task capability。新默认 Request/真实来源/framing/no grant 可从探针创建结果核对。旧 rank12 无 region 的历史语义保留；旧 wheel 拒13与安装生命周期本 reviewer 未重跑，引用 Root/B 独立记录而不冒充自测 |
| S2 完整 writer 库存 | 固定候选87 Python文件静态扫描，45 public operation声明、16 service函数、40个直接提交调用函数、158个对象/委托/潜在文件写入函数。补查动态HTTP method/template/dispatch、legacy/sample、本地worker/cache、terminal replay/settle/cancel/restore例外；分类表不是 guard 完整性证明。F1/F6 表明声明覆盖仍不能代替实际写集合与发布边界 |
| S3 四层/正常出口/lineage | 检查四层 parser/cardinality/完整对象组装/Plan links/候选与proposal-only/Task receipt、四 content_intent completion/close、作者 retained-token ancestry 及独立回执排除。F3 为已复现来源缺口；本 reviewer 未重复功能 reviewer 的全四层组合/四意图套件或实际Host16路径 |
| S4 当前控制/结算/迁移/variant/派生ID | 检查 running stale 先结算再 freshness 的已修次序、terminal receipt优先、父链/unknown事实不回滚、迁移 unreadable Task 显式不确定、restore真实targets、顺序variant来源/export/单current、固定Narrative后续采用约束、merge/split frozen source admission/历史ID不复用/未选页与预算保留。F2/F6 未关闭；真实调用与全variant路径没有在本 reviewer 另跑 |
| S5 真实文件/current control | 检查 selected_output 的 sanitized/notes-policy实际hash、current reviews/policy与历史artifact合并、professional human谓词、export/handoff/readiness共用上下文。并发 current-control 出口由F6反证。没有宣称真实人类专业复核/目标桌面通过 |
| S6 §12/strict/import/bridge | 检查完整adapter action表、URL/service项目绑定、pause/resume锁内Request检查、输入可信字段拒绝、strict source清单/源外输出/无Document、报告重hash与Store映射、external SDK context精确 report/result/subjects/authors binding。F4为固定error映射缺陷；普通JSON不能mint受信上下文，实际native执行本 reviewer未伪造或重跑 |
| S7 四Skill/方法/安装/UI消费 | 检查四职责文件/单canonical references、实际workorder方法路径/hash/角色限制、build inventory与generated例外、四links预检/补偿/rollback、物理尺寸字号留白方法、Studio current状态/冻结pending payload/local draft/partial report/CAS处理。实际installed16与独立installed browser由Root另安排，本 reviewer不重复执行，不以字节存在证明Host已应用 |

有限检查未另立新的 AC、测试配额或通用平台要求。未运行宽 unit/render/ruff/browser/benchmark、模型/图像、安装激活或真实 human/desktop；这些 NOT_RUN 不与本报告的五个定向 L1 轨迹混合。Root 并行执行的宽验证与另一 reviewer 的发现属于各自原始证据，本报告未复制其运行结论。

## 来源与安装记录的解释

- 唯一源码运行 Python：`/workspace/work/rc3/reviews/env-04-snapshot-7a8578b/bin/python`；module origin 为固定 snapshot/src/deck_master，version `1.0.0rc3`。所有 shell 显式 offline wheelhouse，短 TMPDIR 在本目录。
- 本 reviewer 独立 source-before 清单含3610 tracked文件，HEAD/tree/status与Root交接相同；其 SHA256 为 `149ff7af72f975dd6261a9430c97e60eea34112b78392987c189b9a8f56349d6`。Root的原清单 `5c380286…` 是另一格式/记录，本报告没有把两个文件hash冒充相同字节。
- 固定候选安装 manifest SHA256 `50d1e8ce8ac3614757c8d1ad5f3dbb220a61cd3302a302fd9326f17664cab27e`，wheel SHA256 `8d52fd31f7d7321876973e0980401d8a834edfa744cd0bcf5f1b908d1b88e8ee`。本 reviewer只读核对这些记录的hash/source identity，没有用该 installed Python 跑探针。
- Root严格V5 byte audit文件 SHA256 `71155724f8be65c4048187bfb7a10cfa986e7211362dd396f11571daa96768fd`，source tree与wheel同上；Root交接其269 canonical+1 generated/all4roles有限PASS。它证明相应字节审计范围，不能抵消本次行为缺陷或代替Host/整卡PASS。
- snapshot中的 B RESOURCE-MAPPING SHA256 `bfca74fbe58d5780b05026f43ddfab1fcc4aa298881f1cecb35c91c35d8fd386`，记录旧 mutable诊断的 source tree `4acb0e…`、release `634d75e4cc48-ada0b2c28037` 与旧诊断wheel。它是路径/资源映射输入，不是R1固定安装运行身份。当前candidate身份依上面的最终manifest/Root严格审计重新绑定。

## 修复复审出口

Root已交Owner修复；R1 snapshot、失败日志与文件保持原样。本 reviewer现在停止，等新的固定R2 head/tree/env。复审仅审必要受影响diff、原五失败轨迹和必要合法正控；不重复全部宽套件、不扩新泛化配额。F1/F2/F3/F4/F6均关闭后才讨论本卡固定源码PASS；实际human/Owner/听众/目标桌面继续按用户安排后置 NOT_RUN。

末次身份清单与hash核对见 `source-after.json`、`review-status.json` 和 `evidence-manifest.sha256`。
