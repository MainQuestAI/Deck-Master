# RC3-02 独立 regression review — round 2

**结论：REQUEST_CHANGES。** 本轮独立复跑证明初版两个具体失败轨迹已修复，但正式 `content_ops edit` 仍能因 notes writer floor 意外取得原未启用的入口并修改当前正文。不能合并此固定候选；下一轮必须审新 head。

Reviewer：`/root/rc3_02_regression_reviewer`，未参与实现。执行日期：2026-10-14 UTC。

## 固定身份与原件

- HEAD `0b0ed2a85581652fc63ebcbe95bec6fc7fb3f343`，tree `a306e063e8bd93365f1406cd9004c454c3dda3b4`。
- Snapshot `/workspace/work/rc3/reviews/rc3-02-code-snapshot-0b0ed`；专用 `/workspace/work/rc3/reviews/env-02-snapshot-0b0ed/bin/python -I -B` 实际 import 为该 snapshot 的 src，Python 3.12.14。完整读取相对 27823c5 的 12 个路径 delta，未读取 Owner live docs 作为冻结实现。
- 只读 source/env，未装依赖、未改共享 bootstrap。默认 Python native 路线实际编译/渲染；未执行 node artifact-module 路线。所有新增探针/日志在 `/workspace/work/rc3/reviews/rc3-02-regression-round2-0b0ed-scratch/`。
- 初版报告未改，sha256 仍为 `73d1a69862eac9af94246c57e52efa1ba6bfec19e15310088588b9577c8fc0c8`；原始失败与 round1 日志保留。结束时此 snapshot clean。
- 合成 Page、authority、Review、native observation 为明确 L1；真实 native PPTX、最终下载字节及逐页回读为实际 L6 文件工程。imported seed 与 synthetic human adapter 不升级为正式 import E2E 或真人验收。

## 未关闭 P1：content_ops edit 仍把 notes 技术 floor 当原 workbench 入口

本轮独立使用 **edit** 动作复现，未取用另一位 reviewer 的 reorder 探针或运行结果。

1. 正式 `service.create` 创建未 opt-in workbench 的单页 legacy 项目；schema-valid `content_operation_input.v1/action=edit` 的 `content_ops.plan` 原先拒绝：`content operations require a workbench.v3 project`。
2. 正式 `editing.edit_page` 仅增加 speaker_notes，产生 `minimum_writer=rc3.v1`。真实 `Store.workbench_protocol_required(current)` 仍为 **False**，未伪造 region、迁移或授权。
3. 相同项目使用正式 `content_ops.plan → content_ops.commit` 修改可见标题，**成功采用**：current revision 改变，标题变为“新可见标题”，新 notes 保留，Task refs 不变。

`content_ops.py:25` 仍只检查当前 `compatibility.project_format`，而 writer support floor 已把该字段写为 workbench.v3。新 Store history predicate 在已修改入口成立，却没有覆盖这个公开业务入口，导致原本拒绝的操作仅因 notes 编辑被开放。应修复原协议资格的一致入口，不降 writer、不新设 legacy 逃生开关，也不为 legacy 自动制造 collaboration 控制。

证据：`residual_content_edit_origin_probe.py`、`residual-content-edit-origin-probe.log`、`residual-content-edit-origin-probe.json` 与 `residual-origin-project/`。这些是我本轮实际执行的正式写入和 before/after；已直接报告 Root/Owner，未修改产品修复。其余未在本轮独立执行的潜在 origin 入口不写成已验证安全。

## 两个初版轨迹的独立复审

| 初版失败 | 0b0ed 本轮实际结果 | 原始证据（相对独占 scratch） |
|---|---|---|
| legacy create → 首次实际 produce → 修复接纳 → 第二 produce 被 PageVisual/svg_preview gate 阻断 | 原 `test_tasks.py::test_no_progress_repair_stops_instead_of_looping` 现通过；真实 legacy 生产继续按其原协议，仍保持失败 findings/no-progress 语义。明确 opt-in v3 的 assembly prerequisite、实际 assemble 与 replay 正反例亦通过。**此具体轨迹关闭**，不代表全公开 origin 入口关闭。 | `new-notes-pytest.log`、`related-pytest.log` |
| 全空 notes-aware 输出错序或 2slides/3Pages 被正式 export 接受，final ID 丢失 | 直接复用我的初版实际 native 文件探针，仅改冻结 import/scratch/head。正确 a/b/c 成功且 final ID 完整；c/b/a 及 2slides/3Pages 正式 export 拒绝；handoff 分别报 identity/count gap。原件/current 不变。**此具体轨迹关闭**。 | `empty_notes_identity_probe.py`、`empty-notes-identity-probe.log/json` |

另实际执行本版新 4 容器 × correct/wrong-order/wrong-count 全空文件矩阵；pptx_notes/both/pure_reading/separate_script 均验证完整来源身份，再按策略清理或投影。非空 cues/verbatim、none 原注保留、显式 reading 清理、独立 script 无 PPTX 及旧空注窄历史兼容对照通过；未把 none 解释为删原注。

## 实际执行范围

| 执行 | 实际结果 | 日志 |
|---|---|---|
| 新三个 notes 文件全套（含新 origin/空 notes/ID 隐私用例）＋原 legacy 二次 produce 失败轨迹 | 101 PASS，15.64s | `new-notes-pytest.log` |
| changes/candidate 正式 plan/commit/claim/adopt/CAS/replay；v3 assembly 与 legacy explicit-stage 拒绝；ContentPlan 正式能力/接纳/replay/inputs；speech、variant、versioned export/current-control、四个人类/文件绑定 gate、geometry/readback、bound speech | 61 PASS，8.69s | `related-pytest.log` |
| 独立原协议实际 create→notes edit→blueprint dispatch/claim→input update 双变体；独立 body-change 旧任务 start / consumed-result accept 拒绝 | 4 PASS，0.38s；3 个 imported fixture marker warnings，未 skip | `independent-pytest.log`、`actual-origin-*.json`、`formal-body-refusal-*.json` |

本轮 pytest **166 PASS**；上表之外的独立 `content_ops edit` 探针形成真实产品 FAIL，因此卡结论仍为 REQUEST_CHANGES。未重复全树约 1800 项，未沿用他人 PASS 代替本轮执行。

新 Store/protocol/service 增量的独立实际双变体显示：两个原格式都因真实 notes edit 升到 rc3 floor；legacy predicate=False，正式 blueprint 不加 generation protocol/claim time，workbench predicate=True且仍要求匹配的 protocol/capability 声明；后续 legacy 普通 inputs_update 不变成 compose.v1，v3 recoverable update 保留 compose.v1。legacy recoverable 输入入口拒绝且 current 不变。已跑的 changes/candidates/Plan/explicit-assembly 正负例和缺历史的 fail-closed predicate 用例通过；这些不能消除上面的漏入口反例。

## 隐私与旧 A：本轮独立执行

没有将其他 reviewer 的修复结果或绿灯转成本人证据。

- 本版 private-ID 8 变体正式回归已执行。另用不同显式合成 `sk-INDEPENDENT_SYNTHETIC_CANARY_00001` 作为 Page identity，在真实编译文件的 pptx_notes/pure_reading/separate_script 三次正式 export 独立复测：均 `export_privacy_blocked`，客户目标目录不存在，current/原件不变，内部原始 ID 保留。合法中文、路径/token/Bearer 与隐藏 metadata 旧正反例也已实际重跑。证据 `privacy_projection_probe.py`、`privacy-projection-probe.log/json`。只证明可识别模式，不声明通用 PII 检测。
- 真实冻结 A 的 `/workspace/work/rc3/baseline-a/venv/bin/python -I -B` 仍从其原 site-packages 加载，未修改安装、writer 集或 flags。两个本轮受保护项目分别执行 7 个真实 CLI 和 6 个 SDK 入口，共 **26 次拒写**。实际文件项目 **68 个**、已有 1 consumed allowance 项目 **33 个**文件 hash/current/outputs/费用指纹不变；全部 SDK cause chain 明确 minimum-writer/matching-core，CLI 没有 unknown-option/invalid-choice 拒绝。旧 assemble CLI 仍包装 operation_unavailable，匹配 SDK 原因据实记录。证据 `frozen_a_actual_refusals_probe.py`、`frozen-a-actual-refusals-probe.log/json`。消费调用属于合成 L1，不宣称真实美元成本实验。

## 仍未执行与下一轮

初版明确的未执行组合继续保持 NOT_RUN：node compiler exit、bound/imported speech 两者分别串联全部已完成视觉与 assemble/export 的完整组合、两份 live/read 的完整实际 native notes 文件全路径、全入口/安装与完整故障注入矩阵。已有字段/映射、正式 speech 接纳、编辑 full-file 链和 variant L1 的本轮通过不替代这些组合。

真实 Owner/听众、完整彩排、目标桌面 notes 视图与保存重开、完整 RC3 发布验收仍 **NOT_RUN**。按用户要求开发后补，不阻止工程修复/下一轮复审；Runtime professional policy 未放松。

Root 提供新 head/tree/env 后，下一轮至少复跑本轮新增 `content_ops edit` 反例和公开 origin 入口修复 delta、两条初版原失败及 affected 正反例、旧 A 拒写/费用不变。保留本轮原件，不把新候选成功覆写为 0b0ed 已通过。未合并。
