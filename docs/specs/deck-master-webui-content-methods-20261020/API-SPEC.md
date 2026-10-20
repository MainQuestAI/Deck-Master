# 接口、数据与兼容规格

## 0. 现有与拟新增

PR127 的 `selected_resource_ids`、资源 DAG/冻结/读取和安装映射为已有实现，应复用。下面所有新 GET/preview、投影 schema 和 UI capability 均为**本轮拟新增合同**。

本轮不把下列读模型写入 Document，不引入新的 minimum_writer。运行时持久 schema 仍以 `src/deck_master/resources/contracts/` 为准。新增投影 schema 在实施时进入该目录并注册，不能另设一个活动 schema 根。

所有路径中的项目由现有服务绑定；project identity 必须与页面一致。项目级查询省略 revision 时仅解析一次当前版本，响应返明确 revision，后续子请求使用它。

## 1. 接口表

| 接口 | 行为 | 对应服务/前端 |
|---|---|---|
| `GET /api/tasks/{task_id}/methods?revision=R&availability=current` | 冻结 manifest + 可选当前可用性；不改变原 task detail 响应 | 新轻量投影复用 method_resources、run_desk / 任务详情 |
| `GET /api/content/arguments?revision=R&limit=30&offset=0` | 所选快照可达的当前/待选/历史 Narrative 索引 | 新 content insight 读服务 / 主线列表 |
| `GET /api/content/arguments/{sha256}?revision=R` | 一个已索引 Narrative 的结构与决定/采用事实 | 同一读服务 / 主线阅读与比较 |
| `GET /api/content/evidence/{page_id}?revision=R&element_ref=atom:...` | Page 原子→真实论点/条件/来源 | 同一读服务 / 单页依据 |
| `GET /api/reviews/{review_id}/reading?revision=R` | v1/v2 Review 的无损阅读投影与可定位对象 | 同一读服务 / 审阅列表 |
| `GET /api/content/requirements/{page_id}?revision=R` | 既有内容到设计要求；记录值或明确标识的纯推导值 | design_requirements / 单页提示词 |
| `POST /api/method-library/preview` | 只读上下文、目录与选择预览 | 新薄适配复用 catalog/select / 方法准备 |
| `GET /api/method-library/resources/{id}?catalog_digest=D&sha256=H` | 当前已验证资源的 UTF-8 正文 | 同一 resolver / 示例预览 |

`availability` 只允许省略或 `current`。省略则不检查当前安装，不返回伪造的历史可用性。

列表 limit 为 1–100，默认 30；offset 为非负整数。翻页固定 R，无效 revision/重复参数/未知过滤值沿现有请求校验拒绝。Narrative 和 Review detail 整体保留原内容；过大响应按现有 HTTP 大小限制明确失败，不静默截断为完整稿。

新增路由先于通用 tasks/reviews 路由匹配。保留原 `/api/content/lineage` 的页面派生含义，不把它改成论证关系接口。

## 2. 公共读封套

```typescript
type Ref = {path: string; sha256: string}; // 沿用现行严格对象引用
type ReadStatus = "ready" | "absent" | "partial" | "unreadable";
type ReadIssue = {
  code: string; field: string; message: string;
  ref: Ref | null; page_id: string | null;
};
type SnapshotRead<T extends object> = {
  schema_version: string;
  project_id: string;
  revision_id: string;
} & (
  | {status:"ready"|"partial"; issues:ReadIssue[]; data:T}
  | {status:"absent"|"unreadable"; issues:ReadIssue[]; data:null}
);
type ObjectRead<T extends object> =
  | {ref:Ref; readable:true; data:T}
  | {ref:Ref; readable:false; data:null; issues:ReadIssue[]};
```

`status` 和 `readable` 是互斥分支判别字段。unreadable 分支必须保留可验证 Ref（封套通过 issue.ref），issues 非空；不能填空标题、默认成熟度、空 Review 或空节点冒充业务数据。各不可读分支的投影 schema 禁止额外业务字段；T 为非 null 对象。partial 只用于存在可读主体/集合，坏条目采用 ObjectRead 的 false 分支。absent 与 unreadable 的 data 均为 null，但 status 不同。

`absent` 表示所选快照无记录；`unreadable` 表示有记录但无法读取，二者不能混淆。对象内部部分损坏可 HTTP 200 + partial；无效输入 400、不可达/不存在 404、客户端明确提交的目录/上下文预览指纹与服务端观测不符 409、基础存储不可用 503。继承既有 revision 错误码；本轮新增的错误码使用：

- `insight_object_not_reachable`：404，目标不在所选项目/版本的合法引用链。
- `insight_locator_unavailable`：作为局部 issue，不阻断其他完好对象。
- `method_preview_basis_changed`：409，目录或上下文变化，需重新预览。
- `method_preview_invalid_selection`：400，返回具体资源 ID 及适用性错误。
- 无合法的新阶段不是 HTTP 错误：目录可读时返回 200，browse_status 与 dispatch_status 分开，原因见 §8。禁止调用 continue 创建上下文。`method_preview_basis_changed` 仅用于 §8 的 expected_basis 或正文请求指纹冲突；不因固定历史版本不同于 current 就返回 409。

所有字符串与 Markdown 为不可信内容，前端使用安全文本渲染；资源链接只接受同目录已登记 ID 或受控外链，不自动读取任意文件。

## 3. 任务方法依据

响应 schema 名：`ui_task_methods.v1`。data：

```typescript
type TaskMethods = {
  task_id: string;
  task_ref: Ref;
  dispatch_revision: string;
  frozen_status: "recorded" | "not_recorded";
  frozen_release: {release_id: string; methods_sha256: string} | null;
  resources: Array<{
    id: string; relative_path: string; sha256: string;
    display_name: string | null;
    semantic_kind: "instruction"|"example"|"template"|"data"|"script"|null;
    metadata_status: "verified_for_release"|"unavailable";
  }>;
  availability: null | {
    checked_at: string;
    observed_release_id: string | null;
    status: "current"|"basis_changed"|"unavailable";
    issues: Array<{id: string|null; reason: string;
      expected_sha256: string|null; actual_sha256: string|null}>;
  };
};
```

从 snapshot 中找真实 Task；无 manifest 不调用新 selector 伪造历史，返回 not_recorded、空 resources。有 manifest 时 ID/路径/hash 保留原顺序。

当前可用性复用 resolver，但 unknown frozen ID/路径/缺文件应转成局部 issue，不让一项新目录移除使整个任务详情消失。查询不扫描安装历史、不回填缺失 release。

元信息只在能验证与该资源原 release/字节一致时显示 verified_for_release；否则名称/kind=null，前端退回 ID。不得凭当前 catalog 给旧记录套新解释。

资源不包含绝对路径或全文，任务列表不增加全库读取。用户单独展开 preview 才读正文。

## 4. Narrative 索引与详情

索引 schema：`ui_arguments.v1`。

```typescript
type ArgumentItem =
  | {ref:Ref; readable:true; narrative_id:string; maturity:"framing"|"argument";
     relation:"current"|"proposal"|"historical";
     request_id:string|null; producer_task_id:string|null;
     communication_question:string|null; central_statement:string|null}
  | {ref:Ref; readable:false; issues:ReadIssue[]};
type ArgumentList = {
  items: ArgumentItem[];
  pagination: {limit:number;offset:number;next_offset:number|null};
};
```

合法来源：所选 Document.narrative；所选快照引用的 Task 的真实 Narrative result_refs；已存决定中的有效对象引用。仅靠磁盘存在、用户给出的 SHA 或任意 Task input 不足以成为候选。

先验证项目身份、schema 和真实 producer binding。当前请求未采用的合法产物标 proposal；旧请求产物标 historical，即使文件较新也不能标成当前候选。索引损坏条目可保留 Ref+readable=false，其他项可读。

详情 schema：`ui_argument.v1`。data：

```typescript
type ArgumentReading = {
  item: Extract<ArgumentItem, {readable:true}>;
  narrative: object; // 完整合法 narrative.v1；主体不可读时外层 data=null
  related_pages: Array<{page_id:string;page_ref:Ref;node_ids:string[]}>;
  plans: Array<ObjectRead<{
    narrative_ref:Ref; mode:"planned"|"bound";
    planned_roles:Array<{role:object;page_ref:Ref|null;
      basis_status:"planned"|"current"|"changed"}>;
    plan:object; // 完整实际 content_plan.v2，不生成第二计划
  }>>;
  plan_status:"recorded"|"absent"|"partial"|"unreadable";
  decisions: Array<{ref:Ref;effective:boolean;disposition:string;reason_codes:string[]}>;
  adoption: {
    readable_in_revision: string;
    assessed_control_revision: string;
    can_record_direction_decision:boolean;
    can_adopt:boolean; needs_decision:boolean;
    decision_reason_codes:string[]; adoption_reason_codes:string[];
    write_scope: object|null; existing_decision_ref:Ref|null;
    subject_ref: object|null; basis: object[];
    invalidated_refs: Array<{ref:Ref;reason:string}>;
  };
};
```

`subject_ref` 必须是核心生成并经注册的 ProposalRef，例如 Narrative 使用 `projection="direction"`；`artifact_kind` 使用现有 registry 的实际值，不由前端猜。write_scope/basis 同理由核心现有规则派生。

读取内容固定在 R；采用准入针对当前控制版本另行评估并标出 assessed_control_revision。历史阅读或控制变化不能显示为可立即写入。`invalidated_refs` 由与实际 adopt 相同的纯检查逻辑生成，不能在 UI 估算失效范围。

计划读取优先复用 `GET /api/content-plan?revision=R`，只有返回 Plan.narrative_ref 精确等于所读 Narrative Ref 时才关联。该接口仅投影快照当前 Plan；候选 Plan 则从同一固定 snapshot 的正式 Document/已提交 Task result_refs/决定引用关系解析合法可达 Ref，按真实 narrative_ref 过滤后投影。多个真实 Plan 全部按固定 Ref 列出，不随意挑最后一个。planned_roles 来自 input.page_roles；planned 模式没有 Page 时 page_ref=null，related_pages 仅含真实 Page。没有关联或损坏分别为 absent/unreadable，不能借用其他方向的当前 Plan。两侧 Narrative 可以关联不同 Plan，比较保存各自 Plan Ref，不创建持久计划。

比较不以 proposal 数量判断：两份不同、可读、schema/语义合法且在各自指定 snapshot 合法可达的 Narrative Ref 即可，支持 current+candidate。历史比较只读，任何一侧历史引用均不能经比较入口记录决定/采用；要写入须另行显式选择当前对象并完整检查。

can_record_direction_decision 按现有 decision.record 的请求、证据/策略与 scope 准入独立计算，不等于 can_adopt。can_adopt 按实际 adopt_proposal 的所有谓词计算，包括有效 accepted direct_user/delegated 决定、精确 subject/projection、scope、对象语义、当前控制与 writer 边界，不能仅用 eligibility.allowed 代替。无覆盖决定：needs_decision=true、can_adopt=false，只有记录准入通过才可进入第一步；已有有效覆盖决定：needs_decision=false，复用 existing_decision_ref 后独立检查采用。策略拒绝在对应 reason_codes 中保留；历史/不可读/控制依据变化均不可写，不返回伪造预览影响。

如现有 adopt_proposal 将验证与写入混在一起，最小抽取无副作用的检查函数供读取和原采用共用，原事务锁内仍重新检查。禁止为预览调用真实采用后再撤销。

## 5. 方向采用：复用两项写操作

现有接口：

1. `POST /api/projects/{project_id}/collaboration/decisions`
2. `POST /api/projects/{project_id}/collaboration/proposal-adoptions`

第一项请求沿既有字段：

```typescript
type DirectionDecisionRequest = {
  base_revision:string; operation_id:string;
  decision:{
    topic:"direction";
    authority_mode:"direct_user"; // 仍由 adapter 判断 assurance，不由 UI 伪造验证身份
    subject_refs:object[];
    scope:object;
    basis:object[];
    value:string;
    disposition:"accepted";
    instruction_evidence:{kind:"host_attested_instruction";text:string;source_locator:string};
  };
};
type AdoptionRequest = {
  base_revision:string; operation_id:string;
  proposal_ref:Ref; decision_ref:Ref; write_scope:object;
};
```

Evidence 格式复用当前 `controlForm` 与实际 adapter 契约；verified_user 策略不接受时展示真实阻断，不自动降级。页面点击不能把 host_attested 记录改名为已验证用户身份。

UI 编排规则：

1. 展示 adoption 的 exact ref/scope/impact，用户提交前保存两步关联的个人操作草稿。
2. 已有有效决定精确覆盖该 proposal 时直接使用其 Ref；否则仅在 needs_decision 与 can_record_direction_decision 为 true 时提交第一步新 UUIDv4。没有决定时不要求 can_adopt 为 true。
3. 第一项 ACK 后使用回执中的 control revision/decision_ref 重新读取采用准入与影响；can_adopt 为 true 后为第二项生成并保存独立 UUIDv4，禁止沿用决定前 base。记录成功但采用拒绝/失败时保留真实决定，显示“方向决定已记录，采用尚未完成”，不得重录决定或把部分成功显示为全成功。
4. 网络中断先用既有 operations lookup 核实原 UUID。not_found 才允许原 payload/id 重放；unknown 不作失败。
5. 中间发生别的写入时保留决定，重新读取准入与影响；不得悄悄把新 base 填进旧 payload。新提交是新的明确请求。
6. 第二项成功后刷新控制摘要；固定比较仍保留，用户选择是否读取新稿。不得自动继续生图。

不新增合并的“批准并生成”接口；完整状态可由两份真实回执恢复。

## 6. 正文证据与设计要求

证据 schema：`ui_page_evidence.v1`。data：

```typescript
type PageEvidence = {
  page_id:string; page_ref:Ref; narrative_ref:Ref|null;
  alignment:"current"|"bound_to_older_narrative"|"not_recorded";
  elements:Array<{
    element_ref:string; text:string;
    mapping_status:"recorded"|"not_recorded"|"unreadable";
    nodes:object[]; edges:object[]; qualifications:object[];
    direct_source_links:object[]; node_source_links:object[];
  }>;
};
```

text 来自既有 atom 提取器，不自己用 CSS 路径重建身份。source link 保留完整原 source_version/locator。不要因为同一来源 ID 重复就丢掉不同 locator；只去掉完全相同的条目。

首要论证 Ref 是 Page.content_mapping.narrative_ref；不能直接替换为 Document.narrative。用户指定不存在 atom 返回具体错误；没有 element_ref 则返回本页所有原子映射，按原稿顺序。

设计要求 schema：`ui_content_requirements.v1`。data：

```typescript
type RequirementsReading = {
  page_id:string; page_ref:Ref;
  origin:"frozen_task"|"derived_from_snapshot"|"not_recorded";
  producer_task_id:string|null;
  content_basis:object|null;
  content_requirements:object|null; // 已有 content_requirements.v1
};
```

优先展示与当前页 Ref 确切匹配的冻结任务要求；若没有，允许调用 `design_requirements.resolve_content_requirements` 的纯读路径并标 derived_from_snapshot。不能将推导说明写成“制作工具实际采用”。已有不同任务时不得任意挑最后一条。

## 7. Review 阅读与修订交接

schema：`ui_review_reading.v1`。data：

```typescript
type ReviewReading = {
  review_ref:Ref; review:ObjectRead<object>; // 原 v1/v2 全量；不可读 data=null
  targets:Array<{
    finding_id:string; source_index:number;
    page_id:string|null; page_ref:Ref|null; element_refs:string[];
    locator_status:"exact"|"page_only"|"unavailable";
    repair_layer:string|null;
    repair_allowed:boolean; reason_codes:string[];
  }>;
};
```

targets 是读投影，不修改原 review。review.readable=false 时 targets=[]、review.data=null、review.issues 非空，不表示“没有问题”。当前及最早 v1 合同均要求 finding_id、impact、resolution，不能把缺必填 ID 的损坏对象变成合法历史兼容；v1 只对其合同未要求的 v2 扩展字段显示未记录。

定位身份为 `(revision_id,review_ref,finding_id,source_index)`；source_index 是原 findings 数组过滤/排序前的零基索引，仅用于确定性定位与校验，不是持久业务 ID。URL 用 revision、review_sha256、finding、finding_index 携带完整身份，服务端由已提交快照的合法引用解析完整 Ref，保留既有 review_id 路由并核对匹配。索引、ID、Ref、revision 必须同时一致；越界/不匹配/不可读返回局部定位错误，刷新不得默认选第一项。不同 Review 的同名 finding 不互相替换。修订层依实际 finding/subject/scope 得出；无法证明时 null，不根据措辞猜层。

修改仍复用 `POST /api/content/plan` → `/api/content/commit` 的既有 payload、CAS 与候选机制。新入口只预填草稿，不新增“修好此问题”写接口。Review-only 不能直接转入生产；纯 speech/design 的范围保留。Reviewer 写的 resolution 和修稿提交事实分开。

## 8. 资源目录、预览和交接

本轮新增能力 `method_library_preview.v1`；只在目录、适用性预览与安全正文读取均实现后声明。前六类内容读接口使用 `content_insight.v1`，由 WU01 一次完成其服务合同后声明。新 UI 根据能力启用，不能以版本号字符串代替探测。

POST preview 请求：

```typescript
type MethodPreviewRequest = (
  | {context:{mode:"project";revision:string};selected_resource_ids:string[]}
  | {context:{mode:"independent";role:string;phase:string|null;review_units:string[]};
     selected_resource_ids:string[]}
) & {expected_basis?:{catalog_digest:string;context_digest:string}};
```

项目模式只读 `content_production.content_phase_status`、当前 request、待办和范围，得到合法内容阶段；不调用 next_phase_task/continue。phase 不可判定、请求已完成、等待决定或已有冻结待办时，目录可读仍返回 HTTP 200 + browse_status=available|partial 与 dispatch_status=cannot_dispatch。reason_codes 分别记录 no_new_phase、request_completed、awaiting_decision、existing_task_frozen、policy_blocked、historical_revision、basis_unreadable。未知阶段不伪造 phase，也不将 null 传入 selector 以绕过范围校验：可浏览已登记目录及冻结任务，但 selectable=false、selection_status=not_evaluated，default/dependency/resolved_manifest 为空仅表示未评估，explicit_ids 保留用户输入。不适用 ID 的范围检查在真实 role/phase/scope 可判定时进行；未知/不可读注册 ID 始终拒绝。

独立模式允许公开 Skill 中的角色；phase/review_units 与现有 resolver 使用同一验证规则，不伪造项目授权。独立只读浏览不能成为对项目写入的允许依据。

返回：

```typescript
type MethodPreview = {
  schema_version:"ui_method_preview.v1";
  project_id:string|null; revision_id:string|null;
  context_status:"new_content_task"|"frozen_pending_task"|"read_only"|"no_new_phase"|"context_unavailable";
  browse_status:"available"|"partial";
  dispatch_status:"new_content_task_possible"|"cannot_dispatch"|"not_applicable";
  reason_codes:string[]; preparation_only:true;
  selection_status:"validated"|"not_evaluated";
  context:object; catalog_digest:string; context_digest:string;
  entries:Array<{id:string;display_name:string;description:string;
    kind:string;sha256:string|null;selectable:boolean;reason_codes:string[];}>;
  explicit_ids:string[]; default_ids:string[]; dependency_ids:string[];
  resolved_manifest:Array<{id:string;relative_path:string;sha256:string}>;
  preview_digest:string;
  handoff:{status:"preparation_only";copy_allowed:boolean;text:string};
};
```

browse_status 与 dispatch_status 独立；独立浏览 dispatch_status=not_applicable，项目可准备新阶段也仅为 new_content_task_possible，均不产生派发许可。恒定 preparation_only=true。无法解析合法选择上下文时 copy_allowed=false，仍可浏览；恢复明确上下文并通过 resolver 后才可复制准备文本，写入口仍重新校验。目录整体不可用返回 503，局部资源损坏为 200+partial。expected_basis 不符（目录/上下文漂移）或正文资源 hash 不符才是 409；首次无上下文、普通历史阅读不为 409。重取成功后替换预览，保留用户选择。

依赖按原 DAG 顺序、同一规则展开。preview_digest 对 context、catalog 字节、显式 ID 和最终 manifest 计算；复制前重新核对预览。变更后不给旧内容加“已核实”标识。

未选择的目录项 sha256=null（未读取字节）；只有默认、显式或依赖选中项返回已核对 hash，正文阅读使用该 hash。这样列表不为填充 hash 扫描全库；不是将 null 当作已验证字节。

目录的展示名称与说明：先使用合法 UTF-8 Markdown 的首标题和明确的目录项元数据；无可验证标题退回 ID，无明确说明则 description 为空，不能由模型补造。标题读取按需缓存并绑定资源 SHA，列表不扫描/返回全库正文。本轮不为 display metadata 放宽 catalog 的精确字段校验，不维护 JS 私有 ID→业务名表。后续可另行升级 catalog 元数据。

正文接口只接受注册 ID、预览 catalog_digest 与该资源 SHA；同一 safe_file/resolve_root，hash 不匹配返回 409。默认上限 1 MiB UTF-8，超过返回 413 和可解释错误；不得悄悄截断展示为完整案例。scripts 只读；data 按数据展示；示例链接跳转经登记依赖解析，不接受任意 file:// 路径。

库浏览、preview 和复制要求都不写 Task，不要求新增业务 operation receipt。个人选择保存在现有草稿区；跨版本恢复后重新校验。是否真正用于生产由将来真实 Task manifest 提供证据。

## 9. 兼容、性能与验证

- 保留所有原 API 响应与路由；新增投影不要求旧客户端理解新字段。
- 老核心无 capability 时原 UI 可读；新功能局部不可用，不阻断原材料/稿件/任务/交付。
- 旧 writer 不能写新项目的规则不变；打开、比较、预览不提升 writer floor。
- 提取共享只读帮助函数时必须覆盖原 continue/adopt 路径回归，不能用第二份选择逻辑求方便。
- 列表只读元信息，不读取全部方法正文；详情取消/切换后迟到响应不能覆盖当前对象。
- 本轮测试材料采用合成且可公开的工程 fixture；真实内容/Host 证据单独标识，不把 fixture fallback 放进生产。
- 新模块建议 `content_insight.py` 和 `method_library_view.py`，仅为服务投影；不创建新的内容引擎或常驻后台服务。
