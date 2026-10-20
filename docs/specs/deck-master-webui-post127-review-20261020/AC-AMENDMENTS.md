# 原 AC 的最小补充（待原包逐条合入）

不增加卡、不重编号、不改 9 卡/50 AC 总量。以下编号仅转交已明确的原 AC；未给出的 owner/编号待读取 TASKS 与 traceability，不能杜撰。

| 修订 | 原 AC | 必须补入的断言 |
|---|---|---|
| R1 | 原方向决定/采用 AC，编号待原包 | 无决定可记录但不可采用；有效覆盖决定复用；两种策略拒绝独立；决定成功采用失败不丢失前一事实；两个事务 CAS/UUID 分开；unknown 先查询，不重复记录。 |
| R2 | AC39、AC41、AC43 | 无新阶段/已有 frozen Task 仍可 HTTP 200 浏览；dispatch_status=cannot_dispatch 与原因完整；preparation_only 恒 true；400/404/409 basis_conflict/503 与局部 partial 区别；GET 前后 Document、Task、calls、writer floor 不变。 |
| R3 | AC16 | 零 Page 可读 Narrative 与 planned_roles，page_ref=null；current Plan 只服务其确切 Narrative；两个方向分别关联不同固定 Plan；缺失/不可读 Plan 不回退到另一方。 |
| R4 | AC18 | current+candidate 可比较；两不同 proposal 非必要；同 Ref、不可读、非法/不可达 Ref 拒绝；历史比较不提供写动作，不随后台结果漂移。 |
| R5 | AC27、AC28 | 固定 Review 的非首条 finding 经刷新/返回/筛选/排序仍是同一 source_index；相同 finding_id 在不同 Ref 不混淆；缺 ID 的合法适配用索引；越界、Ref/revision 不匹配不默认首项。 |
| R6 | AC08 | schema 正例：readable=true+真实 data，false+null+error；负例：false+伪造业务字段、true+null、不可读 Review 强制非空；损坏对象保持局部错误并禁止采用。 |

本轮只做源码阅读和文档设计，无以上产品测试执行证据。不得以 JSON 可解析或文档差异检查代表 50 AC 通过。
