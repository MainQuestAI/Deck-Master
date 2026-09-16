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
- 两页 p09/p10 主入口运行；回读发现 p10 缺“实施路径”标题，自动派发 repair，补 SVG 后重新编译和逐图检查。此时p09误用了另一张4:3原图的SVG，后续实际原图复核判失败；下面的纠正记录替代该次还原结论。p10保留16:9。不能将这两页等同三类页面全部验收。
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

### 原图身份复核与纠正

- 实际阅读多页项目p09原图后发现之前误配另一张4:3图的SVG；旧自审通过结论无效，新增失败Review，保留旧产物及三个SUPERSEDED记录。
- 正确原图SHA `a2a269744b28d0107ea957012ad80cd6758b426679830c645eb2f8c3c0d12067`，1672×941。按深青三卡、纸笔/书本/专家、只读库标签及灯泡重建，经正常repair接收、重新编译和实际阅图。
- 新两页项目revision `a419ef35ee7948ceab7795af46f48858`，六类Host自审完成；`multipage-working-corrected/`与`multipage-delivery-corrected/`为有效替代，旧目录只作历史。
- `isolated-three-page-corrected/`从独立安装模块生成三页PPT、渲染、读回通过。三页不是同一个新建项目的全链证据。
- 重建任务现在明确暴露当前原图ref/hash/尺寸，Skill要求实际阅读并写入SVG原图hash。声明的hash错误会拒绝接收；历史无标记SVG不新增强制门禁，hash不代替视觉审核。

### 候选打包准备

- 修复普通PEP517构建缺完整Skill入口的问题：自动从唯一Skill源复制到build_lib；sdist重建wheel也验证，不再要求手工预同步。
- 新增按步doctor，renderer缺失只影响render，生图能力明确Host报告/awaiting_host；不检查旧PPTMaster/Library绑定。
- 候选安装器在显式测试前缀建独立venv，校验wheel hash、包资源、真实编译和渲染后才允许激活；current/previous支持失败回退。用户当前安装未切换。
- 当前回归130项通过。候选dev2在installation-test测试前缀完成独立venv安装、真实编译/渲染并激活；candidate-install.json记录来源SHA和dirty状态，未切用户当前安装；T16仅准备切片，不关闭其依赖或整卡。Skill ownership迁移、全链安装验收、专业/桌面证据与最终默认切换仍未完成。

### 资料与工作台实测补缺

- PDF保留无文本物理页及全文，PPTX递归分组/读取备注并标出图片图表，DOCX绘图标待阅图；新source extract保留状态、定位和不可变原文件。扫描PDF实际阅图→一页正文已通过正常Host接收，证据`source-visual/reading-evidence.json`。
- 工作台副本实际保存60/50%显示值及60/.5原始值；另一编辑者更新后保存冲突，草稿仍保留。浏览器历史恢复产生新revision，区域框选带原图ref/版本/归一化区域进入repair，真实Host核对后接受无需改图结论。
- 历史顺序改为已提交父链，不按项目创建时间排序；未提交孤立revision不展示、不允许恢复。待处理Host任务存在时不再显示可交付。
- `workbench-acceptance/browser-evidence.json`保留浏览器行为与真实任务记录。未把部分UI验证扩大为完整T14/T15验收。
- P1未见材料尚无可读取路径，已向用户请求资料和受众用途。不能把本轮合成NOVA当作陌生业务验证或专业验收。

### 本轮可交付节点（源码9c497b0）

- 完整`tests/rebuild`：137 passed；Node语法检查通过。一次setuptools许可证字段弃用提示保留，不影响本次构建。
- 干净候选`candidate-9c497b0/`：wheel由普通构建生成，manifest记录source_dirty=false；显式测试前缀完成安装、原生编译、渲染、激活→previous回滚→再次激活。未改变用户默认安装。
- 安装版从仓库外对三页SVG生成`candidate-three-page/compiled/deck.pptx`，实际渲染、回读与逐页Host阅图通过；246原生形状、84文字段、0整页栅格图片。专业/桌面验收未完成。
- 搬迁项目使用安装版CLI continue（无重复任务）→view→export实际通过，`candidate-mainline-delivery/`两页PPT仍对应已核验修订。
- `Deck-Master-delivery.zip`与`delivery-bundle/`包含三页、主流程两页、单页修改前后、SVG/原图/两段预览和范围说明。`evidence/final-candidate-install.json`与`installed-project-cli.json`记录实际命令和结果。
- 六阶段尚未全部完成：完整SVG语义、细粒度设计影响和自动本地任务跟踪仍需补齐；Skill所有权处理、旧项目迁移、最终入口切换、A/B/C及未见任务和专业/桌面验收未关闭。当前交付为工程试行里程碑，不称完整产品发布。
