# RC3-02 独立 code review：第六轮 acf2b2e（限定测试生命周期）

**结论：PASS（限定 390×844 测试等待实际 fit 状态的修复）。** 新等待与现有读取控制器的真实布局完成顺序一致；原严格几何断言、图层切换、固定 revision 和横向溢出检查保留。独立安装包延迟控制复现 image ready 尚未 fit 的暂态，随后真实 fit 与后续两帧均满足原边界。没有修改产品、notes、privacy、准入或稳定布局，也没有把旧完整 recovery 的失败改成通过。

Reviewer：`/root/rc3_02_code_review`，未参与实现。日期：2026-10-14 UTC。

## 固定对象和范围

- HEAD：`acf2b2edd4a88f74e8b671a18e32eb74b780eb84`；tree：`0d3ce4982e24a081cbf964259ea85891cd713aed`。实际 git 核对、source clean、diff --check 通过。
- 快照：`/workspace/work/rc3/reviews/rc3-02-code-snapshot-acf2b`。相对已审 `65d8203ec099b0460dbf031b24cf2ea5a02fd0f2` 仅 `tests/rebuild/test_workbench_usability_browser.py` 增加三行，其中两行注释、一行等待；完整 delta 与 fixture/运行时相关上下文均已读取。
- source `/workspace/work/rc3/env.sh` 后，精确 pytest 使用绝对 `/workspace/work/rc3/reviews/env-02-snapshot-acf2b/bin/python -I -B`；实际安装包控制使用绝对 `/workspace/work/rc3/reviews/rc3-02-installed-fixture-65d82-validation/venv/bin/python -I -B`。
- 后者实际 core 来自该环境 `site-packages/deck_master/__init__.py`，固定新 acf2b 测试 fixture 来自其 snapshot/tests/rebuild；不加载 snapshot/src、live source 或 Owner wrapper。独立逐字节核对该 snapshot 的 232 个非 pycache core 文件与安装包相同，执行中 47 个 deck_master 模块均来自该 site-packages。这里准确报告我的 232 文件核对范围，不借用 Owner 的 246 项 provenance 作为我的执行。
- 独占输出：`/workspace/work/rc3/reviews/rc3-02-code-round6-acf2b-scratch`；短临时 fixture：`/tmp/rc3cr6-acf`。未安装依赖、使用共享 bootstrap、改产品/测试/Owner raw/docs/冻结原件，未 commit/push/merge。

## 代码与断言判断

`test_workbench_usability_browser.py:20` 在初次窄屏测量前等待既有 `data-reading-mode=fit`，没有等待或重试“底边小于 viewport”这个断言，没有 sleep 或放宽阈值。随后仍立即计算 box 并要求 `box.y + box.height < height`；真实稳定 fit 如有裁切，仍会在这个严格断言失败。

现有 `images.js:143` 在 canvas 替换时先宣布 image ready。`page-reading.js:48` 无实际 canvas 就返回，不能提前宣布 fit；有 canvas 后在 `:51` 设置 viewport 高度、`:56–57` 设置 holder/canvas 实际尺寸，然后才在 `:58` 设置 readingMode/readingScale。`:66–69` 的 MutationObserver/ResizeObserver 通过 requestAnimationFrame 调度 redraw。因此 image ready 和后续 fit 是两个可观察状态。新等待绑定的是后者，属性是在同一同步 redraw 中实际尺寸写入之后设置，未创建一个仅为测试通过的状态。

该 testcase 创建真实新 Page 阅读节点并固定 p01/revision，等待处没有来自旧节点的 fit 属性。源码/默认缩放/读取模式均没有改动；本判断不扩展为任意重试、全屏或尺寸变化的通用保证。

## 我的实际执行

精确调用固定新版本 `test_reading_prioritizes_artwork_and_preserves_fixed_layers[390-844]`，使用 `--require-browser`、独占 basetemp 与 cache：**1 PASS / 1.93s，0 SKIP**。raw：`/workspace/work/rc3/reviews/rc3-02-code-round6-acf2b-precise-browser.log`。本 reviewer 没有把 Owner 的三个 viewport 或完整 recovery 计作自己的测试数量。

独立 `probe_installed_reading_lifecycle_v4.py` 用真实安装包、固定 acf2b 的 synthetic icon fixture、实际 WorkbenchServer 与系统 Chromium。仅扣住首个真实 SVG 请求，字体 ready 与真实帧完成后将原 route 原样 continue；后续请求正常继续。没有 fulfill 图片、伪造 canvas/pending、修改 CSS/控制器/属性或使用 sleep。MutationObserver 只读记录 DOM；浏览器 fetch 的只读 response.clone 核对实际字节，原 pending/response 原样返回给产品。

| 独立实测状态 | 结果 |
|---|---|
| 同 URI 正式 HTTP 与浏览器实际 fetch | 200、image/svg+xml、628 bytes；SHA256 均为 `557276c02680634ab6c0a8169e397fc70e792e5308a6e41b66ff184340d003ae`，与 Store 原 SVG 相等 |
| ready、尚未 fit | canvas ready=true、字体 loaded、mode=null、未写 viewport/canvas fit 尺寸；height=209px、bottom=848.488342px，原几何断言此刻确实失败 |
| 首次实际 fit | 约 9.8ms 后 mode=fit；viewport height=184.562439px、bottom=823.991028px；inline viewport/holder/canvas 尺寸均已写入 |
| fit 后读取与两个后续真实帧 | bottom 分别为 823.992249、823.986206、823.984497px，均严格小于 844px；没有等待几何结果变绿 |
| 原行为检查 | 原严格 box 边界、content 图层切换可见、固定 revision URL、无横向溢出均通过；page_errors=[] |
| 源和证据 | current Document 与 Store 原 SVG bytes 前后相等；47 个 core 模块为实际 installed 来源 |

raw：`probe_installed_reading_lifecycle-v4.log`、`installed-lifecycle-v4-observations.json`（完整事件、HTTP hash、47 模块来源与 232 文件 hash）和 `installed-lifecycle-v4-fit.png`。v4 正常退出且没有 teardown callback 错误。

最初 v1/v2 harness 在 Playwright Response.body() 返回空 bytes、同时 status=200/content-length=628 时中止；原日志、部分 JSON 与 v2 字节原件全部保留，没有将该观察 API 的未知差异判为产品返回空文件。v3 增加真实 fetch 只读 clone 后完整语义探针通过，但切换图层后的额外匹配请求被 harness 再次扣住，关闭时出现 CancelledError。v4 仅扣住首请求，后续原样 continue，保留 v1–v3 原件并得到上述干净结果；产品始终是同一个零差异 installed core。没有据这些 harness 修正修改生产行为或测试断言。

## 复用与未运行层

实际 git diff --quiet 证明 `src/`、`skills/`、`pyproject.toml` 与已审 ca035 为零差异，`examples/` 与已审 65d82 为零差异。按准确范围复用本人 Round 3 产品 code review、Round 4 CI render 依赖分组、Round 5 examples/文件闭环结论；本轮只新增上述生命周期审查，未盲目重跑完整产品套件。

Root/Owner 的旧 installed 完整 recovery **238 PASS / 1 FAIL / 797.48s** 及 bottom=848.805px 原 FAIL 继续保留。本 reviewer 没有重跑完整 239 recovery、三个 viewport 全组或远程七项 CI，也不签它们通过。Owner 的 held-response 原件仅作为背景，表中数值与结论均来自我的独立运行。

无新的实质缺陷；此限定修复可进入既定最终固定 head 的完整 recovery/CI 验证。真实目标 desktop 保存重开、人类 professional review、模型制作 E2E 和完整 RC3/最终 AC 仍按各自原状态记录，不能由本轮限定 PASS 替代。
