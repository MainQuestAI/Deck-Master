# RP-05 / RP-25 本地证据补充

基准：PR #184；本次只在独立 worktree 从
`2e1c5ce40622e366a751c89f783fa23174752355` 创建本地分支。
2026-10-23 UTC 执行；无产品运行时代码改动、无推送或 PR 更新。

## RP-05：必要重建正向测试

既有测试仅证明有效预览复用及缺失/过期/错误页/损伤预览被拒绝，缺少
“实际重建后再审查、组装”的正向序列。新增
`test_real_rsvg_rebuild_then_review_and_assembly[missing|stale]`：

- 提交缺失或过期预览，组装前置真实拒绝。
- 调用 `preview_svg_page`，观察真实 `rsvg-convert` 子进程，不替换输出。
- 检查新预览来源绑定、尺寸、非空白像素；重复请求保持 pointer 且不重复渲染。
- 预览改变后组装仍受 page_visual 门禁阻止；按真实审查协议提交明确标注 L1 的合成审查结果。
- 真实 PPT 编译、LibreOffice 转换、Poppler 渲染及报告回读通过，保留另一页有效预览，整个流程 rsvg 只调用一次。

**新增两例 NOT_RUN**：`command -v rsvg-convert` 返回 1。本轮无系统安装授权，
没有安装、绕过或使用替代渲染器。pytest 明确显示两例 SKIPPED，不是通过。
测试代码已补齐，但其真实渲染路径仍待具备已批准 rsvg 环境后执行。
既有有效预览路径实际通过（含 PPT 渲染/回读）；环境 soffice/pdftoppm wrapper
分别调用已有 native LibreOffice/Poppler，未在本轮安装或改写。

```sh
PYTHONPATH=src /workspace/Deck-Master/.venv/bin/python -m pytest -q -rs \
  tests/rebuild/test_pipeline_preview_reuse.py tests/rebuild/test_summary_poll.py \
  tests/rebuild/test_local_runtime_burst.py tests/rebuild/test_ui_state_clear.py \
  --basetemp=/tmp/rp05-rp25-followup
```

结果 **21 passed, 2 skipped in 9.05s**。日志 `/tmp/rp05-rp25-followup.log`。
`ruff check tests/rebuild/test_pipeline_preview_reuse.py`、`git diff --check` 通过。
RP-05 AC1 仍 PARTIAL（真实重建未执行）；AC2 现有本地转换/回读 PASS，
不代表原图保真、真实专业审查或客户验收。

## RP-25：当前源码的隔离匹配安装

旧证据 `execution/RP-25.md` 已清楚将正式目标 Host 与现场 workload 留为 PARTIAL。
本轮刷新当前集成源码的本地安装证据，不能代替那个缺口。

1. `git archive 2e1c5ce4` 解包到 `/tmp/rp25-2e1c5ce4-match/source`。
2. 现有 venv 执行 `pip wheel --no-deps --no-build-isolation --no-cache-dir SOURCE -w WHEELS`。
3. `pip install --no-deps --no-cache-dir --target /tmp/rp25-2e1c5ce4-match/installed WHEEL`。
4. 对比源码包与安装包：**280 文件全部逐字节相同**，零缺失/不同。
5. 分别以 source/src 与 installed 为 PYTHONPATH，串行运行归档的
   `examples/workbench/rp25_reading_measure.py OUT`。真实系统 Chromium，
   各自独立临时项目和浏览器 profile；未改 HOME 或 Host 注册。

wheel SHA256：`6aa7ca499d8ad7163ab21f313b03f9004da8abd30305de2a58fd9f73fd5be8a8`。
源码运行 04:31:14.245–04:31:34.803 UTC；安装运行 04:31:40.078–04:32:03.786 UTC。
模块路径与图片模块 SHA 已保存，安装运行确从 installed 加载。

固定相同合成 30 页、1440×900、studio→gallery、overview↔gallery 三次、空闲 16 秒：

| 版本/阶段 | wall 秒 | Python CPU 秒 | browser TaskDuration 秒 | 请求数 | 缩略图状态/文件请求 |
|---|---:|---:|---:|---:|---:|
| source cold | 1.9897 | .7996 | 1.5787 | 127 | 34 / 8 |
| installed cold | 2.2389 | .8143 | 1.5555 | 133 | 35 / 13 |
| source warm ×3 | 1.4871 | .3316 | 1.2077 | 61 | 9 / 9 |
| installed warm ×3 | 3.9059 | .3122 | 3.5164 | 61 | 9 / 9 |
| source idle | 16.0142 | .0226 | .0577 | 2 | 0 / 0 |
| installed idle | 16.0044 | .0314 | .1212 | 2 | 0 / 0 |

两次均零 pageerror，空闲仅一次 summary 和一次 control，无缩略图请求；网络峰值≤6、
解码峰值≤2。Python CPU 包含 server 和 Python 浏览器 driver；TaskDuration 是
浏览器主线程任务时间而非 Chromium 总 CPU。端到端 wall 含等待和布局。
这只是各一次测量；安装 warm 明显较慢、cold 图片请求更多，**不能据此宣称性能改善或
请求数降低**，更不能拿旧 19 秒比较。合成运行时间/请求差异保留在原始记录中。

原始结果：[rp05-rp25-followup/](rp05-rp25-followup/) 包含 matching、两份 measure 和
两份 provenance JSON。测试仍是本地合成 workload，不是客户现场。没有付费模型调用。

## 尚未完成的能力

- RP-05 必要 rsvg 重建两条正向路径：因缺依赖、安装未授权而 NOT_RUN。
  恢复步骤：在已有 rsvg 或用户批准后安装的环境运行上述两个参数用例，不修改测试门禁。
- RP-25 正式目标 Host 匹配安装、客户现场规模和长稳态 workload：NOT_RUN。
  需要实际授权环境和明确同一项目/操作序列，临时安装不代表正式现场。
- RP-25 AC1 本地当前源码/安装匹配验证 PASS；现场部分未验证。AC2 已有轮询机制
  回归本轮重跑 PASS，但没有新声明所有现场交互通过。AC3 仍 PARTIAL；不关闭 #140/#142。
