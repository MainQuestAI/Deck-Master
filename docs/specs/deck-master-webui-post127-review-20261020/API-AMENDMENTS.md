# API 最小修订建议

以下是待合入原 API-SPEC 的明确合同；是新 WebUI 投影的设计，不是已存在接口。

## R1 — 决定记录与采用

删除含糊的 adoption.allowed，采用 can_record_direction_decision、can_adopt、needs_decision、decision_ref（可空）及两组 reason_codes。can_record_direction_decision 只描述当前请求、真实用户证据与精确 scope 下记录决定的准入，不暗示一定采用成功。can_adopt 必须依真实 adopt_proposal 全部谓词计算，缺覆盖决定为 false；不可仅根据 eligibility.describe 判断。

无决定但允许记录：needs_decision=true，can_adopt=false；已有有效覆盖决定：needs_decision=false，返回固定 decision_ref 并按实际采用准入判断。策略拒绝分别标明决定/采用原因，不将缺决定伪装为可采用。历史读态两种写动作均 false。

记录与采用仍是两个现有事务，各自原 payload/base/operation_id。决定成功后使用返回的新 revision，重新读取采用准入，提交同一固定 proposal/scope 的采用；不得用旧 base。记录成功但采用失败：保留已记录决定及原采用请求，明确“决定已记录，方向尚未采用”。未知结果先查询 operations；不得重新创建决定、换 ID 掩盖未知，或削弱 CAS、权限、精确 subject_refs/projection、有效性和 writer 边界。

## R2 — 浏览与派发分离

方法准备 GET 返回 preparation_only=true、browse_status=available|partial|unavailable，dispatch_status=not_evaluated|cannot_dispatch|new_task_possible，reason_codes 数组及固定 revision。即使 new_task_possible 也只是当前事实观察，不是派发许可/token；真正写入口仍重新校验。预览不调用 continue、build/open task 或任何会修复/派发/持久化的路径。

目录可读但阶段 complete/blocked/awaiting_decision、已有 frozen Task 或无下一阶段：HTTP 200，浏览 available 或 partial，派发 cannot_dispatch。reason_codes 至少覆盖 no_new_phase、request_completed、awaiting_decision、existing_task_frozen、policy_blocked、historical_revision、basis_unreadable；选定方法越出实际 role/phase/scope 返回独立选择错误。无阶段不得伪装 phase 值或放宽 selector 的 phase 校验。

GET 409 仅在请求显式提交互相矛盾的固定依据（例如 revision 与绑定 task_ref 不一致）且合同定义 basis_conflict 时；“没有可派发阶段”不是 409。非法参数 400、不可达/未知固定对象 404、全局服务不可用 503，局部资源不可读留在 200 的 partial。实际 HTTP 错误映射需在最终 PR127 基线复核，不能声称核心已提供这些新状态。独立写入口的 CAS 冲突/冻结任务拒绝保持原语义。

## R3 — 零 Page 与计划关联

ArgumentReading 增加只读 plans 投影，每项为固定 plan_ref、narrative_ref 与 SnapshotRead<PlanProjection>。计划职责 planned_roles 从真实 content_plan.v2.input.page_roles 读取；尚未产出 Page 时 page_ref=null、basis_status=planned。related_pages 仅包含真实 Page Ref，不用虚拟 Page 填充。

当前采用 Plan 可复用 GET /api/content-plan?revision=<fixed>，须验证返回 Plan.narrative_ref 与所读 Narrative 精确一致。候选方向对应的 Plan 若不是该 snapshot 当前指针，新增只读、合法可达 Ref 投影（不新增持久计划），沿固定 Document/已提交 Task result_refs 等正式关系寻找并验证 narrative_ref；找不到/不可读时显式 missing/unreadable，绝不借用另一方向当前 Plan。不同方向可对应不同 Plan，比较保存双方固定 Ref。

## R4 — 比较准入

compare_eligible 只要求两份不同、可读、schema/语义合法且在所选已提交 snapshot 上合法可达的 Narrative Ref；支持 current+candidate，无需两个 proposal。相同 Ref、孤立对象、外项目或不可读对象不得进入比较。每侧记录自己的 revision 与 Ref，历史比较可读但不可记录决定/采用。历史候选若要用于当前写入，另走显式当前选择与完整准入，不能把比较视图变成写授权。

## R5 — Review 定位

locator={revision_id,review_ref,source_index,finding_id?}；source_index 为固定原始 findings 数组的零基索引（过滤/排序前）。URL 携带 revision、review Ref 的 path+sha256（安全编码并在服务端验证）、source_index；finding_id 有则附加做一致性核对。索引是只读定位器，不是新持久业务 ID。不在读取/刷新时回填旧 Review。

用完整 Ref+revision 验证可达及可读后定位原数组，索引越界、ID 不一致、对象不可读则定位错误，不默认第一项。UI 过滤/排序保持原 source_index。源码当前 review.v1 要求 finding_id；如旧格式适配确实允许缺 ID，仅为合法可读的适配结果使用兜底，不把违反 schema 的损坏对象悄悄变合法。

## R6 — 不可读 union

统一 SnapshotRead<T>：
- {readable:true,ref:Ref,data:T}；
- {readable:false,ref:Ref,data:null,error:{code,message}}。

两分支判别强制、互斥，不可读分支禁止业务字段默认值。ArgumentItem 采用相同 union，业务标题/节点/成熟度等仅在 data 内可读分支存在。ReviewReading.review 为 SnapshotRead<Review>，不可读时 data=null；若复用原外壳字段则须等价 discriminated union，不能仍强制 Review 非空。ref 不可达与内容不可读区分；后者保留可验证 Ref。不可读不等于空、无问题、通过或可采用。
