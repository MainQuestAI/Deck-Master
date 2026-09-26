# W03 前端：项目入口、固定阅读与个人草稿

前置共享核心 [PR #45](https://github.com/MainQuestAI/Deck-Master/pull/45) 已合并，基线 `062fd6974f0f1ed4053ee9a397f2b1c288bd42f4`。本切片仅增加 `/v2/` ES Modules、验证脚本和证据；旧 `/` 与 `view --open` 保持原入口。

## 已实现行为

- 无项目启动页展示显式登记的项目，可新建、手填/选择目录、移除登记、打开只读合成示例。名称、用途、受众、新目录位置有必填标签。创建不会启动模型。
- 新空项目进入内容与来源；已有页面首次进入制作总览，“看整稿原图”为唯一高权重主动作。五区导航、项目名、版本、页与层持续可辨。高级画廊、标注、候选、风格批量操作与新导出仍由后续卡片接入。
- 材料登记使用现有 `inputs_update`。浏览器验证中旧 compose 被新任务接续，只保留一个 eligible compose；交接读取该任务，不调 continue、不重复开任务，复制明确标为尚未开始。
- hash 路由固定逻辑项目身份、页面、层、版本、缩放与任务。阅读位置单独保存。当前版本改变后继续看原版本，历史持续只读；不存在的版本保留错误，不退回当前。未读成功时保留原工作面并标明其版本。
- 无制作工具执行能力时仍可阅读和保存个人草稿。以项目身份、目标层、基准 hash/revision 隔离草稿；同一端口的窗口也有独立未同步缓冲。多份预备提示词需要先选具体依据，不能把不同请求的草稿混在一起。
- 个人草稿区分本机缓冲、保存中、项目 ACK、待核实和冲突。待核实 payload 与后写内容分开；晚到回包不能覆盖重新打开的编辑器。冲突两稿可比较、另存、下载；切换本机副本前留存原稿，副本保存失败就保留当前输入。
- 项目 ACK 后才可从新端口读取；多份已保存草稿提供选择。未同步内容通过恢复文件显式导入。文件不含 session header/token；浏览器存储失败仍保留页内输入并可下载。
- 新 UI 检查真实健康协议；旧核心只进入升级说明，不发送新版写入。新版核心读取旧 v1 项目不迁移业务指针。SVG 经受控文件接口作为图片读取，用户文字用 text node。

## 视觉来源与范围

沿用[本轮读取的 8 个活动文件快照](design-snapshot/sha256-manifest.json)：白底、浅灰面板、黑色主按钮、少量绿色与用户调整的圆角；未覆盖 OpenDesign，也未改写长期 DESIGN.md。实施前第二次只读刷新返回 `Transport closed`，本次没有把它写成刷新成功。

快照的 style、icons 原样引用，tokens 仅清除末尾空行，运行布局与响应式放在 `workbench.css`。本切片在 1440×900、1280×800、1100×800、767×900、390×844 检查了真实服务界面与无整页横向溢出。较窄窗口保留阅读和个人意见，不承诺完整多页编辑。

## 验证与可复制入口

在 Python 3.11/3.12 开发环境安装候选及 dev 依赖，并具备 Chromium 后，从此 checkout 运行：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python examples/workbench/w03_browser.py --out /tmp/deck-master-w03-browser-proof
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python examples/workbench/w03_browser_edges.py --out /tmp/deck-master-w03-browser-edges-proof
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/rebuild/test_workbench_services.py tests/rebuild/test_ui_journal.py tests/rebuild/test_web.py tests/rebuild/test_workbench_reads.py
```

`--out` 必须为新目录。脚本只建隔离 registry/合成项目，finally 关闭自己启动的本机服务，不操作真实 HOME、不调用模型。边界脚本从 Git 已有提交 `09f4486a453d2132a18dbefd10f99ef7317e8fd5` 提取旧核心到临时目录，在独立解释器中运行；仅静态资源适配器向它转发 GET，不模拟旧 health。

本次核心回归 **74 passed in 20.06s**；常规浏览器 **15 项**、边界与兼容 **13 项**，共 **28 项通过**；详情见下列机器记录。JS 语法、Ruff、diff 检查通过。wheel 中 13 个 v2 静态资源逐字节核对；这仅证明构建包包含资源，正式离线安装与启动验收仍由 W12 负责。

- [浏览器场景及测量](w03/browser/checks.json)
- [旧核心兼容、故障注入与安全负例](w03/browser/edge-checks.json)
- [资源 SHA256 与构建包含核对](w03/browser/resources.json)
- [1440 项目入口](w03/browser/launcher-1440.png)
- [1440 单页](w03/browser/page-1440.png) / [1280 单页](w03/browser/page-1280.png) / [390 阅读及意见](w03/browser/page-390.png)
- [跨端口显式恢复](w03/browser/recovered-new-port.png) / [历史只读](w03/browser/historical-readonly.png) / [旧核心升级说明](w03/browser/old-core-upgrade.png)

原始 Playwright trace 仅留在隔离验证目录，可能含本机路径和 session header，不提交到仓库。公开证据仅为不含这些字段的检查结果和截图。未测用户理解时间、求助次数、下载/安装/Host 生成用时，不宣称首次使用少于五分钟。

隔离 Quickstart（源码候选）：

```sh
PYTHONPATH=src python -m deck_master workbench --registry /tmp/deck-master-w03-quickstart/projects.json --no-open --json
```

打开返回的动态 URL，可使用“打开只读示例”。结束后分别使用 `workbench --project <示例实际目录> --stop --json` 与 `workbench --registry /tmp/deck-master-w03-quickstart/projects.json --stop --json` 关闭项目服务和入口。路径从实际启动输出/登记列表获得，不假设固定端口或项目 ID。

## 兼容与剩余项

| 组合 | 已证明的行为 |
|---|---|
| 新 UI / 新核心 / 新项目 | 新建、材料更新、固定阅读、草稿与交接 |
| 新 UI / 新核心 / 真实旧核心建立的 v1 项目 | 可读、无业务指针迁移 |
| 新 UI / 真实旧核心 | GET-only 静态适配下显示升级提示，仅访问 health，零 POST |
| 旧 UI / 新核心 | 原 `/` 继续显示页数与正文，未默认切换 |

W02-AC02 的新 UI 兼容组合由上述真实浏览器证据补齐；旧 reader/writer 拒绝新 minimum_writer 的证据仍见 W02 原报告。

真实 macOS 目录弹窗未驱动：CUA 在界面清单调用时超时，未打开目录弹窗。取消响应后的输入保留/零登记已做浏览器故障注入，服务的固定选择器和取消分支有核心测试；不把这些称为系统弹窗实机通过。W03-AC02 保留这个人工/可用 UI 工具复核项，不阻断后续独立卡片。全卡用户验收、W12 正常安装、默认切换、HOME 迁移与发布均不由本记录签收。
