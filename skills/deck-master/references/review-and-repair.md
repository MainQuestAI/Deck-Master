# 实际审阅与返修

本方法指导实际审阅与返修。保留现有 PR33 的逐 finding 关闭、同页产物检查、原图来源、实际读回以及取消/晚到结果保护。

## 工作单就是本次审阅范围

读取当前 review_plan，确认哪些维度尚未执行、已经过期、存在旧问题或因输入变化需要重新检查。任务列出的每一项都要实际完成或准确说明缺口；不能只提交 instruction 中习惯出现的三个维度。

最终六维是：content、blueprint_content、blueprint_fidelity、conversion、readability、privacy。它们不是六名 Agent，也不是六次用户审批。

content 看任务、正式输入和整稿是否成立；blueprint_content 看全部可见表达是否正确进入正文；blueprint_fidelity 看原图的视觉与业务关系；conversion 看 SVG 到真实 PPT 的转换；readability 看实际阅读；privacy 看面向本次受众的可见/隐藏文字、备注及媒体限制。

## 两个时点不做同样的登记

逐页审图提前发现原图与 SVG 的内容、结构和阅读问题。最终查看实际 PPT，检查转换后结果和全稿一致性。前次真实观察可复用；但是只复制它的 pass 并不能证明最终 PPT 没有变化。

来源/任务变化但物理页面没有变化时，重新核对适用内容与披露条件；转换层的已有观察仍可供使用。不因为 Document 管理版本变化就让所有几何观察过期。

## 问题必须定位并形成动作

每项说明所在页和对象、期待、实际、依据及需要改动的范围。内容不足先补机制与论证，不用增大标题、扩大禁词表或堆几张卡片代替。确有制作缺陷时修 SVG 或转换结果，不改原始参考基准。

privacy 不等于宽泛法律认证；“缩略图”“右屏”等业务词不是自动泄密。真实禁止披露的信息应处理，包括讲者备注和媒体，不仅检查正文。

## 处理历史发现

fixed：同一发现有真实相关修订，当前产物经复查。

accepted_variance：原来需要判断的差异，经具体解释、观察和证据确认可接受；不将 must_fix 改名放行。

只有这两种关闭方式。输入更新让原要求失效时，按 input-update 的方法处理，不新增第三种关闭方式。

没有执行阅读就是未评估，不能填默认高分或两套 reviewer 名称。工具可报告真实机械检查，但不能替用户提供专业认可或独立审查身份。

## RC3 内容前审

preproduction 工作单给出 source-reading、content-methods、content-examples 与 content-calibration 的实际文件和 hash。读取完整材料、任务、Narrative、Plan、全部正文与 notes，再按六组校准检查：只有标签、页间重复、空矩阵、侧栏复述、无收益数据时造数/留空、以拥挤替代完整。合理留白、不确定性、教学复习和示意要结合用途判断。

问题定位到 Page/atom/关系、来源和用途影响；提交具体原句、改句与受影响页，不以加 observation/证据编号代替返修。保留首稿、首次 Owner 稿和后续修订；F0/F1 不能用最后精修覆盖，影响用途的 F2 也须修。

先读 `deck-master capabilities` 的 `review_channels`，或执行只读 `deck-master review channels --check-native [--project <dir>]`。旧 `review_channel_status` 只描述当前注册的回执 provider，不代表没有原生审查入口。原生 `review native --project <dir>` 只支持内容前审，并在实际运行时验证独立身份、固定输入与完成事件；`prerequisites_ready` 仅表示本地客户端/已有登录满足前置，不代表审查已运行。原图表达、SVG 转换、最终交付和人类专业认可不能从内容通道推定。`unsupported`、`receipt_not_configured`、`provider_unavailable`、`tool_missing`、`tool_failed`、`login_required` 和 `not_verified` 各按返回动作处理；保留历史失败与未评估，不用自行编写回执解除门禁。

默认独立前审没有实际独立执行或可信人类通道就记 needs_reviewer；用户明确接受的 host_self 降级只在所绑定范围/原因内适用，不满足交付人类专业政策，不能换名字、声明已独立或自动降级。方法 identity 漂移（method_basis_status=basis_changed）时重核实际消费版本，旧记录保留原身份；`methods --kind review --intent preproduction --read` 可读当前安装的真实文本。

### 实际读取、判断与返修证据

先用工作单 task_id 读取 `deck-master methods --project … --task-id …` 返回的真实全文/hash，核对 dispatch/current 方法身份；再打开 packet 的相关完整来源、Task 事实、Narrative、Plan、每页全部可见 atom 与 speaker_notes。截图/摘要/locator 存在不能代替已读内容，材料含图时同时检查原图。Review 绑定当前被审产物及依赖；未知或未执行的维度保留 not_evaluated，不由通过的机械检查补齐。

每项 finding 写明 Page/atom 或关系、原句/实际结构、所读来源位置、期待、实际、用途影响与 F0–F3 依据；返修给出实际改句/单元格/分支与 diff，复读受影响的总结、引用和 notes。若修改超出 Scope，先报告范围缺口，不静默全稿改写。六组校准中的正对照同样核查，不能为凑密度删诚实限制、教学停顿或合理留白。

事实/批准/授权/改变结论的限定失真按 F0；需用户重建用途、中心论证或章节关系按 F1；局部实质问题影响用途按 F2，修复前不能通过该用途；F3 才是偏好微调。唯一等级依据仍是内容协作 v1.2 `ACCEPTANCE §1.2`，不另设同名 F1。平均分不抵消开放 F0/F1 或影响用途的 F2。

真实非作者 Host controller 观察 native 独立执行的身份、固定工作单和完成输出，并经当前 Runtime 已注册 provider 核对，可诚实取得 host_attested 独立回执；普通模型前审不硬加平台密码学签名。作者提交 JSON、执行 ID、hash 或换 reviewer.id 不能生成该证明。普通内容与成品检查由制作/审阅 Agent 对照任务、来源和实际文件完成。用户正常审稿意见如有则处理；人类专业复核仅在本次明确适用的政策下要求。听众反馈、额外用户试用和真人试讲计时不是默认交付门槛；没有安排时不因此阻塞。已有这类实际观察仍如实记录，不冒充人类。

保留已发生的原稿、具体问题、修订和当前稿；按实际风险复核受影响对象，不默认限制为固定一次返修，也不为交付另建实验。当前稿修好可关闭其缺陷，历史失败不回写。仅在主张方法效果或开展内部对照时，另行区分原始稿、首次交付稿与方法复跑，不把人工精修旧稿改名为新方法首稿。

## 实际物理尺寸与净空

成品审查同时读取 [physical-units](physical-units.md)，核对实际 p:sldSz、逐显式角色可见 run 的有效pt，SVG与原生PPT渲染墨迹两层padding。角色不可判记unverifiable，文字覆盖不能代替关系或可读性。当前报告的模型/工程/人类/桌面证据分别标注；不将历史Desktop记录当本轮人类已验。

### Recover an interrupted native acceptance

If native review failed after its owned completion, inspect the failed Task's
`result_refs`, then use `review recover --project <dir> --task-id <id>`.
This resumes acceptance of the exact committed observation, envelope and
original authenticated receipt without another model call. It keeps the original
executor, operation and consumption; cancellation, changed inputs/methods and
expired receipts still reject. A failure before a unique authenticated checkpoint
is committed returns `needs_evidence`; loose JSON is never a recovery proof and
must not be re-signed. An uncertain response after acceptance returns
`already_applied`. `review native` reports `recovery_available` for a failed Task
with committed proof instead of automatically starting another paid review.

### Recheck only the frozen missing units

Preproduction dispatch freezes `review_scope.units` and historical owner refs in
the packet. A notes-only change can require only `speech`; the packet still
contains the complete manuscript, plan, narrative and materials. Submit exactly
those units and separately recheck/replace each frozen owner while retaining its
finding identities. Never use a fresh unrelated pass to clear another owner's
finding. Other still-current authenticated conclusions remain applicable; the
combined current gate, not the partial Task alone, determines manuscript pass.
Legacy Tasks without this frozen scope retain their full-unit coverage contract.

## page_copy 必查：面向本次受众的实际表达

逐页读取 packet.page_copy_checklist 指向的同一 Page Ref，对标题、正文、标签、引用和必要限定做语义审查。notes、content_mapping、Plan 密度说明和方法操作是理解上下文，不能默认上屏。这里使用原有 page_copy review 和 content/privacy finding，不建立另一条审查流程。

| 实际页面与用途 | 应判断的事实 | 原有 finding 的用法 |
|---|---|---|
| 给客户的故障指南写“此处补充三条来源，Owner 稿待压缩” | 制作指令替代了可使用的故障步骤，真实步骤尚缺 | content / must_fix；定位原句、Page/atom及缺失步骤，退回内容补写，不能凭空编步骤 |
| 内部编写培训页展示“此处补充来源”为反例 | 这句话正是教学对象，不是客户材料泄露 | 可合法 pass；说明教学用途，不按词命中处理 |
| 客户研究页写“来源：2025年公开年报；假设汇率保持不变” | 引用和条件帮助读者校验/使用结论 | 保留；不能因“来源/假设”自动删去或标 F0 |
| 给客户的操作视频标“时间码 02:14：先断电再拆盖” | 时间定位与安全顺序对受众有用 | 保留；核对真实视频/依据，不将时间码当内部痕迹 |
| 页面含确实禁止对该受众披露的内部客户名/数据 | 查明材料限制与实际披露，不把正常业务来源混为泄密 | privacy / must_fix；证据明确；授权不明则 needs_judgment |

按实际泄露、用途损失和误导程度分级；不把所有制作措辞都等同严重泄密。记录原句、期待的受众表达、实际用途影响、位置和证据；未知事实留缺口，不用“客户化”名义造事实。合法 pass/findings=[] 必须来自实际完成的可信审查；未执行与空回执不得登记 pass。复审沿原 owner 和 finding_id 关闭，已有可信结果用 review recover 接纳，不能重复模型调用掩盖事务失败。

Page 文本、packet 的 page_ref、设计投影的 page_ref、冻结请求及实际图像必须逐级对应同一有效版本。文本审查与 prompt 检查仅证明各自层；没有实际图像及原生观察时标图像检查 BLOCKED，不能声称客户表达闭环完成。
