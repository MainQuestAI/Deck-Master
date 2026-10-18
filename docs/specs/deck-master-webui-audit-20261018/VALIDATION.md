# 工程验证与复跑入口

本轮使用实际 HTTP 服务、Chromium、真实 ZIP 下载及本机渲染器。所有项目与已通过工程检查是明确的合成 L1 夹具；没有调用模型、伪造专业认可、启动客户迁移或更改日用安装。完整组合结论取本 PR 最终 head 的 GitHub Checks；本页记录可复跑范围和提交前已观察的证据，后续完整数量见 PR 验证记录，不能把重叠定向运行相加。

## 提交前已观察结果

- 全部 `src/deck_master` 与 `tests/rebuild` Ruff、49个 v2 JavaScript 的 Node 语法检查及 `git diff --check` 通过。
- 完整非浏览器/渲染组在环境修正后：2972 passed、2 skipped、621 deselected；两个跳过均要求外部 Frozen A 安装，未更改跳过条件。
- 完整487例浏览器组首轮479 passed、8 failed，失败均是本轮变更对应的旧入口/摘要/禁用交付预期，未出现新增产品故障；修正后从完整结果XML提取这8例作最终汇总重跑：8 passed。新CI会从最终代码重新完整执行487例。
- 交付判定定向组合：115 passed、1 deselected，包括新增50例相同稿件/控制/口播/实际文件的预检与真实导出矩阵。
- 真实渲染组：133 passed、1 skipped、3461 deselected。唯一跳过项 `test_frozen_a_real_sdk_refuses_protected_notes_write_boundaries` 依赖外部 Frozen A 安装；未把它改为通过。本轮正常 renderer、备注及三输出路径照常执行。
- 新增审查浏览器文件含21例，按批执行了入口/草稿/比较/几何/创建弹窗/交付异常，另单独通过长标题1例、实际正式与工程包2例、真实存储的 legacy 要求2例。另有既有控制/确认稿/阅读/材料定向24例通过，以及交付与备注定向20例通过；这些选择彼此重叠。
- 实际 wheel 构建并安装到独立临时虚拟环境，`w12_offline_browser.py --require-installed` 九项检查全部通过：三用途固定 ZIP 的实际字节哈希、备注保留/隐私剔除、包内静态资源、旧入口和无外部请求。使用本机 Arial 字体；CI 的 Linux 同链路使用 DejaVu Sans。
- 实际 shared-lock 跨进程两例通过，实际 own-wheel 六场景隔离 Runtime 探针通过；没有修改相应保护逻辑。
- 安装包完整恢复组首轮235 passed、5 failed，失败均为旧入口名或旧正式交付点击预期；修正后相关6例使用同一安装包全部通过，所有已加载 Runtime 模块均审计为安装包来源。最终CI会从干净checkout完整执行该组。

开发机器原有 editable 安装指向另一个 checkout，因此改用本任务独立虚拟环境；子进程使用规范化的绝对 Python 路径。旧 recorder 明确拒绝含 `private` 的路径，而 macOS `/tmp` 解析为 `/private/tmp`，所以完整运行的临时根位于任务 workspace。嵌套 own-wheel 测试通过任务虚拟环境可见的原有第三方依赖运行，自己的 deck_master 仍来自本轮 wheel。这些是环境修正，不是放宽产品或实验门禁。

## 条目到行为验证的索引

| 范围 | 主要可复跑文件与断言 |
| --- | --- |
| AUDIT-F01 | `test_webui_audit_browser.py`：真实混合层/页范围、导航无POST/业务版本变化；`test_studio_overview_browser.py`、`test_action_targets_browser.py`：既有动作、层、历史与异常；`test_rc3_studio_control_browser.py`：内容约定完成态 |
| AUDIT-F02 | `test_studio_delivery_browser.py`：精确初始/导入/缺intent模板及未知原文；`test_webui_audit_browser.py`：真实存储的历史 import_draft、改写模板、搜索与详情逐字保留；`test_run_desk.py`、既有 run/task 浏览器：现代摘要和阶段详情 |
| AUDIT-F03 | `test_webui_audit_browser.py`：纯材料/纯要求/混合草稿三分支真实提交、跨入口、刷新、取消、全差异；`test_pr105_inputs_browser.py`、`test_studio_content_browser.py`、确认稿/协作浏览器：输入协调与独立请求路径 |
| AUDIT-F04 | `test_webui_audit_browser.py`：0到5页、完整选择、筛选外页、窄屏说明与可访问关联；`test_gallery_reading_browser.py`、`test_studio_gallery_batch_browser.py`：阅读偏好、层/参考和批量制作范围 |
| AUDIT-F05 | `test_webui_delivery_parity.py`：5口播选择×10服务状态；`test_webui_audit_browser.py`：loading/error/ready、缺能力、迟到口播与R1/R2、重复点击单POST、同首屏；`test_rc3_studio_control_browser.py`：受阻禁用及直接POST仍被门禁拒绝；现有专业/授权/版本导出单元保持 |
| AUDIT-F06 | `test_studio_delivery_browser.py`：历史审阅包、三视口/ARIA/焦点/实际ZIP哈希；`test_webui_audit_browser.py`：正式与工程实际包同组件；`test_rc3_notes_export_browser.py`：丢失回执核实恢复及四备注方式，详情哈希等于真实下载 |
| AUDIT-F07 | `test_webui_audit_browser.py`：相同24页、scrollY=0、画布面积/12px标签/44px触点、长项目标题及控制；`test_studio_reading_browser.py`、`test_studio_page_browser.py`、既有意见/个人草稿/缩放/全屏回归；[前后测量与截图](evidence/) |
| AUDIT-F08 | `test_studio_delivery_browser.py` 及同步定位的既有11个任务区浏览器文件：可见名称“任务记录”；原URL、过滤、搜索、分页、已读及恢复协议继续由原行为回归覆盖 |
| AUDIT-F09 | `test_webui_audit_browser.py`：四视口真实dialog及queued-modal、焦点/必填/动态8页确认稿/关闭恢复/其他弹窗无样式污染；既有launcher及确认稿浏览器覆盖创建、条件口播必填与登记失败恢复；九字段相同条件前后测量见 [evidence/](evidence/) |
| PR120/122 | `test_rc3_studio_control_browser.py`、`test_rc3_studio_intake_browser.py`、`test_rc3_notes_export_browser.py`、`test_native_notes_view.py`：协作/授权/预算、确认稿与四口播方式，native_compile/attachment/public_export 三条真实备注输出路径 |

## 组合命令

使用本 checkout 的安装；本机命令中的 Python 是任务环境绝对路径，下面简写为 `python`。`<workspace-temp>` 必须位于已存在的父目录。CI 用其干净 runner 的默认临时根。

```bash
python -m ruff check src/deck_master tests/rebuild
python -m pytest -q tests/rebuild -m 'not render and not browser' -p no:cacheprovider --basetemp <workspace-temp>/unit
python -m pytest -q tests/rebuild -m render -p no:cacheprovider --basetemp <workspace-temp>/render
python -m pytest -q tests/rebuild -m browser --require-browser -p no:cacheprovider --basetemp <workspace-temp>/browser
```

构建 wheel 后在单独环境安装，运行 `examples/workbench/w12_offline_browser.py --require-installed --font <installed-font> --out <new-output>` 与 `w12_installed_regressions.py --out <evidence-json>`。后者检查所有已加载 Runtime 模块来自安装包，不借用源码资源。所用临时注册表与项目都在任务输出目录；未激活实际 HOME。

390×500 是受限可用高度的浏览器检查，不冒充原生软键盘验收。工程检查通过不等于专业签署、真实Host验收、正式日用激活或发布。
