# D05 工程与零调用预检

2026-10-30。实现 `0c91beac4668311cc9856cd9608e6beed620363b`。D04 作者原话“认可，两份可继续”已记录，D05 尚未关闭。

## 实现

业务内容项目使用 `content_impact.v2`，逐页区分 affected、needs_reassessment、reusable_after_review、unverified。旧 v1 保持可读，UI 将历史 unaffected 显示为尚未核验，不把来源未命中解释为可复用。输入提交后、重编采用前显示影响及待协调任务入口。

input_revision 冻结完整影响对象及六项任务事实依赖；多次输入修改从实际稿件的输入基准累计判断。新能力 `business-recompile.v1` 协商和 writer floor 阻止旧 Host 接纳新写语义。策略变化要求成对 Narrative/Plan、逐页评估和明确取舍；场景变化不得仅改标题。复用须有旧 Page 和采用 Narrative 证据，正文变化须同时协调已有逐字稿。沿用既有原子采用、历史、取消、迟到结算、原图失效与固定 Narrative 约束。

## 实际检查

- 189 项：business_recompile、content_edit_completion、content_ops、dependency_slices、collaboration_restore、planned_input_revision、variant_requests、input_receipt_recovery、business_framing、business_content_review、content_mapping_claims，29.66 秒。
- 27 项：compose_v2_phases、package_boundary，8.46 秒。共216项。
- 依赖注册表接线调整后，business_recompile 与 dependency_slices 重验25项，6.32秒；与上述重叠，不另计独立覆盖。
- Ruff、git diff --check 通过。新增19项含真实 Chromium/HTTP 界面交互，但内容写入均为明确合成的机制测试。
- 已认可会员六页稿的两个历史快照副本：关闭起点拒绝直接修改，经新有界请求后六页均投影为需要重新判断；活动起点同样冻结准确影响。没有生成调用，正文未改，原项目文件树哈希不变。
- 另一个真实六页副本仅扩大页数上限，使用明确标注的合成 Host 复用判断，经普通接纳入口证明六个 Page Ref 完全保留。此项证明接线和原字保护，不证明专业复用结论。

原项目当前是 review_only 请求；预检关闭起点取真实历史生产关闭版本 `f029506ad05d46ff8728ad943a4501af`。仅在隔离副本定位历史指针，没有伪造关闭状态，没有改变原项目。

## 逐项边界

| AC | 当前证据 | 仍缺 |
| --- | --- | --- |
| AC01 | 活动/关闭起点及同次正文讲稿采用机制测试 | 两起点真实模型重组、独立评价、作者判断 |
| AC02 | 来源依赖投影与旧稿保留；表达修改不自动修改来源 | 生成稿事实忠实度判断 |
| AC03 | 四态/API/UI、缺理由或证据拒绝、六页原字复用接纳 | 专业复用理由是否成立 |
| AC04 | 新 Narrative/Plan/Pages/Speech 原子绑定；沿用版本化审查 | 对实际新稿的独立审查 |
| AC05 | 关闭保护、新请求、失败恢复、连续输入、取消/迟到回归 | 真实重编链路证据 |
| AC06 | 既有 content_ops 原图保留/失效回归通过 | 新实际内容版本的失效清单 |
| AC07 | 内容采用不产生 blueprint/图像任务；新增调用预算不含图像 | 实际模型采用后的任务清单 |
| AC08 | 保留 require_fixed_narrative 调用，variant_requests 回归通过 | 不扩展 live/read 范围 |

详细引用、对象与哈希见 [D05-engineering.json](D05-engineering.json)。本地预检失败也保留：第一次误把当前审查请求当作已关闭生产请求，断言及时阻止；读取真实历史后改用明确历史快照。

## 下一关口

历史32次、D04单列10次均耗尽。D05已用0次；[D05-call-plan.json](D05-call-plan.json) 提议单列最多4次：活动/关闭两起点各一次协调重编、一次独立四单位前审，第一组通过才进入第二组。仅现有 Codex 订阅，无新增 API 付费、无自动重试、无视觉/PPT、不启用D08。

预算未获授权，不启动模型。D03同一v2任务多框架比较仍未验证；D06b等待D05实际内容关口。工程通过不能替代真实商业表达验收。
