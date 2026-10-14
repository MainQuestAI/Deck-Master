# RC3-02 独立 regression review — round 1

**结论：REQUEST_CHANGES。** 新增 notes 回归全绿不能覆盖下述两个已复现工程缺陷。本报告只审初版 `27823c5`，不引用 Owner 后续代码为修复结果；须取得新固定 head/tree 后复审。原只读 preflight 保留。

Reviewer：`/root/rc3_02_regression_reviewer`，未参与实现。执行日期：2026-10-14 UTC。

## 固定对象与证据边界

- 工作树：`/workspace/work/rc3/reviews/rc3-02-code-snapshot-27823`。
- HEAD：`27823c5c3e52a50201569e1d087406ddeff3832f`；tree：`dcda89be3e1eeef5ba040f076e5f0df307241772`；parent：`8e274576e7a93de7d10c054558991878501fff0c`。
- 专用 Python：`/workspace/work/rc3/reviews/env-02-snapshot-27823/bin/python`，Python 3.12.14，`-I -B` 实际 import 仅该 snapshot 的 `src/deck_master`。pytest 9.1.1；未安装包或修改共享 bootstrap；所有日志、临时项目与探针在独占 scratch。
- 实际工具：rsvg-convert 2.60.0；LibreOfficeDev 26.8.0.0.alpha0（`2c87e51eeaa2b413ff4ae097b2705eea1995d8e5`）；pdftoppm 26.05.0。native 默认 Python 编译路线实际执行，node artifact-module 路线本次 NOT_RUN。
- 已阅读全文：本卡新增三个 `test_rc3_notes_*.py`、39 个变更路径的 diff；两处 schema 镜像与资源合同逐字一致。正式 source 没有修改，检查结束时工作树 clean。
- 合成内容/授权/Review/native observation 明确属于 L1；实际 native PPTX 与最终下载文件回读属于本轮实际 L6 文件工程。seeded imported mapping 不称正式 import E2E，synthetic human adapter 不称真实人类评阅。

独占证据目录：`/workspace/work/rc3/reviews/rc3-02-regression-round1-27823-scratch/`（下文文件名均相对此目录）。

## 已复现的工程缺陷

### 1. P1：技术 writer 升级使 legacy 第二次 produce 进入未启用的 PageVisual 路线

正式旧路径创建 draft → blueprint/reconstruct → 第一次真实 produce → 修复任务接纳 → 第二次 produce，在本快照的既有回归 `tests/rebuild/test_tasks.py::test_no_progress_repair_stops_instead_of_looping` 失败：

```text
test_tasks.py:499 again = produce(project)
pipeline.py:325 require_assembly_ready(store, doc)
stage_prerequisite_missing: pages/p09/svg_preview:
assembly requires original image, current SVG and its preview
```

第一次 `produce` 会调用 `require_writer(new, 'rc3.v1')`；`models.py:524` 同时写入 `project_format=workbench.v3`。之后 `pipeline.py:324` 将该技术升级当成原本 opt-in v3 生产路线，第二次调用要求 SVG preview/PageVisual gates。notes 文件消费需要受保护的 writer，但不能把旧项目的生产协议未经真实迁移改为另一套路径。不能通过降 writer、自动生成 control/假 review 或新 legacy 逃生参数修复。

证据：`legacy-render-pytest.log`（1 FAIL，1.06s）及 `legacy-floor-trace.json`（实际提交历史、兼容字段与页槽）。Root 提供的 9FAIL/43PASS/1ERROR 是上游结果；我本轮独立复现的是上述单个正式失败，不将其数量写成我执行。

### 2. P1：全空 notes 的新输出绕过最终 export 页数/页序身份检查

独立探针使用三个 schema-valid 合成 Page/真实 SVG，调用实际 `compile_deck` 生成真实 PPTX；初态输出在隔离 Store 中显式 seed 为 notes-aware（`rc3.v1`、完整有序 SVG 和 `page_notes:*` 依赖）。这是一组实际文件负例初态，不称正常 pipeline 已采用坏文件。随后执行未 mock 的正式 `exports.create(notes_policy='pptx_notes')`、download、`check_handoff`。

| 实际原 PPTX / 当前 Document | 正式 export | 最终 PPTX 的实际 page_id | handoff notes 判别 |
|---|---|---|---|
| 正确 `a/b/c`，三页全空 notes | ACCEPTED | `null/null/null` | 无 notes gap |
| 原 PPTX `c/b/a`，Document `a/b/c` | **错误 ACCEPTED** | `null/null/null` | **没有页序/身份 gap** |
| 原 PPTX 两页 `a/b`，Document 三页 `a/b/c` | **错误 ACCEPTED** | `null/null` | 此处正确报 `candidate_notes_policy_mismatch`，但 export 仍已成功 |

`exports.py:318` 仅 `any(notes)` 时才向 sanitizer 提供可信 Page records；全空新输出直接走旧纯阅读清理，既不验证实际页数/ID，也删掉稳定身份。`handoff.py:72` 仅 `any(expected_text)` 时核对 page_id，因此 notes-aware 且文本全空的错序文件也漏报。`output_matches_current_svg` 在这些负例返回 True，只证明声明依赖匹配，无法替代实际字节检查。

应区分没有新 notes 承诺的窄历史兼容与新 notes-aware 文件。新文件必须在全空文本时仍核对真实 count/order/identity；`pure_reading` 可清理副本 notes，但不能让新消费输出借清理跳过来源文件身份验证。不要因为 none 不生成新 notes 而撤掉文件完整性要求。

证据：`empty_notes_identity_probe.py`、`empty-notes-identity-probe.log`、`empty-notes-identity-probe.json`，三组内部/最终真实文件也保留在同名 case 目录。探针记录各输出 hash、manifest policy、完整回读与 handoff gaps；正式 export 前后 current 与原件保持不变。此项已直接告知 root 和 Owner，修复必须另 head。

## 实际执行与保留的正反例

pytest 使用 `-p no:cacheprovider`、各自独占 `--basetemp`；没有重复全树约 1800 项。

| 本轮实际执行 | 结果 | 原始证据 |
|---|---|---|
| 新增 notes transactions / visual_inputs / files 全部 | 77 PASS，11.26s | `new-notes-pytest.log`；临时正式项目在 `new-notes-pytest/` |
| speech policy、sequential variant、versioned exports、current-control delivery；四个 exact-file/human/must_fix 正反例；compiler geometry 与 truncated/extra slide readback | 44 PASS，5.04s | `related-pytest.log` |
| bound speech 正式成功、正文/错误 kind 拒绝、speech scope | 3 PASS，0.38s | `bound-speech-pytest.log` |
| 独立真实 body edit 后旧 Task start 拒绝；已有实际 fixture call consumed 后旧 result accept 拒绝且保留费用 | 2 PASS，0.23s | `test_formal_consumed_body_refusal.py`、`formal-body-pytest-v2.log`、`formal-body-refusal-*.json` |
| 既有 legacy 第二 produce 回归 | 1 FAIL | 缺陷 1 |
| 独立 notes-aware 全空实际文件反例 | 缺陷复现 | 缺陷 2 |

本轮 pytest 最终有效结果共 **126 PASS + 1 个产品 FAIL**。独立 body 探针首次将“晚到结果允许新增 settlement revision”误约束为“整 Document 必须不变”，初次 1PASS/1FAIL 的原日志 `formal-body-pytest.log` 保留；纠正为内容/产物不采用、allowance 不变后两变体通过。该首次断言失败不是产品缺陷，未覆写其日志。

## 原 8 组 preflight / 14 组准备的覆盖映射

下表只标实际覆盖程度，不产生新的 AC 状态；AC 签结论仍归原 T06 Owner。

| 既有准备组 | 本轮实际工程观察 / 尚未覆盖组合 |
|---|---|
| N-01 文件完整关系 | 非空中文/数字/限定/连续换行/末段、实际 native manifest、最终导出 PPTX 逐页完整回读通过；全空新输出身份/页数反例失败。未做目标桌面检查。 |
| N-02 容器 | cues/verbatim × pptx_notes/separate_script/both 六种及 default verbatim 降为 cues 通过；独立脚本来自有序 Page，原件不改。Plan 初态是明示 seed；不是正式 import E2E。 |
| N-03 none/原注/reading | none 用户原注实际保留、不自动脚本、显式纯阅读副本清理及隐私负例通过；全空新输出严格身份缺口见缺陷 2。 |
| N-04 真实 inputs 生命周期 | 四时点 before claim / before freeze / after freeze / after begin 均从真实派发 `Task.inputs` 读取 immutable request；同 Task、freeze/hash 与一份 allowance 保留，采用不覆盖新 notes。native observation 是合成 L1。 |
| N-05 候选 | 实际 SVG trial 保存 → notes edit → plan/adopt 通过，无新的 generation attempts/allowances；原 blueprint 与新 notes 保留。 |
| N-06 消费/权限反例 | 正式撤回后 claim 拒绝；真实 Task 的 body/visual/design/font/style、arrow/责任/表格归属消费反例通过。额外实际 body edit → start/consumed-result accept 拒绝，内容/成本不回退。全部 mutation × 全生命周期组合未无界扩跑。 |
| N-07 已完成视觉 | 正式 edit 保留 blueprint/SVG/svg_preview Ref 与旧 Review 字节；PageVisual pass 当前适用；assemble/export 实际读到新 notes，旧输出/stale file applicability 失效，完整 Task facts 不新增图像调用。legacy 生产对照失败见缺陷 1。 |
| N-08 speech/映射 | bound speech 正式接纳；imported_mapping/null Narrative 的正式 speech 接纳，合法空 node mapping、完整原稿/roles/order/source/evidence/Plan links 保留。两种 speech 路径各自再贯通“已完成视觉→实际 assemble/export”的全部组合本轮未独立执行。 |
| N-09 finding | notes-only 后开放视觉 must_fix 仍 fail，assembly 阻塞；自称 fixed 且只援引新 Page 的 review 正式接纳被拒。 |
| N-10 identity | 正式 content operation reorder/remove/split/merge 后实际 native compile/export、脚本、lineage、旧 snapshot 保留通过；未知 split/merge 映射正式接纳拒绝，删除页 notes 不残留。内容初态是显式 v1 合成稿。 |
| N-11 两版本 | 顺序 live/read、共享 Narrative、单 current、首份 manifest/bytes 不被第二份改写、不得第三份等 L1 通过；两份完整 native notes 文件全路径组合尚未独立执行。 |
| N-12 privacy | notes 的可识别私密路径/Bearer/token link 正式拒绝；合法中文与 raw notes hidden metadata 清理、原件保留通过。另一个 reviewer 的 stable-ID privacy 结果不转录为我的执行结论。 |
| N-13 CAS/replay | edit 精确 replay、export 同请求/不同 policy 冲突、未知/重复 speech 事务拒绝、v2 Plan stale/duplicate 拒绝及既有 versioned export concurrency/restore/recovery 通过；不是全文件系统故障矩阵。 |
| N-14 writer | 真实冻结旧 A CLI/SDK 两类隔离项目拒写及费用/全文件不变独立完成，详见下一节。 |

## 冻结 A 的真实拒写核实

没有直接重跑 root 提供的 harness，因其硬编码旧临时项目并会覆盖共享报告；我阅读其源码/原 JSON 后，在独占目录重建等价真实入口，未改冻结 A 的代码、支持 writer 集或安装。

`frozen_a_actual_refusals_probe.py` 实际使用 `/workspace/work/rc3/baseline-a/venv/bin/python -I -B`，加载的是该冻结安装的 `site-packages/deck_master`。冻结 manifest sha256 在完整 JSON 中记录，与原 harness 对照；候选代码由 snapshot Python 加载。

- 项目 0 是本轮正式 notes-only edit → actual assemble/export 留下的受保护项目，复制到独占目录；7 CLI + 6 SDK 拒写，71 个文件 hash 全部不变、current/outputs/实际 PPTX 不变。
- 项目 1 是本轮真实派发/freeze/begin/settle/accept 的合成 L1 项目，已有 1 个 consumed allowance；相同 13 入口拒写，33 个文件 hash、Task allowances/attempts 与费用指纹全不变。
- CLI 均 exit 4，未传新 flag，不是 argparse “unknown option/invalid choice”拒绝；continue/claim/accept/edit/restore/historical delivery 明确报 `unsupported minimum writer; use the matching core`。旧 assemble CLI 包装成 `operation_unavailable`，对应真实 SDK exception cause chain 明确追到同一 minimum-writer/matching-core原因，未把 wrapper 文案误写成 CLI 已直接显示升级理由。
- SDK compile/assemble/claim/accept/edit/restore 六入口的实际 exception chain 均包含 minimum writer + matching core。选择旧 revision 不改变当前 floor/权限；相关新 core restore/current-control 回归也已执行。

证据：`frozen-a-actual-refusals-probe.log`、`frozen-a-actual-refusals-probe.json`，两份复制项目保留。此项证明技术拒写与已记录调用事实不变；合成 allowance 不能宣称真实模型美元成本实验。

## 后续处理

保留 27823c5 的 REQUEST_CHANGES 与以上原始证据。Owner 修复后 root 应重新提供准确 head/tree/env，复审至少重跑两个失败轨迹、全空/非空/pure-reading 对照、受影响原回归，以及实际旧 A 拒写/费用不变；影响分析再决定额外范围。没有 merge。

真实 Owner/听众、完整彩排、目标桌面 notes 视图与保存重开仍 **NOT_RUN**，按用户要求开发后补，不阻止工程修复和下一轮独立复审。Runtime 真实 professional policy 保持原要求，工程结果不代替人类身份或最终文件认可；本轮 synthetic human 正例只是 L1 组合谓词。
