# 09｜目标数据契约、接口与迁移规则

## 9.1 契约地位

`contracts/` 是本轮新/升级对象的正式设计草案，不是已经进入当前仓库的 schema。开发时先与 `docs/contracts/`、Skill schemas、运行时 validator 和上游 handback 做 diff，再统一落库。不得将本包样例混成生产输入。

所有新对象具备 schema_version 与 run_id；有内容结果的对象绑定输入版本。路径必须是 Run 内安全相对路径，或在内部来源注册表中的受控句柄。公开报告不得包含未脱敏源目录。

## 9.2 本包提供的六份 Schema

| Schema | 文件/用途 | 权威地位 |
|---|---|---|
| `deck_capability_execution_plan.v1` | `workflow/capability_execution_plan.json` | Runtime 可重算任务投影，不管理审批 |
| `deck_context_pack.v2` | 导入结果，规范化到 context_manifest | 原始来源、精确片段、覆盖和研究承接 |
| `deck_research_task.v1` | 阶段内研究任务 | 操作任务，结果仍回 Context Pack |
| `deck_solution_model.v1` | `solution_model.json` | 唯一方案结构与设计依据对象 |
| `deck_diagram_view.v1` | `diagram_views/<view_id>.json` | 方案模型的派生视图 |
| `deck_external_quality_review.v2` | 既有审查结果导入 | 当前内容的专业审查记录 |

Schema 的结构校验不代替跨对象引用、文件真实性和语义审查。自检脚本覆盖结构与少量样例关系；完整业务验证必须由 Codex 实现。

## 9.3 既有对象扩展，不另建平行对象

| 既有对象 | 本轮扩展 | 兼容策略 |
|---|---|---|
| request | quality_profile、library_mode none、研究策略、授权/预算引用、任务类型 | 老 Run 读原策略；新 SC-1 Run 固定新策略，不可静默降级 |
| context_manifest | 保留 v1 字段，增加来源版本/位置/coverage/冲突 | Context Pack v1/v2 均可导入；未知位置不自动补造 |
| consulting_judgments | statement、rationale、source/claim refs、类型、review_status | 规则结果标 scaffold；未审计数不转成 supported |
| claim graph | evidence key 消歧、support/contradict、claim_type、计算与设计依据 | 裸 ID 映射不唯一则阻断；保留旧版本读入 |
| narrative_plan | 目标 v3：solution_ref、候选/选择、issue_tree、page_jobs 与依赖 | 原 v2 可读；新写统一；MBB 仅为新 Run 的兼容投影 |
| page_tasks | 从 narrative v3 派生，保存稳定 page/claim/view refs | 不独立维护另一份页面顺序 |
| page_package | solution/view refs、typed content、data derivation、quality intent | 先核对 additionalProperties 与现有 dataclass；必要时正式升版，不能悄悄丢字段 |
| external review/gate | v2 的 action、input hashes、covered_refs、observations | v1 可读但不自动满足新正式语义审查 |
| learning pack | 去重反馈统计、sample_count、pattern cards/适用边界 | 老 approval_rate 不参与新排名；不保留第二套反馈真相 |
| stage-contracts/decision | 答案 authority/schema、typed trigger、依赖与复用引用 | 旧 Run 保留原策略；新 Run 显式启用新规则 |
| capability lock / suite status | 托管组件 provenance、真实 smoke；分层 readiness | 旧 readiness 不能悄悄改含义；新增 task_ready 投影 |

Q0 必须把所有 exact version、别名和读写路径冻结到实现对照表。表中“目标 v3”若与最新仓库已有版本冲突，可递增版本，但语义与兼容要求不变。

## 9.4 通用引用与支持规则

引用键：source 使用 source_id；证据使用 source_id#evidence_id；方案对象使用其 id；页面使用稳定 page_id；来源/模型/产物使用内容 hash 绑定版本。禁止依据数组序号生成业务身份。

设计模型中的 existing 组件须有证据；proposed 组件须有需求或问题绑定与 reasoning。图形 edge 的 relation_ref 必须存在且端点一致。每个模型节点/关系改动产生依赖影响。受控布局装饰无需造假 evidence；业务标签和数字仍受内容规则约束。

字串出现在来源中，只证明出现，不证明主张受到支持。支持关系需 reviewed 状态与审查观察。派生数字用受限可复算表达式/实现，不 eval 来自材料的任意代码。

## 9.5 接口清单：现有与拟扩展严格区分

以下新参数/新命令属于目标 API，当前不可假定可运行。Q0 检查 parser 命名后统一文档、Skill、测试与 `--help`。

| 操作 | 现有承接 | 本轮目标扩展 |
|---|---|---|
| 托管安装 | setup / suite-install / release install 现有链 | 在现有安装入口增加 managed 选项并作为完整安装默认；不要新建另一套 installer |
| 状态 | setup-status / suite-status / agent-doctor | 根据 run/task 生成 execution plan；新增任务 readiness，不改旧字段语义 |
| 材料接入 | start-conversation / import-context-pack / build-brief | 混合材料、v2 Context Pack、生产返回 Agent 提炼任务 |
| 自动规划 | autoplan | `--planning-mode solution_core_v1`，生成/消费当前 solution 和 narrative，禁止生产模板冒充完成 |
| 资产检索 | search-library | 新 `--library-mode none`，明确不请求检索，仍形成完整 sourcing |
| 阶段内任务导入 | 既有 handoff/结果 import | 新 `workflow action accept --run-dir <r> --action-id <id> --input <result> --expected-input-fingerprint <hash>` |
| 变更影响 | 既有 freshness/lineage | 新只读 `workflow impact --run-dir <r> --changed-ref <ref>`，输出受影响对象与授权边界 |
| 页面生成/构建 | generation-session import-results；build prepare/run/status/retry | 保留标准/high-density 命令；输入统一到当前 Page Package |
| 审查 | prepare-quality-review / import-quality-review | 支持 v2，范围/哈希/coverage/独立性；既有 Gate 名称统一映射 |
| 推进 | workflow autopilot / next-step | 可执行 Agent 动作不停在无意义“继续”点 |
| 交付 | final-readiness / export | 当前语义/证据门与批准绑定；客户投影全文件扫描 |

新增 action import 的 payload 通过 action.expected_schema 选择适配器，不能任意写输入指定的文件路径。Runtime 决定允许输出路径，结果仅提交 schema 内数据与允许资产。

## 9.6 公共错误代码（目标，和既有代码映射）

`SC_CAPABILITY_MISSING`：缺本次必需能力；`SC_SOURCE_PARTIALLY_READ`：关键区域未读；`SC_SOURCE_CONFLICT`：关键材料冲突；`SC_RESEARCH_UNAVAILABLE`：必需研究未执行；`SC_EVIDENCE_UNSUPPORTED`：关键事实未获支持；`SC_SOLUTION_INCOMPLETE`：问题/机制/验收关系不完整；`SC_VIEW_MODEL_MISMATCH`：视图与方案不一致；`SC_ACTION_STALE`：旧结果；`SC_ACTION_SCOPE_EXCEEDED`：越权范围；`SC_REVIEW_COVERAGE_MISSING`：审查缺页/缺维度；`SC_REPAIR_BUDGET_EXHAUSTED`：预算耗尽；`SC_APPROVAL_STALE`：批准非当前版本。

错误结果必须包含相关 ref、原因、可执行恢复动作和是否确实需要用户。不得返回“请完善所有资料”这类不可操作的统一提示。
