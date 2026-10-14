# RC3-02 独立 code review：第四轮 bc0b39f（CI 测试依赖）

**结论：PASS（限本次测试依赖分组与断言修复）。** 四个真实预览调用者均进入 render gate，剩余 unit 在缺失配置工具时通过，工具可用时四个 render 用例实际执行通过，没有新增 skip、伪造 renderer/pending 或弱化断言。本报告不把旧 0d12 CI 失败改成通过，也不宣称新远程全七 CI 已完成。

Reviewer：`/root/rc3_02_code_review`，未参与实现。日期：2026-10-14 UTC。

## 固定身份与 delta

- HEAD：`bc0b39fd9265d3408f69e95bc09047bf59a802d4`；tree：`6f860d74e88543e965023b36ca0ee25ed4884f53`。
- 上一 CI HEAD：`0d12a9d78ed0526f0fb74d1b8abed0a2ec154b4e`。
- 隔离快照：`/workspace/work/rc3/reviews/rc3-02-code-snapshot-bc0b3`；实际执行器：`/workspace/work/rc3/reviews/env-02-snapshot-bc0b3/bin/python -I`。source `work/rc3/env.sh` 后始终使用该绝对 Python；独立探针核对 module 来自固定 bc 快照。
- delta 唯一文件为 `tests/rebuild/test_rc3_notes_transactions.py`：四处 render marker、helper 文档及正常 continue 的明确 status/单 pending/实际 PageVisual/已存 preview 断言。`src/`、`skills/`、`pyproject.toml` 相对 0d12 和已审 ca035 都无 delta。
- 独占 scratch：`/workspace/work/rc3/reviews/rc3-02-code-round4-bc0b3-scratch`。未改源码、Owner raw/docs/生产账本，未安装依赖、共享 bootstrap、commit/merge。`git diff --check` 通过，固定 source clean。

## 审查判断

完整搜索确认 `_completed_visual` 只有四个测试调用者，且四者都执行真实 SVG preview 与正式 PageVisual 流程：

1. `test_notes_edit_preserves_completed_visual_and_actual_review_bytes`
2. `test_visual_open_finding_not_fixed_by_notes`
3. `test_actual_completed_visual_notes_assembly_export_zero_image_ledger`
4. `test_frozen_a_real_sdk_refuses_protected_notes_write_boundaries`

因此这些测试确实需要 rsvg，归入已有 render CI job 合理；该 job 已安装 librsvg2-bin、LibreOffice、Poppler 和字体。新增 helper 断言要求 normal continue 返回 awaiting_host、恰一个实际 page_visual review Task、已持久化 svg_preview；没有把 needs_tool 当 pass，没有生成 fake pending 或填 placeholder preview。原 notes/ref/hash、开放 finding、实际 PPTX/export、zero image ledger 和旧 A 拒写断言保留不变。

第四项原来已有 `if not frozen_A_python.exists(): pytest.skip(...)`，本 delta 没有新增或放宽它。本地隔离 A 资源存在，本轮四项均实际执行，**0 SKIP**。新远程 CI 是否具备这项外部 A 资源只能按其实际日志记录；收集到 render 不等于远程四项都执行，不能用本地结果把既有条件 skip 写成远程 PASS。

## 本 reviewer 实际对照

两个 pytest 命令分开记录：

| 执行 | 实际结果 | 证据 |
|---|---|---|
| 设置 `DECK_MASTER_RSVG_CONVERT` 为实际不存在的 scratch 路径，运行该文件的 `not render and not browser` | **15 PASS / 4 deselected，1.41s** | `rc3-02-code-round4-bc0b3-no-tool-unit.log` |
| source 实际工具链，运行该文件 `-m render` | **4 PASS / 15 deselected，2.42s，0 SKIP** | `rc3-02-code-round4-bc0b3-four-render.log` |

另独立运行正式 create/Task/SVG accept→normal continue 缺工具/有工具对照，没有 mock。缺配置工具返回 needs_tool、0 pending、svg_preview=null；实际 rsvg 可用时返回 awaiting_host、恰一个正式 PageVisual Task，真实 PNG 为 320×180，并经 Store 文件 hash 与 Pillow 解码核验。证据：`probe_renderer_requirement.py/.log`。

独立读取四个 render 测试留下的真实项目：每个 svg_preview 都是正确页面的实际 PNG，file hash 检查通过、Pillow verify 通过、derived_from 指向当前 SVG，Document 中确有正式 PageVisual Review 记录。证据：`probe_preview_and_collection.py/.log`。这些 Review/原图是明示合成 L1；实际 rsvg PNG 是本地工程证据，不冒称真实模型视觉或人类批准。

## CI 收集边界

以 `.github/workflows/rebuild.yml` 未修改的实际选择器作完整 collect-only，未重新执行全套产品测试：

| CI selector | 实际收集 |
|---|---|
| `not render and not browser` | **1847 / 2307 collected，460 deselected** |
| `render` | **57 / 2307 collected，2250 deselected** |

四个 helper 调用者各自恰一次出现在 render collection，全部不在 unit collection；该文件余下 15 个 parameterized unit 条目保留。没有删除测试或通过 skip marker使它们从 gate 消失。日志为 `rc3-02-code-round4-bc0b3-collect-unit.log` 与 `rc3-02-code-round4-bc0b3-collect-render.log`，独立脚本逐项核对了四个 node ID。

## 历史失败与产品审查复用

Root 提供的原 CI `38639118685` 四个 Unit job 各 `3 FAIL / 1845 PASS / 3 SKIP`，以及 `/workspace/work/rc3/reviews/rc3-02-ci-toolchain-0d12-reproduction` 的真实缺/有 rsvg 复现原件保留。本 reviewer 阅读了其 reproduction JSON 与缺工具 continue JSON，但没有冒称本人重新运行旧远程矩阵。bc 本轮实际对照与该根因一致：依赖 renderer 的 fixture 被误放进无 renderer 的 Unit job；产品在无工具时正确返回 needs_tool。

产品字节与 ca035 独立工程 code review 相同，可精确复用 `rc3-02-independent-code-review-round3-ca035.md` 的工程结论及其注明的前轮文件证据，不重新宣称旧 0d12 CI 绿，不无界重跑约 1800 项产品审查。此处只关闭测试依赖归类/报错断言的问题。

新完整 unit/render 和全部七项远程 CI 以实际后续运行记录为准，本轮没有签其整体 PASS。桌面 notes 视图、编辑保存重开、真实 Owner/听众、人类 professional evidence、完整 RC3/最终专业 AC 仍保持各自 NOT_RUN 或已有独立状态；本修复不改变 Runtime 门禁、不授权部署。
