# 完整开发执行记录（持续更新）

用户授权按六阶段完整计划实施；只面向 macOS Codex Desktop，使用内置 ImageGen。

## 已固定基线

- `cc3288e`：项目额度、任务领取、停止/unknown、结算、资产和 CLI 边界修复。
- `0339423`：原图派生 SVG 单页编译切片及既有产物记录。
- 初始 111 项 tests/rebuild 已本次复验通过。T01/T02工程行为有当前回归；T03图页Host证据仍需补足。
- 既有T06证据已完整复制到仓库外稳定目录 `Downloads/Deck-Master-development-20260916/evidence/t06`，旧临时目录与原件不改。

## 已完成的实际主流程动作

- 同源材料D1三页/D2五页首次正文，当前Codex读取材料与方法后编写，经create/start/accept保存。现场版以本次分阶段决定结尾；独立阅读版包含责任与回落、结论与边界。仅Host自查，不声称独立A/B/C或专业人类验收。
- NOVA原图 → reconstruct派发 → SVG与纠正文案采用到Page → Python原生编译 → SVG/PPT双段实际渲染 → 文件读回 → Host阅图Review → 主入口ready_for_export → CLI delivery导出。
- 第一次Python实际渲染发现默认阴影/表格换行，修复后重新渲染并主审；失败版保留在项目历史。
- 真CLI改稿已将54条/45%改为60条/50%，同步除式及关系说明；原始蓝图hash不变，继续推进至新版待阅图。

## 工程范围与未完成

新增pipeline、editing及原生DrawingML后端；源函数取用见compiler-extraction.json。当前只验证实际需要子集，SVG完整特性、多页、完整复核/恢复、隔离安装、对照和最终切换仍在实施，不关闭T07–T25整卡。

## 仓库外证据

根目录：`/Users/dingcheng/Downloads/Deck-Master-development-20260916/`

- `evidence/d1-first-draft.*`、`d2-first-draft.*`：真实成对首次正文及任务信封。
- `delivery-before-edit/`：通过主入口导出的第一版PPT/原图/SVG/双段预览。
- `evidence/edit-chain.json`：真实CLI局部修改及原图保留。
- `p10-redraw/`：第二页重建自审；主线程尚待复核。

### 主入口制作与编辑里程碑复验

- Python 原生编译 → LibreOffice 渲染 → PPT XML 回读 → Host 实际阅图 → 导出已运行。单页修改 54→60、45%→50%，提交关系改为“已核对设备条件”，原蓝图不变。
- 两页 p09/p10 主入口运行；回读发现 p10 缺“实施路径”标题，自动派发 repair，补 SVG 后重新编译和逐图检查。p09 4:3 输入在16:9 PPT中等比contain，左右留白；p10保留16:9。不能将这两页等同三类页面全部验收。
- 工作台真实浏览器验证反馈进入 awaiting_host，取消后任务移除；分离服务缺 session token 的实测错误已修复。完整正文、SVG预览与实际PPT预览可查看。
- 工作稿导出包括固定 revision 的可继续编辑项目，迁移副本 continue 不产生重复任务；交付稿不带内部 Page/trace。
- 稳定证据：`/Users/dingcheng/Downloads/Deck-Master-development-20260916/` 下 `delivery-before-edit/`、`delivery-after-edit/`、`multipage-working/`、`evidence/edited-mainline-review.json`、`evidence/multipage-review.json`。原始失败修订仍在项目历史。
- 本节只关闭已列明工程切片；完整编译子集、三类页面、全面工作台/安装、专业阅稿、桌面编辑保存重开仍未完成。

### 扩展复验

- 第三类架构页用程序 prompt 原样调用 Codex ImageGen（`exec-750dba28-2236-4611-8287-9aa2c6376c0a`），完成 start→begin→ImageGen→settle→accept；`architecture-v3` 保留原图、prompt、Host报告、Page人工审核说明、SVG与PPT。前两次准备中的错误与未发送额度解除记录保留。
- `isolated-candidate` 是新venv，wheel安装后在仓库外使用 `python -I`；`isolated-three-page/` 只提供SVG、明确字体参数，生成3页PPT并渲染读回通过。该证据是独立编译接口，不冒称三页都从同一个新建项目完整执行。
- 额外修复：use样式继承、有限渐变与零透明度、明确批准的PNG/JPEG图片、未知属性拒绝、跨后续修订的编辑幂等、历史恢复CLI、移动项目后服务身份验证、防止旧PID误终止、compose/blueprint变化废止旧下游输出、坏草稿不先创建项目。
- 浏览器1280/1440阅图布局已实看；未提交正文在p09→p10→p09切换后保留。刷新/反馈/取消已检查。尚未宣称全区域反馈和全部冲突交互验收完成。
- 独立PPT已由桌面LibreOffice打开并枚举真实文字/形状；自动化输入和剪贴板超时，修改保存重开未通过，不能以headless渲染替代。
- 当前交付审阅需每一页具备content、blueprint_content、blueprint_fidelity、conversion、readability、privacy六类当前产物记录；Host自审不等于专业或桌面验收。

- 后续编译修复：rx/ry圆角转可编辑路径、填充路径仿射剪切、文本旋转锚点、批准图片contain/slice裁切；重新实际渲染架构页确认未回退。当前完整rebuild回归127项通过。仍未关闭T08/T09/T10全卡，任意渐变变换、内联tspan自动布局等存在明确支持边界。
