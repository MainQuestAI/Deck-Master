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

## 3. 实施分支全量回归（T01 后）

命令：`.venv/bin/python -m pytest tests/rebuild -q`（仓库源码直跑，2026-10-12）。结果：**1752 passed / 3 failed**，3 个失败均已定位并修复：

| 失败 | 归因 | 处置 |
| --- | --- | --- |
| `test_package_boundary.py::test_retired_tree_has_zero_living_references` | **PR106 分支既有失败（非 T01 代码）**：首个规范提交 9797f9e2 引入的 `docs/reports/controlled-collaboration-audit-20261012/source-index.md` 与 `workbench-v3-execution-20260926/W01.md` 已含 retired 树引用（在 9797f9e2 上即红）；后续 1c266c86 又给 `repair-plan.md` 新增 3 行同类引用 | 收窄豁免：仅 `docs/reports/` 下**目录名带 8 位日期后缀**的非 `.py` 文件按时间戳审计记录豁免（与 `docs/archive/` 同等非活动面）；`.py` 代码与未注日期目录（含本证据目录）保持受扫描。PR107 审查（P2-3）将最初的整前缀豁免收窄为当前口径 |
| `test_package_boundary.py::test_spec_contracts_match_packaged_contracts_byte_for_byte` | T01 为 review.v1 新增可选 `identity_receipt` 后 spec 镜像未同步 | 同步 `docs/specs/deck-master-rebuild-v1/contracts/review.v1.schema.json`（向后兼容的可选字段） |
| `test_styles.py::test_schema_mirrors_and_cli_typed_errors` | 同上（同一镜像守卫） | 同上 |

修复后以上测试单独复跑全部通过。测试套件运行会重新生成部分跟踪的 `output/playwright/` 截图（字节级非确定性产物），提交前已还原，不进入实施提交。

**行为微变登记**：`editing._professional_evidence`（现为 `delivery_eligibility` 统一实现）对不可读的 review ref 从基线的异常上抛改为跳过该记录（状态如实缺省为 not_evaluated），方向更稳；其余既有报告字段与语义不变。

**PR107 审查修复登记**：`blocking_fail` 去除依赖完整性条件（fail 只要主体当前即保持阻断，防止较新 fail 因依赖不完整被 pass 掩盖——审查已实证的放行漏洞）；`replaces` 信任收窄为同 kind 同 review_id 的同逻辑审查替代；新增 2 个回归负例。

## 4. 环境与来源差异（保留，不覆盖）

- 用户主工作区（main）存在未提交的 `README.md` 修改与 `docs/reports/`、`docs/work-items/`、`evidence/`、`output/` 下若干未跟踪目录；实施分支不包含、不覆盖这些修改。
- 本轮验证使用仓库 `.venv`（Python 3.x，仓库源码直跑）；未验证目标安装版本行为（见上表 digest 行）。
- 实际客户资料不在仓库内；本目录全部样例为合成材料，真实 Host/生图/PPT 编译/用户试用均未执行（`not_run`，归 T08）。

## 6. 二轮审查（PR107）记录

外部二轮审查（2026-10-12，针对 head `06996040`）确认 2 个 P1 专业交付缺陷与 3 个 T00 验收缺口；全部修复已落在本分支后续提交：

| 发现 | 修复提交 |
| --- | --- |
| F01：额外声明依赖未纳入当前性校验（审查以正式接纳路径复现放行） | `cbd7abbb`（review.dependency_problems 单一实现 + stale/unresolvable 缺口 + 三例正式入口测试） |
| F02：记录替代≠有效重审（host_self/not_evaluated 替代解除人类 fail） | `29a94858`（两阶段判定，仅有效重审解除；四个正式路径负例 + 有效重审正例） |
| 边界豁免过宽（审查裁决 IV.1） | 显式注册表 + "带日期但活动"反例单测 |
| F03/F04/F05：决策正例缺真实替代、未来提案误标确定错误、B02/B03 证据未闭合 | `6e26176a` + 本轮复核修复（q4a 两路径与归因测量、q4b 确定性承诺与成对校准、锚点 12 条、cues/阅读分支、SPEC §10 引用修正） |

修订后二轮独立复核：evaluator-c/d 均 PASS-with-repairs（commit `6e26176a`，输入哈希重算相符），复核提项已全部处置（见 evaluation/adjudication.md §6）。当前 head 的定向与全量测试、远端 CI 需在最终提交上复跑后汇报；一审与二轮的状态记录均不替代 T08 的发布验收。
