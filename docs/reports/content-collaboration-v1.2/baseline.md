# T00 固定基线记录（AC-B01）

核实时间：2026-10-12（Asia/Shanghai）。执行环境：本机 macOS (darwin arm64) git 工作树 `Deck-Master-t01`（基于 `origin/codex/skill-flow-review` 的隔离实施分支 `impl/t01-t00-content-collab`），用户主工作区未提交修改未受影响。

## 1. SHA 记录

| 项目 | 值 | 核实方式 |
| --- | --- | --- |
| 代码基线（PR106 base = main） | `af9fd7a6b4d08f753d2f16536a03f386384f49d2` | `git ls-remote origin main`，2026-10-12 |
| PR106 规范编写前 head | `9797f9e25fbc20880752933be6324b879783603b` | README §2 声明 + git 历史 |
| PR106 当前 head（本包提交） | `1c266c86bcab4fd855f384d3f59bd9fa2d24db50` | `git ls-remote origin codex/skill-flow-review` |
| 实施分支 | `impl/t01-t00-content-collab`（基于 1c266c86） | 本地 worktree |
| T01 实施提交 | 见 `../README.md`「实施提交」小节（本文件随文档提交，无法自记其 SHA；代码提交 SHA 由后续文档提交固定） | — |
| 安装包 digest | `not_run`：当前验证环境未安装 deck-master 发行包（`.venv` 内无 deck-master 安装记录，测试以仓库源码路径运行）。安装切换与 HOME 验证按 TASKS 归 T07/T08，本卡明确记录缺口而非推定 | `pip show deck-master` |

## 2. 文档/源码漂移检查

规范 CONTRACTS §10 引用的固定源码锚点与 base `af9fd7a6` 实际内容逐一比对：

| 引用 | base 实际内容 | 结论 |
| --- | --- | --- |
| models.py L262–L310（writer 校验） | L258 `validate_review_semantics`，L262 `WRITER_RANK`（rank 保留点） | 基本吻合；引用起点落在 WRITER_RANK 而非函数签名 |
| store.py L306（原子提交） | L306 `def _commit_locked(` | 一致 |
| operations.py L103–L145（operation receipt） | L103 `recover`，L126 起 `commit_locked` | 区间覆盖收据路径；起点为相邻函数 |
| service.py L715（continue） | L715 `def _continue_project(` | 一致 |
| service.py L1738（task start/cancel） | L1738 `def task_start(` | 一致 |
| tasks.py L343（freshness） | L343 `def task_inputs_current(` | 一致 |
| tasks.py L915（结算后接纳） | L915 `def accept_result(` | 一致 |
| tasks.py L1335（调用额度） | L1335 `def reserve_allowances(` | 一致 |
| editing.py L383（restore 保留事实） | L383 `def restore_document(` | 一致 |
| exports.py L106（错误 professional gate） | L106 `def _gate(`——含 `status != fail` 与 `kind==professional_use OR human` 两个缺陷 | 一致（缺陷在场，T01 修复对象确认） |
| handoff.py L58（工程投影） | L58 render_report 分支，L58–L93 覆盖 gaps/report 组装 | 基本吻合 |

结论：本包关键源码路径与 base 无实质漂移；三处引用起点有 1 行级偏移，不影响所指行为。T01 实施后 `exports._gate` 已由统一 `delivery_eligibility.professional_policy` 替代。

## 4. 实施分支全量回归（T01 后）

命令：`.venv/bin/python -m pytest tests/rebuild -q`（仓库源码直跑，2026-10-12）。结果：**1752 passed / 3 failed**，3 个失败均已定位并修复：

| 失败 | 归因 | 处置 |
| --- | --- | --- |
| `test_package_boundary.py::test_retired_tree_has_zero_living_references` | **本包规范提交 1c266c86 引入的既有失败**（非 T01 代码）：`docs/reports/controlled-collaboration-audit-20261012/` 审计文档以历史证据名义引用 retired 树路径 | 将 `docs/reports/`（时间戳审计/证据记录目录）与 `docs/archive/` 同等列为非活动面；src/tests/skills/CI/根文档/specs 守卫不变。裁决记录于此 |
| `test_package_boundary.py::test_spec_contracts_match_packaged_contracts_byte_for_byte` | T01 为 review.v1 新增可选 `identity_receipt` 后 spec 镜像未同步 | 同步 `docs/specs/deck-master-rebuild-v1/contracts/review.v1.schema.json`（向后兼容的可选字段） |
| `test_styles.py::test_schema_mirrors_and_cli_typed_errors` | 同上（同一镜像守卫） | 同上 |

修复后以上测试单独复跑全部通过。测试套件运行会重新生成部分跟踪的 `output/playwright/` 截图（字节级非确定性产物），提交前已还原，不进入实施提交。

## 5. 环境与来源差异（保留，不覆盖）

- 用户主工作区（main）存在未提交的 `README.md` 修改与 `docs/reports/`、`docs/work-items/`、`evidence/`、`output/` 下若干未跟踪目录；实施分支不包含、不覆盖这些修改。
- 本轮验证使用仓库 `.venv`（Python 3.x，仓库源码直跑）；未验证目标安装版本行为（见上表 digest 行）。
- 实际客户资料不在仓库内；本目录全部样例为合成材料，真实 Host/生图/PPT 编译/用户试用均未执行（`not_run`，归 T08）。
