# 版本、迁移与兼容入口

状态：拟实施规范；没有执行迁移、修改产品或更新任何客户项目。实施基线 `af9fd7a6b4d08f753d2f16536a03f386384f49d2`；本文件与 [CONTRACTS.md](CONTRACTS.md) 共同约束新写入路径。

## 1. 当前合同与必须保持的事实

当前 `document.v1.schema.json` 和 `task.v1.schema.json` 都禁止未声明字段；Document 的 compatibility 只接受 `workbench.v3` 和现有 minimum_writer 枚举，最高为 `workbench-quality.v1`。因此新字段不能仅靠“Host 多写一些 JSON”部署，必须同时修改 schema、语义校验、writer rank、所有适配器和安装资源。

当前 CLI 的可选 `--project-format` 与 Studio 强制 workbench.v3 存在差异；新建默认统一，但不把旧项目字节改写为新合同。来源：[CLI 参数](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/cli.py#L108-L109)、[Studio create](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/registry.py#L118-L136)、[writer ranks/语义校验](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/models.py#L262-L310)。

旧 `existing_decisions` 是上下文字符串，默认 `live` 有 `presentation_mode_source=default` 区分，历史 Review 有其原始身份标签。迁移不得给它们补造用户确认、委派、人类身份、已听众验证或新的主体 hash。

## 2. 格式与 writer 策略

1. 保留现有 Document/Page 版本与 `workbench.v3` 项目格式，追加 `minimum_writer=collaboration.v1`；在 `models.WRITER_RANK` 单调追加到现有最高 rank 之后。
2. 在 Document schema 显式加入 `collaboration`/Narrative Ref，在 Task schema 加 `collaboration_binding`，按 CONTRACTS §11 注册 Narrative/Plan v2、Decision/Authorization、compose v2、style v3、Review v2 和 Page 映射扩展。Review/Plan/Style 按 schema_version 分发读取，不能替换全局默认 validator 后令旧对象无法读取。语义校验要求新 writer 的新派发任务带有效 binding。
3. 当前旧 Document 可以无 collaboration 被新 reader 读取；当作 `legacy_unreconciled` 派生视图。该视图不是新存储状态，不自动落盘。
4. 所有新 create 均启用新 writer；旧 `--project-format` 参数可以保留用于识别/报错兼容，但不能创建可绕过协作控制的新项目。不能设置 `--legacy` 作为生产逃生门。
5. 新 Task 声明 `collaboration.v1` Host capability。支持旧 generation 协议但不支持协作 binding 的 Host 不能领取新任务；返回具体升级需求。只记录已有调用的 settle 兼容旧任务协议，不因此取得领取/接纳资格。旧运行时必须在未知 minimum writer 时拒写，不能剥离新字段。
6. 模型中多处手工列举 minimum_writer 的校验必须同步支持新 rank；优先改为比较 rank 的同一 helper，禁止文档能写入而 ContentPlan/candidate/change 校验因漏枚举失败。

## 3. 迁移入口与原子步骤

拟新增 `collaboration migration describe`（只读）与 `collaboration migration apply`（写入）；这些是设计名称，当前不可运行。

describe 必须给出当前 revision、格式、页/稿件/来源/现有 Review 数量、活动/在飞任务、unknown calls、可复用产物、待核对决定和新 writer 影响；同时返回拟变更的精确 plan digest。读取项目、浏览历史或普通诊断不得偷偷 apply。

用户请求继续、局部修改或导出时，Host 可先展示 describe 并在既有授权范围内执行必要且可逆的迁移，无须把技术升级另加成一次业务审批；但不得把“允许迁移”当成“批准方向/整套生产”。若没有任何写项目的用户意图，则保持只读。

apply 使用 `base_revision + plan_digest + operation_id`，在单个 Store lock/CAS 中：

1. 复核 plan 对应当前状态、最低 writer 可升级、无并发变化；幂等重放原结果。
2. 保留全部不可变 Page/来源/候选/蓝图/SVG/PPTX/Review Ref、历史操作收据和调用事实，生成一个新 Document revision。
3. 初始化唯一 collaboration 区域。旧决定字符串记录为历史上下文或 imported_unknown，不能创建 accepted direct_user 决定。未提供的 mode 仍标 default。
4. 新请求取自本次明确用户指令；无本次指令时 collaboration.request=null，不造执行请求/授权。若已有确认稿件，建立带来源边界的 imported mapping；保留稿件，不重新虚构 Narrative，也不把“导入成功”当作用户确认。
5. 把仍可运行但缺少新控制 binding 的旧任务标为 superseded；在飞调用只允许继续结算。晚到结果作为事实/隔离候选保留，不直接更新当前稿件。不得重新执行旧 operation ID。
6. 将 minimum writer 提升为 collaboration.v1，提交迁移收据，说明复用项、没有转移的权限及当前阻塞。随后普通 continue 根据新请求与新授权判定，不自动重做全套。

调用 unknown 事实不得在迁移中清零；仍阻塞新的外部调用，直到按现有协议解决。迁移不是修复当前业务主线的替代动作。

## 4. 历史项目可做什么

| 项目/操作 | 新版本行为 |
|---|---|
| 旧项目只读 show/history/preview/材料检查 | 直接读取，显示 legacy/unverified 证据边界，无隐式迁移 |
| 用户明确严格只读审查 | persistence=none；源项目不记录 request/Review/缓存/日志，不迁移；报告与渲染副本写项目外，外部文件无需创建生产项目 |
| 旧项目导出 review/engineering 副本 | 可以在现有文件完整性与输入一致性规则内导出，明确 purpose/证据等级；不能标正式交付已批准 |
| 旧项目正式 delivery | 先按统一 delivery 谓词判断当前控制；缺 collaboration 时返回 migration/reconciliation 要求，不走旧 gate 放行 |
| 旧项目继续生产、任务领取/新调用/修改/采用候选 | 要求 apply 后的新请求/binding；任一直连 CLI/HTTP 入口同样阻塞 |
| 旧的已完成 operation 重放 | 只返回原历史收据；当前 readiness 与后续动作重新计算，不借历史成功取得当前授权 |
| 新 writer 项目使用旧 Runtime/CLI | 拒绝所有写入，提示最低 writer；不降级、不丢字段 |
| 旧快照 restore | 内容恢复到新 revision；当前 request/授权撤回/暂停/调用账本/minimum writer 保持，旧权限不复活 |

对新控制下的历史 artifact 做正式交付，取“历史 artifact snapshot + 当前 control snapshot”。旧快照里较松的 policy、旧授权或旧 human 标签不得覆盖当前政策。撤回后重复选择更早 revision 也不能重新放行。

## 5. 部署顺序与回退

1. 独立修复 professional review 谓词及 delivery 各入口一致性；既有错误正例改成显式 reviewer fixture。该修复不能等待全部协作合同落地。
2. 先实现 reader/schema/语义校验/只读 eligibility 和迁移 describe；以固定 fixture 对照现状，不改生产项目。
3. 实现 writer/迁移 apply 与每个突变入口的 enforcement；在尚未全部覆盖时，不向真实项目启用新 writer 的生产。开发期 shadow 只能用于诊断，不得宣称不可旁路。
4. 实现统一 create、四 Skill 路由、Studio/CLI/Chat 投影与 capability 协商；方法、合同、任务索引、Skill 安装清单同批发布。
5. 跑分层验收；真实 Host、内容效果、视觉效果与工程均达到各自标准后再讨论发布。CI pass 不自动触发安装/客户运行。

回退软件可保留只读访问，不能使用旧 writer 继续写新项目；不能通过 restore 降低 minimum writer。若实现失败，保留当前项目与调用事实，修复或使用支持新合同的恢复工具。全量备份另行作为用户可选择的文件恢复，不声称可以防止具有文件权限的人手工操作旧副本。

## 6. 必须通过的迁移验证

这些验证尚未执行，**需要 Codex 核验**：

* 新建 CLI/Studio/聊天同输入产出相同格式、authority 默认与缺口；遗漏 `--project-format` 不绕过。
* 新 reader 读取基线格式和 workbench.v3 fixture 不改任何字节；真实 apply 只新增 revision 与控制对象，旧 Page/artifact hash 保持。
* 历史 accepted-looking 字符串、默认 live、host_self 的 professional_use/pass、PPT-only not_evaluated 都不升级成新批准或人类证据。
* 有/无 Page、已有确认稿件、无 ContentPlan、进行中 Task、reserved/in-flight/unknown 调用、旧候选和历史输出各有 fixture。
* apply 的 crash/retry/CAS 冲突不重复迁移或重复调用；旧在飞结果只结算，不能采用。
* 所有旧项目写入口都触发相同 migration-required；不能通过 import_draft、task start、call begin、candidate adopt、style expand、compile 或手选旧 revision 绕过。
* 升级后的旧任务不被 continue 自动重建为整套生产；只在新的明确范围内创建新任务。
* restore 后 minimum writer、当前撤回/暂停/费用不回退；历史 delivery 仍用当前 control。
* 有明确双版本请求时，顺序子请求复用 Narrative、各自冻结 Plan/Page/output/revision；第二份修改不改变第一份 manifest 的字节事实，当前撤回/语义变化仍重新评估两份交付；不能自动多做第三份。
* 原项目新增/替换请求统一经 start_request；同一来源换 operation ID 不刷新 request/预算。明确同步可用图稿的局改按必要重绘页各 1 次、重试 0；只改字/稿件范围仍为零图像额度。
* 安装后的 skill/method/schema 与指定 release SHA/digest 一致；本地源码测试通过不能冒充用户安装版本已更新。

基线的 Store 已拒绝降级最低 writer，并把权威收据保存在已提交 Document 链；迁移应利用该机制：[Store 提交边界](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/store.py#L339-L404)。
