# A01 实施与验证记录

日期：2026-09-30。分支 `codex/webui-a-implementation`，基线 tag `baseline/webui-v4-20260930`（`5e2c4de`，产品代码 `66da345`）。机器可读结果见 [a01-browser-verification.json](a01-browser-verification.json)。

## 交付内容

改动文件（均在 `src/deck_master/resources/static/v2/`）：

| 文件 | 改动 |
|---|---|
| `dom.js` | 新增共享状态组件：`loading()`（加载提示）、`errorNote()`（局部错误：发生了什么/内容是否保留/下一步/文档入口）、`disabledReason()`（禁用原因，可见文本 + `aria-describedby` + `title`，可选不可见模式）、`sortHeading()`（表头排序基础组件：`th[scope=col][aria-sort]` + quiet 按钮，设计系统第 07 节） |
| `run-desk.js` | 最小移植 PR66 的 `choiceMade` 水合竞态修复（4 处 hunk，仅此文件）；接线 AC03 组件：读取中显示加载提示、读取失败显示局部错误 + 重试、分页与取消按钮给出禁用原因；notice 从 `p` 改为 `div`（修复 div 嵌 p 的无效结构）；修复既有的修改组下拉 `replaceChildren` 数组未展开缺陷 |
| `workbench.css` | 全部硬编码颜色改为设计 token（`--fg/--bg/--surface/--surface-warm/--border/--border-soft/--muted/--accent/--accent-hover/--danger` 派生式）；焦点环对齐覆盖层（2px `--accent-hover` + focus-ring）；主按钮 hover 对齐 `--fg-2`；禁用态保持可读并 token 化；移除 `.ui-icon` 20px 覆盖（恢复规范 18px 默认/导航 20px）；修复 `.reference-button` 26px 违规（恢复 44px）；外壳密度对齐设计（workspace 40px/1520px、topbar 40px、sidebar 28px、h1 32px、page-head p 15px）；新增状态组件样式 |
| `tokens.css` / `icons.js` / `style.css` | 未改动——已与收讫设计逐字节一致（style.css 与设计 1–462 行相同；设计尾部 463–493 行属 A03 总览矩阵/待办样式，不在本卡范围） |

## PR66 评审结论

PR #66（`codex/workbench-w12-final` @ `93c76a1`，OPEN）。**复用其 `run-desk.js` 的 `choiceMade`/分页恢复修复**：筛选变更、翻页、“核实最新执行状态”都置位 `choiceMade`；“核实最新执行状态”新增 `persist()`；水合在 `choiceMade` 时跳过恢复已保存状态并改为持久化当前选择（同时覆盖 `draft-editor-replaced` 重水合路径）。**不复用其余文件**（W12 报告完成声明、execution-state/run-state-recovery 证据块、installation.md 措辞）：安装/压力证据归 B07 且必须以新整合 SHA 重建；PR 本身不合入、保持 OPEN。

## 验证命令与退出码

```bash
# 核心/HTTP（真实 Python 核心，无 mock）
PYTHONPATH=src pytest tests/rebuild/test_run_desk.py tests/rebuild/test_browser_wire_digest.py -q   # 9 passed
PYTHONPATH=src pytest tests/rebuild/test_web.py tests/rebuild/test_workbench_e2e.py \
  tests/rebuild/test_workbench_reads.py tests/rebuild/test_workbench_operations.py \
  tests/rebuild/test_workbench_services.py tests/rebuild/test_summary_poll.py \
  tests/rebuild/test_package_boundary.py tests/rebuild/test_install.py -q                          # 106 passed
PYTHONPATH=src pytest tests/rebuild -q                                                             # 905 passed, exit 0

# 浏览器（真实 WorkbenchServer + 合成可编辑示例项目 3 页 33 任务，无模型调用）
# fixture：/tmp/a01-browser/prep_a01_server.py（附录全文），playwright-cli 会话 a01/a01check
```

## 分层结果

**AC01（两视口对照收讫规范）**：1280×800 与 1440×900 下 59 个可见按钮 0 个低于 44px、控件 0 个低于 44px；计算样式断言主按钮黑底白字 44px/12px 圆角、`:focus-visible` 键盘聚焦为 2px `#0a7a5e` + 3px focus-ring、禁用态可读（surface 底 + muted 字、opacity 1）；从 `#view-title` 起的 Tab 遍历与 DOM 顺序逐项一致（run desk 无 roving tabindex）；“放大固定参考图”弹窗 Escape 关闭后焦点返回触发按钮；body/h1 字体为设计 sans 栈，`document.fonts.size=0`、0 外部资源、无 `@font-face`/CDN/框架。截图：`output/playwright/a01/ac01-overview-1280.png`、`ac01-runs-1440.png`。**aria-sort**：`sortHeading` 基础组件已交付；A01 文件范围内无消费面（总览矩阵排序属 A03/G02，任务列表重排属 A07/G36），不将其记为产品行为通过。

**AC02（慢 UI 状态读取保护）**：`/api/drafts` 延迟 3s 后重载，在水合完成前点“核实最新执行状态”→ 水合后仍为“当前执行状态 · 第 1 页”（用户选择未被覆盖）；该选择经整页刷新仍保留（offset=0 + live）；同样延迟下先把状态筛选改为“执行失败”→ 水合后筛选保留（共 0 项）；回归：已保存 offset=30 刷新后仍恢复第 2 页固定记录。PR66 复用结论如上。

**AC03（实际服务状态组件）**：读取进行中显示“正在读取当前执行状态…”且旧行保留（不以空数据代替）；筛选无结果显示“没有匹配的运行记录”空态；中断 `/api/tasks` 显示局部错误（“本机服务暂时无法连接，已读内容与本机输入仍保留。” + 恢复手册引用 + 重试按钮，旧行保留，重试后恢复 33 项）；禁用原因两模式验证——分页（不可见：`title`/`aria-describedby`）与历史版本取消按钮（可见文本“当前视图只读，不能取消任务。”）；示例身份可见（横幅 + 侧栏标签 + 历史横幅）。生产入口 grep 无“模拟接手/返回/失败”控件（仅存在于设计原型，保留为参考）。截图：`ac03-historical-disabled-reason-1280.png`。

## 过程中发现并修复的既有缺陷

修改组下拉（`按修改组筛选`）将选项数组未展开传入 `replaceChildren`，Chromium 把数组字符串化为 `[object HTMLOptionElement]` 文本节点，下拉长期不可用。已改为展开传入，验证后 33 个真实选项可读。

## 缺项与边界

- aria-sort 的产品行为随 A03（矩阵）/A07（任务列表）落地；A01 只交付共享组件。
- PR66 保持 OPEN，其 W12 安装/证据文件未合入（归 B07，按新 SHA 重建）。
- G02 roving→Tab、G12 画廊焦点归 A03/A04，未在本卡顺带修改。
- 真实制作工具与最终安装层不在本卡闸门（见 EXECUTION）。

## 附录：浏览器 fixture 脚本

全文见 [a01-browser-fixture.py](a01-browser-fixture.py)（复用 `tests/rebuild/test_candidates.py` 的合成任务/结果助手：`create_sample(page_count=3, readonly=False)` + 32 次 dispatch + 5 次 task_start + 1 次 SVG 结果接受，`WorkbenchServer` 输出真实 HTTP API；运行方式 `PYTHONPATH=src python a01-browser-fixture.py`，stdin 保持打开即服务存活）。
