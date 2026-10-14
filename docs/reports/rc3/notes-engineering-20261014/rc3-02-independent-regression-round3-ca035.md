# RC3-02 独立 regression review — round 3

**结论：PASS（本轮独立工程回归范围）。** 在固定 ca0351d 上，三条本人前轮实际失败轨迹关闭；本轮九个模块的 origin 修复没有发现新的工程缺陷。该结论可作为工程复审输入，不关闭 T06 专业 AC、真人/桌面或完整 RC3，也不代替 Root 的最终集成/CI/merge 判断。

Reviewer：`/root/rc3_02_regression_reviewer`，未参与实现。执行日期：2026-10-14 UTC。

## 固定对象与原件

- HEAD `ca0351d2397ba154e9f77363bd0f325629eb0ebd`；tree `05191deede70f26e661b28f4221c3c0d00ef2ecf`。
- 工作树 `/workspace/work/rc3/reviews/rc3-02-code-snapshot-ca035`；Python `/workspace/work/rc3/reviews/env-02-snapshot-ca035/bin/python -I -B` 实际 import 该 snapshot 的 src。已完整读取相对 0b0ed 的九个产品模块及新增测试 delta。Owner live 源码/docs 未混入审查。
- 只读 source/env；未安装依赖、未改共享 bootstrap/生产 fixture/冻结 A。结束时 HEAD/tree 不变，工作树 clean。默认 Python native 路线实际编译与渲染；Chromium 实际运行，node compiler exit 没有执行。
- 新证据独占目录 `/workspace/work/rc3/reviews/rc3-02-regression-round3-ca035-scratch/`，下文文件均相对此目录。
- 前轮报告/失败原件保留：round1 sha256 `73d1a69862eac9af94246c57e52efa1ba6bfec19e15310088588b9577c8fc0c8`；round2 sha256 `b0c1aa7281731820ddd77443456f68f94362c4a4519aa8bf3eba9fc0ba9a73f4`。不将本轮成功覆写成旧 head 通过。

合成 Page/authority/Review/native observation 为 L1；实际 native PPTX、最终下载字节/逐页回读为实际 L6 文件工程。Chromium 技术 UI 检查不等于目标桌面 PPTX 备注视图、人类使用或专业认可。

## 本人前轮失败的关闭证据

| 失败轨迹 | 本轮实际结果 | 证据 |
|---|---|---|
| legacy 首次 produce 后因技术 floor 意外触发另一协议、第二次 produce 失败 | 原 `test_tasks.py::test_no_progress_repair_stops_instead_of_looping` 再次通过，legacy 合法生产/失败 findings/no-progress 保留。原 opt-in v3 的 assembly prerequisite、实际 assemble/replay 与 legacy explicit-stage 拒绝对照也通过。 | `new-notes-pytest.log`、`related-pytest.log` |
| 新 notes-aware 全空 PPTX 的错序/缺页被 export 接受且 ID 丢失 | 直接复制本人原探针到新 scratch/import/head。正确 a/b/c 的最终文件保留稳定 ID；c/b/a 和两页对三 Page 均由正式 export 拒绝，handoff 分别报 identity/count gap。current/原件不改。四个容器的全空矩阵、非空导出与 none/reading 对照通过。 | `empty_notes_identity_probe.py`、`empty-notes-identity-probe.log/json`；相关测试日志 |
| legacy 真实 notes edit 后 `content_ops action=edit` 意外开放并采用可见标题 | 同一个本人正式 create→notes edit→content plan/commit 探针现拒绝，predicate=False、current 不变、可见标题仍“原可见标题”，notes/Task refs 保留。另 action=edit/reorder、legacy/v3、notes 前后四组合正式正反通过。 | `residual_content_edit_origin_probe.py`、`residual-content-edit-origin-probe.log/json`；新正式 regression |

## 九模块修复的实际正反核验

- **content_ops / annotation_service / styles / visual_styles / icons**：legacy notes 技术 floor 不开放内容编辑/重排、意见、风格提案、截图参考或图标提案。原显式 v3 经真实 notes edit 升 floor 后，合法内容写入、意见保存、style propose/confirm、实际 PNG reference import、icon propose/confirm 均成功；Page/notes 与已有 Task 事实不被技术升级伪造。
- **content_production**：legacy notes floor 的正式 compose.v2 speech 派发明确拒绝且 current 不变；真实协作区域的 compose.v2/binding、membership/speech scope 正反通过。原 v3 并不由 floor 自动获得 region、用户决定或授权；真实区域的方向/生产范围、风格/内容资格和撤回后 candidate adoption 门禁仍按适用条件拒绝。
- **web / ui_journal**：实际 loopback HTTP 的 legacy content plan 拒绝；candidate plan/adopt/decision 均 409 `unsupported_project_format`。原 v3 合法 HTTP content plan/commit 与 candidate adopt/replay 通过。`GET /api/project` 的 FORMAT_GATED 投影与实际服务一致。
- **实际 Chromium UI**：两个 notes-upgraded 项目分别为原 legacy / 原 v3；连接面板真实显示对应能力状态。legacy 展开未开放原因后出现“旧格式项目，该动作需要 workbench.v3 项目”，v3 没有错误旧格式提示；两例无 pageerror，current 不变，截图/DOM 文字及 API facts 保留。不是仅私有 helper 布尔值测试。
- **tasks 晚到结果**：真实 cancel 后首次 late result 不采用 Page/output；同 payload 的精确重复在 legacy 按原语义 already_applied，在原 v3 继续拒绝取消后的重复采用。当前 notes 和成本事实保留；style-analysis/icon cancelled-result 对照亦通过。
- **历史不可证明**：缺早期协议记录的 fail-closed predicate 用例通过。另在独占合成项目中暂时隔离真实 parent revision，正式 content plan 及 history predicate 因 snapshot missing 拒绝，current 指针不变；归还文件后原历史/文档可读且 predicate 恢复为 False。没有拿缺历史推断成 legacy 或打开业务入口。

## 本轮实际执行

| 范围 | 实际结果 | 原日志 |
|---|---|---|
| notes transactions 全部、真实 inputs 四时点、受影响 empty/none/public/privacy 文件对照、原 legacy 第二 produce | 49 PASS，8.36s | `new-notes-pytest.log` |
| 独立原协议双轨、HTTP/UI 投影、missing-history fault、late duplicate、notes 后 v3 annotation/style/reference/icon、旧 body start/consumed-result 拒绝 | 11 PASS，1.87s | `independent-pytest.log`；`actual-origin-*`、`http-ui-origin-*`、`late-result-origin-*` JSON |
| real-region compose/scope/direction/withdrawal、实际 v3 HTTP candidate/assembly/replay、sample readonly 与 legacy/style/icon late-result 对照 | 16 PASS，5.07s | `related-pytest.log` |
| 额外正式 legacy compose.v2 拒绝 | 1 PASS，0.21s | `compose-negative-pytest.log` |
| Chromium 实际连接面板双轨 | 2 案例 PASS，0 pageerror，current 不变 | `browser_origin_projection_probe.py`、`browser-origin-projection-probe.log/json`、`browser-origin-*/connection-panel.png` |

本轮 **77 项 pytest PASS**，另有上列真实文件/Chromium/旧 A 独立探针；无产品失败、无 skip。未把不同证明层加成一个测试总数，也未重复全树约 1800 项。

## 冻结 A、费用与证据复用

`frozen_a_actual_refusals_probe.py` 再次使用真实原安装 `/workspace/work/rc3/baseline-a/venv/bin/python -I -B`，实际 module 位于其原 site-packages，未修改 writer 集或用新参数制造语法拒绝。两个本轮受保护项目各 7 CLI + 6 SDK，共 **26 次拒写**；实际文件项目 68 个文件、已有 1 consumed allowance 项目 33 个文件的完整 hash/current/outputs/PPTX 和费用指纹不变。SDK cause chain 全部为 minimum-writer/matching-core，CLI 没有 unknown-option/invalid-choice；旧 assemble CLI 的 operation_unavailable 包装如实记录。证据 `frozen-a-actual-refusals-probe.log/json`。合成 allowance 不能声称真实美元成本实验。

按影响而非测试数量复用本人的 round2 证据。compiler/native/notes 输出净化/handoff/pipeline、visual dependencies、models/Store/history helper、Plan/generation、eligibility/delivery、editing/review/workbench 等 **18 个依赖文件 byte-identical**，记录在 `reused-evidence-source-hashes.json`。本轮另执行了变化的 Task/compose/public-origin/HTTP/UI 门禁及必要文件正反；因此可沿用 round2 对未受影响的 cues/verbatim 六容器、稳定拆合删除/lineage、其余隐私/geometry、固定 variant 与 exact-file professional 谓词范围的自身证据，不将新入口的结论用旧证据覆盖。

## 边界与后续

Root/Owner 另提供 `rc3-02-speech-native-ca035/trace-catalog.json` 的 N08 bound 与 imported_mapping/null Narrative 两条 installed-I 轨迹。它们是 **Owner 执行证据**，未计入本人 workflow run/PASS；本人本轮没有独立重放两个完整组合。其首次工程 compile 已执行，之后补相应 L1 内容 Review 再重编译/导出，不能记成首次先被 guard 阻断。工程编译、审阅副本可用与前审/final/delivery 资格分别判断，编译成功不证明专业批准；未将基线已有 action 枚举差异静态定为本卡新 P1。

本独立 reviewer 仍未执行：node compiler exit、两条 speech 完整视觉/实际文件组合的独立 workflow 复跑、两份 live/read 的完整 native 文件全路径、全入口安装/完整故障矩阵及全 RC3 集成。Owner 已补的证据由 Root 按其归属整合，不冒充本人的运行。

真人 Owner/听众、完整彩排、目标桌面 notes 视图/保存重开、完整 RC3 发布验收继续 **NOT_RUN**。按用户安排后补，不阻止本卡工程集成；Runtime professional policy 未放松。

本报告只支持固定 ca0351d 的本轮工程 regression 复审。未 merge；任何后续代码变更先分析影响，受影响轨迹需按新固定 head 复审。
