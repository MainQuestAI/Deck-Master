# RC3 普通功能接续：审阅、预算与交接

2026-10-17。用户明确要求先完成普通开发，暂挂旧效果实验。原 S12/S14–S19 实验原件缺口不再作为普通产品开发的前置条件；历史失败、预算、对照和验收签名仍保留。操作全部在云端，未操作用户 Mac、激活日常安装、合并或发布。

代码快照为 `f9ebfbf98ee704d8784da72eae0ffece600d1562`，接续 `21c3bc34`。后续仅证据文档提交的最终 head、完整 CI 和独立安装身份以 PR120 当前检查及交接清单为准。本记录登记时最终 head CI 尚未执行，不使用旧 head 的绿灯替代。

## 实际功能修复

- `0cc54a7d` 修复严格审阅的消费端：切回独立要求后，旧自审或自报独立名字的 PASS 不能用于生产。正式接收的 Task receipt 与外部 import commit/report 绑定仍可使用，不要求原 provider 一直在线；当前稿件及来源依赖照常核对。
- `fd6b5631`、`c4e40606` 将整套初次预算与局改重建预算接入现有 grant CAS、CLI、HTTP 和网页。依据真实已采用 Plan / 不可变 ChangePlan 计算，正式 Task 绑定每页 credit；已有调用账本是唯一调用事实。保留显式数额模板，不把 `explicit` 当成计算模板。
- 网页局改直接从已完成的修改影响预览带入方案，无需手填内部编号。预算提交后读取新版本、保留要求、重新预览并创建候选交接，真实浏览器走到两项 `awaiting_host`，没有图像调用。修复了该路径在无具体 targets 的项目重读中报 TypeError 的故障。
- 空 pages、空 scope 对象或 null scope 不能扩成全部页。固定 manifest 父授权可以合法物化；固定全套 manifest 与显式单页要求冲突时明确拒绝，不忽略单页要求扩大范围。合法可复用原图还需当前内容、文件及设计依据相符。
- 候选上限从已有 trial Task / candidate_refs 派生。合法的两槽可先同时派发；超额批次整批拒绝。取消尚未产生候选的任务释放槽；已有候选在采用或恢复后仍占原槽。达到上限不影响最后结果接收、回执重放、查看和有权限的采用。
- gate 和 Task binding 使用同一个满足本次数量的授权选择；零调用父委派及旧零额 execute 不遮挡新合法 execute。已绑定 Task 不借用别处的大额授权。一个批次固定使用实际检查过的同一授权，不再逐页误选旧小额授权。
- `f34636db` 修复当前中间父额度：同身份缩小父上限后，子任务的新 reserve 读取当前上限；已合法持有的最后调用仍可 begin/settle。替换同身份授权不能把历史调用或候选消费转挂到另一个数字预算根。
- `8490c8ff` 区分从未授数额的零调用规划委派与已有数字额度降为零：沿原数字父链、权限父链、替换历史和当前头核对，旧引用也不能把降额后的预算重新变大。只读预览显示既有较小上限，重复授权不刷新额度。
- 仅候选授权不能被 Runtime 自动提升为采用当前稿的任务；派发原子拒绝且不预留调用。合法 trial 仍能接收真实候选，明确 `within_scope` 的自动制作照常更新所选页。旧任务接受也重新检查当前采用权限。网页区分整套/直接修改与试作的采用方式。
- `f9ebfbf9` 补齐新预算预览的 CLI、HTTP 和 adapter 精确只读入口登记。grant 仍是唯一授权写入 CAS，未用只读豁免覆盖任何写入口。
- 全量回归随后发现 Task 的文档 schema 镜像漏同步已实现的可选 `budget_key`，现与 Runtime 字节一致；独立增量复审通过，`required` 不变，package-boundary 5 passed。首次失败保留在 `contract-mirror-before.log`，见 `contract-mirror-independent-review.md`。

此前网页 notes 四种选择、预检/未知响应恢复、正常显式自审选择和 classic 新版 Plan 展示继续保留。本轮没有内置或伪装 LLM provider；没有独立通道时仍返回可读稿与真实缺口，仅用户的明确选择可以改普通前审方式。人类专业交付政策未降低。

## 实际运行与边界

普通新建脚本使用 public `create/continue/task_start/accept_result/record_decision/adopt_proposal`，没有重置 collaboration。已真实走过：材料 → framing → argument proposal → 等待方向确认 → 明确决定并采用 → 两页完整 Page/Plan/notes → 缺独立 reviewer → 明确自审 → computed budget → 两个不同逐页 credit 的 blueprint Task → 调用前取消 → 恢复严格要求并拒绝旧自审 → 可读审阅导出。

这是 **L1 合成输入的正常 SDK 软件流程**，内容由验证脚本明确提供，实际模型和图像调用为零。它证明程序流程可用，不代表实际模型已完成整套写作/生图。单独的用户样稿使用自主编写 SVG，经公开 native compiler 实际生成可编辑 PPTX，真实 LibreOffice 渲染与逐页 notes/text 回读；没有伪造生产项目的 readiness 或 professional PASS。`70c7d07d` 的全新隔离 candidate 已 ready（未激活），其 own-package 普通主链、样稿编译、真实渲染和 notes/text 回读均重跑 PASS。后续仅镜像文档变化的最终 head 仍会重建准确的 source manifest。

本地证据位于 `/workspace/rc3-product-tryout-20261017/`；独立证据在 `/workspace/rc3-recovery-20261017/`。生成项目、虚拟环境、原件和运行凭据不入仓库。

## 验证与保留的首次失败

| 记录 | 实际结果 |
|---|---|
| 严格审阅 Root 回归 | 126 passed；独立消费端复核 4 passed，见 `strict-consumption-independent-review.md`。首次恢复 strict 的 `qualify.allowed=True` 失败保留。额外 human 自报负例被既有 schema 拒绝，不冒充合法接收正例。 |
| 核心合流 | 168 passed / 38.05s，涵盖严格审阅、预算、scope、binding、eligibility、候选。 |
| 网页/预算/选择合流 | 116 passed / 24.16s，含真实桌面/窄屏预算、完整网页局改交接及两种批量授权选择。该轮早于最后 explicit/中间父上限补修，不能替代最终独立轮次。 |
| 最后定向补修 | explicit 数字模板 1 passed；当前祖先/预算根稳定 3 passed。其前独立复现两项 ancestor FAIL 保留。 |
| 最终独立组合 | R6 单轮 114 passed / 46.61s，26 文件运行前后 hash 一致；含真实桌面/窄屏/局改交接、7 个祖先边界、5 个采用权限 SDK 流程与入口登记。见 `budget-candidate-independent-review.md`。 |
| 零父与采用首次失败 | 独立 fresh-root FAIL 及 candidate_only auto 修改当前 SVG 的 FAIL 保留。R4 独立组合 112 pass/2 个公开错误接口断言不正确；仅修复测试的公开错误类型匹配后，R5 5 pass，再收 R6 完整终态。不同轮次不拼接。 |
| 新入口与既有验证准备 | 漏登记的预算预览导致 inventory 负例报警，已补真实只读分类；纯 task.start 旧 child 数额超过零 parent，以及交付失效测试未授候选槽，分别改为零调用准备、公开显式授予单个试作槽，原业务断言保留。定向 50 passed。 |
| 预算早期轮次 | R1 36 pass；R2 41 pass/1 非法 fixture kind；R3 43 pass；R4 127 pass/1 网页新版本读取失败，R5–R9 诊断原样保留；R10 4 pass，实际定位并修复项目重读的空 targets 错误。不同轮次不拼成单轮通过。 |
| 本地全单测初轮 | 主动中断于 477 pass/1 fail/559 deselected；该唯一失败为纯 design.propose 范围测试的旧 child calls=1 超过 parent=0。只将其纯设计 child 设为零调用，保留原 scope 断言，独立数字超额负例仍在。该中断轮不是完整通过；最终完整 CI 必须另收终态。 |
| 隔离安装首次离线轮 | 13 passed / 1 failed / 47.48s；真实 wheel/sdist 安装链通过，唯一失败为构建后 HEAD 从 8490 切到 f9eb，清单检查检测 source_sha 不一致。冻结 `70c7d07d` 后清单检查重跑 1 passed / 3.42s，不改测试预期。 |
| 本地全单测后续诊断 | R2 因命令入口未带仓库工具路径而 collection error；改用 python -m pytest。R3 在修正上述登记和验证准备前为 881 pass/11 fail/3 error 后中断，其中隔离安装依赖下载因云端 DNS 失败，view_url 曾为 null、定向重跑通过。完整 CI 仍需最终 head 全量终态，不能用这些诊断轮替代。已从官方 PyPI 下载依赖留作新隔离安装的离线副本，未改测试安装预期。 |

完整源代码独立复审见 `budget-candidate-independent-review.md`。Root 独立检查协作者实现的预算主体，并通过额外真实空页 scope probe 找到扩大范围缺陷；协作者独立检查 Root 的严格消费、候选数量、授权选择、批次绑定和祖先修复。结论仅为所列修复的有限工程通过，不代表整份 RC3 的实际效果或 Owner 签结论。

## 交付与后续试用

普通功能入口和直接安装/启动步骤见 [RC3 功能进度与试用](../../../rc3-tryout.md)。可先试读审阅包；实际制作仍由接手工作单的制作工具提供能力。

37 AC、13 CQ 的唯一台账仍是 `../evidence-ledger.json`，原状态、Owner 和签名不改：37 AC 为 2 PASS / 10 BLOCKED / 25 NOT_RUN，13 CQ 为 1 PASS / 3 BLOCKED / 9 NOT_RUN；正式 candidate 身份空、release 为 NOT_RUN。本轮工程补修单独登记，不把这些历史数量当成功能完成百分比。

待实际使用检查的项目是：真实 Host/图片工具的端到端执行、页面观感与长稿质量、现场版和阅读版整体效果、Owner/听众及计时、目标 PowerPoint 打开/编辑/保存重开和适用 professional 证据。旧实验如以后恢复或新建合法运行，必须分别登记，不用本轮 L1 软件验证补原对照。
