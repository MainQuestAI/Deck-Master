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
