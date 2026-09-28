# W05 单页链路与提示词工作台

共享核心 PR #49（精确 head `4640a02555a701e9dd41084df2b1fffced2c63f9`，8 项 CI 全绿）已合入 `a2a27f6937209da6befc440dd787c1065a845c94` 后，才开始此处前端实施。前端代码提交 `0df9546bed3a356e7266c183893d0b062f895222`，所在 worktree 为本线程 `workbench-implementation`；原 A/B/设计工作树未修改。

单页标签可查看来源、逐页稿、预备/实际提示词、原图、SVG 与整稿制作后的按页 PPT 预览。原图的生成依据只使用该图绑定的请求、尝试和观察记录，未知模型/seed/附件不从默认值补齐。来源、比较侧的依据链接始终保留自身固定版本。界面沿用用户修改的浅灰白表面、黑色按钮和绿色状态；没有回写 OpenDesign。

提示词全文只读，可核对原始 Unicode 码点选段；鼠标 DOM UTF-16 偏移显式转换，不归一 CRLF、组合字或 emoji。只对核心已证明格式显示结构段落。预备/实际与原文/个人草稿可看差异，长文本退回明确标注的全文对照。草稿复用 W03 journal、ETag 与恢复文件；多份请求选择会一起改变原文、冻结参数、参考图和草稿基准，历史文本不被编辑。

同页、同层比较固定两个已提交版本；宽屏并排，窄屏切换。背景标题和原图更新只出现提示，已读两个 canvas 的像素内容、版本保持不变。比较读取失败保留原有双方。SVG/PPT 制作摘要保留各项来源和真实计数口径、声明字体与编译输入、专业使用/桌面编辑记录。没有实际桌面评估就显示未评估。

## 验证

- [W05 浏览器原始检查](w05/browser/checks.json)：真实 Chromium / 本机 HTTP，15 组行为；代码提交及 21 个静态文件 SHA256 已逐一对照 Git 对象。macOS 27.0 arm64 / Python 3.12.12 / Chromium 149.0.7827.55，1440×900、1280×800、1100×800。
- 原图到实际提示词、逐页稿的路径在 3 次明确点击内；prepared/实际/草稿边界、可信结构段、恶意 HTML 原样显示、Unicode 与 CRLF、长文本差异上限、Host申报/未知、固定参考文件均覆盖。
- 提示词草稿 ACK 跨端口自动恢复、未同步内容不会自动出现、下载后新端口显式导入通过。恢复文件与 trace 仅留本机。
- [W03 主流程 15 项回归](w05/w03-main-regression.json)及[边界 13 项回归](w05/w03-edge-regression.json)通过：包括丢 ACK 后续写、两窗口 ETag 冲突、配额失败、原文基准隔离、旧核心防护、XSS/SVG 隔离、历史只读。真实目录弹窗仍未实机操作，不升级该结论。
- [W04 画廊 18 项回归](w05/w04-gallery-regression.json)通过，包含连续阅读锚点/键盘、画廊状态冲突、缩略图并发与 80 页缓存走查。完整 300×5×3 压力与 W10 的 20 分钟 heap 仍未在这里验收。
- `test_web.py`、`test_workbench_reads.py`、`test_page_detail.py`：60 passed（16.95s）。Node 语法、Ruff、diff 检查通过。
- [wheel 内容检查](w05/wheel-assets.json)：从固定提交隔离构建，21 个 UI 文件与源码字节一致；这是包内容验证，不代替 W12 完整安装和离线使用验收。

[提示词与选段截图](w05/browser/screenshots/prompt-selection-draft.png)、[固定比较](w05/browser/screenshots/fixed-original-comparison.png)、[1280 比较](w05/browser/screenshots/comparison-1280.png)、[制作摘要](w05/browser/screenshots/production-evidence.png)。

脚本：`examples/workbench/w05_page_chain.py`。全部内容、图件、制作记录均为明确标注的合成 fixture。工具观察场景重放隔离目录中的人工 native event，只验证界面如何呈现已存记录；没有调用模型、读取真实会话、运行 Office 或新增真实 Host 证明。提示词强语义仍依赖 W02 已有的实际工具绑定边界；非空参考附件观察仍不补造。

W05-AC01/02/04/05/06/07 为工程验证，未标客户验收。W05-AC03 的固定版本部分已验证；候选对象、切候选时的依据/采用目标联动待 W07，W05 保留最终验收责任。整卡 accepted=false。
