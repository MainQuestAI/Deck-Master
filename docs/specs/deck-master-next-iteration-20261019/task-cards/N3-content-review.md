# N3｜内容结构与审查方法派发一致性

## 1. 任务定位

| 项目 | 约定 |
|---|---|
| Spec 包版本 | v1.0 |
| 建议目标候选 | 1.0.0rc4；这是规划目标，不表示代码已经修改或版本已经发布 |
| 审查基线 | `main@a08bc68c1cbbbc806205104c2bb01f3f096305f0` |
| 本卡目标 | 让新 argument 提案满足明确的结构连通规则；让每次审查准确取得所需的方法，并保留旧任务的实际执行合同 |
| 主要 Owner | 内容合同与审查 Runtime 开发 Agent |
| 协作关系 | N4 消费本卡冻结的方法清单并优化读取投影；N6 在本卡规则明确后改进方法并实际应用；安装方法身份沿 N2 的安装流程核验；宿主桥接沿当前既有合同 |
| 修改边界 | 现有 Narrative 校验、Task 派发/接纳、方法解析、只读入口及对应测试；不新增内容数据库或独立工作流 |
| 验收编号 | AC-N3-01 ～ AC-N3-12 |

**事实边界：** 本卡根据固定基线的只读审查记录形成。实施开始时，当前 SHA、下述文件路径、函数签名、测试覆盖及重现结果均**需要 Codex 核验**。若 main 已前进，先记录与本卡基线的差异，再实施仍成立的部分；不得把计划行为写成已经具备的能力。

## 2. 问题与业务目标

审查记录包含两项可定位差异，实施时需要 Codex 核验：

1. `CONTRACTS.md` 要求 argument 具有中心节点和连通的论证/讲解结构，但 `models.validate_narrative_semantics` 目前只校验中心存在、引用完整等条件。合成正式路径曾将 `nodes=[n1, orphan]、central=n1、edges=[]` 接纳为 argument 提案，返回 `adopted=false`。本卡补的是成熟提案的结构检查，不把该记录解释为绕过独立前审或成功交付。
2. `deck-review/SKILL.md` 要求普通内容审查读取内容方法和浅稿校准，但普通/最终 Review Task 的方法清单与无 Task 入口存在缺项。有 Task 时，`read_skill_methods` 不会另外合并角色方法。本卡使书面职责、派发清单、实际返回字节和消费记录一致。

业务目标是让作者在交出方向提案前发现可机械定位的结构缺口，让独立审稿会话取得完整且适用的方法。源码检查仍不负责判断一句商业论断是否正确、一个案例是否足以证明结论；这些判断继续由适用的内容审查完成。

## 3. 输入与实施前核对

### 3.1 必读输入

下列路径为审查基线中的定位，实施前需要 Codex 核验：

| 输入 | 读取目的 |
|---|---|
| `AGENTS.md`、`docs/agent-task-index.md`、`docs/agent-recovery-playbook.md` | 确认唯一 Runtime、读写边界及恢复规则 |
| `docs/specs/deck-master-content-collaboration-v1.2/CONTRACTS.md` §11.1、§11.6 | Narrative 语义与前审合同 |
| 同目录 `ACCEPTANCE.md` §1.2 | 保留现有 F0–F3 定义；本卡不另立内容等级 |
| `src/deck_master/models.py`、`content_production.py` | 校验、argument 接纳及输入修订路径 |
| `src/deck_master/method_resources.py`、`service.py`、`tasks.py` | 方法选择、工作单、Task 身份及正式接纳 |
| `src/deck_master/content_review.py`、`external_review.py` | 适用审查单元与严格只读入口 |
| `src/deck_master/resources/contracts/narrative.v1.schema.json`、`task.v1.schema.json` | 现有对象、允许字段及兼容性 |
| 四个公开 `SKILL.md` 及 `skills/deck-master/references/` | 专业职责与唯一可编辑方法真源 |
| `tools/build_hook.py`、安装资源相关测试 | 确认新派发清单在安装版也能找到准确字节 |

### 3.2 开工输出

先在实施记录中给出当前 SHA、受影响入口、旧任务兼容方式，以及与 N4/N2 约定的接口。该记录是开发交接，不再建一套项目审批或内容状态机。没有发现路径变化时，直接进入开发。

## 4. Narrative 连通规则

### 4.1 适用范围

新规则标识为 `argument-connectivity.v1`，应用于明确携带该校验策略的新 Task：

- `compose.v2 / argument` 新提案接纳。
- 新的 `input_revision` 或正式内容修改中，实际写入 `maturity=argument` Narrative 的分支。
- 导入后明确转为新论证创作的任务；只按确认稿制作的 `imported_mapping` 不为本规则补造 Narrative。

不将新规则直接加入所有历史读取共用的无条件校验。旧对象读取、历史比较、已完成操作的幂等回执和旧 Task 的原合同保持可解释。新策略必须在派发时冻结，不能到接纳时凭当前包版本临时推定。

### 4.2 节点集合与中心

1. 参与连通判断的节点集合为本次 argument 的全部 `nodes`。在 argument 中保留的节点就属于该次论证/讲解结构，不能用未出现在 Page 上作为脱离主线的豁免理由。
2. `central_node_id` 必须存在。中心可以是解释命题、教学任务、研究问题或决策判断；不强制是商业推荐或 CTA。
3. 只有一个合法中心节点、没有边时，结构检查通过。`framing` 继续允许按现有合同没有中心或节点；其完成不等于 argument 已完成。
4. 一个节点是 hypothesis、inference、target，或存在诚实未知，不因缺少收益数字被拒绝。现有 reported_fact/calculation 的来源或 blocker 要求继续执行。

### 4.3 两类连接与方向

连通性采用**以中心为起点的弱连通检查**：构建仅供校验的无向邻接表，但不改变原始有向关系，不把所有边重写为指向中心。

| 关系输入 | 原始语义方向 | 连通检查处理 |
|---|---|---|
| `supports` | 支撑材料/理由 → 被支撑命题 | 加入无向邻接，原始方向保留 |
| `qualifies` | 限定 → 被限定命题 | 加入无向邻接，原始方向保留 |
| `challenges` | 异议/反例 → 被挑战命题 | 加入无向邻接，原始方向保留 |
| `explains` | 解释 → 被解释对象 | 加入无向邻接，原始方向保留 |
| `prerequisite` | 前提 → 依赖该前提的对象 | 加入无向邻接，原始方向保留 |
| `leads_to` | 前一步/条件 → 后一步/结果 | 加入无向邻接，原始方向保留 |
| `illustrates` | 案例/例子 → 被说明对象 | 加入无向邻接，原始方向保留 |

上表所有合法显式边都向校验邻接表加入双向邻接；原 `from_node_id / to_node_id / relation` 按输入原样保存。该表定义方法解释与测试样例的方向，不要求 Runtime 从自然语言自动证明方向正确。

对 `node.qualification_node_ids=[q]`，按“q 限定该 node”加入一条仅供结构检查的连接，语义方向为 `q → node`。这与显式 `q --qualifies--> node` 等价；两种表达同时出现时，邻接表去重，不写回补边，也不改变原对象 hash。由现有合同已经检查的引用有效性负责确保 q 存在。

`issues.affected_node_ids`、`alternatives.affected_node_ids`、共用来源、同属章节、相同标题和 source_links 都不是论证边，不能据此连接两个节点。自环不增加对其他节点的可达性。结构规则不新增“必须无环”或“所有节点必须沿有向边到达中心”的限制。

### 4.4 失败行为与作者修复

计算中心所属连通分量；若不能覆盖全部 nodes，返回可定位的校验错误：

```json
{
  "code": "narrative_disconnected",
  "path": "payload.narrative.nodes",
  "central_node_id": "n1",
  "unreachable_node_ids": ["orphan"],
  "policy": "argument-connectivity.v1"
}
```

沿用现有错误外壳和退出码；上例是本卡要求的错误信息，不授权另建错误协议。未接纳结果不得留下“已完成 Task”或改变当前 Narrative/Plan/Page。Stage 文件是否保留沿用现有失败保存规则。

错误提示说明：为相关材料补写真实支持/解释/限定关系；不相关内容从本次论证移出，必要时转为现有 issue 的待解决说明；不要为通过校验添加无意义边。模型前审仍审查主张、关系、推理和限定，结构通过不升级成内容 PASS。

## 5. 按范围派发 Review 方法

### 5.1 维度来源及公共规则

沿用现有 `Task.review_units[].kind`、前审 `required_units` 及已约定的只读审查范围。不得另造与现有 Review.kind 平行的内容等级或维度字典。

建议保持 `method_ids_for(kind, *, intent=None, phase=None)` 的现有调用兼容，增加可选 `review_units=None`。新 Task 派发时传入实际审查单元，方法清单由同一 selector 形成并冻结。有 Task 的读取始终以已派发清单为准。

### 5.2 选择矩阵

表中的名称全部指向 `skills/deck-master/references/<name>.md`。Review 方法先取所需集合的并集，再按唯一规范顺序 `source-reading → content-methods → content-examples → content-calibration → review-and-repair → physical-units` 过滤并去重；不能由入口、单元遍历顺序或集合实现决定 manifest 顺序。非 Review 方法保留原合同顺序；旧 Task 保留第 6 节的冻结 RC3 顺序。`collaboration-routing` 是入口说明，单独标记，不假装它是 Task 新增审查方法。

| Task intent / stage 或入口 | 实际审查范围 | 必需方法清单 |
|---|---|---|
| `review / preproduction`，新论证 | 当前 `required_units` 的 argument、page_copy、progression；适用时含 speech | source-reading、content-methods、content-examples、content-calibration、review-and-repair |
| `review / preproduction`，确认稿 fidelity | 现有 fidelity 所要求的 page_copy、progression | source-reading、content-methods、content-examples、content-calibration、review-and-repair；按确认稿范围核对，不重新要求新 Narrative |
| `review / final` 或无 Task 的明确内容审查 | content、argument、page_copy、progression 中任一项 | source-reading、content-methods、content-calibration、review-and-repair |
| 明确只审口播的外部/职责入口 | 仅 speech，核对口播完整性、与固定 Page 一致及约定用途 | content-methods、review-and-repair；若事实来源/上屏正文也在审查范围，再并入上一行 |
| `review / page_visual` | blueprint_content、blueprint_fidelity、readability | review-and-repair、physical-units |
| `review / final` 或明确只审视觉/转换/文件 | blueprint_content、blueprint_fidelity、conversion、readability、privacy 的实际子集；没有内容评审范围 | review-and-repair、physical-units |
| 最终六维审查 | content、blueprint_content、blueprint_fidelity、conversion、readability、privacy | source-reading、content-methods、content-calibration、review-and-repair、physical-units |
| 无 Task 的普通“审查这份稿/PPT”，尚未收窄维度 | 按原请求可合理覆盖的内容与成品检查 | source-reading、content-methods、content-calibration、review-and-repair、physical-units；明确范围后再准确投影 |
| `final-readiness` / `handoff-check` 的文件交接读取 | 查询实际 eligibility、未完成检查和文件身份 | 沿用 Runtime 事实；供 Host 解释结果时读 review-and-repair，涉及实际物理检查再读 physical-units。readiness 不新增为 Review.kind，也不创设独立专业 PASS |
| 非 Review 的 compose、blueprint、reconstruct、repair 等 | 保持本轮已约定的职责 | 原清单不因本表整体替换；发生本轮方法改动时按明确受影响的分支处理 |

新 Task 的 `review_units` 缺失时，从当前 Runtime 本来应执行的 stage / scope 推导实际单元，再选择方法；不得把未知当空范围以减少检查。显式非法或互相矛盾的单元按现有合同返回定位错误。未知自然语言不另添一轮固定访谈，由 Host 结合已知请求判断；方法 selector 不替用户扩大审查权限。

### 5.3 四类入口

- **named：** 直接调用 Review 时，根据实际要求选方法。没有 Task 时也必须能获得 calibration；严格只读不为取得清单而创建项目或 Task。
- **natural：** 保留原始文本，角色建议不等于执行授权；方法按最终已确认的职责范围选择，不因为关键词只出现“视觉”就丢掉明确要求的内容审查。
- **Master handoff：** 传同一项目、Task、scope、固定对象和清单，不加载另一套角色默认方法覆盖 Task。
- **recovery：** 重读当前 scope/control 和原 Task 合同；原清单优先。换会话或安装后，要么准确重读原方法，要么按第 6 节处理差异。

本卡可以修正 Skill 中方法读取说明，使其准确描述上表；不得通过删除 canonical 内容方法或降低浅稿标准来制造“清单已经一致”。N6 的实质方法改善单独保留变更理由。

## 6. 对象、版本和旧任务兼容

### 6.1 复用现有 Task，不新增业务对象

在现有 Task 中增加两个最小可选字段；不增加独立业务对象，字段最终落位由总集成 Owner 与 N3 固定：

| 字段 | 新任务内容 | 用途 |
|---|---|---|
| `method_manifest` | 有序 `{id, relative_path, sha256}` 数组 | 保存该 Task 真正派发的方法身份；不存部署相关绝对路径，也不复制方法正文 |
| `content_validation_policy` | 适用新 Narrative 写入时为 `argument-connectivity.v1` | 固定该 Task 的结构校验语义 |

schema 中的 optional 仅用于旧数据兼容。本轮候选的所有新派发 Task 必须由 producer 自动写入准确 `method_manifest`；实际写入新 argument 的适用 Task 必须同时写入 `content_validation_policy`，不是由调用方选择是否启用。Task 创建/派发的正式路径统一负责生成字段，接纳端校验其与冻结合同一致；不能通过调用方漏传标记或另一个派发入口绕过规则。必须覆盖 `create`、`continue`、`open_phase_task` 以及 Review 派发的真实 producer：仅当入口确实产生新 Task 时写字段/提升 floor，返回既有 Task 或纯投影时不改旧对象。非 argument Task 不为填字段而设置该内容策略。上述实际入口及其 Task 创建分支需要 Codex 核验。

现有 `task.v1.schema.json`（以及确实受影响的已有 schema）只同步 `docs/specs/deck-master-rebuild-v1/contracts/` 已登记的唯一镜像，不在本轮目录复制第二份。新只读合同及其 `docs/specs/deck-master-next-iteration-20261019/contracts/` 镜像由 N4 按总架构约定处理。

保留 `method_release.release_id / methods_sha256` 的既有意义；其聚合 hash 从同一有序清单计算。方法正文的唯一可编辑来源仍为 canonical references，准确路径由被明确选择的安装解析。

新字段属于写合同变化，本轮采用最小 writer 兼容标记 `rc4-content.v1`，由 N3 实现、总集成 Owner 统一接受；N2 仅验证安装/回退兼容，不写项目 floor。只有首次提交包含这些新字段/策略的 Task 或其他相关写入，才原子提升项目的最低 writer 要求。纯读、已提交操作/回执的精确重放，以及 N4 v2 读取投影不提升 writer floor，也不回写旧项目。版本号变成 rc4 本身不触发数据迁移。

新增 writer 标记时，统一审计现有 writer rank、兼容判断和所有显式 writer 名单，特别是 `collaboration_required` 及独立审查/受信回执分支。新的较高 floor 必须继承已有约束，不能因旧代码只认识有限的版本字符串而放松协作要求。交付可复核的旧 writer 拒写证据：对已提交新字段并提升 floor 的项目，旧 writer 在任何项目状态修改前明确拒绝，项目字节不变；对未使用新能力的旧项目，既有兼容路径保留。

### 6.2 唯一读取接口

增加 `method_resources.resolve_task_methods(task)` 作为 Task 方法清单的唯一读取来源，输出该 Task 的准确有序清单及 basis 状态。实际所需的 store / 安装参数采用当前 Runtime 的依赖注入方式；本函数不创建任务、不授权、不决定业务通过。无 Task 的 selector 用于产生新派发或明确的无 Task 读取范围，不能替代已存在 Task 的 resolver。

N4 只消费此结果来生成全文或紧凑投影。N4 不能重新运行当前角色默认映射、补入未在 manifest 中的方法、以用户文字猜测旧 Task 范围，或通过复用一个不匹配的“已读”标记跳过内容。方法选择属于 N3；传输去重和读取协议属于 N4。

### 6.3 历史兼容表

| 对象/状态 | 行为 |
|---|---|
| 已存历史 Narrative | 只读继续可打开；可提供标明“按新策略观察”的辅助诊断，但不回写失败、不改变原 hash/审批/完成状态 |
| 旧已提交 proposal/结果的读取、已完成 Task 的同 operation/payload 精确重放 | 返回原对象/提交回执，保持当时语义；不以新连通规则重判，不提升 writer floor |
| 升级前已接纳的旧 proposal，升级后首次正式采用 | 仅当升级前 committed Task/receipt 可证明它已被接纳、对象未改，且仍满足当前既有 scope/decision/CAS 时，沿原语义采用；不追溯强制新 policy，也不冒称已按新策略通过。可以提供标明新策略的只读诊断，不因此重标旧结果 |
| 新 proposal、原 proposal 改写、旧 Task 新提交，或只有磁盘孤立旧对象/自行伪造的旧标记 | 不享受上一行兼容；新写入按适用新 policy 接纳，执行合同变化则先 `basis_changed` 并重新派发。旧对象存在或字符串标记本身不能代替 committed 接纳事实 |
| 旧活跃 Task，无新标识，向当前候选新提交且本次写入适用新结构规则或新方法清单 | 先报告 `basis_changed`，说明执行合同需更新；沿既有取消/取代/重新派发路径建立带明确策略/manifest 的新 Task。不能在旧 Task 接纳瞬间偷偷升级，也不能用新方法执行后冒称遵循旧合同 |
| 旧活跃 Task，新提交仍属于未变化的兼容路径 | 只有原输入、scope、方法字节和执行合同仍可证明一致时才继续原合同；缺少新标识本身不能成为绕过本轮适用规则的豁免 |
| 旧 Task，无 `method_manifest`，有原 `method_release` | 以本轮固定的 RC3 历史 selector 还原原有序方法集合，仅当可读字节聚合 hash 与原记录相同才作为原方法返回；不使用新维度映射替代 |
| 原方法字节已经改变、缺失，或无法证明旧清单 | 保留 `basis_changed` / `not_recorded` 等准确状态，指出实际缺口；既有可读稿正常返回。按既有恢复路径选取明确的匹配安装，或正式重新派发新 Task；不自动从任意 HOME/PATH/旧目录借文件 |
| 新 Task manifest 的文件缺失或 hash 不符 | 返回定位错误，拒绝冒称本 Task 方法已完整读取；不自动降为角色默认方法，不补一份内容后仍沿用旧 digest |
| 已有旧结果待接纳，但当前任务/范围/输入已变化 | 继续受原 CAS、取消、撤回、晚到结果与依赖检查约束；读取旧方法不恢复其采用权限 |

“正式重新派发”是执行已有任务时的恢复动作；在已有授权范围内进行，不附加固定人工确认。若确实缺少原本就必要的用户决定，沿当前 Runtime 的具体缺口处理，不因本卡新增笼统审批。

## 7. 开发流程与模块分工

| 顺序 | 开发工作 | 涉及模块/对象 | 交付结果 |
|---|---|---|---|
| 1 | 固定策略与兼容矩阵 | 本卡、Task schema、最低 writer 注册 | 新旧任务适用规则和字段表 |
| 2 | 实现纯结构分析与校验 | `models.py` 或同职责小模块 | 可定位断连分量；读取行为不变 |
| 3 | 在正式新写入点消费策略 | `content_production.py` 及 Narrative 修改分支 | 新 Task argument 接纳生效，失败不半写 |
| 4 | 实现维度→方法选择 | `method_resources.py` | 一套稳定选择器，表格每行有确定结果 |
| 5 | 派发冻结与读取统一 | `tasks.py`、`service.py`、`content_review.py`、CLI/Skill helpers | 新 manifest，准确原任务解析，与 N4 接口一致 |
| 6 | 接通无 Task / 外部只读 | `read_skill_methods`、`external_review.py` 的交接入口 | 不写源、不创建 Task 也可获得适用方法；工具机械观察不冒称已模型审稿 |
| 7 | 安装与定向回归 | build hook / install / 既有测试 | canonical 字节未分叉，准确安装资源可读取 |

路径和当前职责划分在实施时需要 Codex 核验。函数拆分以最小必要改动为原则，不趁本卡整体重写 `service.py` 或扩展 Provider 配置。

## 8. 验收标准

| AC ID | Given | When | Then |
|---|---|---|---|
| AC-N3-01 | 新 Task 明确适用 `argument-connectivity.v1`，argument 含合法中心和断连节点 | 通过正式 start / accept 提交 | 返回 `narrative_disconnected` 及准确节点集合；Task 未完成，当前内容指针不变，不留下半采用 |
| AC-N3-02 | 合法单中心 argument，或现有合法 framing | 执行适用校验及正式接纳 | 单节点 argument 不要求人为补边；framing 保持原要求；二者不因无数字或非商业用途被拒绝 |
| AC-N3-03 | 教学/流程结构包含 supports、prerequisite、leads_to 等不同方向的连接，整体弱连通 | 执行结构检查并保存 | 通过；原有方向、关系和正文不被归一重写；不新增无环或全部指向中心要求 |
| AC-N3-04 | 中心通过 qualification_node_ids 连接限定；另有自环、仅共用来源或仅 issue/alternative 引用的对照 | 执行连通检查 | qualification 与显式限定边等价且不补写；自环和元数据共用不能掩盖真实孤立节点；诚实未知继续可用 |
| AC-N3-05 | 未携带新策略的历史对象/原操作、升级前有 committed 接纳证据的旧 proposal、旧活跃 Task，以及孤立对象/伪造旧标记对照 | 分别读取、精确重放、首次采用旧 proposal，或向适用新规则路径新提交 | 读取/重放保留历史语义；真实已接纳旧 proposal 在对象未改且当前 scope/decision/CAS 有效时沿原语义采用，不冒称新策略通过；新提案/改写/旧 Task 新提交适用新规则或先 `basis_changed` 重派，孤立对象及伪造标记不能取得历史兼容 |
| AC-N3-06 | 新 Review Task 的 stage 与 review_units 覆盖表中内容、前审、口播和混合情况 | 派发并读取方法 | 每种情况得到表中适用清单，稳定去重；final 内容审查含 calibration，前审保留现有五方法 |
| AC-N3-07 | 明确只做 page_visual 或限定视觉/转换检查，内容评审不在范围 | 派发或无 Task 读取 | 不加载完整内容示例；同时保留原图、物理尺寸及适用审查方法；不减少实际 Review 单元 |
| AC-N3-08 | 同一职责范围经 named、natural、Master、recovery 进入；另有无 Task 的只读文件审查 | 获取方法及执行上下文 | 相同 Task 返回同一派发清单；无 Task 内容入口也含 calibration；读取不创建项目/Task、不扩大权限 |
| AC-N3-09 | 当前候选及 canonical 方法可用，调用方没有预填新字段；包含 Review、非 Review 与 argument 派发路径 | 经正式入口实际新派发 Task，再读取 Task、工作单及方法 | producer 自动写准确 manifest，适用 argument 自动写 policy；ID/相对路径/逐文件 SHA/规范顺序/聚合 digest 一致；新字段提交与 floor 提升原子发生，不能靠漏传绕过；正文只有 canonical 真源 |
| AC-N3-10 | 老 Task 无 manifest，原 digest 可准确证明旧方法；或存在缺字节/hash 漂移 | 恢复读取 | 前者按冻结 RC3 清单返回；后者准确报告 basis 缺口；两者都不自动注入新方法或重标旧执行 |
| AC-N3-11 | N4 协商全文/紧凑读取，Task 清单相同 | 比较两种投影并模拟缓存不匹配 | 清单、语义、hash 与适用策略不变；只改变重复传输，缓存失配能取准确全文；不把收到/已读/已应用混为一项 |
| AC-N3-12 | 当前候选和旧 writer 可核对；存在未升级旧项目与提交新字段后提升 floor 的项目 | 核对打包并执行写入、纯读、精确重放、N4 v2 投影和旧 writer 写入负例 | 方法资源准确；只有新能力写入提升 `rc4-content.v1`；旧 writer 对已升级项目在改字节前拒写；新 writer 保留 collaboration_required 等原约束；工程结果不冒称效果或已发布 |

## 9. 定向测试方案

1. **结构纯函数组：** 两节点断连、单中心、分量链、限定列表、显式限定重复、自环、异向流程、诚实未知；验证算法结果与对象字节不被修改。
2. **正式事务组：** 使用临时合成项目，通过公共 create / open task / start / accept 重现断连拒绝和合法接纳；针对 `create`、`continue`、`open_phase_task`、Review 派发的真实 producer 验证新字段自动产生，而非全部手工预置 fixture。覆盖新 input_revision 写 Narrative、失败原子性、取消与精确重放。无真实模型或图像调用。
3. **方法选择组：** 参数化选择矩阵；包含缺省 review_units、明确非法维度、无 Task 及内容/视觉混合；比对实际返回的每个文件字节及 SHA。
4. **历史兼容组：** 保留固定 RC3 清单、旧 digest 与原对象；分别测试可证明相同、正文改变、文件缺失、Task 过期、旧活跃 Task 新提交的 `basis_changed` 和新策略重新派发。测试旧已提交 proposal 读取/精确重放不改语义；升级前 committed 接纳的未改旧 proposal 在当前 scope/decision/CAS 有效时可沿原语义首次采用，另测失效范围、改写、磁盘孤立对象与伪造标记均不能享受兼容。禁止通过改历史 fixture 的失败预期使回归通过。
5. **writer 兼容组：** 新字段首次提交与 floor 提升同事务；纯读、精确重放和 N4 v2 投影不提升；旧 writer 对升级项目明确拒写且字节不变；覆盖 rank 与显式名单，验证 collaboration_required、独立审查和受信回执要求不随新 writer 放松。
6. **集成组：** 复用 `test_content_contracts.py`、`test_content_preproduction_review.py`、`test_rc3_content_methods.py`、`test_rc3_early_methods.py` 等相关组；与 N4 只验证清单/全文等价，不跑不相关全流程。

现有测试命名、所需环境及当前通过状态需要 Codex 核验。测试目标是实际结构和派发行为，不编写只断言函数自身常量的镜像测试。完成这些定向验证后，是否运行总集成 CI 由包级质量门安排。

## 10. 交付与关闭条件

- 代码及必要 schema / writer 兼容修改；只修改本卡涉及的路径。
- 一份最终维度→方法映射表、旧任务处理表，以及与 N4 的读取接口约定。
- 正式 accept 的断连负例、合法正例、历史兼容结果和安装字节核对证据。
- Skill / 活动文档的最小同步；不复制 canonical 方法到其他 Skill，不引入 readiness.md 等虚构方法。
- 清楚报告“结构检查通过”“方法准确派发”“实际模型应用”“普通成品检查”的不同状态。

本卡通过不代表浅稿问题已经全部解决；N6 必须完成实际方法改善和正常任务应用。普通交付继续遵守本次有效范围和政策，不恢复旧 Frozen A/B、固定听众、真人试讲或默认人类签字门槛。
