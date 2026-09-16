# T01 基线与处置记录

状态：实际执行记录（2026-09-16，T01.01–T01.03）。本记录只冻结事实与边界，不声明任何产品实现完成。后续核验者可按相同命令复核。

## T01.01 开发与提取基线核验

**当前 checkout（实施基线）：**

- 分支：`codex/rebuild-mainline-v1`，HEAD `b67a129`（任务卡拆分提交），工作树在实施前干净，远端 `origin` 同名分支已同步。
- `b67a129` 由快进合并引入：其父提交 `61d43a1` 即任务卡声明的拆分基线 `codex/rebuild-mainline-v1@61d43a1`，无分叉、无历史改写。

**B0/K0 可解析性：**

| 标记 | 固定 SHA | 本地可解析 | 说明 |
| --- | --- | --- | --- |
| B0 | `2a866cf138f6359f853db35e0a926ad79391b691` | 是 | 本分支历史中存在（`d9370a0` 的父提交），主题"Preserve transformed SVG icon curves and stroke scale in PPTX" |
| K0 | `2c5a4c50048b2641739356e72ddc1d6fea1d962f` | 是 | 本地不可达时需先 fetch；实际承载分支为远端 `origin/codex/sc1.1-native-core`（spec 00 所称 PR31 来源）。禁止整体合并或 cherry-pick |
| M0 | `main@bcb5b37` | 按 spec 00 仅作历史参照，不作为取用来源 | |

**B0→当前差异映射：** `2a866cf..b67a129` 仅含两个规格文档提交（`d9370a0` 落地 v1.1 规格包、`61d43a1` 规范化来源、`b67a129` 增加任务卡），无产品代码改动。实施从本 checkout 继续，不 reset 到文档 SHA。

**安装解释器与模块来源：**

- 系统 `python3` 为 3.14.6，`pip3 show deck-master` 与 `deck-master` 命令均不存在：**本机没有可解析的已安装 deck-master 实例**。spec 00 的 I0 附件安装源记录无法与任何本机安装对应，按"未知"如实登记。
- `python3.12`（`python3.12`）与 `uv` 均可用。开发环境按 handoffs 规定用 `uv venv --python 3.12 /tmp/deck-rebuild-dev` 建立候选解释器，再以该解释器 `python -m pip install -e '.[dev]'` 安装新包进行测试；不替换、不触碰用户已有安装（当前为不存在）。

## T01.02 完整文件处置表

按 handoffs 命令运行只读清单工具（未修改仓库，输出在仓库外）：

```bash
python3 docs/specs/deck-master-rebuild-v1/tools/materialize_inventory.py \
  --repo . --ref 2a866cf138f6359f853db35e0a926ad79391b691 \
  --out /tmp/deck-rebuild-inventory
```

结果：`status=inventory_generated_not_implementation_verified`，B0 跟踪文件 **931** 个，规则命中 exact 417 + prefix 514，`unclassified=[]`、`planned_or_absent_exact_paths=[]`、`repo_modified=false`。即 old-files/new-files/root-and-config 台账对 B0 全部跟踪路径给出处置去向，无未知路径；未知/差异项为零。

处置分类统计（`inventory/old-files.csv`，177 条 scripts 路径）：

| action | 数量 | 含义 |
| --- | --- | --- |
| RETIRE_THEN_DELETE | 105 | 行为不继承，历史留 Git |
| EXTRACT_THEN_DELETE | 43 | 行为移植到 `src/deck_master/*` 后删除 |
| DELETE_AFTER_CUTOVER | 28 | 多为包壳 `__init__.py`，切换后删除 |
| REPLACE | 1 | `scripts/deck_master.py` → `src/deck_master/cli.py` |

用户资料单列（不删除、不随包）：`runs/`、`benchmarks/` 私有源、`.codex`/`.claude` 会话、客户原件与历史发布工件。T01 阶段任何旧文件不删除；最终引用归零归 T24（AC-L05）。

本分支在 B0 之后新增的规格文档（`docs/specs/deck-master-rebuild-v1/**`）属于台账自身的输入，不在退役处置范围。

## T01.03 提取边界与反向 import 禁区

**新包禁用旧命名空间（spec 01.2 原文）：** 新 `src/deck_master` 不得出现 `runtime.* / workflow.* / high_density.* / preview.* / build.native_*` 等旧包导入；不得用 `sys.path` 插入 `scripts/` 或 HOME 仓库偷取实现；编译子包不得 import `service`、`tasks`、workflow、review 政策、安装用户 HOME 或模型工具。 enforcement 测试落在 `tests/rebuild/test_package_boundary.py`（AC-L07），随 T01 建立。

**逐项提取来源（B0=`2a866cf138f6…`、K0=`2c5a4c50048b…`；逐功能移植，不整包合并 K0）：**

| 新目标 | 提取来源 | 来源分支/SHA | 行为测试落点 |
| --- | --- | --- | --- |
| store.py 原子写/哈希/安全路径 | `scripts/high_density/contracts.py` | B0 | `tests/rebuild/test_store_transactions.py` |
| 完整稿接收/编排事实 | `scripts/runtime/orchestration.py`（`import_plan`、完整 PagePackage 接收） | B0 | `tests/rebuild/test_service_flow.py` |
| SVG 解析与几何修复 | `scripts/high_density/svg_native.py` | B0 | `tests/rebuild/test_geometry.py`、`test_svg_parser.py` |
| 文字（修 800/900 字重） | K0 `native_pptx` 文字实现，与 B0 `high_density/pptx.py` 对照 | K0 `2c5a4c50` | `tests/rebuild/test_text.py` |
| 取消/原子/晚到保护 | K0 `workflow/actions.py`、`build/native_tasks.py` | K0 `2c5a4c50`（需逐函数核验，见 spec 02.3） | `tests/rebuild/test_tasks.py` |
| SVG 画笔/透明度 | `scripts/high_density/svg_paint.py` | B0 | `tests/rebuild/test_paint.py` |
| DrawingML/PPTX 写入与 readback | `scripts/high_density/pptx.py` | B0 | `tests/rebuild/test_readback.py`、`test_drawingml.py` |
| 蓝图 prompt 装配 | `scripts/high_density/blueprint.py` | B0 | `tests/rebuild/test_production.py` |
| 正文可见原子/内容关系 | `scripts/high_density/content.py` | B0 | `tests/rebuild/test_content.py` |
| 材料定位/散列 | `scripts/context_intake/local_sources.py` | B0 | `tests/rebuild/test_sources.py` |
| 渲染对比度量 | `scripts/high_density/visual.py` | B0 | `tests/rebuild/test_render.py` |
| Web workbench 服务骨架 | `scripts/preview/server.py` | B0 | `tests/rebuild/test_web.py`（T05/T14） |
| 前端静态资源 | `scripts/preview/static/` | B0 | UI 人工验收（T14/T20） |
| 审阅/交付检查 | `scripts/review/readiness.py`、`scripts/quality/external_review.py`、`scripts/delivery/validate.py` | B0 | `tests/rebuild/test_review.py`、`test_export.py` |
| 安装器 | `scripts/skills/installer.py` | B0 | `tests/rebuild/test_install.py` |
| CLI | `scripts/deck_master.py`（重写，REPLACE） | B0 | `tests/rebuild/test_cli.py` |

上表为 T08–T19 的取用导航，不是已完成的提取；每项提取在对应 T 卡内以实际移植提交核验。禁止把 `high_density` 整目录搬入新包。

## T01.05 固定制作输入（仓库外）

按 `task-cards/inputs.md` 建立三类合成样本与登记表，存放于 `$DECK_REBUILD_EVIDENCE/inputs/`（本机根目录由执行者选择并登记在 index.json 的 env_var 字段；私有路径与原件不进仓库）。原事故图本机未提供，按 inputs.md 允许的替代路径执行：全部样本标注 `source=synthetic`，原图登记 `blueprint_pending`，由 T06 真实生图、T07 实际读图后修订期待为 v1 并登记原图 hash。**原事故未复跑，不以替代样本关闭事故复现结论。**

| 样本 | 覆盖内容 | Page | 期待版本 |
| --- | --- | --- | --- |
| REBUILD-ARCH | 三层职责、嵌套模块、图标、建设状态、双向/单向关系、脚注 | `deck_page_package.v2` | v0 生成前期待 |
| REBUILD-CHART | 数值、单位、图例、标签、比较关系（占比除式可复算） | 同上 | v0 |
| REBUILD-SOLUTION | 方案理由、阶段/责任、辅助说明、四级视觉层级 | 同上 | v0 |

每份样本含 `page.json`（完整 Page）、`content-source.md`（材料正文，尾部带只读/不可回写约束）、`design-requirements.md`（blueprint 输入）、`visual-expectations.md`（逐区域独立期待，含删除模块/反转箭头/数值一致性等反例）。`index.json` 登记全部文件 sha256、准备者与交接日期；消费者先核验路径可读与 hash 再继续。

## 证据与未验证项

- 实际命令与输出保存在仓库外 `/tmp/deck-rebuild-inventory/`（`summary.json`、`all-tracked-files.csv`、`cli-parser-literals.csv`）；本记录仅登记结论。
- AC-L07 的自动化验证见 `tests/rebuild/test_package_boundary.py`（本卡新增并运行）。
- 未验证项：本机未安装旧版本，I0"附件安装源 920dc3c5"无法核验为实际安装来源，按未知登记，不影响后续任务。
- 未验证项：三个样本原图 pending（blueprint_pending），T10 还原验收必须取得 T07 确认的真实蓝图。
