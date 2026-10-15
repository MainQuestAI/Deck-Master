# RC3-04 R2 独立行为复审：PASS（限定受影响 installed 行为范围）

固定 HEAD `573a46a85bf93d71a13652756bc3a6cdb1fab6ae`、tree `135769e0b16d6397baa51b5c098425b9a80eb9ff`。本 reviewer 已完成下列有界复验，没有新增 must-fix。**这不是整卡 PASS。** Root 已通知 R2 候选整体仍为 CHANGES_REQUIRED（另一路 F9，以及宽验证尚余 255 unit / 19 render 失败）；这些是 Root 的报告，本 reviewer 未将其冒称自己复现。Owner 正准备 R3，本证据不跨候选签署。

## 身份、来源与不变项

- 产品来自实际安装 `/workspace/work/rc3/candidate-04-573a46a-ready/prefix/.deck-master/releases/573a46a85bf9-13e3d2708abf/venv/`。所有产品探针均使用该安装的绝对 Python、`-I -B`、私有 cwd、短 TMPDIR，无 PYTHONPATH、conftest 或产品测试 helper 注入；未借用旧环境。`env.sh` 仅加载工具链；shell 显式 offline pip flags。`probe_common.py` 是 reviewer 自编辅助，不是产品测试模块。
- 安装 manifest SHA256 `fe17cde02538dece2cd311ec7c103f387ca2471b5b8e05945c5ec043f4a3eaae`；wheel `13e3d2708abf0e18ff387c7a74ca96bf05bf187b050a308f9b1f145232bbe9e0`。module 实际路径、版本 `1.0.0rc3` 与 isolated/no-bytecode 标志保存在 `source-install-before.json` 和 `source-install-after.json`。
- 本 reviewer 比较 Root 固定 source-before 中的 **3619 tracked files**，并自行枚举安装包 **358 files**。前后均匹配，changed tracked / installed paths 均为空。没有产品、产品测试、fixture 或 Git 写入，没有 patch gate。
- Root 的严格四角色 byte 审计另见 `../rc3-04-root-validation-573a46a/install-admission.json`，其 strict report SHA256 `0063a2bf4fd515c6269d1c834c27097448502e064cdd6a3f15504e45ed702cc4`。该结果是 Root 的 PASS_BYTES_ONLY，不是本 reviewer 的真实 Host 应用证明。
- 探针均为 **L1_SYNTHETIC**。call facts / analysis observations 为明确工程合成数据；没有模型、图像生成、外部付费调用、受信 native 或 human 正例。涉及原输出保留的实际 PPTX 仅通过明确 L1 工程关联放入输出 Ref，不能据此宣称生产链路、专业审查或最终交付通过。
- 所有输入脚本、原始响应、事件、before/after 和失败均原位保留；`case-execution-index.json` 不改写原始状态。`immutable-originals-summary.json` 对存在成对全树快照的原对象逐个核 hash；业务改变时允许新增对象，旧对象不能消失或改写。各拒绝全树不写断言的具体输入与结果仍以对应原始探针为准。

## 本次实际受影响轨迹

| 轨迹 | 实际正负预期和结果 | 原始证据 |
|---|---|---|
| C5 空 report / known replay / 补 invocation | 公开 generation dispatch、真实 capability claim、prepared input、allowance begin 后，in-flight/unknown 的 None、空 bytes、空 dict/list、空白均不能 settle consumed；unknown 无 report 不能 release。原非空 Host report 可 settle consumed，保持 host_reported / price unknown。known 无 report、原 report、空 dict replay 无写入。空 report 不能补 invocation，改变 report / 冲突 invocation 拒绝；同一原 report 可补缺失 invocation，仅新增同一 Attempt observation，保留原证据，usage 未捏造数值，只有一份 allowance。补后 replay 与取消后 known replay 均不写。没有真实外部调用。 | `run1/results.json`、`run1/events.jsonl`、`run1/C5-*-before/after.json` |
| 额度用完和 scope 撤销后的费用事实 | spent scope 不能新开 blueprint call，整树无写；显式 revoke 后已知 consumed receipt 的无 report replay 仍可读回，已消费事实与 host_reported 等级保留，不复活 Task、许可或费用。 | `run2/results.json` 的 C5-spent case、`spent-credit-no-new-dispatch-*`、`settlement-after-revoke-*` |
| C1/C2/C3 真实 v2 Plan 与导入稿 | imported p1/p2 上公开 content_ops plan/commit 编辑新增段落，p2 Ref 和原 notes 不变；可见 atoms 有完整空 node/source maps，来源保持 unknown，无伪造 Narrative；真实 content_plan.v2 与当前 projection 可读，固定历史 Plan projection 不改。authored 稿新增无映射 atom 则公开拒绝并保持 Document 不变。 | `run2/results.json` 前两 case、`imported-body-*`、`authored-atom-*`、events |
| 输入协调、取消与恢复、真实 no-change | 公开 inputs 更新后产生 input_revision；claim→cancel→pause，continue 诚实 needs_input 且不新建业务内容；显式 resume 后仅一份新 Task / 新 operation id，重复 continue 稳定。原取消 Task late result 拒绝且不能采用内容；replacement Task 的合法 Plan-only/no-change accept 使 alignment current，保留原 Page refs 与非空实际 PPTX Ref，更新真实 Plan basis。原 inputs 精确 replay；相同 audience 更新为 unchanged，不改变 pages/Narrative/Plan/outputs/tasks/协作状态。 | `run2/results.json` recovery case、`recovery-*`、`cancelled-late-*`、`noop-*` |
| trial no-change 显式采用 | 输入新背景文件 trial：Plan-only 候选在显式 adopt 前不改当前稿和输出，alignment 仍待协调；真实 adopt 返回外层 committed、operation_result.status=adopted。采用后 alignment current，Page refs、原实际 PPTX Ref、Plan input 保留，零 allowance。原 adoption 已成功，不再重复执行 adoption；run3 仅读回原响应/原状态确认。 | `run2/trial-nochange-*`、run2 原 adoption event、`run3/trial-original-adoption-confirmation.json` |
| R2 validator 下四层消费和回滚 | 原 R1 自编公开 composite 正控在 R2 安装重跑：Narrative 实际语句、Plan role/links、Page 正文和 Unicode speech 单业务 parent 真正采用；链接一致且 current。重复 Plan、末层 speech 夹正文均完整 Document 回滚；exact terminal replay 不新建 revision。 | `run3/results.json`、`four-layer-*`、events |
| F8 两种旧形状的合法 speech | 两个明确 L1 历史 fixture：old03 无 mapping；oldR1 honest imported Plan 的 empty roles。实际 describe/apply migration 保留旧 Page bytes、request=null、无批准授权；随后真实 speech_only scope / claim / accept 新建诚实空 mappings，phantom node 拒绝并全树不写；可见 copy/visuals 不变，Unicode notes 写入，旧原件保留，最终 completed，continue 同 revision，无 calls/allowances。这不是公开任意 legacy 注入能力证明。 | `run4/results.json`、`old03-mappingless-*`、`oldR1-empty-roles-*` |
| style 自身输入绑定及只提案 | 实际 reference import/analyze 后，无关正文 edit 不阻止 claim/accept proposal_only，analysis 不改页/outputs。为区分内建零调用限制，显式合法 scope 给 1-slot 额度，analysis 自身仍拒任何 image allowance 且不写；改变实际字体输入后 claim 以 StaleInputContext 拒绝且不写。分析内容为 L1 合成 observations，无视觉质量结论。 | `run5/results.json`、`style-*`、events |

## 原始探针失败没有删除

共 **13 条原始 case 执行记录：9 条有效 PASS，4 条探针断言或前置错误**。9 条中包含一次对原 trial adoption 的只读判读，不当作第二次业务采用或额外独立风险覆盖。

1. `run2` trial case 的实际 adoption 已成功；探针错把恢复性 envelope 外层 status 期待为 adopted。真实值是 committed，内层 operation_result.status 才是 adopted。`run3` 仅读回原响应和原状态确认，原 FAIL 不改写。
2. `run3` F8 helper 假定 request 非 null，在迁移后的合法 request=null 上 AttributeError；修正仅在私有新脚本，`run4` 两种旧形状通过。
3. `run3` style 脚本缺少私有 editing import，NameError；不归为产品错误。
4. `run4` style 初始 scope 额度为零，因此先被正确的 budget_exhausted 拒绝，未命中探针预期的内建 style CallBlocked。`run5` 使用合法 1-slot scope 区分控制，仍被 style 零调用规则拒绝；没有实际调用。

原脚本、traceback、events 与各 run 目录保留，修正脚本单独命名；没有修改产品以使探针通过。

## R1 12 组与本轮边界

R1 原报告 `../rc3-04-behavior-review-round1-7a8578b/report.md` SHA256 `3d1f02f95975b10b001977fae0703684493d42f4eae511b3fa8667a1ba565117` 继续作为 **R1 证据**；不换标签称 R2。

| 原计划组 | 本轮情况 |
|---|---|
| G01 default/首次 visible | R2 未重跑。原 F1 修复反例由 code reviewer 复跑，UI 另一路；本 reviewer 不签这些修复。 |
| G02 migration/all writers | 本轮仅 F8 两种旧形状 migration→speech 的受影响正负样本；非全 writers / 旧安装回退矩阵。 |
| G03 四层原子性 | 本轮实际重跑合法 composite、两个回滚负控、terminal replay；原 F3 来源反例由 code reviewer 复跑；merge/split 仅保留 R1 原证据。 |
| G04 四 intent 完成 | 本轮 speech_only 两种旧形状 completed/稳定 continue；其余三 intent 无 R2 新结论。 |
| G05 variants / 旧版窄 edit | R2 未重跑，不把 R1 samples 跨 head 当 R2 验证。 |
| G06 running-stale 先费用 | 本轮未重复原 still-running stale 样本；新增 C5 receipt/replay/取消撤销边界。没有真实货币或 native 正例。 |
| G07 祖先撤回/最后额度 | R1 该目标 NOT_RUN 仍保留。本轮只测单 grant spend/revoke，不能替代 parent 撤回完整矩阵。 |
| G08 replay/capability/restore | 本轮 real cancel/recovery、known settlement replay、terminal replay；restore/旧 claim 全矩阵未重跑。 |
| G09 lineage/reviewer | R2 未重跑，R1 作者集合证据仍属 R1；无 real reviewer/human 正例。 |
| G10 strict/read-only report import | R2 未重跑；code reviewer 对原失败负责。没有新的外部可信 import/native 声明。 |
| G11 最终文件/政策控制 | 本轮只核实际非空输出 Ref 在 no-change/recovery/trial 中保留；未重新 sanitize、notes policy/currentcontrol/发布竞争检查，不能签完整文件交付。 |
| G12 安装/适配 | 本轮全部轨迹来自固定实际安装且包字节不变；没有重复 CLI/HTTP/UI 宽套件、真实四角色 Host16 或旧 wheel。 |

未运行 broad unit/render/benchmark、完整 Studio、真实 Host16、目标 PowerPoint、专业/人类审查、真实费用、全权限和所有并发矩阵。C4 原 bitmap/render recovery 缺口未由本 reviewer 单独关闭。Root/code/UI/B 各自报告保持原来源和各自结论。

本 reviewer 按 Root 要求停止扩展、冻结此有限报告。只有新的固定候选及明确受影响范围才能开始下一轮；本轮不要求用户材料，不冒充后置 native/human 验收。
