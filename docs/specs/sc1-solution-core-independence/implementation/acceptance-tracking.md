# SC-1 Q0｜验收追踪（acceptance-tracking）

数据源：`docs/specs/sc1-solution-core-independence/acceptance/cases.json`（91 项）。本表在每轮 PR 后更新 `status` 与证据；未经执行的用例一律 `not_started`，禁止提前置 pass。

状态口径：`not_started / blocked（注明前置缺失）/ in_progress / pass / fail / deferred_to_uat`。

## 总览（2026-09-07，PR-02 后）

| 组 | 数量 | 当前状态 | 说明 |
|---|---|---|---|
| A（安装/托管/就绪） | 13 | A-01/A-02/A-04/A-05/A-06/A-11/A-12 部分（工程测试通过，真实环境证据待补）；A-03 blocked（后端 unbound）；A-07—A-10 部分（P-02 测试覆盖）；A-08/A-09/A-10 待评估 | 证据：`tests/test_capability_lock_and_managed_backend.py`、更新后的 `test_build_runtime.py`/`test_open_source_preview_gate.py` |
| I（材料/Context Pack） | 8 | I-01/I-02/I-05 工程测试通过；I-03/I-04/I-06/I-07 随 PR-04/05 集成验证；I-08 待评估 | 证据：`tests/test_sc1_intake_research_brief.py` |
| R（研究） | 6 | R-01—R-04 工程测试通过（构建/脱敏门/执行前置/回写同一 manifest）；R-05/R-06 需宿主真实研究执行，deferred_to_uat 候选 | 同上 |
| S（方案/Brief/判断） | 8 | S-01/S-02 工程测试通过（agent_extract 标注、未审引用不记支持）；S-05/S-06/S-07/S-08 工程测试通过（solution model 校验、方案驱动叙事、差异化材料不同叙事、关键词过滤移除）；S-03/S-04 随 PR-05 | `tests/test_sc1_solution_narrative.py` |
| N（叙事/双路径） | 5 | N-01 工程测试通过（candidates/recommended/selected + single_viable_path 不造伪备选）；N-02—N-05 随 PR-05 | 同上 |
| P（页面生产/构建） | 6 | P-02 工程测试通过；P-04/P-05/P-01（工程面）通过：生产写入方逐 beat 全覆盖、制作要求不得进正文、无证据/设计依据保持 draft、标准构建真实消费 Page Package（hash 锚定 + 正文渲染 + 生产 gate）；P-01 真实两页 PPTX 生成 blocked（需后端绑定）；P-03/P-06 随 PR-06 | `tests/test_sc1_page_packages_views.py`、`test_build_runtime.py` |
| D（架构视图/图形） | 6 | D-01/D-02/D-03 工程测试通过（四类视图构建、模型一致性拒绝未知节点/关系、组件变更影响投影）；D-04—D-06 随 PR-06（客户扫描/回读门） | `tests/test_sc1_page_packages_views.py` |
| W（工作流/问题/动作） | 10 | W-01/W-05/F03 通过；W-06—W-10 通过（旧输入不覆盖新版本、中断保留上版、幂等、预算阻断、定向修复 affected-only 复审）；W-02—W-04 typed trigger 表改造 open（见偏差登记） | `tests/test_sc1_question_authority.py`、`test_sc1_actions_and_gates.py` |
| Q（语义审查/质量门） | 13 | Q-01/Q-04/Q-05/Q-13 工程测试通过（v2 失败封闭校验、独立性、输入版本绑定、无来源数字/内部标签扫描、交付 PPTX notes/元数据/隐藏页扫描）；审查 prompt 已升级 v2 六维（与 schema 枚举一致）；**Q-08 通过**（生产必需门含 semantic_review、external_* 报告满足之、packages 变更即审查过期）；P0 永不 override、隐藏内容扫描接入 customer_visible_safety；Q-02/Q-03/Q-06/Q-07/Q-09—Q-12 随 final_readiness 集成验证 | `tests/test_sc1_external_review_v2.py`、`test_sc1_actions_and_gates.py` |
| L（学习/反馈口径） | 4 | L-01—L-04 工程测试通过（9/100 复现 9%、supersession 去重、重复导出不抬分不升序、legacy_unknown 隔离、经验卡仅来自真实反馈）；F11 Review Desk 回写带 revision 落地 | `tests/test_sc1_feedback_metrics.py`、更新 `test_workspace_learning_pack.py` |
| E（对照/UAT） | 6 | E-01/E-04 元数据层通过（pairing 校验、manual_effort 全量记录透传）；E-02/E-03/E-05/E-06 需三类真实样本 ×2 配对真实执行，deferred_to_uat | `tests/test_sc1_benchmark_pairing.py` |
| M（迁移/回滚） | 6 | M-05/M-06 工程测试通过（回滚不删新旧用户数据、未知宿主拒绝不虚报）；M-01—M-04 由既有迁移/回滚测试继续覆盖；真实环境迁移证据待 A6 实机执行 | `tests/test_sc1_migration_safety.py`、既有 `test_skill_installation.py`/`test_release_runtime.py` |

### PR-02 证据边界（真实 vs 工程）

- **工程测试证明**：lock 组件固定/hash 校验/漂移检测/重复安装幂等（A-01/A-02 工程面）；env 不能伪报 ready、smoke 证据驱动 ready（A-04）；桥接退役（A-11）；托管优先命令解析与缺失如实上报（A-05/A-06 解析面）；none 决策全量 generate、无 fixture 候选（A-07/P-02 断言）。
- **待真实环境补证**：A-01 公开报告脱敏与真实 release 安装（依赖 suite-repair，A6）；A-05 真实 `ppt-lib` 托管安装后的真实检索（本机仅 PATH 2.0.1.dev0，未装托管副本）；A-03/A-04 的真实两页可编辑 PPTX 生成与渲染（需真实 PPT Master 绑定）；A-12 真实旧库保护（当前仅保证安装器不触碰 asset db 路径）。

## 已知前置条件与阻塞（Q0 实测）

1. **真实标准后端缺失**：A-03、A-04、P-01、P-06、M-05 中涉及"真实 build/render"的部分在 PPT Master 绑定建立前保持 blocked。修复路径：A1 能力锁 + A2 托管安装 + `backend`/`suite-repair`。
2. **真实样本缺失**：E 组全部、S/P/Q 组中要求"真实客户材料"的断言，只能以合成样例做工程验证，效果断言留待 UAT（`engineering_complete / outcome_pending` 口径）。
3. **宿主工具（ImageGen/网页研究）授权**：R 组"无网络真实报告"、D 组 HD provider 证据按实际环境如实分档，不虚报。

## 量规冻结记录（Q0 要求）

- 评分量规与阈值以 `acceptance/rubric.md` + `specs/11-benchmark.md` 为准，本轮不新增、不放宽；E 组执行时按冻结版本引用。
- C1 六维量规词表升级（`quality_reviewer.prompt.md` v1→v2）在 PR-06 落地，验收 Q-01—Q-05、Q-13。

## 已通过 acceptance IDs

（Q0 为先决审计任务，无 A—M 组用例通过；Q0 自身完成证明=本目录六份文档 + PR-01 提交。）

## 未执行/失败 IDs 与影响

全部 91 项 not_started；其中 8 项受真实后端/样本前置约束（见上），其余按 PR 顺序在各自任务内执行。
