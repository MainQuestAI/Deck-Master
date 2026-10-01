# 两线接口合同

本文件中的“拟增”是本轮约定、尚未实现。实施以 `src/deck_master/resources/contracts/` 为唯一活动schema来源；A不得假定存在这些字段。所有新读响应都保留旧字段；新写行为显式能力协商，不能静默降级。

## 复用现有接口

| 用途 | 已有HTTP面 | 实施原则 |
|---|---|---|
| 当前/固定版本 | GET /api/view、/api/workbench、/api/view/summary、/api/pages/{id}，revision参数 | 读模式current/fixed；固定比较不被轮询换版 |
| 输入/大纲/来源 | GET /api/inputs、/api/content-plan、/api/content/sources/{id}、/api/content/lineage/{id} | 真实来源引用；旧页推导明确标记 |
| 草稿/读位 | /api/drafts、/api/ui-state、/api/gallery | 独立UI journal，不驱动业务revision |
| 修改/操作恢复 | POST /api/annotations/batch、/api/changes/plan、/api/changes/commit；GET /api/operations/{id}、/api/changes/{id}/handoff | 同页意见保留独立选区；operation原ID查询与重放 |
| 内容结构/材料 | POST /api/content/plan、/api/content/commit、/api/content/inputs、/api/inputs/update | 共享content_ops/service，不新造上传成功即读取事实 |
| 候选 | GET /api/candidates、/api/candidates/{id}；POST /api/candidates/plan、/api/candidates/adopt | 保留原图/SVG能力；新增正文时按result类型渲染 |
| 风格 | GET /api/styles；POST /api/styles/propose、/api/styles/confirm、/api/styles/plan | 固定参考和单页验证后扩选 |
| 历史/导出 | GET /api/history、/api/export-facts、/api/exports/{id}/…；POST /api/history/plan-restore、/api/history/commit-restore、/api/exports | 冻结版本，下载复用export ID；delivery仍由共享检查门禁 |

具体请求字段沿用当前web.py/service函数签名；上述表不是另一个全量API定义。原有三用途、指定版本和恢复已实现，不重复建设。

## B01：summary增补合同

先修 `candidates` 分支：无记录仍为 `{status:not_recorded}`；有记录合法返回 `{status:recorded,count:N}`。保留v1旧字段；新增可选结构并提供能力名 `workbench_actions.v1`，旧UI忽略新增字段，旧核心缺字段时新UI显示读模式引导。

拟增每页 `prompt_summary`：`prepared`、`frozen`、`submitted`分别给出status及ref，允许not_recorded/unreadable；`submitted.observer`沿实际证据，不由配置推断。摘要只读索引/元数据，不展开prompt正文。不存在冻结记录不能用草稿补全。

拟增 `attention.items[]` / 顶层 `next_actions[]`：`action_id`、`kind`、`page_ids`、`layer`、`reason_code`、`source_refs`、`enabled`、`blocked_reason`、`revision_id`。状态derived/unknown区别；action_id由事实身份+kind稳定产生。只返回允许的动作种类，前端本地映射路线，不执行后端任意URL或命令。

排序：保存未知/冲突等需先解决的恢复事项（个人journal由A另并列展示，不注入业务真相）→待交接handoff（主执行回路步骤，先于重做类事项）→明确失败→待决候选→未协调输入→缺层/依据已变→一般阅读。超时/长时间运行中归入恢复层（与run_desk.task_row判定一致）。服务无专业记录时不生成“风格偏离”；质量不明是未判断。候选count保留总数，另增pending_count排除adopted/keep_current，引用决定事实。没有可执行动作时给原因与可读位置。

## B02：有效能力与主入口（已实施，切片见 evidence/b02-slice.json）

保留 `/api/health.ui_capabilities` 作为server支持（单一常量 `web.UI_CAPABILITIES`）。`/api/project` 已增 `effective_actions`，每项 `action`、`supported`、`writable`、`reason_code`；响应同时携带 `project_format`、`minimum_writer`、`core_readers`、`core_writers`。动作族：`drafts`（个人journal，无需workbench.v3）、`annotations/changes/content/styles`（镜像各自服务的真实 workbench.v3 门槛，v1 格式禁用）、`candidates/inputs/run_desk/exports/restoration`（写路径当前无格式门，投影如实报告可写；端点补门缺口见 GAP-MATRIX G54，归 B07）。`reason_code` 是投影词汇表而非写端点的 error envelope 码（`sample_readonly` 与真实 403 码一致，其余为投影描述）。指针级不可读（未来format/writer）时返回降级载荷：`read_status.reason_code` + 全部动作禁用，不使 /api/project 整体失败。历史视图由A根据fixed模式进一步禁写（`fixed_revision` 由前端按route组合，服务端不产生）；服务写接口仍独立验证，不信任前端disabled。

行为原因覆盖 `unsupported_project_format`、`reader_upgrade_required`、`writer_upgrade_required`、`sample_readonly`、`fixed_revision`；除 `sample_readonly` 对应真实 403 码外，其余为投影词汇表（真实写拒绝仍以其服务层 envelope 码为准）。`deck-master view --project … --open --ui v2` 已实施（`--ui` 不带 `--open` 报 invalid_input/退出码2；选项非法退出码2）；既有不带--ui行为保留；workbench现有入口复用，不固定端口，Skill 指向显式新入口。

## B03：Page/内容变更集候选与Task结果

拟增能力 `content_candidate.v1`。changes intent=content + mode=trial允许进入，目标必须有固定page_ref/基准/input依据。使用Task既有compose/content_update能力承载，新增候选结果处理分支；模型结果只能包含所请求页与字段。此处需修改Task契约和结果写入，明确属于B范围。

候选采用可判别联合：现有Artifact分支保持兼容，Page分支给 `result_kind:page`、`stage:content`、不可变 `result_ref`（deck_page_package.v2）、target_ref=基准Page；`request_ref`指对应冻结内容请求，不假填图像GenerationRequest或Attempt。读取show提供 `page`，不得要求artifact.file。采用前验证Task已提交、结果可达、page_id/范围与basis匹配；返回后只记录候选，采用时才更换当前Page。

复用content_update的局部更新/版本失效算法，不能复制一套失效服务。结构及材料影响仍经content_ops/inputs分派，但本轮显式trial新增 `result_kind:content_update` 分支：候选固定完整content_update、ContentPlan、输入摘要与受影响页引用。Host结果接受只记录候选，采用才执行变更集。新输入登记可以进入待协调，不能提前改正文/页序或宣称对齐。单页Page分支可复用同一变更集执行器，不建立第二套内容更新代码。采用plan展示新旧页面映射、保留/移除、新ID派生关系、页序、相关任务取消与下游失效；取消/保留当前不改稿。一个变更集原子采用，重叠候选或不一致页序不能混批。只改一个页的候选可按精确scope检测并发；涉及完整页序/大纲/输入的变更集使用固定basis并拒绝相关并发变化。既有auto content_update命令保持其原语义，新UI必须显式请求trial，旧Host不支持时提前拒绝。新能力旧writer不支持时拒绝调用，并记录所需版本；旧图像/SVG候选可照常读取。新增合约不将任意磁盘Page文件当合法候选。

## A04 补充（评审 P1-1）：ui-position.v1 的 layer 枚举新增 `source`（六段制作链第一段），镜像同步至 deck-master-workbench-v3/contracts；个人阅读位置在来源层照常保存。

## B04：候选决定

【终审修正 2026-10-01】G54 收口终态：candidates 属 FORMAT_GATED（投影 reason=unsupported_project_format），服务层 candidates.plan/adopt/decide 首行 `_require_workbench` 强制（CLI 与 HTTP 同源；web.py 仅留防御副本）；stages.assemble 维持服务层既有 stage_format_required（不经 web 门，避免遮蔽精确错误码）。已知粒度限制：run_desk 族混合 /api/feedback（v1 合法）与 v3-only assemble，族级投影无法区分，记为 G54 后续。

拟增 POST `/api/candidates/decision`（对应单一CLI子命令 `deck-master candidates decision`；实施前按现有CLI树核对命名并同步help）。输入：`operation_id, base_revision, candidate_id, decision=keep_current|reopen, expected_decision_ref`。同源session与既有Origin校验；Host/脚本经CLI调用共享服务。

决定写入不可变对象，并在Document记录引用；与operation结果同事务。输出 `decision_ref, candidate_id, status, revision_id`。候选本身及当前产物不改变。show/list投影加decision及pending状态；adopted历史记录不删除。重开不自动采用，基准变更仍阻断旧plan。expected_decision_ref冲突返回409及当前决定引用，重复operation返回原结果，跨项目候选404。状态命名应映射现有OperationError而不是吞掉异常。

决定记录合同 `candidate-decision.v1`（Document新增可选数组 `candidate_decisions`，引用不可变对象；镜像同步至 deck-master-workbench-v3/contracts）。workbench summary 的 candidates 块新增 `kept_count`（required，recorded 分支）：pending_count=count−adopted−kept；已采用候选的决定历史不影响 adopted_count。show/list 的候选投影新增 `decision`（state/decision_ref/decided_at）与 `pending`；已采用候选 `pending` 恒 false。keep_current 与 reopen 幂等：重复同向决定返回 `unchanged` 不新增修订。终审补丁 P1 后契约——两种终态信封：`committed` 表示产生并记录业务提交（operations 信封，携带修订号）；`unchanged` 表示本次无业务变更（committed_revision_id=null，不新增修订），但回包仍携带与请求一致的 operation_id 与 request_digest，前端按同一身份校验视为终态并清除收据。同向重复提交丢包后，经 `operations show`（not_found → 重放原请求）收口，不产生新修订。legacy 兼容：升级前以 `candidates.decision`（旧 action）冻结的待核实记录，恢复/核实/重放经 `receipt-verdict.js` 的 LEGACY_ACTIONS 映射与按规范 kind 的摘要重算识别（终审补丁 P2）。

## B05：个人状态清理

拟增 POST `/api/ui-state/plan-clear`、`/api/ui-state/commit-clear`。plan输入明确scope=current_project、所选draft_id列表或全部草稿、是否reading_preferences；返回plan_id/manifest_digest、每项etag、恢复备份ref、阻断项。commit输入operation_id、plan_id、manifest_digest及确认范围。仅删除计划已确认的UI对象；清理事务日志放个人journal，不进入Document业务revision。

服务先完成恢复备份再接受commit；存在business operation未确认保存时拒绝清理其关联记录。新草稿/etag变更返回409，不扩大删除范围。清理失败/重放可查询同操作结果。原型“清项目记录/任务/候选”的描述不进入正式产品。接口不用于清理registry、项目目录、调用账或安装。

合同 `ui-clear-plan.v1`（只读投影：items/blockers/kept_out/manifest_digest/plan_id/backup_ref）与 `ui-clear-result.v1`（个人journal事务记录，镜像同步至 deck-master-workbench-v3/contracts）。blocked 草稿按 operations.committed_record 判定；显式点名 blocked 草稿时 plan 直接拒绝。commit 顶层参数 operation_id/plan_id/manifest_digest + input(scope/draft_ids/reading_preferences)；删除前逐项 etag 复核，备份失败或任一 etag 变化即整体 409 不删。幂等日志 `.deckmaster/workbench/clear-log.jsonl`，备份位于 `.deckmaster/workbench/clear-backups/<manifest16>.json`。CLI：`deck-master ui plan-clear / commit-clear`。备份落盘合同 `ui-clear-backup.v1`（写入前校验，A07 恢复入口消费）。输入仅接受 project_id/scope/draft_ids/reading_preferences 四键，未知键拒绝；`draft_ids: []` 合法=只清阅读设置；重复 draft_ids 拒绝。commit 在 verify→备份→删除全程按固定顺序持有 drafts/journal.lock、gallery.lock、position.lock 三锁，与三类保存方互斥；clear-log.jsonl 残行按缺失隔离。

## B06：保持约束

在现有style recipe/request内明确selected_dimensions与preserve_dimensions、目标事实引用和固定参考。核心可验证身份/范围/内容字段；视觉构图是否退化需实际阅图，不能写成自动可判定承诺。扩选仍由用户明确确认目标与预算，不靠单页task completed自动执行整稿。

实施（2026-10-01）：style_proposal.v1/style_recipe.v1 新增可选 `preserve_dimensions`（键限定 palette/typography/density/lines/composition，值为保持说明），由 propose 按 DIMENSIONS 全集与所选 dimensions 差集投影，随 recipe 可追溯并进入 instruction（明确保持维度：沿用目标页，不向参考看齐）；dimensions 键做范围校验（未知维度拒绝）。镜像同步至 deck-master-workbench-v3/contracts。AC02 真实制作闭环与 AC03 30 页真实项目保持外部待验（引用 W07/W08 证据，不合成关闭）。

## 合同交付与同步

B每卡先提交schema/服务/CLI/HTTP及兼容用例，独立复核进入main后A同步消费。例子必须来自临时真实服务回包，不写假revision/hash为成功示例；提案示意值只可出现在此规范。按既有退出码与error envelope，覆盖鉴权、旧项目、未知字段/能力、不合法引用、幂等、CAS、cancel/late以及partial read。
