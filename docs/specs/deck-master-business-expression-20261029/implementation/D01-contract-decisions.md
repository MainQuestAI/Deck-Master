# D01 合同与兼容决定

执行基线：`035845f228d1ba4cd7fc9b41cdedd8fd734043df`；2026-10-30 重新 fetch，origin/main 仍为该提交。D00 的作者继续结论见 [关口记录](../evaluation/author-go-20261030.md)。

## 单一语义来源

活动合同为 `src/deck_master/resources/contracts/narrative.v2.schema.json`。它逐属性引用 v1 的既有定义，新增 `business_strategy`、`business_frame`、`method_applications`；不向 strict v1 塞字段。原始要求继续存在 Document.task，事实、能力、场景、限制继续由原有节点及来源承载。Plan.v2/Page.v2 不升级、不复制业务框架。

策略保存任务情境、作者目标、已形成共识的节点、重点/支撑/省略节点及理由。框架保存一个不可变提案中的业务主题、含义、组织依据及主题关系；主题以 role + node_id 关联需求、能力、场景、限制或支撑，以 issue_id 记录缺口，不复制事实段落。framing 可为 null 框架；argument 必须有框架及中心主张的重点引用。对象/过程/责任/关键约束等组织依据允许自定义，不强制四词或固定图形。

方法作用只引用本 Task 的方法 ID/hash 和实际产物 JSON pointer。Runtime 拒绝伪造 Task、方法/hash、不存在的结果位置和失效输入；这些检查不证明方法有效或专业内容通过。

## 协商与首次写入

协议保留 `compose.v2`；新能力及 writer floor 为 `business-framing.v1`。D01 通过显式 `deck-master create --business-framing` / service 同名 boolean 选择新策划合同，旧默认不变；新版默认组合及 Web/审查选卡属于 D02b，不在此提前切换。

首个持久化的新 Task 冻结此能力并要求 Narrative.v2。它本身就是旧 core 无法正确执行的新语义，因此与 Task 同次原子提交将 writer floor 提至 21；不是等返回 v2 后才允许旧 core 继续写新 Task。只读旧项目、未选择新合同的创建、失败的 opt-in 均不提高此边界。Store 只检查新增/变化 Task refs 和变化的 Narrative 指针，避免为该边界重新读取全部历史 Task 对象。

旧 Host 缺能力不能 claim；新 Host 声明支持却返回 v1 也拒绝。旧 Task 不补签能力、方法或字段，不能提交 v2。已有 v2 真源不能经 v1 提案静默降级；明确历史 restore 仍沿旧版本和现有边界执行。读 v1 不补造商业策略。

确认稿、write_only、speech_only、design_trial、review_only、edit 不因新入口被迫重开策划。显式 opt-in 与这些范围冲突时在项目创建前拒绝；不带 opt-in 的旧入口保留职责。

## 输入、决定与采用

新 framing/argument 和 direction 决定绑定 brief、audience、scenario、existing_decisions。existing_decisions 注册为 task_fact；新合同的 narrative input_revision 即使复用 page_copy phase，也强制绑定这四项。历史记录只读其原 basis，不回填新事实。

结果按实际 Task 验证四项当前输入及冻结值，并检查真实来源版本/定位；附带 planned Plan 必须绑定该 Task 的 ID、dispatch revision、input digest 和本次 Narrative 的节点/来源。输入更新仍保留整体摘要、显式退役和 CAS/迟到结果保护。

零 Page 的 plan_only 先完成关闭原请求。正式采用复用新的有界 narrative/plan/review 请求和覆盖两个具体 Ref 的 direction 决定；先采用 Narrative，再以最新 revision 采用匹配 Plan，不重新生成。两步之间场景或共识变化，决定与 Plan 采用均失效；已有 Narrative 和此前版本保留，不混入旧 Plan，不派发失配 outline。Narrative.v2 登记进现有采用分派，无新采用状态机。

## 四态影响投影（D05/D06a 的冻结接口）

现有 `content_impact.v1` 保留原格式；其 unaffected_pages 仅表示没有匹配变化来源，不能解释为策略可复用。D05 对新商业合同新增 `content_impact.v2`：

| state | 含义 | 可以触发什么 |
| --- | --- | --- |
| affected | 已有明确证据确定需要改写 | 在原授权范围内形成新提案 |
| needs_reassessment | 策略/任务改变，需要判断原内容是否适合 | 先复核，不当作自动重写或复用 |
| reusable_after_review | 针对新策略完成复核，可复用具体旧 Ref | 沿既有采用与版本绑定复用，不伪造新生成 |
| unverified | 缺依据、不可读或尚未检查 | 保留缺口，不进入可复用集合 |

v2 以 `page_assessments[{page_id,state,reason_codes,evidence_refs}]` 明确互斥状态。`affected_pages` 仅由 affected 派生；不提供语义含混的 unaffected_pages。task/source 差异和固定对象依据继续保留，具体检查证据由 D05 提供；当前 D01 不生成这份投影，也不声称语义影响分析已实现。

API 依据真实 schema_version 返回，不把 v2 伪装 v1；D06a/D06b 消费时先识别版本。旧 v1 的“未直接命中”展示为尚未核验，新 UI 不将其升级为已复核可复用。旧调用者继续请求/接收原 v1，新版本采用按能力/新项目边界启用；只读和状态投影不提交业务写入。

## 消费者及证据

完整静态检索清单和逐文件处理见 `D01-consumers.json`，包括无显式版本字符串的 Ref、节点与字段消费者。`content_review` 的作者沿革和 `editing` 的实质修复摘要纳入策略/框架；只改方法引用不会成为“已修复内容”。API 原样保留 v2 对象；D06 再提供专门作者阅读/修正界面。

工程测试、服务级结构探针与专业评审分别记录。D00 作者认可是设计依据，不当作 D01 新合同的模型生成效果或 UI 采用体验已验收。未执行的模型/作者界面验证保持明确缺口。
