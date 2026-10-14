# RC3-02 独立 code review：初版 27823c5

**结论：REQUEST_CHANGES。** 固定初版有两项已证实缺陷，不能据已有测试绿灯合并。本报告没有把 Owner 的新修复或其他 reviewer 的探针记为本轮已审通过；修复须重新冻结 HEAD/tree 后复审。

Reviewer：`/root/rc3_02_code_review`，未参与实现。日期：2026-10-14 UTC。

## 固定对象与审查边界

- 实现 HEAD：`27823c5c3e52a50201569e1d087406ddeff3832f`；tree：`dcda89be3e1eeef5ba040f076e5f0df307241772`。
- 基线：`8e274576e7a93de7d10c054558991878501fff0c`。
- 隔离快照：`/workspace/work/rc3/reviews/rc3-02-code-snapshot-27823`。所有源码读取、测试及探针均对该快照；没有读取 Owner 正在修复的产品文件来替代初版。
- 实际入口：`/workspace/work/rc3/reviews/env-02-snapshot-27823/bin/python -I`。source `work/rc3/env.sh` 后始终使用该绝对 Python；探针核对实际模块来自固定快照。没有安装依赖、运行共享 Node bootstrap、改产品源码/raw/ledger、commit 或 merge。
- 审查全部 39 文件 delta，覆盖共享 Task.inputs getter/视觉切片、任务/candidate/recipe、新旧 writer/control、Page/Plan 和 speech 事务、completed artifact/Review/findings、compiler/native/pipeline、sanitizer/export/handoff、CLI/HTTP、schema 镜像及新增/调整测试。`git diff --check` 通过，快照 working tree 无修改。
- 已读 AGENTS、task index、recovery、原 RC3-02、v1.2 CONTRACTS/MIGRATION 与 AC-N01–N04/CQ-06 完整相关段；implementation-boundaries 的 14 组和 independent-regression-preflight 仅作为准备输入，不作为执行结论。

## F-CR02-01 / P1：技术 floor 将历史项目误识别为显式新协议项目

定位：`src/deck_master/pipeline.py:354` 新增 `require_writer(new, 'rc3.v1')`；`models.py:524` 由该 helper 附加 `project_format=workbench.v3`；`pipeline.py:324` 又据这个标记强制 `require_assembly_ready`。同样的 floor 提升发生于正式 notes edit。

实际影响：一个原本没有 compatibility/控制 region、合法保有 SVG 的历史项目，仅修改备注或完成一次新 notes-aware 编译后，下一次普通 `produce` 被当成原始 opt-in workbench.v3，额外要求原图、SVG preview 和 PageVisual 通过。因此不能完成原 SVG 复用与备注重编译闭环。技术 writer 保护与项目协议来源被混为一谈。

我的独立正式 L1 反例：使用清楚标为 synthetic 的初态，正式 `service.create` 接纳三页、为隔离编译边界 seed SVG；随后真实 `editing.edit_page` 只改备注，再调用真实 `pipeline.produce`。没有调用 native renderer，也没有 patch gate。结果：

```text
before.compatibility = null
after.compatibility = {minimum_writer: rc3.v1, project_format: workbench.v3}
after.collaboration = null
produce -> stage_prerequisite_missing / pages/p-a/blueprint
失败后 current 完全未变
```

证据：`rc3-02-code-round1-27823-scratch/probe_legacy_notes_gate.py` 与 `probe_legacy_notes_gate-final.log`。最初探针记录因 reviewer 使用错误异常属性而终止，已保留为 `probe_legacy_notes_gate.log`；更正的是隔离探针日志采集，产品始终是同一个固定 HEAD。

Root 提供的初版 render `9 FAIL / 43 PASS / 1 ERROR` 是另一次执行，本报告不冒称我复跑了该整组。其 second-produce 回归与本探针确认的来源混淆一致。

修复建议：从真实可达不可变历史证明项目原始协议来源，沿共享 Store 判定供需要区分历史协议的 consumer/dispatcher 使用；不能把当前较高 minimum_writer 视作已迁移/原 opt-in v3。无法证明来源时 fail-closed。显式 Stages、真实协作 region、原 opt-in v3 继续完整门禁；保留 `rc3.v1` floor、暂停/撤回/范围与费用规则，不能设置可由 Host 自选的 legacy 降级开关。

复审至少应包含普通 legacy 重编译/notes edit、legacy 后续 input_revision/blueprint protocol、新协议与显式 Stage 的缺前置负例，以及真实 region 的控制门禁对照。

## F-CR02-02 / P1：新脚本与公开 notes manifest 的 page_id 绕过隐私扫描

定位：`exports.py:286`、`321–334` 直接把 page_id 放入脚本，只对 title/notes 调用 `text_safe`；`exports.py:274` 及 `450` 将 page_id 放入公开 notes_policy/manifest，未扫描它。Page schema 允许 `^[A-Za-z0-9][A-Za-z0-9_.-]*$`，因此其合法身份值可以包含实际 sanitizer 明确识别的 credential-like 标记。

我的独立正式反例：合法稳定 page_id 使用 **合成非真实凭据** `sk-SYNTHETIC_CANARY_NOT_A_REAL_SECRET`，标题为普通中文、notes 为普通合法提示。没有 PPTX、没有 seed 私有 helper 或手改 Store 对象，完整走 `service.create` → `exports.create(purpose=review, notes_policy=separate_script)` → `exports.download`。对照先调用现有 `text_safe(canary)`，实际返回 `export_privacy_blocked`，证明它属于当前已经支持的识别范围。正式 export 却成功，并且三个实际公开下载字节均含该 canary：

```text
speaker-script.json: true
speaker-script.txt: true
manifest.json: true
源 Document/current: 未变
```

证据：`rc3-02-code-round1-27823-scratch/probe_script_identifier_privacy.py`、同名 `.log`；实际导出文件保存于隔离 scratch 的 `script-identifier-public/`。这是新加 metadata 投影的扫描遗漏，不是在声称通用 PII 检测能力；不需要外部服务、真实凭据或桌面环境便可复现。

修复建议：在同一个公共投影/最终字节边界校验新暴露的 page_id 与 notes_policy 字符串字段，覆盖脚本和 manifest/delivery.json 的实际所有容器选择；识别到已支持的私密值时拒绝公开包，不改原 Page/原文件、不猜一个新 page_id。保持普通稳定 ID、中文、多换行及 none 原注正例。补脚本及纯阅读 manifest 的负例，验证拒绝时没有可下载半包。

## 本 reviewer 实际验证

以下为两个独立 pytest 命令，不合并成一次总跑结果：

| 执行 | 实际结果 | 范围 / 限制 |
|---|---|---|
| visual_inputs + transactions 定向选择 | **24 PASS / 21 deselected，2.35s** | 真实服务派发 Task.inputs；notes 四时点/immutable freeze；实际消费变化；getter 缺失/冲突/损坏；撤回；speech 未知/重复字段；Plan 旧映射拒绝；null Narrative speech；开放视觉 finding；floor 不伪造控制 region |
| notes_files 定向选择 | **22 PASS / 10 deselected，3.03s** | 默认 Python native 实际 PPTX 字节；备注完整回读、四容器、有效 Plan speech 策略、隐私 canary/隐藏元数据、none 原注与有序独立脚本。不含 render 全组 |
| 独立 legacy notes gate probe | **FAIL 确认产品缺陷** | 上述 F-CR02-01；失败前进入 Stage 门禁，未启动 renderer |
| 独立 script identifier probe | **FAIL 确认产品缺陷** | 上述 F-CR02-02；正式 export/download 成功泄漏已识别合成 canary |
| notes-aware handoff 确定性探针 | **窄边界 PASS** | 实际 compile→export，间隔 2.5 秒两次 handoff 的最终 sanitized hash 相同、均识别 sanitized_copy。初态没有 previews/最终 Review，handoff 整体依然诚实 blocked；不宣称交付通过 |
| 静态 diff whitespace | **PASS** | `git diff --check BASE HEAD` |

日志：`rc3-02-code-round1-27823-focused.log`、`rc3-02-code-round1-27823-files.log`、`rc3-02-code-round1-27823-scratch/probe_notes_handoff_determinism.log`。

费用/授权/Review 的 fixture 均是显式合成 L1；测试内模拟 observation 的名字不代表真正 native provider 或人类。imported_mapping/null Narrative 采用明示 schema-valid seeded initial state，不称完整正式 import E2E。我的本次执行没有运行冻结 A CLI/SDK 或 Node/artifact-tool 路线，不转用别人的结果来填成我的 PASS。用户要求的目标桌面 notes 视图、保存重开、真实 Owner/受众及 human professional evidence 仍 **NOT_RUN**，后置不阻工程修复，但不能覆盖严格 Runtime 政策。

除两项已证实缺陷，未在此固定 delta 中确认其他新增实质缺陷。此句不把未执行场景写成通过，也不关闭最终 AC-N01–N04/CQ-06。

## 复审出口

本轮结论保持 REQUEST_CHANGES；由 Owner 修复并提供新冻结身份及实际日志后，独立复审失败反例、受影响正反对照与新 delta，再决定是否满足工程 merge 条件。既有初版失败、Owner/root/另一 reviewer 的独立运行身份及后置 NOT_RUN 分别保留。
