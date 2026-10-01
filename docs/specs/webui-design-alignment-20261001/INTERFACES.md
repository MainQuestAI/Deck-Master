# Web UI 开发接口

活动 schema 位于 `src/deck_master/resources/contracts/`。本文件先冻结 U01 的读取与导航范围；后续包追加自己的接口，不改变历史合同。

## U01：action_targets.v1

新增 server 能力 `action_targets.v1` 与只读 `GET /api/actions/{action_id}/targets?revision={revision_id}&limit=30&offset=0`。必须提供唯一非空 revision；limit 为 1–100，offset 为非负整数，未知/重复参数拒绝。action_id 来自同一版本的 next_actions 或逐页 attention；未知、已变化或跨项目 action 返回 404 `action_not_found`，不回退到首项。目标存在于固定 snapshot，不使用当前对象补齐历史。

响应 `schema_version=action_targets.v1`、project_id、revision_id、action_id、total、limit、offset、targets。targets 项显式给 kind（task/page_layer/candidate/content_changeset/content_reconciliation/review）、page_ids、layer、object_id、status、enabled、blocked_reason。object_id 为真实业务身份；不可读对象的身份未知时为 null，仍保留成员并解释阻断。ID 绝不从对象 hash 推断。

summary 保持原合同与体积：动作成员关联只在组装读取时内部保存，端点按相同事实解析聚合与逐页动作。相同对象去重，顺序稳定；解析不读取全部历史、不写 Document、不派发任务。当前 summary 中的时钟超时提示可能在固定版本消失，解析失败必须明确告知并保留所看版本。

前端：一个可读目标直接打开，多目标进入固定版本的目标列表，按页码/层/状态区分，分页读取。不可靠目标不提供可执行跳转。task → runs + task；page_layer/candidate → page + page/layer/candidate；content_changeset → content + candidate（整稿比较，不能假填 page）；reconciliation → content；review → runs + review。

URL 新增 action、review 参数；action 仅允许 overview，review 仅允许 runs，content 上的 candidate 为整稿变更集比较。所有这些对象链接必须含 revision，保留 project 身份校验。跳转其它工作面时清除不相关的对象参数。个人 ui_position.v1 仍只保存已有阅读位置字段，不把临时动作列表、候选或 review 对象塞入旧严格 schema。

缺少 action_targets.v1 的核心使用明确标为通用入口的旧路线；多对象不假称精确定位。候选及变更集详情读取继续复用 `/api/candidates/{id}?revision=...`；正文按 result_kind 分型，固定基准左侧、变更集新稿右侧。U01 比较为只读，采用仍从既有候选计划/提交路径完成。
