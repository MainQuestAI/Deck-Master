# Web UI 开发接口

活动 schema 位于 `src/deck_master/resources/contracts/`。本文件先冻结 U01 的读取与导航范围；后续包追加自己的接口，不改变历史合同。

## U01：action_targets.v1

新增 server 能力 `action_targets.v1` 与只读 `GET /api/actions/{action_id}/targets?revision={revision_id}&limit=30&offset=0`。必须提供唯一非空 revision；limit 为 1–100，offset 为非负整数，未知/重复参数拒绝。action_id 来自同一版本的 next_actions 或逐页 attention；未知、已变化或跨项目 action 返回 404 `action_not_found`，不回退到首项。目标存在于固定 snapshot，不使用当前对象补齐历史。

响应 `schema_version=action_targets.v1`、project_id、revision_id、action_id、total、limit、offset、targets。targets 项显式给 kind（task/page_layer/candidate/content_changeset/content_reconciliation/review）、page_ids、layer、object_id、status、enabled、blocked_reason。object_id 为真实业务身份；不可读对象的身份未知时为 null，仍保留成员并解释阻断。ID 绝不从对象 hash 推断。

summary 保持原合同与体积：动作成员关联只在组装读取时内部保存，端点按相同事实解析聚合与逐页动作。相同对象去重，顺序稳定；解析不读取全部历史、不写 Document、不派发任务。当前 summary 中的时钟超时提示可能在固定版本消失，解析失败必须明确告知并保留所看版本。

前端：一个可读目标直接打开，多目标进入固定版本的目标列表，按页码/层/状态区分，分页读取。不可靠目标不提供可执行跳转。task → runs + task；page_layer/candidate → page + page/layer/candidate；content_changeset → content + candidate（整稿比较，不能假填 page）；reconciliation → content；review → runs + review。

URL 新增 action、review 参数；action 仅允许 overview，review 仅允许 runs，content 上的 candidate 为整稿变更集比较。所有这些对象链接必须含 revision，保留 project 身份校验。跳转其它工作面时清除不相关的对象参数。个人 ui_position.v1 仍只保存已有阅读位置字段，不把临时动作列表、候选或 review 对象塞入旧严格 schema。

缺少 action_targets.v1 的核心使用明确标为通用入口的旧路线；多对象不假称精确定位。候选及变更集详情读取继续复用 `/api/candidates/{id}?revision=...`；正文按 result_kind 分型，固定基准左侧、变更集新稿右侧。U01 比较为只读，采用仍从既有候选计划/提交路径完成。

## U02：按动作选择与批量试作

不新增业务接口。原图试作、SVG 重建/修复复用 `change_intent.v1` 的 trial / targets / stage / references / max_calls，经 `/api/changes/plan` 和 BusinessOperations 的 changes.commit 交接。原图每页需要一次已批准调用；SVG 请求固定为零图像调用。计划显示服务实际范围和下游失效，不以浏览器选页代替服务端校验。

总览选择动作后才判断可操作页：有效动作族、当前版本/只读、内容引用、原图或 SVG 必需输入、未知任务/调用、未确认业务或个人保存。needsWork 仅影响筛选。动作改变保留当前勾选并列出不适用项；必须明确移除受限页或取消勾选才能预览，不能静默缩减。筛选、搜索、输入、参考、预算或版本变化使旧预览失效。

总览勾选和未提交预览仅保留在当前工作面内存，不存进偏好或草稿。提交只冻结已确认计划到现有收据协议，响应丢失仍核实/重放同一 operation_id。刷新不重派任务。

风格交接复用 app.styleSelection，但携带 project_identity、revision、target_refs、target_ids、可选固定 reference 和原样短要求。到达时校验身份/版本/内容引用并消费一次；仍由用户确认参考、风格版本、单页试作与采用后扩展。参考同时在目标中时必须明确调整，不自动删除目标。既有风格业务草稿的恢复保持其原协议，不把它当作总览偏好。

## U03：总览阅读偏好与清理屏障

新增 `ui_overview.v1` capability / 活动 schema；严格只含项目身份、固定 revision_id、search（最多 200 字符）、filter（all/todo）、sort（ascending/descending）。GET `/api/overview?revision=...` 返回该版本记录、整个偏好文件 CAS etag 与保留问题；POST `/api/overview` 接受 state 和 expected_etag。个人文件最多保留 12 个阅读版本，按明确修改顺序淘汰，轮询不产生偏好历史。

恢复采用显式有效 URL 的 q/filter/sort → 此项目此固定版本的已保存偏好 → 默认值。离开、刷新恢复不恢复批量勾选、计划或 operation_id。无 capability 使用当前窗口会话态，读写失败保留输入，冲突须明确选择项目保存稿或此窗口稿后再保存；结果未知先按原内容/etag 核实。

清理 reading_preferences 覆盖 `overview_preferences`，纳入计划、同 etag 复核、原记录备份和日志。清理持有 overview.lock，并保留空的 CAS 屏障；即使清理前尚无偏好记录，也写空屏障，阻止旧窗口延迟的 expected_etag=null 保存复活偏好。屏障不是阅读偏好，不计入下一次清理范围。损坏/外项目文件保留供恢复。清理不写 Document、任务、调用或业务收据。
