# RC3-02 独立 code review：第二轮 0b0ed2a

**结论：REQUEST_CHANGES。** 初版两项 P1 的指定反例已独立复测关闭，空备注的最终文件身份检查也按预期生效；但原始协议来源 gate 尚未覆盖全部新 workbench 写入口。一个仅被提升 notes 技术 floor 的历史项目可以正式提交重排、意见和截图参考，因此当前固定版本仍不满足工程 merge 条件。

Reviewer：`/root/rc3_02_code_review`，未参与实现。日期：2026-10-14 UTC。

## 固定身份与审查范围

- HEAD：`0b0ed2a85581652fc63ebcbe95bec6fc7fb3f343`；tree：`a306e063e8bd93365f1406cd9004c454c3dda3b4`。
- 快照：`/workspace/work/rc3/reviews/rc3-02-code-snapshot-0b0ed`；绝对执行器：`/workspace/work/rc3/reviews/env-02-snapshot-0b0ed/bin/python -I`。
- source `work/rc3/env.sh` 后始终使用该执行器；独立探针核对实际模块来源为新快照。只读审查 initial `27823c5` → fixed `0b0ed2a` 的全部 12 文件 delta，继续追踪相关公开入口中的旧 format 判定。没有读取 Owner 后续 live 修复作为此 HEAD 已通过的依据。
- 独占 scratch：`/workspace/work/rc3/reviews/rc3-02-code-round2-0b0ed-scratch`。未装依赖、未启动共享 Node bootstrap、未改 source/raw/ledger、未 commit/merge；`git diff --check` 通过，快照 working tree clean。
- Round 1 报告未修改；本轮核对其 SHA256 仍为 `37e9d155ddff439f6af5b2ee0142b476ddfd303c6e8c2928559d35d2bd2f67ee`。初版失败保留，不改成首次通过。

## F-CR02-03 / P1：共享来源 gate 未贯通全部新 workbench 写入口

**实际复现**定位：`content_ops.py:25`、`annotation_service.py:95`、`visual_styles.py:90`。三处仍只读取当前 `compatibility.project_format == workbench.v3`，而没有采用此次新增的 `Store.workbench_protocol_required`。notes-only 写入仍需技术 floor，所以其 current 的格式字段会是 v3；该字段本身无法证明原始 opt-in/迁移事实。

正式服务反例 A：对无 compatibility、无协作 region 的历史协议项目，`content_ops.plan(reorder)` 在 notes 修改前明确返回 `content_invalid: content operations require a workbench.v3 project`。随后只经真实 `editing.edit_page` 修改 speaker_notes。此时实际：

```text
minimum_writer = rc3.v1
Store.workbench_protocol_required(current) = false
collaboration = null
content_ops.plan -> 成功
content_ops.commit -> committed
Document.pages: p-a/p-b -> p-b/p-a，current 实际推进
```

正式服务反例 B：同类历史项目在 notes 修改前，`annotation_service.save` 与 `visual_styles.import_reference` 分别明确拒绝新 opinion/screenshot 写入；真实 notes edit 后，同一共享来源判定仍为 false、region 仍 null，两条公开服务却均提交成功。最终 Document 实际保存了一个 annotation 和一个 screenshot reference。

证据为独占 scratch 中 `probe_residual_content_ops_origin.py/.log` 和 `probe_residual_opinion_reference_origin.py/.log`。所有内容、指令与 PNG 均显式合成 L1，没有手改来源 history、没有 patch gate、没有伪造人类/用户身份。因而这不是仅凭 helper 返回值作出的推測：以前被格式边界拒绝的公开写事务，确实由 notes floor 单独解锁。

**静态同类遗漏，未冒称实际复现**：`styles.py:58` 的 style proposal、`icons.py:277` 的 icon proposal 仍用 current format；`ui_journal.py:95` 与 `web.py:188` 的 format 投影/防御判断也未反映真实来源。样式/图标提案所需全部合法 artifact 初态未在我的本轮另行构造，因此记录为需要跟踪的同根因消费点，而不是新增两项已执行失败。

另外，`content_production.build_phase_task` 虽还含 format 检查，但其 compose.v2 构造继续需要实际协作 binding/control region，不能只凭该行认定已可越过 region；本报告没有把它列作已证实 bypass。

修复建议：统一所有原本明确要求 opt-in workbench.v3 的公开 write/plan/confirm/import 入口使用同一来源判定，并同步 UI 的真实能力投影。不能由 notes floor 扩充协议能力、不能降低 writer 或添加 Host 可选 legacy 开关。明确迁移/原 opt-in v3、真实 region 继续原完整权限、scope、暂停/撤回、费用及质量门禁。补每个实际遗漏写入口的 notes 前拒绝/notes 后仍拒绝及合法 v3 正例；单独保留 current-control/CAS/幂等对照。

## 初版两项 P1 的独立复审

| 初版项 | 本 reviewer 实际复测 | 局部结论 |
|---|---|---|
| F-CR02-01，legacy notes 后误 Stage gate | 原有三页合法 SVG 初态，真实 notes-only edit 后调用默认 Python native `pipeline.produce` 两次；两次实际 native/readback 均 pass。最终 PPTX notes 完整对应 edited Page，原 SVG Ref 与 Task Ref 不变，来源仍 legacy、region 仍 null、floor 保持 rc3.v1 | 指定编译失败反例已关闭；上述遗漏的新协议入口仍阻断本 HEAD |
| F-CR02-02，公开 ID 隐私漏扫 | 使用与初版相同的合法 sk-合成 canary page_id，普通合法标题和 notes；正式 create→export，对 pptx_notes/both/pure_reading/separate_script 四容器均返回 export_privacy_blocked，无公开输出目录，也无可下载 manifest，源 current 不变 | 指定泄漏反例已关闭；正常容器/中文 notes 正例仍通过 |

证据：`probe_round1_fixes.py`、`probe_round1_fixes-final.log`。最初探针给了不符合现有 export-id 格式的 reviewer 自造 ID，旧 API 正确返回 invalid_export_id；该 harness 失败原日志 `probe_round1_fixes.log` 保留。修正的只是探针 export ID 与隔离运行目录，产品仍为同一固定 0b0ed HEAD。

## 空备注的实际最终文件身份对照

运行新用例中的正确/错误页序/错误页数 × 四容器：合法三页全部空 notes 的最终 PPTX 仍保留 p-a/p-b/p-c；错误次序或 2 slides/3 Pages 的实际原生文件被正式 export 拒绝，handoff 标明身份/策略缺口。没有使用“文字都空，所以相等”放行。

另独立构造实际三页全部空 notes 的 PPTX，分别删除一个 slide.name、重复 page ID、改成不属于当前 Page 集的合法 ID，并在明确 adversarial seeded output 初态登记其实际 bytes 与完整 notes-aware dependencies。走正式 export/handoff：**3 类错误 ID × 默认与四种显式容器，共 15 个负例**，全部 export_privacy_blocked、无公开目录，handoff 均有 candidate_notes_page_identity_mismatch，原件与源 current 不变。证据：`probe_empty_notes_ids.py`、`probe_empty_notes_ids-final.log`（第一次日志 `.log` 同样保留；final 追加逐次原件字节不变断言）。这是实际文件身份边界测试，不称正常生产 E2E 或内容/视觉通过。

## 本轮实际执行与限制

两个 pytest 命令分开记录，不拼成一次总跑：

| 命令范围 | 实际结果 | 覆盖 |
|---|---|---|
| notes_transactions + notes_files 定向 | **40 PASS / 26 deselected，7.21s** | 原协议来源/floor、不启已修新入口；全空 notes 正确/错误 count/order 四容器；ID 隐私正反；正常 Policy/容器及实际 pipeline 到 export |
| candidates/eligibility/visual_inputs 指定对照 | **8 PASS，2.92s** | 原 opt-in v3 缺前置/未审视觉 Stage 拒绝、明确 legacy Stage 不迁移、真实 Stage 过 gates 后实际编译和精确 replay、实际 region 的 output scope 拒绝、撤回不复活、imported/null Narrative notes basis 保留 |

日志分别为 `rc3-02-code-round2-0b0ed-focused.log` 和 `rc3-02-code-round2-0b0ed-controls.log`。Owner 的 123 定向/88 文件及其他 reviewer 的结果不记为我的执行。

静态核对新增 Store predicate 的 rc3 ancestry 遍历、missing/cyclic history 错误、真实 region 优先与所有 product `protocol_fields` 调用均传 Store；独立执行中的未知原始 ancestry 正例保持强 workbench 判定，没有以当前 notes floor制造 Narrative 或 collaboration region。service 普通 legacy compose/generation、changes/candidates 新 gate 的定向对照通过；上文记录的剩余入口没有因这些局部 PASS 自动关闭。

所有 grant/review/observation 身份都是明示合成 L1；Python native、实际 PPTX/回读属于所测文件工程。没有运行本轮冻结 A SDK/CLI 或 Node/artifact-tool 路线，不挪用其他 reviewer 的证据作个人 PASS。真实目标桌面 notes 视图、编辑保存重开、真实 Owner/受众与 human professional evidence 仍 **NOT_RUN**；不以工程通过降级严格 Runtime policy，不给完整 RC3/最终专业 AC PASS。

本固定 HEAD 的结论保持 REQUEST_CHANGES。F-CR02-03 及新 delta 修复后，需要新固定身份与第三轮独立反例/对照复审；当前报告、初版报告与每轮失败均保持原件。
