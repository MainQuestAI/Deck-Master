# RC3-02 独立 CI regression review — round 4

**结论：PASS（bc0b3 测试分组/renderer 修复的独立回归范围）。** 四个真实渲染 fixture 的 caller 进入 render gate，缺工具的其余 unit 选择通过，四条 render 轨迹实际执行通过；完整 collection 没有丢测试。旧 CI 的失败保持原失败，不改写为 PASS。

Reviewer：`/root/rc3_02_regression_reviewer`，未参与实现。日期：2026-10-14 UTC。

## 固定身份与变更

- HEAD `bc0b39fd9265d3408f69e95bc09047bf59a802d4`，tree `6f860d74e88543e965023b36ca0ee25ed4884f53`；parent `0d12a9d78ed0526f0fb74d1b8abed0a2ec154b4e`。
- Snapshot `/workspace/work/rc3/reviews/rc3-02-code-snapshot-bc0b3`；专用 Python `/workspace/work/rc3/reviews/env-02-snapshot-bc0b3/bin/python -I -B` 实际 import 该 snapshot src。
- 完整 delta 仅 `tests/rebuild/test_rc3_notes_transactions.py`：一个 helper 增强真实返回断言、四个 caller 加 render marker。相对 0d12 与本人 round3 ca035，`src`、`skills`、`pyproject.toml` 均零 delta；CI workflow 也未改变。未改产品、旧报告/旧 CI 原件、依赖或共享 bootstrap，未 commit/merge；结束时固定 source clean。
- 所有本轮新日志/合成临时项目在 `/workspace/work/rc3/reviews/rc3-02-regression-round4-bc0b3-scratch/`，下文路径相对此目录。L1 合成输入与实际 renderer 文件工程分层记录，不声称生产、模型、人类或目标桌面效果。

## 实际缺工具与四条完整 render 路径

| 执行 / 条件 | 本人实际结果 | 原件 |
|---|---|---|
| 受影响文件的剩余 unit selection，真实配置 `DECK_MASTER_RSVG_CONVERT` 为不存在的可执行路径，`-m 'not render and not browser'` | **15 PASS，4 deselected，1.49s**；无 skip、没有伪造 pending 或替代 renderer | `unit-missing-renderer-pytest.log` |
| 同文件 `-m render`，实际工具可用 | **4 PASS，15 deselected，2.57s**；包括已完成视觉/Review 复用、开放 finding、实际 produce/export/零新增 image、真实旧 A SDK 拒写 | `four-render-pytest.log` |
| 独立正式 create→Task/SVG 接纳→正常 continue，配置缺失 renderer | `needs_tool`，0 pending，svg_preview=None，具体原因 `rsvg-convert unavailable` | `actual_renderer_contrast.py`、`actual-renderer-False-continue.json`、`actual-renderer-False-document.json` |
| 同一正式路径、真实可用 renderer | `awaiting_host`，恰好 1 个 `review_stage=page_visual` Task，实际 svg_preview file；逐字节 PNG signature、PIL 完整读取与尺寸/hash 检查通过 | `actual-renderer-True-continue.json`、`actual-renderer-True-document.json`、`actual-renderer-contrast.json/log` |

已确认 `_completed_visual` 恰有四个 caller，全部 render-marked。新 helper 不再盲取 `[0]`：明确校验实际 `awaiting_host`、一个 pending、review kind/page_visual stage 和真实 preview Ref。独立探针进一步读取真实 PNG，不能靠手造 pending、空 preview 或 fixture fallback 通过。

## 完整 collection 与 CI 边界

使用同一专用环境在两个固定测试树分别完整 `--collect-only`，只收集、不执行全树 fixture：

| 固定测试树 | Total | Unit（not render/not browser） | Render | Browser |
|---|---:|---:|---:|---:|
| 0d12 parent | 2307 | 1851 | 53 | 403 |
| bc0b3 | 2307 | 1847 | 57 | 403 |

变更恰为四个既有 node 从 Unit 转 Render：notes visual/Review 复用、open finding、notes assemble/export、frozen A SDK。无新增/删除测试，browser 不变。原始 collection 两个 ID 因未变 `test_new_operation_ids_are_uuid4` 在 import 时生成 `uuid4().hex/uuid1()` 而不同；保留 raw inventory，仅按这两个已核实的生成参数种类归一化后比较，节点集相同，不宣称原始字节相同。

证据：`collect_inventory.py`、`collection-before-0d12.log/json`、`collection-after-bc0b3.log/json`、`collection-diff.json`。

`.github/workflows/rebuild.yml` 的真实边界正确：四个 Python 3.11/3.12 × Node 22/24 Unit jobs 运行 `not render and not browser`，不装 renderer；独立 Python 3.12 render job 先 apt 安装 librsvg2-bin/LibreOffice/poppler/fonts 再运行 `-m render`。browser job 另装 renderer 与 Chromium，`--require-browser`，随后已安装 wheel 验证；Group report 依赖 Unit/render/browser 全成功。marker 调整让真实依赖与此分界一致，没有删测试或用 skip 代替本人四条 render 的实际运行。

本轮 **未执行完整 1847 Unit、完整 57 Render、四个远端矩阵或全部七个 GitHub CI jobs**，这些由 Owner/Root 后续固定候选与 CI 原件证明；不能把 collection 数量写成执行数量。

## 旧失败、证据复用与限制

PR117 的旧 CI `38639118685` 四个 Unit jobs 的 `3 FAIL / 1845 PASS / 3 SKIP` 和原 IndexError 复现仍保持旧版本失败，原件目录 `reviews/rc3-02-ci-toolchain-0d12-reproduction/` 未改。该历史结果来自 Root 的归档，未冒称本人重新运行四个远端 jobs。本人本轮的正式 missing/available 对照独立确认相同 renderer 根因。

产品、权限、notes 与费用事实实现相对本人 round3 ca035 byte-identical，因此按准确 hash 不变复用本人 round3 的适用工程范围（77 项定向执行、原三条失败关闭、两例 Chromium、真实旧 A 26 拒写/费用不变），未无界重跑。其中一个真实旧 A SDK fixture 本轮也在四个 render cases 内实际执行；其余成本/文件全 hash 证据仍引用原 round3，未伪称本轮重新跑了 26 入口。

真人 Owner/听众、目标桌面 notes 视图/保存重开、完整彩排与完整 RC3/最终发布验收仍 **NOT_RUN**。本轮 PASS 只支持固定 bc0b3 的小范围 CI regression 修复；最终 docs/head 漂移与全部 CI 结论由 Root 再核，未合并。
