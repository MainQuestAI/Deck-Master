# RC3-04 R4 独立 installed behavior 复审：PASS_LIMITED

固定 HEAD `02a6d44da85cf4ecde9d84d4587f648587c41597`，tree `8a12383ab597dbd061ad53de6f5186c5343d19d4`，parent `8223df80be654c9a89a44cd97cf770fa01bf4383`。正式 `run2` 的 **9/9 条有限轨迹通过，未发现 must-fix**。本结论限于 R4-C2/C3 的实际安装软件行为，不代替整卡、Root broad/CI、独立代码/UI review、真实模型效果或人类验收。

## 身份与执行边界

实际执行 Python 是 `/workspace/work/rc3/reviews/env-04-r4-installed-02a6d44/bin/python`，版本 `1.0.0rc3`，使用绝对路径、`-I -B`、私有 review cwd、短 TMPDIR、显式 offline wheelhouse。它是同一 wheel 的独立、非 editable、带固定开发依赖的 **CI-like wheel-installed validation environment**，不是 managed release 激活证明。没有向现有 managed candidate 安装开发工具，也没有切换 HOME、managed current 或 Host links。

wheel SHA256 `76b68e5cbcabc13a643af489df71160dee670bbec518f821687443039e2b345e`；managed manifest SHA256 `79984097ceecbad29a86346fc90179410a9cc0b90027fc779eef6a02f01c23f5`。Root 的严格报告 `b36887af47e1027f0ece811e8687820d2646145d057ac930c02365ecf4d6c314` 仅引用为 270 canonical + 1 generated / 四角色 PASS_BYTES_ONLY，不冒称真实 Host 应用或专业评审。

正式 run2 前后，本 reviewer 独立读取全部 **3935 tracked 文件**，并与 Root fixed baseline 逐项比较；HEAD/tree/status 均保持精确身份和 clean。validation 包与 managed 包分别枚举 **358 个文件**（包含原有 bytecode），正式探针前后均逐文件相同。两份完整 identity JSON 逐字相同，SHA256 均为 `17f626631c1fcbc97a8f86daedd1e748dbe80d808c5f22e5c5793d8ddbd1db72`。

首先实际预载了 33 个 installed deck_master 模块，之后才显式追加只读 `tests/rebuild` helper 路径，用 `_deck_with_pages`、`icon_store.__wrapped__` 等具名 helper 构造明确的 L1 合成输入。没有导入 source core、PYTHONPATH、pytest/conftest 或 monkeypatch；helper 内实际调用的服务仍为 installed core。最终审计 **55 个 deck_master 模块 origins 全部位于该 validation site-packages**，记录见 `run2/runtime-origins.json`。没有运行 imported test 函数或完整 suite。

## 正式实际轨迹

| Case | 实际观察 |
|---|---|
| C2 distinct authored reason | 真正 dispatch/claim compose.v2 input_revision，并通过 public accept_result 采用。impact_summary 与含中文引号、内部双空格、换行和 emoji 的独立 unchanged_reason 分别保留，二者不同。Page/output/Narrative/源材料/原质量记录/策略/权限不变；无额外调用。 |
| C2 old summary fallback | 不提供 unchanged_reason 时，真实回执使用原 summary，原有 envelope 继续成立。 |
| C2 proposal_only | 真实 proposal-only workorder 返回 adopted=false，独立理由仍在回执；当前 Page、Plan、content_basis、output 和权限保持不变。 |
| C2 五项 invalid | 显式 null、空串、空白换行 tab、object、array 各自通过 public accept_result 以 EnvelopeError / concrete reason 拒绝；每项拒绝前后完整项目文件树、Current 与 Document 逐项相同。 |
| C3 corrupt icon Task | 在自建、明确零 image-call 的 L1 icon 项目中，实际完成当前请求、方向、bounded grant 与 host_self fidelity 协议，派发真实 icon repair Task，然后故意损伤其历史对象 bytes。没有修复、重写或跳过损坏对象。 |

按三个 C2 正例、五个 C2 反例和一个 C3 场景计 **9 条**；下述重放和读控制是各轨迹的内部断言，不另外扩增通过数量。

三个 C2 正例均进一步实际提交 exact terminal replay，返回 `already_applied` / `same_revision=true`，revision、result_refs、impact_summary、unchanged_reason 全与第一次回执相同，完整项目树无任何变化。随后使用同一 terminal operation 但改变理由，均实际拒绝，原回执和完整树保持不变。所有旧 immutable 文件的 hash 保持不变，只有首次真实采用所需的新 Task/Plan/revision/operation 对象和 Current 更新；不是“首次采用零写入”。实际 changed Document fields 清单见 `C2-actual-field-delta.json`。理由没有新增独立核实的业务事实、源材料事实或权限；普通 Task 完成和采用事务事实正常登记。原 `results.json` 的 `new_fact_or_authority_created=false` 仅具有前述业务/权限意义，不应解释为没有事务事实。

理由按当前实现做首尾 whitespace trim；本次保真正例测试原文内部空格、换行、Unicode，而不声称首尾空白逐字保留。旧 summary 同样 trim。没有因 invalid reason 重新解释或弱化来源/映射/scope 校验。

## C3 损坏对象后的准确判据

健康同项目最初 preproduction satisfied=true。损坏真实 icon Task 后，安装的 `eligibility.preproduction_state` 返回 `status=unreadable`、`satisfied=false`、全部 required units 为 missing、satisfied_units/review_refs 为空、via=null，并明确 preserve/inspect 原件。`collaboration.describe` 与 `ui_journal.project_info` 都实际成功返回原 revision；dispatch.blueprint blocking card 明确 allowed=false / unreadable。`icons.listing` 的原提案仍为 `dispatch_unknown`。

随后直接调用 installed strict `production.resolve_page_rendering_design`，仍以 ModelError / generation lineage 拒绝；没有 skip bad Task 或 fallback。公开 `pipeline.produce` 实际以 `preproduction_blocked` 拒绝，decision.preproduction 明确是 unreadable。所有只读调用和 production 拒绝后，完整项目树、坏 bytes、Current、旧 refs、授权和费用事实保持不变，零 image/provider 调用。

公开 delivery export 也实际拒绝，但它遇到的判据仍是该项目原有的 `decision_needed`（并伴随实际权限缺口），不是独立验证新的 unreadable delivery 规则。本 reviewer 没有补造 delivery acceptance、native quality、人类专业证据或输出以越过这个缺口；不把此结果扩大成新的 delivery 门禁证明。两次公开拒绝都没有产生 bundle/临时发布或项目变化。

## 原路径的精确复用

`precise-reuse.json` 记录 **18 个 installed/source/parent module bytes 三方相同**，包括 production、tasks、service、content_ops、collaboration/binding/budget、method_resources、run_desk、exports、store/models 等。另对 content_production 与 eligibility 做完整 top-level AST 比较：各自只改变 `_accept_input_revision`、`preproduction_state`，其余所有 top-level 节点 AST 相同；installed bytes 与 fixed source 相同。全部产品 delta 精确为这两个 Python 和 C1 三个 UI JS。原 F1–F9 健康路径仅复用既有有限证据与其原身份，不宣称在 R4 新跑过；R4-C2/C3 改动分支由本次实际轨迹覆盖。未重复原 16 Host 流程或 Root 的 unit/render/browser 矩阵。

## 原始失败与未运行边界

本 reviewer 最初的探索命令误用 Root JSON 的 `tracked_files` 键（实际为 tracked），以及最初 identity capture 使用非 NUL 的 git ls-files，导致中文路径被 Git 引号转义后无法读取。均是 reviewer 作者错误，不是产品缺陷。第一次 capture 失败时，shell 继续完成了 run1 的原 9 条探针，全部通过，但该轮没有完整的 reviewer 前置身份捕获，所以不作为正式 9/9 的身份依据。原 capture 脚本、traceback `capture-before.log`、run1 原脚本/日志/项目/结果全部保留；没有删除、覆盖失败或把其改记为产品 PASS。改为 `git ls-files -z` 后成功捕获 before，再只运行原九条有限轨迹到 run2，最终 after 完整相同。初次探索 KeyError 的工具输出存在于本轮对话；下方原件说明记录事实而不冒充额外原始日志。

没有更改核心、源码、测试、原项目、现有安装或 SDK validator；所有私有项目/日志只在本 review 目录。所有业务材料、Host claim、fidelity 记录均明确 L1_SYNTHETIC；没有受信 native/human context、伪平台回执、真实模型/imagegen/provider/付费调用、桌面 PowerPoint、实际人类或端到端效果实验。与本报告同目录的项目 Store 仅供原始工程追溯；交接时应只选择安全报告/日志/清单，不将 Store 或任何 runtime key 当交付件复制。

本次有限行为复审完成，停止扩展。整卡接纳与合并由 Root 汇总新的 fixed suites、各独立 review 和 exact-head CI 后决定。
