# PR #189 本机渲染与键盘差异修复

基准为 `260e13f4a9e810ced5d9c8f1582c8950aed4cc46`。范围是上一轮本机的 11 项渲染失败和 3 项键盘验收失败；旧基准同样失败不构成豁免。保留 Draft，不合并、发布或迁移实际 HOME。当前候选的独立 QA 和 CI 身份、完整结果以 PR 正文与本次 QA 原始记录为准，不沿用上一候选数字。

## 渲染：宿主与 LibreOffice 的 Fontconfig 默认配置不同

同一份 PPTX、相同字体与渲染工具，默认环境产生 LinuxLibertineG 替代字形；向渲染子进程传入宿主完整 Fontconfig 配置后，PDF 实际嵌入 HiraginoSansGB-W3。默认环境下，中文文本可能不可见，拉丁字形宽度也发生变化；仅检查文件存在或可提取文本不足以发现这个问题。

本机为 macOS、LibreOffice 26.8.1.1、Fontconfig 2.18.3、Poppler 26.10.0；LibreOffice 内置 Fontconfig 默认前缀与宿主 `fc-match` 使用的前缀不同。旧候选 CI 日志对应 Ubuntu 24.04.5、LibreOffice 24.2.7、Poppler 24.02.0、Noto CJK。这个平台差异经本机单变量对照确认，未通过替换字体或降低几何阈值修复。

`renderer_environment()` 在 macOS 且调用方未显式配置 Fontconfig 时，从 `fc-conflist` 发现唯一活动的完整根配置，只传给 LibreOffice 和 PDF 栅格化子进程。缺失、歧义或不可读时明确报告 `NeedsTool`，`doctor --step render` 同步展示配置检查。显式 `FONTCONFIG_FILE` / `FONTCONFIG_PATH` 和其他平台保持原有继承行为，不修改全局环境、应用包装脚本、字体或实际 HOME。

原用例不变的开发阶段对照：

| 阶段 | 结果 |
| --- | --- |
| 旧入口默认配置 | 11 failed / 23 passed / 4 deselected |
| 旧入口仅显式传入正确完整配置 | 34 passed / 4 deselected |
| 正式入口自动发现，外层没有配置覆盖 | 34 passed / 4 deselected |
| 新增子进程配置、调用方设置保留、失败拒绝和 doctor 用例 | 10 passed |
| 正式修复后完整渲染套件 | 138 passed / 1 Frozen A skipped，0 failed |

11 项包括 3 项真实 PPT 预览、2 项原生对象所有权差异、6 项真实字形溢出边界。没有修改这些用例的断言、阈值或超时。定向与完整套件、重复对照有重叠，不累加覆盖。

## 键盘：macOS 无头 Chromium 的原生菜单输入

旧本机使用 Playwright 1.61 / Chromium 149；CI 使用 Playwright 1.64.1 /
Chromium 156.0.8078.4。隔离下载与 CI 相同版本后，macOS 上原三视口仍全部
失败。产品控件与不包含产品脚本的裸 `select` 均表现为 ArrowDown 打开菜单，
Enter 后值仍为 `project`，未产生 input/change，排除了产品处理和版本差异。

验收仍通过 Tab 抵达原控件，改用浏览器支持的 Unicode 文字检索按键选择“独立”
上下文。由于 Playwright 的 press 键表不含中文字，驱动通过同一个 Chromium
`Input.dispatchKeyEvent` 输入通道发送真实 keyDown/keyUp；没有设置 select.value、
调用 select_option 或用 JavaScript 派发 change。三个视口共用同一序列，不按
平台跳过。原业务、焦点及长内容断言全部保留，新增选中值、焦点与可信
keypress/input/change 检查。

开发阶段同 CI 版本在本机 5/5 通过：原三视口与正常/故意阻断 change 的两条
对照。阻断处理时，控件仍可收到按键并选择值，但原“准备已核对”断言必须失败，
且不能出现独立上下文的准备请求；正常处理时二者均成功，Document 始终不变。
这证明驱动没有绕过业务处理。该修复针对自动化输入的跨平台可执行性，不将其
表述为真实 macOS 原生弹窗或输入法验收，也不改动产品控件迁就测试。
同 CI 版本的键盘及邻接回归共 15/15 通过；旧本机 Playwright 1.61 /
Chromium 149 下原三视口也 3/3 通过。上述重复执行不相加为独立覆盖。

## 验收与证据

原始记录在本次任务的 `.gstack/pr189-local-parity/`：`render/red.*` 保留修复前失败，`render/explicit-host.*` 为单变量对照，`render/fixed.*` 为正式修复定向，`render/fontconfig-probe.json` 包含实际 PDF 字体证据。`keyboard/` 保留输入事件与平台控制；`qa/` 是独立 qa-only 的原始日志、JUnit 和报告。仅自有隔离运行目录用于测试，不借用用户项目或实际安装目录。

一次开发环境全量收集使用了 Python `-I`，导致仓库工具模块 `tools` 不可导入；该 setup 失败原样保留。完整源码验收使用与 CI 相同的 `python -m pytest` 入口，同时核对产品模块来源。旧轮 archive 缺 Git 元数据的问题亦保留，不通过变更产品行为掩盖环境问题。

Frozen A 外部资源、真实 Host/S3、专业效果、原生目录选择器取消、用户视觉认可与 owner/第二人签收继续分别记录。自动化通过不代替这些验收，也不把 Mac 锁屏作为当前阻碍。
