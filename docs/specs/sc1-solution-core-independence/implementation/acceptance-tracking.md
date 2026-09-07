# SC-1 Q0｜验收追踪（acceptance-tracking）

数据源：`docs/specs/sc1-solution-core-independence/acceptance/cases.json`（91 项）。本表在每轮 PR 后更新 `status` 与证据；未经执行的用例一律 `not_started`，禁止提前置 pass。

状态口径：`not_started / blocked（注明前置缺失）/ in_progress / pass / fail / deferred_to_uat`。

## 总览（2026-09-07，PR-02 后）

| 组 | 数量 | 当前状态 | 说明 |
|---|---|---|---|
| A（安装/托管/就绪） | 13 | A-01/A-02/A-04/A-05/A-06/A-11/A-12 部分（工程测试通过，真实环境证据待补）；A-03 blocked（后端 unbound）；A-07—A-10 部分（P-02 测试覆盖）；A-08/A-09/A-10 待评估 | 证据：`tests/test_capability_lock_and_managed_backend.py`、更新后的 `test_build_runtime.py`/`test_open_source_preview_gate.py` |
| I（材料/Context Pack） | 8 | not_started ×8 | PR-03 |
| R（研究） | 6 | not_started ×6 | PR-03；R 组含"无网络真实报告"分支 |
| S（方案/Brief/判断） | 8 | not_started ×8 | PR-03/04 |
| N（叙事/双路径） | 5 | not_started ×5 | PR-04/05 |
| P（页面生产/构建） | 6 | P-02 工程测试通过；P-01 blocked（真实标准 build/render 需后端绑定） | PR-05 继续 |
| D（架构视图/图形） | 6 | not_started ×6 | PR-05 |
| W（工作流/问题/动作） | 10 | not_started ×10 | PR-04/06 |
| Q（语义审查/质量门） | 13 | not_started ×13 | PR-06；Q 量规按规格在 Q0 冻结（见 §2） |
| L（学习/反馈口径） | 4 | not_started ×4 | PR-07 |
| E（对照/UAT） | 6 | not_started ×6 | **deferred_to_uat 候选**：需 ≥3 类真实样本 ×2 配对运行，仓库现无真实素材 |
| M（迁移/回滚） | 6 | not_started ×6 | PR-08；本机失效 symlink 与空 release 树为真实迁移场景 |

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
