# WP-C｜内容质量、返修与真实验收任务卡

## C1 语义审查 v2 与量规

依赖：B4/B5；量规在 Q0 即冻结。
涉及：`quality/external_review.py`、既有 review tasks、contracts、Skill 方法包、`skills/deck-master/prompts/quality_reviewer.prompt.md`。
实现：输入版本、覆盖、逐维观察、独立性证据、具体 findings；报告状态由 Runtime 校验，不接受空 pass；语义检查前移。同步将 `quality_reviewer.prompt.md` 从 v1 五维英文输出升级到 v2 六维量规（维度枚举与 `deck_external_quality_review.v2` 一致），并核对 `narrative_advisor`、`source_decision_reviewer` 的维度词表未漂移；旧 v1 报告仅按 v1 语义读取。
验收：仅存在 reviewer 字符串不算独立；来源匹配与语义支持区分；每个关键页面/论点均有覆盖；prompt 产出的维度与 v2 schema 枚举一致。
测试：Q-01—Q-05、Q-13。

## C2 阶段内动作与定向修复

依赖：C1、A5、B1—B6 输出协议。
涉及：workflow/handoff/fingerprint、generation import、autopilot、impact resolver。
实现：action envelope、权限/范围、幂等、迟到结果、staging+提交标记、预算、定向返修和受影响项复审；不新建 Runtime。
验收：旧输入不能覆盖新版本；跨文件中断保留上版；局部授权不扩为整套；预算耗尽不自动放行；不要求无意义“继续”。
测试：W-06—W-10、Q-06—Q-08。

## C3 必需质量门、当前批准和客户导出

依赖：C1/C2、A4、B6。
涉及：quality gate_policy/gate_freshness、runtime final_readiness、delivery/export、客户可见扫描。
实现：SC-1 profile 固定；语义/证据与现有工程门同源汇总；当前版本批准；notes/metadata/隐藏内容扫描；保留正常限定条件。
验收：换 profile 或 run_mode 不可降级过门；旧报告/批准不能通过新文件；P0 不可 override；标准与 HD 标准一致。
测试：Q-09—Q-12、P-06、M-05。

## C4 反馈口径修复与有限经验卡

依赖：Q0；可与 C1/C2 并行。
涉及：`learning/pack.py`、feedback collectors、现有 learning pack/显示。
实现：以 asset + run + reviewed revision 为统计单元，取该轮最终 accepted/rejected 决定；显式 supersedes 的中间决定不重复算。`acceptance_rate=accepted/(accepted+rejected)`；delivery_count 与 outcome 独立。缺乏 revision 的旧事件单列 legacy_unknown，不猜去重。
经验卡最少记录：适用问题、采用结构/机制、用户为何修改或保留、证据来源类别、适用/不适用范围、来源 Run 引用和批准范围。只由真实反馈形成；客户事实不自动进入跨项目通用知识。依旧通过既有 learning pack 按需加载。
验收：9次通过91次拒绝的样本得到9%，重复导出不抬分；样本量小显示计数，不把1次通过当普遍优质；无反馈不伪造高价值模式。
测试：L-01—L-04。

## C5 对照 harness 与人工投入记录

依赖：Q0 冻结量规；B/C 链路完成后执行。
涉及：现有 benchmark runner/report/aggregate/checkpoints、UAT 工具和测试。
实现：配对运行元数据、输入/宿主/预算控制、初稿保存、主动投入、失败/重试完整登记、blind scoring、脱敏导出。
验收：至少三类真实样本两次配对；不能只记最佳结果；baseline_blocked 不当零；未做 UAT 不通过。
测试：E-01—E-06；具体阈值以 `11-benchmark.md` 为准。

## C6 全链路与交付收口

依赖：所有任务。
涉及：README/用户指南/AGENTS/全部受影响 Skill/known-limitations、发布与证据报告。
实现：完整说明原始材料→研究→方案→叙事→页面→构建→审查→修订→批准→导出；按真实支持范围写宿主能力；最终迁移/安装/真实 UAT。
验收：用户不需要先编写逐页稿、不调用外部命名 Skill、不知道后端路径即可完成；缺失工具/证据诚实阻断；工程与效果分别报告。
测试：全表；结论 accepted/changes_required/outcome_pending，不用 Fixture 顶替。
