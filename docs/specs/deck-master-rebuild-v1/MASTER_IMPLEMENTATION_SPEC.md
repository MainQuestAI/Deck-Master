# Deck Master 主流程重建｜完整实施总Spec v1.1

日期：2026-09-16。交付为修订规范文档，未实施产品代码。

**方向不变：同仓src/deck_master重建主流程、提取有效资产、唯一默认入口；本版补实来源/设计输入、额度、UI时机、编辑边界和早期切片。**

本手册由15章、任务工作包、文件清单及完整例合并。机器可读schema/CSV与可验证对象字节在完整ZIP；不将合成例视为真实产品验收。

## 目录
- [00｜执行基线、范围与最终裁决](#spec-00)
- [01｜目标架构与新核心边界](#spec-01)
- [02｜逐文件施工、跨分支提取与删除操作](#spec-02)
- [03｜数据、版本与状态契约](#spec-03)
- [04｜默认宿主内容方法与完整首稿](#spec-04)
- [05｜完整生图输入、蓝图文案往返与SVG重构](#spec-05)
- [06｜独立SVG→PPTX内核与具体修复](#spec-06)
- [07｜检查、审阅与返修的唯一解释](#spec-07)
- [08｜局部修改、事务、取消与费用](#spec-08)
- [09｜CLI与Host执行协议](#spec-09)
- [10｜真实审阅工作台与API](#spec-10)
- [11｜包、安装、独立运行与默认入口切换](#spec-11)
- [12｜旧run、旧流程、旧合同与历史文档退役](#spec-12)
- [13｜验证矩阵、完整稿证据与最终验收](#spec-13)
- [14｜执行型AI任务说明、依赖与交付](#spec-14)
- [v1.1修订说明](#v11-changes)
- [五个工作包](#work-packages)
- [文件级实施清单](#file-list)
- [成对内容与宿主指令](#content-pair)
- [接口往返例入口](#roundtrips)


---

<a id="spec-00"></a>

## 00｜执行基线、范围与最终裁决

### 00.1 文档状态与授权

版本：v1.1；日期：2026-09-16。状态：**吸收 Codex v1.0 审查后的 v1.1 建议实施基线；实施仍以实际授权为准**。用户本轮要求的是完整施工清单和开发文档；本包没有修改代码、分支、安装、真实客户文件或线上状态，也不默认授予发布权限。

明确建议：重建默认内容生产、任务推进、当前事实、审阅工作台与安装入口；选择性提取文件操作和图形内核。不再按旧 OS 的每一个对象、门禁和 Skill 做一轮全量修补。使用现有仓库的隔离包边界，完成后替换默认入口；不长期并行两套产品。

### 00.2 三个版本不能混用

| 标记 | 固定依据 | 含义 |
| --- | --- | --- |
| B0 | codex/professional-first-draft@2a866cf138f6359f853db35e0a926ad79391b691 | 本包主要起点；v1.0 编制时已查 GitHub；本轮由用户提供的 Codex 报告复核本地 HEAD，未重新联网读取 |
| K0 | PR31@2c5a4c50048b2641739356e72ddc1d6fea1d962f | 内核与恢复行为的候选来源；不能整体合并 |
| M0 | main@bcb5b37a4e32b5b98b063ec31e745a8ce017c8f1 | 历史主分支，不能当作 B0 或 K0 |
| I0 | 附件记录安装源 920dc3c5c3f9772d46d007cbeeea77deda3297b0 | 仅是附件当时本地安装记录；当前实际值需要 Codex 核验 |

v1.0 留存的远端 tree 显示 B0 的 `scripts/build` 只有 `__init__.py`、`manifest.py`，不能假设 native_engine/native_budget 已在 B0。旧快照中的工作区模板门槛、固定 auto 12/15 页等已做局部调整，不重复视为全量当前缺陷。

### 00.3 来源与新增设计分开

- E1：`sources/architecture-audit.md`。全链路、本地复现、目录与文件统计、UI/安装现场。其 61 项定向通过为附件报告，不是本包复跑。
- E2：`sources/rebuild-plan.md`。主流程重建、遗产提取和五批方向，是方案输入，不是已完成事实。
- E3：`sources/diagnosis.md`。事故 D01–D13、已修与未修、还原和审阅失效。
- E4：`sources/prior-refactor-decision.md`。上一轮跨分支判断与隔离探针；不能升级为真实新稿验收。
- G1：v1.0 编制时 GitHub `branches` 与 B0 recursive tree，确认路径存在与分支状态；tree 可确认存在，不能证明函数正确。
- G2：v1.0 编制时 `pyproject.toml`，现有 Python 范围、setuptools、依赖和 console entry。
- E5：`sources/codex-v1.0-review.md`。用户转交的 Codex 只读审查：本地 HEAD/干净工作树、清单核验及 R1–R6；不是本次重新访问仓库的结果。
- N：本文新增的路径、对象、接口、失败行为、工作包与验收要求。它们是工程设计建议，不能归因成附件原话。

### 00.4 本轮必须完成的用户结果

从资料与已有讨论进入宿主 Agent；得到适合场景的完整正文和设计；逐页生图、编辑蓝图新增表达、忠实重构 SVG；输出可编辑 PPTX 与实际渲染；同一工作台看正文、蓝图、SVG 和 PPT；提出局部修改后只重做受影响内容；通过真实检查后可本地导出，同时保留可恢复源文件。

首稿可用：受众可以讨论方案与取舍，不必替系统重写主线、补写核心机制、清除成批制作语言。系统交付前可以自行审稿修订。没有效果数字不阻断合理推导；没有实质依据不能编造现有能力、客户成绩或效果。

### 00.5 范围冻结

**纳入：**主 Skill 与 CLI；本地 Markdown/TXT/JSON、PDF/DOCX/PPTX 的资料定位和合理提取；宿主成稿方法；一次受控外部生图交接；SVG→PPTX；渲染/读回；本地工作台；页级修改/版本/取消/恢复；独立安装；受支持旧输入的只读导入；默认路线切换与旧代码退役。

**不纳入：**内置 LLM provider、模型账号管理、云端多租户、团队 RBAC、CRM/商机、计时节省证明、知识库前置、行业包平台、类型注册市场、PPT Library 新整页混编、深度行业研究承诺、Windows 正式支持、所有 SVG/CSS/动画特性、可视化自由拖拽编辑器、自动双向导入任意人工修改过的 PPT、Office 原生数据图表的“编辑数据”与原生表格增删行列承诺。首版表格/图表按可编辑形状组与文字交付，不能称原生数据对象。

首次生产路线固定为 image blueprint→SVG→PPTX。纯 SVG 内核可以单独调用和测试，但不是在缺少生图工具时悄悄改走的降级路线。用户直接提供蓝图时可以省略生图；已有完整正文时省略从材料创作，不重新采访。

### 00.6 已裁决的工程选择

| 决策 | 选择 | 避免什么 |
| --- | --- | --- |
| 仓库 | 同仓 `src/deck_master/` 新包；不新建独立仓 | 分叉、重复维护 |
| 基础技术 | 复用 Python 3.11/3.12 测试范围和现有依赖；stdlib 本地服务；现有原生前端 JS/CSS 提取 | 为重构更换全技术栈 |
| 模型执行 | 外部 Host Agent；代码交接任务与接收结果 | 再造通用 Agent OS |
| 生产内容 | 完整 PagePackage 语义；v2 明确可见字段与设计关系 | 同版本不同形状、隐式丢字段 |
| 制作源 | SVG 唯一手工视觉源，IR 从 SVG 派生 | Scene/SVG 双份手工维护 |
| 状态 | 单 current pointer＋不可变资源＋纯派生视图 | 多套 completed/ready 互相覆盖 |
| UI | 实际产物对照与修改请求；不内置模型聊天服务 | UI 只是管理看板或虚假运行按钮 |
| 旧代码 | 先隔离入口与发布包，验证替代后删除源码；历史保留在 Git 固定引用 | 直接删用户数据、永久双 OS |

### 00.7 完成定义与非完成定义

完成需要同时有：默认任务内容结果、真实制作产物、局部修改与恢复、UI/CLI 一致、安装独立和旧默认路线退役。测试数量、对象数量、hash、空 findings、self/main 两个名称、文件存在均不能单独证明完成。

暂无合格人类专业阅稿时可以交付方法/工程试行；专业业务可用的证据状态须保持“尚未验证”，不暂停所有工程改善等人，也不将模型互相同意当作用户认可。

### 00.8 v1.1修订生效范围

只补 R1–R6 与往返接口，不改变重建方向、不增加第六类永久对象、不增加新运行平台、不以目标文件数量作为开工前置。包版本升级为v1.1；五个schema的对象版本沿用v1.0草案名称，因为这些是尚未实施的合同澄清，不表示已部署格式原地升级。若实施时发现已有使用者或已持久化v1.0新格式，必须显式规范化导入并保留原件，不能改写历史对象。

v1.0保留供对照；v1.1完整包替换活动Spec，不能同时把旧版合并手册当成另一权威。当前修订仅创建文档包与合成例，没有产品实现、真实编译、安装激活或业务验收。

---

<a id="spec-01"></a>

## 01｜目标架构与新核心边界

### 01.1 新建方式

在现有仓库创建 `src/deck_master/`，采用 `src` 包布局。开发初期不改旧安装的 current 链接，不覆盖用户run；新入口通过隔离虚拟环境的 `python -m deck_master` 调用。WP04验证后，把公开 `deck-master` console entry 切到 `deck_master.cli:main`。旧 `scripts/deck_master.py`只保留明确命令映射或退役提示，不允许新任务再次进入旧OS。

分支建议名 `codex/rebuild-mainline-v1`，基于B0创建；若本地已有后续提交，Codex先列出B0至当前HEAD的差异，只补充受影响的映射，不整轮重新讨论。分支名是建议而非已存在事实；创建/切换须有实施授权。不得reset未提交修改或自动切换用户工作树。

这不是一个新的长期profile。新包在切换后拥有唯一正常新建路径；旧代码仅固定旧版使用/只读导入。在隔离验证期间允许两套源码短期并存，但安装和单个run绝不混用两套写入者。

### 01.2 依赖方向

```text
宿主 Agent（阅读、推理、内容主编、图像制作、审阅）
  ↕ 五种工作任务：compose / blueprint / reconstruct / review / repair
CLI / 本地 Web
  → service（用例）
    → content / sources / production / review / export / tasks
      → store / models（文件与数据）
    → compiler.api → svg/geometry/paint/text/drawingml
                     → render/readback（实际文件工具）
  → view（只读派生，与CLI/UI共用）
legacy → 只读旧格式 → content/store；不得import旧engine
install/doctor → 新包资源与实际步骤依赖，不参与内容判断
```

编译包不得import service、tasks、workflow、review政策、安装用户HOME或模型工具；它可以接收显式资产/字体路径和输出目录。上层可以调用编译器，编译器不能读取“已批准”等业务状态。review可以调用实际readback，但readback不决定客户可用。web/cli不得自己重新计算一套就绪逻辑。

在CI中建立AST导入边界测试：新 `src/deck_master` 不出现 `runtime.* / workflow.* / high_density.* / preview.* / build.native_*` 等旧包导入；编译包只依赖其内部、stdlib与声明依赖。抽取时修改import与资源定位，不允许用sys.path插入scripts或HOME仓库偷取实现。边界测试是防实际回流，不建设通用插件注册框架。

### 01.3 目录与职责

下列目录和75项台账是最终范围，不是首份成品前必须创建的文件数。可在现有目标内先完成最小纵向切片，再补全一般能力，不能先造空壳文件。具体35个核心文件及构建/方法/测试等附属目标见 `inventory/new-files.csv`；以下为稳定边界，不要求拆成更多“服务”。

| 子域 | 文件 | 职责与主要接口 |
| --- | --- | --- |
| 内容输入 | sources.py、content.py | 来源登记/读取、PagePackage v2、可见原子、整稿归一化；不生成规则目录 |
| 项目状态 | models.py、store.py、view.py | 五对象校验、不可变对象、原子当前指针、真实页面视图 |
| 宿主工作 | tasks.py、service.py、production.py | 发出具体任务、接收结果、协调转换、按影响继续；不内置LLM |
| 检查交付 | review.py、export.py | 实际观察与当前性、修订、审阅稿/正式导出 |
| 编译内核 | compiler/*.py | SVG解析、IR、几何/画笔/文字、原生对象、渲染与读取 |
| 使用入口 | cli.py、web.py、resources/static/* | 一致命令/API/工作台，失败产物可查看 |
| 兼容部署 | legacy.py、install.py、doctor.py | 只读历史导入、候选安装、实际依赖与模块来源 |

`__init__.py`只暴露版本，不通过import启动engine、扫描HOME或加载字体。schema和静态资源通过 `importlib.resources` 读取，不根据仓库相对路径假定已经checkout源码。

### 01.4 权威来源只保留三层

1. **文档当前状态：**`.deckmaster/current.json`指向一个不可变Document。Document中的pages数组是当前页集合与顺序，不能由目录glob、preview或旧stage推导。
2. **每次制作/检查的输入与结果：**不可变Page、Artifact、Task、Review对象。它们可以被历史Document引用，但不能就地改写为“当前通过”。
3. **呈现状态：**`view.py`读取当前Document及相关对象，派生正文状态、制作进度、检查状态、专业证据状态。派生值可以缓存，但删除缓存不得改变事实或阻断恢复。

不引入一个永续的`status.json`同时接受CLI、UI、review各自写ready。日志是诊断，不是必须重放的另一数据库。current pointer既不是用户批准，也不是质量结论。

### 01.5 核心接口（拟实现签名）

- `service.create_project(brief, sources, output_dir, existing_decisions) -> ProjectView`
- `service.continue_project(project, expected_revision=None) -> ActionResult`
- `service.request_edit(project, page_ids, instruction, expected_revision) -> Task`
- `tasks.accept_result(project, task_id, operation_id, input_fingerprint, result) -> CommitResult`
- `store.commit_change(project, base_revision, read_set, writes, cancelled_task_check) -> revision_id`
- `production.project_prompt(page, resolved_design_context, permitted_assets) -> prompt_text`（配置由同一Document快照解析，不能另取默认值）
- `compiler.api.compile_deck(inputs, options, output_dir) -> CompileResult`
- `review.evaluate_current(document, reviews, actual_artifacts) -> CheckSummary`
- `view.project_view(project, revision=None) -> ProjectView`

签名表达职责；具体Python类型在models中落地。接口不能偷偷回读另一套current，也不能以“调用方承诺已审阅”代替实际输入验证。显式参数包括revision和依赖，避免长操作期间读到半新半旧内容。

### 01.6 首轮生产与调试路线

正常新建：源资料→Host完整稿→接收→逐页蓝图及文案编辑→按原图SVG→编译→实际渲染/读回→审阅/返修→查看与导出。

已有正文：接收完整稿，省略compose。已有用户蓝图：登记原图来源、完成内容对照后重构，不重新生图。独立转换工具可以接受SVG进行转换诊断；不能把这种诊断结果冒充完成了“从材料生成专业Deck”的任务。

所有路径都复用同一Page/Artifact/Review概念；不复制一套fixture、standard、high-density产品状态。fixture仅是测试输入来源，必须如实标记，不能改变production的验收判断。

### 01.7 资产选择失败后的处理

编译器提取首先保持有效行为，然后修已知缺陷。某类SVG特性无法可靠支持时，返回对象级不支持原因，修对应组件或明确更换组件，不建外围规则掩盖。若完整稿仍空泛，改Host方法/源输入，不扩大JSON字段和最低密度限制。

新核心不得直接依赖历史PPT Master仓库。若未来要接其他renderer，应在明确业务需求下通过编译接口适配；本轮不实现可插拔框架。

### 01.8 最早可交付切片

按14.2的`start_after`启动部分能力；`depends_on`仍是整项T任务完成的依赖。T10.min无需等T03全部格式/T09全部通用特性；先用已知TXT/JSON材料、事故页实际需要的SVG子集、真实PPT渲染和只读四视图，紧接T12.min单页修订。原图对照、原件保存、基础原子写入、必要取消/晚到保护不因为“最小”省略。未通过的原图对照不能标完成；未实现格式与特性继续列在最终范围，不能被切片偷偷取消。

---

<a id="spec-02"></a>

## 02｜逐文件施工、跨分支提取与删除操作

### 02.1 三类表必须一起执行

`inventory/new-files.csv`规定新建/重写目标、职责和测试；`old-files.csv`覆盖B0全部177个scripts文件；`root-and-config.csv`覆盖入口、包、文档和CI。旧58个contracts与122个顶层test分别有台账。剩余文档、fixture、样例与根文件由 `path-rules.json`及只读清单工具展开，未知文件显式REVIEW。

对CSV的完成登记可以加一列执行结果，也可以在PR说明引用ID；不创建新的运行时治理对象。未获得实施授权前，不创建项目分支、不改源文件、不执行删除。

### 02.2 新建的操作顺序

1. 创建src包与最小`__main__`、models、store、service、view、cli；先用合成对象接收/查看/恢复，不把所有产品旧文件复制进来。
2. 将本包五份schema安装到resources/contracts；实现类型/语义校验和引用解析。示例数据仅作合同测试。
3. 提取content/sources和实际宿主任务协议，同时创建真实内容方法reference；从第一批就让Host完整稿能通过正常入口进入。
4. 编译器在独立包中逐模块提取，先纯API调用；依赖检查禁止import旧运行时。将已知坏样例逐项修复后再接production。
5. 实现production/review/工作台/导出和局部修改；把指针、页面集合、任务结果接到同一个view。
6. 更新安装、CLI入口、Skill与文档，执行独立安装后切换默认；最后物理删除旧运行代码。

新路径均是拟建，不是已存在事实。Codex不得因为目标文件不存在就转而继续往旧文件加profile分支。

### 02.3 跨分支取用表

| 能力 | 首选参考 | 具体取用 | 明确不带入 |
| --- | --- | --- | --- |
| 完整稿接收/页集合 | B0 runtime/orchestration.py、production/page_package.py | 预校验、稳定身份、增删重排、失败恢复测试 | sourcing/preview必需、全目录复制 |
| 可见内容与设计 | B0 high_density/content.py、blueprint.py | PagePackage直投影、正文叶子、设计prompt；修错接字段 | MBB二次主线、词元证据阈值、密度分 |
| SVG几何/画笔 | B0 svg_native.py/svg_paint.py 与 K0 native_pptx 对应实现 | 对照有效函数和测试，保留B0最近圆角/描边修复 | 审阅回执、run路径/审批依赖 |
| 可编辑文字/多行 | K0 native_pptx/pptx.py及text相关代码；与B0 pptx.py比较 | 实际文本基线、分组、画笔改进，修800/900等 | 不经输入校验的静默fallback |
| 独立API/渲染/readback | K0 native_pptx/api.py、render.py、readback.py | 显式请求、错误定位、真实工具运行 | 旧Scene/Lock批准作为编译必需；HOME探测 |
| 取消/原子/晚到保护 | K0 workflow/actions.py、build/native_tasks.py（函数实际需要Codex核验） | 保护行为与反例，按小文件事务重实现 | 固定尝试次数授权平台、任务全局治理 |
| 工作台 | B0 preview/static与server相关代码 | 页面导航、对照、样式的有效部分 | preview_manifest真相源、团队/审批看板 |
| 安装/回滚 | B0 skills/installer.py与K0安装回归 | 隔离release tree、启动器、原子激活行为 | 15Skill完整性、PPTMaster认证、RC文件当使用前置 |

每项提取记录源SHA/源函数/目标函数/保留测试/行为差异。只需普通Markdown表，不做新运行时“提取登记服务”。源模块现状和具体可用函数需要Codex核验；不可假设K0已合并入B0。不得整体merge或cherry-pick带入大量治理变更；逐功能移植并保留许可证归属。

### 02.4 删除不是一次rm

#### S1：停止新调用
在WP04切换时，默认CLI、Skill、UI、installer、doctor与文档不再导向旧OS；新包依赖边界已在WP01建立。旧run通过显式legacy读取或固定旧安装操作。新run不生成旧问卷、approval/handoff、sourcing或preview占位文件。

#### S2：停止随包安装
新wheel/release tree只包含src/deck_master及实际resources、单Skill与合法依赖。旧scripts、product_capabilities、旧Skill和历史contracts不进入新发行包。必须用安装后的模块路径和wheel内容证明，不仅靠pyproject过滤文字。

#### S3：物理删除仓库旧源码
WP05逐行对照台账；有效行为已移植且新测试覆盖；新默认与独立安装已通过；旧输入有规定的只读导入/固定旧版回退；静态import、CLI、资源、文档执行命令、CI与运行探针均无默认引用后，删除旧源文件。保留Git历史与发布旧版定位。无实际使用者的旧兼容shim在同批或已注明的下一次破坏性版本删除，不无限期保留。

`EXTRACT_THEN_DELETE`不授权删除目标新文件；`ARCHIVE`表示保留原字节并更改活动索引。凡有未知消费者，先定位具体调用；不能以“可能有人用”为由无期限保留整个OS，也不能凭未命中grep证明绝对无动态消费者。

### 02.5 每类旧代码的明确裁决

- planning/conversation规则Brief与轮询配claim：停止生产执行，示例需要时迁入明确demo；不作为正常失败fallback。
- workflow/team/advisory/learning等旧平台：不迁入新运行时；保留有用方法文本和历史数据解释，不保留原队列/审批语义。
- library/sourcing/adapters：本轮不重建库平台；旧PPT按来源读取；手动历史库需求留固定旧工具，不影响新核心。
- runtime/preview/generation：提取文件/Host交回/预览工具后旧状态逻辑退役。新结构无需通过补旧文件让旧状态器“满意”。
- high_density：逐函数拆，不整个删除后重写；也不整个import到新包。绘制内核、视觉测量、来源审阅必须分离。
- quality：真实文件、可见正文、引用和隐私检查保留；默认评分、空集合满分、风格模板、风险数量不是专业检查。

### 02.6 配置与文档是否全覆盖

除台账中根文件外，Codex用 `tools/materialize_inventory.py`对本地固定SHA展开全部跟踪文件：每个文件得到exact/prefix/REVIEW处置。docs中的旧操作指南允许新建更正索引并保留历史原文；默认README、Skill及可执行示例不能继续指向旧链。

本包对部分活动docs路径提出目标：本地存在则重写，不存在则新建并在台账标NEW；不得把拟建路径说成已核对的旧文件。仓库当前路径清单和精确引用更新需要Codex核验。

### 02.7 测试如何删除

原测试不是按文件名直接整删。先列出函数级断言：可靠性/转换/内容保持→迁入新测试；旧产品已退出的固定阶段和错误门禁→附替代行为后删除；第三方兼容→留固定旧版，不在新核心跑。任何新测试失败不能用删测试、skip整目录或放宽到无意义值解决。

同一阶段既有旧测试失败且属于已明确退出行为，可以据台账解释，不必强行维持旧预期；但新核心的正反例与独立安装必须实际通过。发布说明分别列旧基线、新测试结果，不将未运行旧套件说成“全量回归通过”。

### 02.8 不可触碰范围

不得自动删除 `/Users/...` 等用户资料、`.codex`/`.claude`会话、客户run、历史PPT、第三方Skill、字体文件、旧已发布工件。不得执行`git clean -fdx`清理用户工作树。旧安装清理只针对本安装器记录为自己拥有且未修改的资源；同名ppt-master来自其他项目时不处理。

---

<a id="spec-03"></a>

## 03｜数据、版本与状态契约

### 03.1 五对象，不新增阶段注册平台

正式草案见contracts/五份JSON Schema（Draft 2020-12）。落地后只保留安装资源中的一份schema真源；docs引用它，不维护并行同名不同形状。`examples/`的合成对象和引用可用来验合同，不是运行成绩。

| 对象 | 权威内容 | 不负责 |
| --- | --- | --- |
| Document v1 | 当前任务、资料、design_context、页顺序与每页当前对象ref、任务/检查ref、当前输出 | 不把所有维度压成一个completed |
| PagePackage v2 | 完整对外正文、备注、设计意图、业务节点边、引用、内部说明 | 不含编译批准、流程阶段、重复order |
| Artifact v1 | 文件字节、角色、依赖、来源、生成时输入、原图区域期待 | 不从hash推专业质量 |
| Task v1 | 一次Host工作、页面范围、输入依赖、结果、取消/失败 | 不规定每个用户走固定九阶段 |
| Review v1 | 实际检查对象、观察、发现、结论及当前性依赖 | 不用两个名称证明独立、不默认高分 |

JSON Schema只检查可解析格式、必要字段与枚举；跨引用、内容原子覆盖、计算等由明确语义校验承担。专业判断由实际方法与审阅承担，不靠schema计分。

### 03.2 自动项目目录

```text
<output-project>/
  .deckmaster/
    current.json                        # {format,revision_id}，唯一当前指针
    revisions/<revision_id>.json         # 不可变Document快照
    objects/<sha前2位>/<sha>.<ext>         # Page/Task/Review/Artifact JSON及二进制资源
    staging/<operation_id>/...           # 工作临时目录，不能直接成为当前产物
    write.lock                          # macOS/Linux advisory文件锁
  exports/<export_id>/...                # 用户明确导出，不反向成为上游蓝图
```

源文件默认留原位置，Document.sources记录原URI、已知原文件hash和页/段定位。`original_sha256`允许null或缺省；未知不填全零、不对URI字符串求hash，也不拿提取文本hash替代原文件hash。能实际读取的提取文本、已保存媒体分别以extract/Artifact.file记录自己的真实字节hash。既有可信测得的原文件hash可保留，文件后来不可达不抹掉它；只从旧声明拿到但无法核实的hash保留在原始导入说明中，不冒充本次测量。已产生的提取文本可存objects；大原文件无需自动复制，离线可移植包仅在用户要求且允许包含时打包。源文件不可达时已有正文/产物仍可查看、导出审阅稿；依赖原文的再创作/证据检查明确缺口，不假装原文已读。

current指针写在最后。对象路径中的sha必须匹配实际字节；JSON对象使用统一canonical编码计算，媒体直接字节计算。schema不使用全零hash作未知值；未知为null或该字段缺省。用户原路径不是content provider prompt的一部分。

### 03.3 Document语义

`pages`数组就是顺序；每项page_id唯一，引用的Page.page_id一致。删页是新Document不再引用，旧Page和旧产物保留。重排不修改稳定page_id；若可见页码或跨页引用随之变化，系统明确更新相关Page/产物。不得用目录glob把遗留页重新拼回。

`task.brief`保留原始任务与已确认决定，不能因方法迭代被自动改写成另一目标。`page_limit`只表示明确上限；用户明确要求精确页数则在brief及验证中记录精确约束，而不是补通用章节。未指定为null。

`Document.change`记录本次operation_id、变更种类、说明和read_set，用于幂等恢复；历史父链可重建操作索引，索引缓存不成为另一权威。

Document内Task/Review数组引用每个逻辑对象的最新版本；旧记录可通过历史Document读取。对象更新写新blob再换ref，不就地修改。全稿current revision变化不自动使未改页面的artifact过期。

`policy.professional_review_required_for_delivery`只有用户明确要求人类专业复核作为交付条件时为true；默认false并不声称“已获得专业认可”，它只是允许方法/工程试行导出。业务认可在view中独立展示。

#### 03.3a 唯一制作配置：Document.design_context

配置内联于当前Document，随Document快照版本化，不新建配置平台或第六种永久对象。create规范化默认值并持久化；Host、prompt、compiler和UI只能解析这个快照，不能各自补默认。默认1600×900逻辑像素、40/3×7.5英寸、zh-CN、contain；用户指定4:3等时按输入保存。原SVG viewBox原点/范围必须由解析器读取，不能硬编码缩放。

| 字段 | 真实消费者与约束 |
| --- | --- |
| canvas.width_px/height_px/slide_width_in/slide_height_in/fit | prompt布局、SVG归一化、PPT大小与UI比例；正数；fit首版只有contain；逻辑与物理比例不同要显式留白提示，不静默拉伸/裁切 |
| language | prompt文字与字体选择；Page可覆盖语言，不修改原资料语言 |
| fonts[] | font_id、family、face、weight、可选asset_id、明确fallback_font_ids；compiler解析实际字体；不存用户机器绝对路径 |
| styles[]、default_style_id | style_id、colors、typography（正文/标题font_id及字号）、layout_notes；prompt与compiler共用；不是任意JSON配置袋 |
| assets[] | asset_id、kind（logo/icon/image/font）、Artifact Ref及external_use；Artifact.role=asset，file为项目内不可变实际字节 |
| allowed_asset_ids | 本项目准许本轮外发/设计使用的资产集合；不是所有读入材料自动获准上传 |

`Page.visual_spec.style_ref`只指当前Document.styles中的style_id，不是文件路径或URL。未写时继承default_style_id。Page.design_overrides可覆盖language、已登记的body/heading font_id及allowed_asset_ids；后者只能缩小Document许可集合，不能提权。一个PPT文件使用同一物理页面大小，不支持各Page覆盖slide_size；不同源图比例按contain处理。

解析顺序：Document默认style→Page.style_ref→明确Page覆盖；未知style/font/asset ID返回明确配置问题，不回退到隐藏默认。纯素材导入不自动选用该素材。`create --design`接用户指定配置；`import asset`将显式选择的本地字节存为Artifact并登记asset_id；`design update`提交新Document。`--design`/`design update`的临时输入整体使用design_context形状；其中assets项在首次导入时允许用`file`代替`artifact`，如`{asset_id:"demo-logo",kind:"logo",file:"./logo.svg",external_use:"allowed"}`。这只是接收格式，先按配置文件目录解析file并复制真实字节、建立asset Artifact，再转换为正式Document中的artifact Ref；file与artifact不可并用。既有项目可以直接使用已登记Artifact Ref。所有assets规范化后再一次验证完整设计，不把临时路径写入权威Document。

`design update`按完整配置替换进行原子提交，不作任意深层隐式merge；原有正在被Page引用的style/font/asset被删除时拒绝并列出受影响页，或与明确的Page变更同事务提交。永久Ref只指项目内对象，移动项目不要求旧Logo路径复活。

字体二进制仅在用户提供并允许本地复制时保存为私有asset，绝不随公开发行/Spec包附带。选择系统字体时family/face是需求而非保真证据；编译记录实际匹配字体文件hash与版本为toolchain依赖。缺指定字体只影响需要该字体的生成/编译，旧预览仍可看；只能使用已声明fallback并报告实际替代，否则needs_tool。fallback实际发生后也不得声称原指定字体完全还原。

已保存资产Ref的hash始终必填且逐字节核对；来源original_sha256的未知特例不放宽这里。restricted素材不能因为出现在allowed_asset_ids就外发；unspecified须由已有任务授权明确可用，否则先澄清该项，不制造全项目问卷。字体配置可向图像工具传family与设计说明，但默认不上传字体二进制。

依赖用解析后的**当前页有效配置和实际用到资产**，不是整段Document hash。样式覆盖其他页时，仅这些页失效；修改未用style不影响成品。相同asset_id换字节、实际字体换版本、全局画布变更均使相应依赖过期。原始已生成蓝图仍是不可变历史；不按新版style回写它的生成参数。

### 03.4 PagePackage v2的显式正文

沿用v1的customer_visible/internal_only概念，使用v2明确字段与跨版本转换。body_blocks首轮支持paragraph、bullets（嵌套items）、table；表格cells使用display_text保持小数、千分位、百分号和单位，value用于可复算但不能取代展示文字。0、0.0、空字符串、null语义不同，不用`x or fallback`处理数字/透明度。

标题、副标题、所有正文条目、表头/单元格、labels、footnotes、callouts都是可见文字。节点target/id、证据ID、layout metadata不自动成为正文。备注是用户可编辑业务备注，与内部指令分开；允许被明确检查的正常业务备注，不默认全部删除。

`visible_atoms(page)`返回稳定atom_id、JSON Pointer、显示文字和业务必要性。atom_id基于block/item/cell稳定ID而非数组位置；JSON Pointer仅作定位。规范化输出的label_ref/responsibility_refs使用atom ID，不再留下依赖数组下标的正文关系；旧Pointer仅允许在导入当前旧Page时一次性解析并改写。具体规则见03.10及完整往返例。所有非空对外正文默认应保留。允许改写/合并时在内容编辑阶段产生新Page，不让渲染阶段悄悄截断。一个atom可由多段SVG文字实现，但应能重组其内容；不能为凑引用加入微字、透明文字或重复节点名字。

无法识别的旧body对象不能直接忽略；legacy转换返回需要规范化的路径，Host决定映射成哪种正文块。无需为覆盖任意旧JSON建立开放类型注册系统。

### 03.5 设计关系与视觉期待

visual_spec.intent是设计任务，layout_hint是参考，不是固定坐标模板。nodes有稳定ID、正文label_ref、existing/proposed等状态，edges有实际from/to、方向、关系及可选可见label_ref。技术说明只读/回写、建设中/已有等必须与正文一致。

结构边的`relationship`是语义说明，不自动要求在画面重复印字；有label_ref才必须显示标签。已有节点名不必在每条边再印一次。关系可以用拓扑、分组、方向等表达，检查应验证关系而不是简单比文字。

原图视觉期待在blueprint Artifact.reference_regions中，来自实际阅图而非SVG输出。bbox为归一化x/y/w/h四数，程序校验长度、正面积和范围。区域重要性分essential/supporting/decorative，只对当前图的真实区域登记；原图未识别不能记无图标满覆盖。

### 03.6 Artifact版本、来源与双向编辑

Artifact.file是实际文件Ref；derived_from描述已知数据依赖。`provenance.generated_from_page`记录图当时对应的Page版本；`submitted_prompt`只保存实际提交内容，Host工具不可提供时为null并注明不可核实，不能根据当前Page倒填旧prompt。

蓝图新增文案被编辑接受后，新Page可以继续引用原图；SVG同时引用“原图Artifact”和“编辑后Page”。这不是来源冲突。若文字变化使原布局不再适用，生产任务应重排相应区域或明确重新设计，不为两个词修改强迫重生整张图。

禁止已知本页svg_preview/ppt_preview及其派生产物被标为该结果的原始独立blueprint。按角色/已知依赖方向检查，不能只检查两个文件hash不同。用户明确要求从成品开始新设计时，建立新设计任务和新的起点，历史还原验收不回填通过。

### 03.7 依赖指纹分层

| 指纹 | 组成 | 变化后的动作 |
| --- | --- | --- |
| 内容/证据 | 当前任务中相关条件、Page正文与节点关系、实际来源版本 | 重新判断受影响内容和审阅 |
| 视觉制作 | Page展示文字、design、选定原图、资产与样式 | 使相应SVG/页面预览过期 |
| 编译/渲染 | 有序SVG、实际资产、画布、字体和编译/渲染版本 | 重编译/渲染，不重新写正文或生图 |
| 检查 | 被检查Artifact与适用方法/规则版本、必要来源 | 只使该检查失效 |
| 管理记录 | 反馈说明、预算记录、操作者、日志时间 | 不改变前四项，除非修改了真实制作参数 |

依赖种类可在现有字段内表达，不再建通用图谱平台。全局实际输入如主题风格改变可以影响多页；不能为了局部缓存忽略它。未知依赖不能假装没有，先保守重新检查，再在已识别格式内缩小范围。

### 03.8 状态派生规则

ProjectView展示四维：content、production、checks、professional_use。例：`content=ready_for_review, production=rendered, checks=needs_revision, professional_use=not_evaluated`。这种状态允许查看和请求修改，但不能输出“已验收通过”。

Task.kind分Host任务（compose/blueprint/reconstruct/review/repair）和本地确定性动作（compile/render/check）。这是同一Task结构的执行区分，不增加用户阶段或通用调度平台。本地动作queued→running→completed/failed，Host任务awaiting_host→running→completed/failed；cancelled/superseded为不可再提交的终态。completed必须由实际结果校验和原子采用产生，不能接受Host自填的完成字段。

Task.call_allowances是项目事务分配的外部调用名额，不由Host结果覆盖；usage仅调用后观察。取消、重试、项目恢复均保留已消耗和未知调用事实，见08.6。

Task状态是执行事实。没有Host接手就是awaiting_host，点击按钮只创建任务不变running。Artifact存在但相关输入变化，view标stale并仍可查看旧版。Review.status=pass但依赖不匹配，view显示历史通过/当前未检查；不得改写旧Review自身的结论。

整套完成必须以当前页集合全部有预期产物、必要检查当前且无must_fix/未裁决必需问题为依据。局部文件已生成不等于整稿完成。没有人类专业阅稿始终不显示human-approved。

### 03.9 必须实施的跨对象校验

同run/同project引用、唯一页ID与顺序、节点边端点存在、label_ref指向可见正文、表列ID/cell匹配、citation源存在、对象hash一致、图片/PPT实际可读、取消/旧输入提交拒绝，以及未来未知schema不写入旧数据。格式错误返回明确路径，不通过丢弃字段来完成导入。

Current pointer写入事务和文件锁规范见08章。程序不把源引用存在解释为语义证据充分，不把所有非空字段列成必须引用历史事实。

### 03.10 稳定可见atom ID规则

采用`atom:<page_id>:<类别>:<稳定ID>:<字段>`，不取正文hash、数组下标、显示顺序。固定标题为`atom:p09:title`，副标题为`atom:p09:subtitle`；块标题/正文为`atom:p09:block:service:heading`或`...:text`；所有层级条目在页内item ID唯一，正文为`atom:p09:item:version:text`；表头为`atom:p09:column:sample:count:label`，单元格为`atom:p09:cell:sample:need:count:display_text`；脚注/标签/callout按其id组成。

已有ID全部保留。缺ID时规范化器一次分配UUID/稳定持久标识并把规范化Page与映射返回Host；同operation重试复用同一结果，不按运行时重新发号。重排、修改文字、将同一条目移到另一嵌套位置不变item ID；复制新条目必须新ID；删除后不能给无关内容复用ID。拆分/合并产生新ID并在本次编辑说明中列old→new映射，相关node/citation/绑定由Host显式更新；不要构建长期ID映射平台。

显示文字、JSON Pointer和ID分开。节点只引用明确的atom，不引用整个items集合要求渲染器再自行猜测。程序可为目标词提供候选匹配，但不能因文字相同就自动把两个业务对象当同一身份。完整新增、重排、改字往返例见`examples/roundtrips/atom-identity.json`。

### 03.11 v1.1跨对象补充校验

design_context中的style/font/asset唯一，所有引用存在；Page许可集合是Document许可子集；字体fallback无环；asset角色和真实字节匹配；全稿单一物理画布。项目移动后只能从对象Ref或重新解析并验证的系统字体加载，不读取旧绝对路径。

来源hash未知不阻止读取已存提取文本/媒体；依赖身份可用已保存extract或注册信息的canonical hash，但必须标为该对象/声明的hash，不能称原文件hash。具体事实的证据强度仍由实际资料和审阅决定。

Review.fixed必须是针对新产物的真实复查版本，replaces连接旧Review，不能只改一个字段；Task额度分配、begin和settle按08.6在同一项目事务内处理。JSON Schema通过只证明格式，不证明上述跨对象条件或业务检查已经成立。

---

<a id="spec-04"></a>

## 04｜默认宿主内容方法与完整首稿

### 04.1 要替换的真实路径

将正常新建从“摘要→规则Brief→规则Claim→autoplan”改成“任务＋相关原文＋既有讨论→Host成稿→PagePackage”。现有规则脚手架不得再次覆盖已写论点。删除生产调用中的index取模配claim、关键词推完整目录、按指定页数循环补GENERIC_BEATS。测试样例可以保留通用结构演示，但必须不在默认路由。

不增加内置LLM供应商。CLI发出compose任务，宿主读取本项目单一Skill的方法并调用自己的阅读/推理能力；结果通过task accept接收。Host已写完整正文可直接import draft，无需重新采访或生成另一套Brief。CLI打印任务并不是“AI内容已经生成”。

### 04.2 来源输入能力与失败行为

| 输入 | 本轮实现 | 必须保留 | 失败行为 |
| --- | --- | --- | --- |
| TXT/MD | Unicode文本读取；保留段/行定位 | 原文件hash、位置、全文；摘要仅导航 | 编码不可读给出文件和原因，不返回空摘要成功 |
| JSON | 按结构读取，可定位键/数组项 | 数字、单位、0值、嵌套对象 | 非对象/坏JSON明确定位；不吞字段 |
| PDF | 使用声明的pdftotext提取；按页保留；图表/图片按页渲染交Host看图 | 页号、原文件、提取文本与图页关系 | 无文本/图形决定含义时派发阅图，不将空文本当已读；缺工具标该资料未处理 |
| DOCX | ZIP/XML提取段落、表格与图片关系 | 文档顺序、表格单元格、页码不可确定时用段/表定位 | 不伪造页码；嵌入媒体列为待查看 |
| PPTX | python-pptx/XML与需要的页渲染 | 真实页序、文本、备注、图/表与来源页 | 图片型页必须看图；旧Deck可作资料，不能默认整页混编 |

直接读取用户现有路径，不能要求先搬进知识库。提取数据须由来源原文可追溯；单个源摘要没有关键约束时，Host仍必须读取相关原文。不能用“全文已读=true”代替内容行为检验。材料末尾重要条件必须进入相应方案/图示，作为AC-C01检验。

默认不自主访问网络。任务明确授权补查公共事实时，Host按自身可用工具搜索，并记录可回查来源、日期与引用范围；没有访问就不补造来源。扫描PDF无需默认OCR，只有没有可用文本或视觉读取手段且任务确需时才单独采用，并标识结果待核对。

文件和私密参考可用于Host理解，进入外部图像工具的payload仅包含已形成的对外正文、必要设计与允许资产。遇到明确限制“不能上传第三方”的资料内容不能外发；缺少相关外部工具时停在该动作，不要求用户重建完整隐私表单。

### 04.3 任务理解不形成必填问卷

Host先从已有内容识别：交流目的、受众已有认知、对方本次待理解/待决定事项、现场/独立阅读、真实篇幅要求。无法推断且会改变核心方向时，集中询问；普通方法取舍由Host给出建议并继续。

例：首次能力交流通常需要适度信任依据，但不强制公司历史专页；已有客户接口评审不重复公司介绍；研究简报说明样本、发现、解释及建议，不默认导向采购或POC。资料充分的两页说明也可以完整，不因页数不足硬加痛点/风险/CTA。

“没有额外约束”“不适用”是有效输入，与“不知道”不同。不要求用户回答不存在的历史库复用许可。用户给定明确公司介绍/章结构时尊重；结构明显与任务冲突时提出具体调整理由，而不暗中改目标。

### 04.4 六个可执行判断动作

| 动作 | 实际写法 | 不合格反例 |
| --- | --- | --- |
| 确定交流任务 | 用现有材料说清本次受众要理解或选择什么，据此删减无关材料 | “高管必须15页”“先讲行业痛点” |
| 提取业务机制 | 识别人、输入、条件、动作、交接与瓶颈；说明哪个环节可以改变 | “打通孤岛、智能赋能、闭环”无实际工作 |
| 形成任务相关观点 | 连接观察与机制，说明优先改变什么、为什么以及可能反转建议的条件 | 只重述资料；或每份稿强行创造惊人洞察 |
| 比较真实取舍 | 对有竞争力的选项说明改变环节、额外工作、适用条件与推荐理由 | 给弱选项陪跑；给没测过的方案打精确分 |
| 组织页间解释 | 后页回答前页留下的关键疑问；案例支持相应主张；复合Deck只有一个整体任务 | 五个小Deck拼接、案例重复三遍、每页三条价值 |
| 实际编辑成稿 | 写出全部对外正文；检查图示/制作结果后回到内容修订 | “本页突出交付能力”；报告建议加强但不改稿 |

这些动作写进reference，不要求每次持久化六张表或把六个动作变成六个阶段。先写有价值正文，再按Page契约接收；不强迫先填数十字段。

### 04.5 事实、推理、建议、计算的处理

事实要有来源/已给定条件。推理要能说明由什么观察和机制推出，强度不超证据；缺效果数据不阻断机制明确的方案。设计建议应标为拟采用/建议，不包装成已上线能力。样本54/120的45%可按表达式复算，不要求来源原文已有“45%”。目标/计划数字与已实现结果分开。

只有缺失信息足以反转核心推荐且不能合理条件化时，才暂停该判断。例如接口是否允许写入会决定自动执行方案，不能擅自假定；但没有效率收益实测不应阻止提出只读知识查询方案。未知内容可以明确留待确认，但不能删除任务核心然后宣称专业完成。

### 04.6 完整正文与设计一同交付

compose结果包含完整pages数组（page.v2）、顺序、来源映射和跨页必要条件。page.visual_spec提供当前页面所需结构与设计意图，不只是“画高级架构图”。关键关系和建设状态作为可核对语义输入，正文、节点职责与图示不得冲突。

副标题、脚注、labels、callouts、表格文字都在可见内容范围内。内部编辑说明进internal_only；正文中可以合法出现“缩略图、左屏、右屏”等业务词。不能为避词表将准确业务表达改模糊。

在写入前schema/跨引用校验只证明可用数据结构；完成稿价值另由内容审阅检查。Host第一次交付前可自行返修；第一次发给用户的完整版本记录first-delivery对应revision，不将后续人工精修倒算成首稿成绩。

### 04.7 成对开发与未见验证

D1/D2使用同一资料：公司能力、真实范围明确的案例、客户工作流程、样本数据、本期约束。D1任务是首次能力交流；D2是已合作客户方案评审。必须在方法形成时一起使用，不能先把D1调成唯一优秀模板再适配D2。

P1为陌生企业不同工作机制，第一次主链可运行就使用；用于调试后标为开发材料。H1/H2在候选方法与代码冻结后才使用：陌生能力/产品说明与材料驱动研究简报。H1/H2失败后修改方法，则该材料转回归，另取未见材料或缩小结论。

方法包应包含“什么时候适用、好坏完整正文、为什么”而不仅是标题列表。示例在examples/content-pair.md；都是方法范例，不是生产结果。没有知识库、没有历史Library也必须能用给定资料正常工作。

### 04.8 输出与错误

compose接受失败返回具体page/字段；不得为了schema通过填假事实。来源不足影响个别页时，其余页面仍可形成候选，整稿状态明确未完成，不将部分候选叫完整交付。

新核心中不要生成placeholder页面后交给生产自动填充。正文由Host写完；如果仍然依赖用户补写核心机制，说明内容任务失败，应修改方法而不是添加新门禁。

---

<a id="spec-05"></a>

## 05｜完整生图输入、蓝图文案往返与SVG重构

### 05.1 唯一展示投影

`production.project_prompt`直接消费PagePackage v2和03.3a解析出的同版本design_context/style上下文，不从旧enrichment.chart_plan猜测新字段。列出并测试：title、subtitle、所有body块/嵌套items、表头与单元格display_text、footnotes、labels、callouts、visual_spec.intent/layout_hint/nodes/edges、语言、画布、允许资产。speaker_notes只在其中内容被明确提升为页面正文时进入prompt；internal_only与原始私密路径不进入。

投影输出两个视角：供Host/图像工具阅读的完整prompt_text，以及供测试定位的字段映射；二者来自同一次函数调用，不分别维护。自动marker测试逐字段核实真实prompt_text包含期待内容，不能只核对中间projection JSON。

不要固定“high-density consulting slide”作为所有任务请求。密度和呈现方式由Page设计任务决定；默认16:9只在create规范化时写入Document；明确其他画布时按design_context配置。prompt、SVG和PPT共用同一有效配置；Page.style_ref必须解析到明确样式。Logo/图标只经asset_id读取已存字节，允许列表不等于自动插入或外发所有资源。不要求每页有management takeaway，不把生成器字段名渲染到图里。

### 05.2 Host生图任务实际输入与输出

任务输入：当前Page版本、完整prompt、允许使用的资产、任务约束和画布。Host必须调用实际可用图像工具，结果关联真实图像文件。每次调用前先按08.6取得项目分配的allowance并begin；工具返回失败/未知也结算，不通过重试Task清零。包不声称能约束绕过产品的Host工具调用。工具缺失返回awaiting_host/needs_tool，不能切fixture、套通用无字模板或直接生成几张图分配全部页面。

同一视觉模板可跨页复用，但每页实际业务内容和角色必须在设计中体现；不得以页面hash不同证明图已分别设计。每页不强求独立一次收费调用，工具支持批量可使用，但必须有真实页内容与相应返回图的映射。

输出：源图Artifact及工具实际可得的调用记录。记录的是实际使用的prompt与版本；不从当前内容反向伪造原调用。记录缺失如实标unknown，不能用exec文件名、时间戳、随机nonce和签名补成已核实调用。

### 05.3 蓝图检查必须包含内容编辑

在重构前，Host/审阅者打开源图，识别实质区域、模块、关键图形、关系、建设状态与新增文案。结果落入blueprint Artifact.reference_regions及Review。允许无图标页面不适用；未检查不能记无对象满覆盖。区域数量不是合格指标，不要求所有装饰都单独登记。

新增文案分：已支持且有价值→写入Page；仅说明性标签→明确为对外标签；夸大效果/虚构能力→改写或删除；图中错字→最终正文修正。图片不能因为漂亮就成为业务事实来源。原图有不合适的新内容时，不应“忠实”复制错误事实。

纯语义保持的文字修订，可用原图布局制作新Page文字；大幅删改改变布局时，由Host局部重新设计或生成新蓝图。不要强制每次改字都重生图，也不要通过覆盖旧prompt/manifest假称原图就是用新正文生成。

### 05.4 原图保持与谱系

源图字节写入不可变objects，所有后续SVG/PPT预览有不同role和derived_from。当前reference可切到一个新设计，但切换必须通过新的设计动作、保存旧版并明确比较对象。不能用当前输出预览回灌上游，继续宣称通过原始还原。

拒绝规则基于已知角色与祖先关系；哈希相等只是一种直接证据，重编码/缩放不能改变下游身份。系统无法自动识别未知外部文件是否经过人为转存时，记录来源不确定，不捏造完备防作弊能力。

本地导入外部/用户蓝图是正常能力，不要求它有ImageGen请求回执。核实视觉内容与任务适配，来源身份保持user_supplied或unknown。不要为“证明真实生图”堵死合理导入。

### 05.5 SVG为唯一手写制作源

Host输出SVG（UTF-8、自包含可支持子集）及必要语义绑定。`data-text-ref`用稳定可见atom ID，图形节点/边用 `data-node-ref` / `data-edge-ref`；这些是拟实施的元数据，不是已存在的source字段。纯装饰无需绑定业务节点，但仍可有稳定element ID用于局部修订。

IR/Scene由compiler.svg解析，记录解析节点、几何、画笔、文字run、输入元素ID与绑定。Host不再手写另一份相同几何的Scene。无法自动解析的业务意图从Page/源图期待取得，不由IR发明。

一个正文atom可以跨多个tspan，但可按顺序复原；表格单元格各自映射。不能用不可见/极小的全文层补覆盖，也不能把所有正文塞在notes替代画面。图形关系以连接真实节点为准，不接受悬空装饰箭头代表业务架构。

### 05.6 重构任务执行方法

先打开真实原图和完整Page，确认分区/比例/对齐/层级/关键关系，再决定SVG对象。优先保留真实布局而不是套通用三卡片；只为恢复正确文字、保留编辑能力或任务已授权变更而做必要调整。调整应能对应具体内容/视觉问题。

完成SVG后渲染并与原图并列。发现职责缺失→补正文/对应区域；连接错误→修改端点；内容本身不成立→返回Page编辑，不让画图修补虚构主张；编译失真则修改内核，不重画成更简单图以躲避。

每次接收不因“合法SVG、文字全有、对象可编辑”就跳过原图布局比较。图像->SVG与SVG->PPT分别检验，后一段高保真不为前一段简化背书。

### 05.7 实际相似性与业务检查

相似度、边缘、bbox差异是定位候选，不是独立投票。删除一个关键业务节点、改变建设状态、反转只读/回写是具体must_fix；正常抗锯齿和无字形遮挡的框交集是待局部核实。检查规则与Review写入/读取用同一实现。

原图区域预期保留在上游Artifact；删除SVG registry不能缩小期待。若源图明确没有某类图形，该维度为not_applicable；尚未识别为not_evaluated。

#### 制作任务与规则修改隔离

成稿会话不修改产品安装代码、验收方法或测试以接受自己的当前结果。确实发现工具误报时提交具体反例，在独立开发变更中用正常/故意删减/合理差异样例验证后发布新工具，再重检；原失败记录不改写。版本留存能说明用过哪套规则，不声称可以在同一拥有本地写权限的主体下实现不可伪造的身份认证。

### 05.8 验证与已知范围

- 全字段marker：字幕、脚注、标签、设计关系进入真实prompt。
- 原图新增文案往返：Page更新但原图生成时Page/prompt不变；后续SVG使用新Page。
- 换图检验：同样业务、明显不同布局的两张真实参考，重构几何应相应改变，不能只换hash。
- 删除/反转/极小字/下游回灌：在独立期待不变时必须被发现。
- 未识别原图/缺工具：不生成假的完成或独立通过。

本Spec没有调用图像工具，也没有新生成真实PPT。真实视觉能力需要Codex/Host按任务执行并记录，不能用本包示例抵扣。

---

<a id="spec-06"></a>

## 06｜独立SVG→PPTX内核与具体修复

### 06.1 API与依赖边界

拟接口：`compile_deck(inputs: Sequence[SvgInput], options: CompileOptions, output_dir: Path) -> CompileResult`。

SvgInput含page_id、SVG路径或字节、明确资产映射。CompileOptions含从Document.design_context解析的canvas、slide_size、实际字体与资产映射及受支持特性策略。adapter将有效配置显式传入纯内核；内核不得自己从HOME或另一配置文件选择默认。CompileResult含真实PPT路径、trace路径、每页对象映射、diagnostics、工具/内核版本。编译器不返回client_ready，不读取用户HOME，不读取故事线批准、content_lock签章或PPTMaster绑定。

`render_deck(pptx_path, output_dir, options)`实际生成预览；`readback(pptx_path, inputs, expected_content, expected_relations)`读取文件并对独立期待核验。解析trace可用于对象定位，但不是完整预期。文件IO、schema、图形语法与业务判断分开。

输入一致性由调用方固定字节或内容hash；读取期间文件发生变化应拒绝本次结果，不将混合输入登记完成。编译输出写新目录，成功后由store统一采用，不能覆盖已交付文件。

### 06.2 首轮SVG子集

| 类别 | 必须支持 | 暂不承诺/处理 |
| --- | --- | --- |
| 基本几何 | rect含rx/ry、line、circle、ellipse、polygon/polyline、path常用M/L/H/V/C/S/Q/T/A/Z | 无法精确保留时明确诊断，不默默丢对象 |
| 变换 | translate/scale/rotate/matrix及嵌套组合；可检验的stroke处理 | 任意非等比仿射描边若只能近似，显式限制/转轮廓，不能宣称完全保真 |
| 画笔 | solid fill/stroke、opacity、fill/stroke-opacity、线宽、基本linear/radial gradient | CSS动画、动态滤镜、外部样式不执行 |
| 文字 | text/tspan、显式字体/字重/字号/位置/对齐、多行基线、可编辑run | 任意浏览器排版CSS不承诺；中文断行必须在本子集内实际检验 |
| 图标 | g/symbol/use的本地定义、稳定ID、路径/形状组合 | 外链use不允许；资源内联或明确本地资产引用 |
| 图片 | PNG/JPEG等真实批准资产，位置与裁切 | 不将关键正文/架构整页栅格化替代原生编辑 |
| 连接 | 直线箭头端点、方向，可能时建立原生连接器附着 | 任意曲线可成为可编辑freeform；不假称全都具有自动连接器跟随行为 |

输入通常由受控Host按这个子集写出；不需为外部任意SVG引入浏览器级CSS引擎。简单内联style可在预处理白名单中规范为属性；不支持的属性明确报错或给出可定位不保真项，不用安全理由一律抹掉有用结构。

安全检查保留：禁脚本、事件处理、外部可执行引用、DOCTYPE实体扩展、输出逃逸。正常图形样式与恶意输入是不同问题。

### 06.3 必修缺陷与实现方向

| 缺陷 | 源定位 | 必须达到的行为/测试 |
| --- | --- | --- |
| 800/900字重变非bold | B0 high_density/pptx.py::_add_text | 实际可用字体匹配字重；需合并为PPT bold时800/900不得反而不加粗；记录替代字体，不假称任意字体精确 |
| 负斜率/反向端点丢失 | svg_native.py::_geometry(line)；pptx.py::_add_line | IR保留(x1,y1,x2,y2)及方向，DrawingML读回真实端点，不从bbox左上到右下重建 |
| 旋转圆/椭圆bbox错误 | svg_native.py::_geometry(circle/ellipse) | 用解析极值或正确曲线变换求边界，半径10圆绕圆心45°仍为20×20；不是四采样点 |
| 透明度0被默认1 | svg_paint/pptx画笔写入 | None判缺值、0合法；fill/stroke/gradient stop/组opacity均覆盖 |
| 圆角/描边已有局部修复 | B0最近svg_native改动 | 提取时不得丢掉缩放圆角与有效描边改进；补等比和非等比范围测试 |
| 中文多行/位置被扁平化 | B0文字处理与K0对应改进 | 保留每行基线与run，视觉不允许被精确全文拼接检查掩盖；K0有效实现优先比较 |
| 连接业务方向检查不足 | visual/pptx readback | 核对Page实际from/to/读取与回写含义，以及输入SVG端点和PPT端点；宽高比不是方向 |
| 转换器导入业务运行时 | high_density.__init__/pptx imports | 独立pip安装只给SVG/资产即可编译；不能依赖review/worldspace/MBB |

不要整包复制K0后假设这些都解决。每个case先在候选提取实现运行，再修复，保留前后结果。当前源函数与本地环境需要Codex核验。

### 06.4 字体、画布与可读性

默认画布只在Document创建时持久化为13⅓×7.5英寸/1600×900、contain。编译读取03.3a的有效配置，坐标按输入SVG viewBox计算，不硬编码1672/941。非16:9按Document明确设置；同一PPT不混合物理页尺寸。比例不同等比contain并报告留白，不暗中拉伸或裁切。

生产样式从任务指定和可用字体取得；默认中文字体通过doctor报告是否存在。缺字体不得静默替换后称完全保真。规范中的“字号可读”以实际PPT尺寸判断，不能仅大于0。首轮默认正文建议范围16–24pt、辅助文字10–14pt只是设计起点，不是强制所有页面统一字号；实际必须能在目标展示方式读清。业务关键字不得1pt/透明藏字；放不下时修改布局或内容页分配，不自动无限缩小。

当硬阈值无法判定可读性，报告明确对象和实际字号/截图供审阅，不因为低于某一通用阈值自动删正文。用户明确密集打印用途可用较小字，但仍需实际阅读验证。

### 06.5 单元与真实转换验收

纯函数测试覆盖几何端点、圆极值、颜色alpha、字重映射。XML测试检查真实DrawingML里的内容、端点、path/connector、透明度、字体。真实渲染测试分别渲染输入SVG与输出PPT，比较局部特征与文字；不是只查trace。

桌面编辑验收：用目标PPT应用打开实际当前产物，修改一处关键文字和一条关键关系/图形，保存重开确认。LibreOffice headless成功不是PowerPoint桌面编辑已验证；无法进入桌面时标pending，保留工程结果不越级。

图标/曲线/表格/文字都可有局部误差诊断；核心业务节点、数字、端点错误必须修。原生对象数量与“图片数0”不是成功标准；产品照片作为图片正常，关键正文整页图片不等价可编辑交付。

### 06.6 实施落点与失败后的去向

先在compiler/内完成独立可调用接口和测试，再由production调用；不把质量审批注入compile_deck要求它读业务批准。unsupported对象返回code/page_id/element_id/feature/recovery；上层请求对应SVG修改或替换转换组件，不能悄悄退fixture。

相同语义SVG的字体或line错误，修内核后只重编译受影响输出；不得为适应bug把原图重画成没有图标/连线的卡片。内核替换必须遵守同一接口与坏样例，不另造一套runtime。

### 06.7 首版可编辑能力承诺

首版承诺高保真的**可编辑形状、路径与文字**。表格用可编辑形状/文字组成，Page.table保留行列和值以便工作台修改后重生成，但不承诺Office原生Table的增删行列操作。图表可按SVG画成可编辑形状组，首版不实现原生Chart数据序列/嵌入工作簿接口，不承诺PowerPoint“编辑数据”。“原生PPT对象”在此指DrawingML形状/文字，不等于原生数据图表。

PPT Artifact.editability为editable_shapes_and_text；导入旧文件且未核验为unknown。该字段不自动证明实际对象可编辑，必须按06.5在目标应用修改文字与图形。UI、README、导出说明同样写清“可编辑形状/文字；非原生数据图表/表格”。不能通过默认提供chart模型或新增编译接口悄悄扩大本轮范围。

用户任务明确要求Office原生图表编辑数据时，说明首版不支持，不能把形状组当作满足。后续若纳入，需单独数据/单位/序列与编辑验收，不挤入本次修订。

### 06.8 最小制作切片与最终支持范围

T08/T09/T10可在当前事故页实际需要的子集上先交付真实成品：该页需要的圆角/文字/线条问题必须修好，不能先删去原图对象以缩小子集。暂时未实现且本页不涉及的通用SVG特性、全部材料格式，不阻止T10.min试做；T10整体完成仍需06.2最终范围验收。早期同一工作台至少显示正文、原始蓝图、SVG预览与PPT真实渲染，Host/人类实际对照不可省略。

---

<a id="spec-07"></a>

## 07｜检查、审阅与返修的唯一解释

### 07.1 检查对象与职责

系统保留实际检查，但不保留默认九项4分、空finding满分、risk_flags数量、固定opener/页数或密钥签章代表专业的逻辑。

| 检查 | 输入期待 | 实际对象 | 执行者 |
| --- | --- | --- | --- |
| 内容专业与任务完成 | 原任务、来源、内容方法 | 完整正文与实际页面 | Host编辑；人类专业阅稿提供更高层业务证据 |
| 蓝图文案 | 已知事实/建议与当前Page | 原始生成图全部实质表达 | 看图的Host/人类 |
| 蓝图还原 | 独立源图区域与业务关系 | SVG真实渲染 | 工具定位＋实际看图 |
| 编译保真 | 输入SVG及Page必要原子 | 实际PPT/XML/渲染 | 工具＋局部审阅 |
| 可读/可编辑 | 目标使用方式 | 真实字号/遮挡/桌面编辑 | 工具发现＋实际阅读/编辑 |
| 隐私/内部语言 | 真实禁止内容与字段边界 | 页面、备注、隐藏内容、元数据 | 结构检查＋语义编辑 |

数据存在、schema合法与hash正确是输入可靠性，不是审稿结果。预算、安装成功、生成阶段完成都不进入内容专业评分。

### 07.2 统一纯函数解释

`evaluate_current(document, reviews, artifacts)`在同一份当前对象与依赖上计算CheckSummary。Review接受、读取、continue、export、UI都调用同一解释，不各写一段否决if。

发现分类：must_fix=明确业务内容/制作错误或明确泄漏；needs_judgment=测量发现尚不能确定；advisory=不影响任务的改进。status不是P0/P1计数合成总分。尚有must_fix open→fail；必需维度未执行或必要needs_judgment未处置→needs_review；适用检查均完成且问题修复/有具体理由解释→pass。

`accepted_variance`只能用于具体测量差异或可接受表达取舍，必须给出观察与证据；不能用“语义满足”覆盖少节点、反向回写或读不清正文。程序对确定性文件坏/内容缺失/取消任务无权允许泛化豁免。改变规则版本后旧结果保留历史，不重签旧报告成新通过。

#### 当前默认路线的必需检查集合

image_blueprint与supplied_blueprint的整稿交付，都需要当前内容审稿、蓝图新增文案检查、蓝图→SVG还原、SVG→PPT转换、可读性和隐私/内部内容检查。不存在某类素材/图标等子项可not_applicable，但整页/完整正文不得因未登记而不适用。内容专业审稿不能只由机械Tool类型的规则扫描替代，必须有实际Host或人类阅读。

独立compiler API可以只返回转换和读取诊断，不要求业务审稿；因此它的输出不能自动被标记为“从资料完成专业Deck”。人类professional_use和目标桌面editing证据单列；缺失必须显示尚未验证，不捏造通过。

### 07.3 不适用、未知与无发现

原图确实无图标，维度not_applicable；尚未看原图，not_evaluated；完成实际检查且未见问题，才可能pass。空registry只能表示登记集合空，不能得到coverage=1。Review.findings=[]不自动通过，必须有subjects、适用检查、执行身份/观察和当前依赖。

工具能够得到的对象覆盖只叫“已声明输入对象覆盖”；不能外推原图全部业务内容。必要文本与关系来自Page/源图，不来自输出SVG或其trace。

### 07.4 像素指标怎样用

可使用SSIM、边缘、bbox、局部裁切等工具，但它们相关、受字体与抗锯齿影响，不能按“两项失败比一项严重”投票。只用全页高相似度无法保证局部正确。

读取端和写入端不允许不同判定。测量产生具体位置与差异，审阅查看源图/SVG/PPT再判断：圆角变直角、箭头方向错误、实际字形重叠是实质缺陷；bbox相交1px但字形不交可能是可接受测量差异。阈值调整要用正常样例、故意删减、合理渲染差异三类验证，不能只把当前坏输出调成通过。

### 07.5 真实审阅与独立性

Tool报告自己的检查，Host自审用host_self。independent_host要求实际独立执行上下文取得原任务、来源要求和真实产物，给出自己的观察；两个reviewer字符串或脚本两次调用不够。系统不能认证Host无法提供的内部身份，只记录可核验invocation/ref和来源级别；未知独立性为false。

独立审阅不是强制用户招募第二个人才能用产品。默认可以Host实际自审并如实标识；声称独立时必须真的发生。human_internal/external需要实际人类阅稿记录，模型不得代填。缺合格人类审阅不阻断全部工程改善，但公开专业可用证据仍未完成。

### 07.6 审阅必须完成修改

发现能自行解决的问题：创建具体repair任务，包含问题对象、原因、期待和相关资料。修正文产生新Page；修版式产生新SVG；修转换器使用原SVG重编译。不要只输出“建议补充案例”。

repair结束后重新运行受影响检查；未变页面结果可沿用，但全稿引用/数字或页序影响的检查重新验证。问题fixed必须指向新Artifact与实际检查，不靠把resolution从open改fixed。

同一错误、同一候选连续无变化，停止原样重试并说明下一步；没有质量收益的循环不继续。停止不是合格，不能把未完成稿改名成“初稿已完整交付”。

### 07.7 出口规则

本地`export --purpose review`允许输出可打开的未通过稿，附真实未通过/未评估列表；不得改图中业务文字加大水印影响审阅，交付包README和文件名明确用途即可。用户查看失败产物无需先批准。

`--purpose delivery`要求当前整稿产物齐全、当前工程/内容/隐私/可读必要检查无未解决问题；用户要求人类复核时再检查对应条件。无专业人类阅稿时可作为“方法与工程试行交付”而非“专业业务可用已经验证”，输出字段明确证据等级与editability=editable_shapes_and_text/unknown；不得暗示Office原生图表“编辑数据”或原生表格能力。

本工具不发送客户邮件、上传外部系统；外发由用户/Host按独立授权执行。导出本地文件不新增团队审批，也不取消真正的外发授权。

### 07.8 安全但不泛化防御

保留文件/脚本安全、真实私密数据限制、正常业务备注核对。移除“缩略图/左屏/右屏”等普通词即P0；元数据缺page_role不自动意味着泄漏；未知可评估维度不能给4分。缺检查显示待检查，不能通过默认值达标。

输出建议中不能列出内部制作说明作为正文；但是在讲解“如何制作PPT”的教学任务中，相关词可以是正常主题，要结合任务语义，不建设无限禁词表。

### 07.9 fixed的完整复查关联

不新增RepairProof对象。复用Review.replaces、subjects、dependencies、findings.evidence与observations：旧R0失败指向产物A0；repair产出A1（新的相关依赖/字节）；实际check或阅图后生成R1，replaces=R0的不可变Ref，保留finding_id，subjects包含A1，evidence指本次实际核查文件/对照，观察说明期待与实际。只有这个新Review才可把该finding列fixed；旧R0仍为open/fail历史。

接收时检查R0存在、同一逻辑review/finding、R1检查对象和依赖当前、复查针对A1。仅改resolution、继续引用A0、引用过期A1、或只有repair自报“已修好”时不能更新当前通过。实际文件未变而发现是测量误报，应提供accepted_variance的具体复核，不伪造fixed。不同于单次修复的全稿检查仍按实际依赖处理。

完整合同往返在`examples/roundtrips/review-fixed/`。其中before/after和Review全部是合成文件，用于示范关联与负例，不是已经执行真实审阅。

---

<a id="spec-08"></a>

## 08｜局部修改、事务、取消与费用

### 08.1 原子提交算法

所有CLI、UI、Host提交均通过store；不得直接写current Page文件。采用macOS/Linux `fcntl.flock`小范围排他锁，不实现分布式锁服务。

1. 读取current Document与相关输入read_set；校验拟修改内容和所有引用。耗时阅读、生成、渲染在锁外。
2. 新Page/Artifact/Task/Review与文件写入staging，计算hash，复制/移动到不可变objects；相同hash复用，不覆盖现有不同字节。
3. 取得write.lock，重新读取current，核验目标输入read_set、任务未取消/未被替代、operation_id幂等性。
4. 可重基的独立页操作在最新Document上合并；全稿顺序替换/恢复要求明确base_revision匹配。
5. 写新的Document快照，fsync；最后通过临时文件+os.replace原子切换current，必要时fsync目录。
6. 释放锁，返回真实新revision。历史对象/快照不删除。

第5步前崩溃：current仍旧，无半套可见状态；可能有孤立objects，不自动采纳。切换后崩溃：重试同operation_id读取同结果，不能再写一个不同结果。去重映射是Document/Task可追溯字段和对象，不另建事件溯源数据库。

### 08.2 幂等与并发语义

同task/operation与相同结果内容重复提交→already_applied；相同身份不同输出→conflict；输入改变或任务取消→拒绝late_result，不写入当前。保留候选作为诊断可以，但不能改current。

两页独立编辑：A改p1、B改p2，只有各自read_set时允许在最新revision合并。B读过全稿共享结论则必须校验共享依赖。两人改同页，后提交得到conflict并读取新页，不自动最后写覆盖。UI表单发送expected_revision和目标page hash；其他页改变可重基，同页改变提示比较后重新提交。

本地compile/render/check也用同一Task记录开始与结束，可同步在CLI或本地服务内执行，不新增常驻作业平台。取消时可终止本动作持有的子进程；无法立即终止则至少禁止结果采用，并如实显示停止请求/计算收尾，不能误杀其他进程。

锁与取消采用同一current判定：cancel先提交则晚到结果不可落地；accept先提交则cancel不能撤销已接受产物，只能创建后续修订。普通轮询不创建新task、不消耗调用额度。

### 08.3 修改影响表

| 修改 | 必须更新 | 必须保留 |
| --- | --- | --- |
| 一页文字 | 该Page、相关SVG和预览；全PPT装配及文件检查；相关语义检查 | 未变页原图/SVG，不改原图生成历史 |
| 图中某条边 | 该页设计关系/图形端点、对应审阅 | 其他无关节点和页面 |
| 改某个全稿重复事实 | 所有引用该事实的Page与图示、相关检查 | 不含该事实的内容；不得只修用户点的那一处 |
| 增删页 | 当前页集合和装配；相关页码/跨页引用 | 删除页历史与旧完整PPT |
| 重排 | Document顺序；可见页码/引用受影响页；装配 | 无可见页码的未变SVG |
| 换风格/字体 | 所有真实依赖该样式的视觉/渲染 | 原始业务正文与来源 |
| 改预算/日志备注 | Task/管理记录 | 正文、SVG、构建/检查有效性不被无关地取消 |
| 更换来源原文 | 相关事实审阅与内容判断；必要时内容重构 | 当前旧稿仍可看；不是发现来源变化就立刻删除全部产物 |

本轮不建设通用知识图谱。使用Page引用、内容依赖和明确共享条件定位；查不到影响范围就报告并扩大相关审阅，不假装自动精确影响分析已成立。

### 08.4 文件重建与页级复用

python-pptx重新生成整份容器是允许的；不能要求整份PPT字节不变证明局部修改。但未受影响SVG/blueprint的hash应不变，且没有新的生图/重绘任务。可见共享页码变化例外必须列明。

已完成的每次输出写新Artifact对象。没有引用的旧文件不立即删；失败修复保留至少现有历史引用和明确保留点。归档ID唯一单调或UUID，不封顶3，不重用已存在路径。显式清理只能删除不被当前/历史保留点引用的临时孤立文件，并先给清单；本轮不默认后台GC。

### 08.5 恢复与重定位

`history restore`产生一个新revision选择旧内容/产物引用；不回写旧快照，不回滚Task调用消耗、未知结果、取消事实或当前用户停止状态。当前代码/字体与旧产物检查不一致时旧产物仍可查看，重新检查才宣称当前有效。

项目整体移动后，objects和artifact refs按项目相对路径仍可用。源original_uri失效时允许用户/Host明确重映射 source_id→新路径；有已知原hash时核对，不同hash是新来源版本。原hash未知时读取新字节并说明“本次首次核实的候选来源”，不能把它追认为历史原文件；保留旧提取文本和未知来源记录。不要将所有源目录迁移/复制到一个新workspace。

### 08.6 重试、进展与项目内调用额度

区分外部生图调用、Host推理和本地格式/转换修正。`Task.usage`只是调用后可得观察；缺数据为not_reported，不用运行时间估算节省。用户明确设置`Document.policy.external_call_limit`时，按**经本项目交接的一次Host图像工具请求**计数，不按图片张数；批量一次调用产多图计一次，Host再次调用计新一次。工具内部隐藏的重试/计费无法由产品核实，不能将请求数声明为准确账户费用。

#### 最小额度记录与原子分配

复用Task.call_allowances数组，每项含allowance_id、state、execution_ref、invocation_ref、evidence；不建账户预算服务。state为reserved/in_flight/consumed/released/unknown。allowance由service在同一project的write.lock内分配，Host不能提交新额度或覆盖状态。

有限额L时，可分配数量为`L - count(reserved,in_flight,consumed,unknown)`，统计当前Document中每个Task的最新记录，已完成/取消Task和重试历史不得丢弃。不得用usage.external_calls（仅已知回报）替代此统计。两个Host并行申请最后一个名额，只能一个成功；读到旧revision的申请需重读后重新判断，不能各自扣一份副本。

无用户限额时仍记录实际调用，不凭空设置默认三次上限。任务起草/排队本身不计消耗。可以提前reserve，但实际调用前必须claim任务并begin；预留不等于有工具执行证据。

#### 调用前、调用后与未知结果

1. `task start --execution-ref`认领当前Task；同Task另一Host不能同时执行。begin将一个本Task/本execution_ref的reserved名额原子变in_flight，返回一次可执行许可。重复begin返回already_started，Host不得再次调用工具。调用前检查user_stop及项目是否有未核实unknown。
2. Host调用实际工具。已发送的成功请求或已发送的失败请求都计consumed；明确未发送可released。报告记录可得invocation_ref和观察，不能因为HTTP/工具报错就自动退还。
3. 响应丢失、超时或Host中断且不能知道是否实际发送：标unknown，继续占用名额；暂停本项目**新的**外部begin与追加分配，已在途请求允许结算，本地编辑/校验继续。
4. 仅在工具记录/明确执行证据证实已发出时unknown→consumed，证实未发出时unknown→released。不能按超时自动释放、不因重建Task清零。无法核实时如实保留，等待核实；不是要求重新批准整套流程。
5. 取消未开始调用可释放reserved；取消在途不得假定未消耗，未获结果则unknown。晚到响应可以结算成本事实，但不能采用已取消任务的页面产物。settle重复相同结果幂等；冲突报告不得覆盖。相同invocation在项目内不能重复消费/登记成两次成果。

Host报告只能提供调用结果，状态迁移由service执行。包不能约束绕过此协议、直接调用其他工具的宿主；这项边界在CLI/UI/文档明确。若没有可核验调用记录，只能称host_reported，不签成provider_verified。

#### 额度变化与项目恢复

policy降低到已占用数量以下时，允许保存更低上限以停止新调用，但不能抹掉过去消费。增加上限需要用户对该费用/次数变更的明确授权，不建设逐修复审批。`history restore`恢复内容与产物，不回滚调用记录、取消/停止事实或自动恢复旧高额度；当前Task操作事实合并保留。否则恢复旧revision会重获已经消费的名额。

本地重绘文件格式修正、查看状态、重复提交不消耗外部额度。若修复确实需要再次调用图像工具，必须取得新名额。实际工具提供的自动幂等请求标识可复用核实，但不能假定每个工具都支持。

#### 进展与早期实施

同输入/同输出、同一确定性错误没有变化时，改变修法或返回具体缺口，不无限循环；停止不能变成质量通过。renderer超时是执行失败。T13的最小额度分配/调用边界应在T06第一次真实外部调用前交错实现；T13整体仍在WP03完成并发、未知、取消、恢复及历史测试。完整四视图/所有格式不是该小段实现的前置。

### 08.7 必测故障注入

对象写一半、Document写完指针未切、指针已切响应丢失；两个独立页并发；同页冲突；取消与提交竞态；旧任务相同hash但已取消；已完成提交重复；4次以上归档；项目重定位；删除页不混入新PPT；源资料断开时只阻相应动作。所有注入用合成项目/副本，不能破坏用户原run。

### 08.8 制作配置的修改与恢复

`design update`提交Document.design_context的新版本。以03.3a解析出的page有效style/字体/允许资产计算影响：全局默认样式改变不影响明确选择另一样式且无共享改变的页；未使用的asset更新不触发生成；同ID实际Logo字节改变会更新依赖它的页；实际字体替代或物理画布改变必须重新处理相关渲染/布局。

仅重新绑定相同字节的项目路径不使语义或视觉过期。整体项目移动后，Logo/图标从objects恢复；系统字体按登记需求重新定位并比实际hash，不同版本明确重新检查。恢复旧设计快照只恢复内容/样式选择，不回滚实际调用消耗。

---

<a id="spec-09"></a>

## 09｜CLI与Host执行协议

### 09.1 主命令的最终语义

以下为拟实施的公开接口，不是现有CLI。`--project`接自动建立的产物目录；允许兼容`--run-dir`别名，但内部一律同义。所有命令支持`--json`；默认人类输出简洁，Host默认使用JSON。

| 命令 | 必要输入 | 实际动作/返回 |
| --- | --- | --- |
| `deck-master create --brief task.md --source file1 --source file2 --out project [--design design.json]` | task文件/文字、资料、输出位置 | 创建最小Document、来源与明确design_context；已有完整稿可用`--draft`省compose；返回待Host任务，不宣称生成完成；桌面主Skill首次接收到页即自动view --open |
| `deck-master continue --project project` | 项目 | 运行可执行的本地动作，返回稳定的下一批Host任务或当前检查/成品；不重新询问已经确认内容 |
| `deck-master edit --project project --page p09 --instruction changes.md` | 范围与修改要求 | 创建修订任务，返回task与影响范围；没有Host运行不能显示修改完成 |
| `deck-master view --project project --open` | 项目 | 启动/复用loopback审阅服务并打开当前任务；浏览器不可开则给实际URL |
| `deck-master check --project project` | 项目 | 执行当前适用的实际文件检查；需语义/视觉阅稿则产生review任务 |
| `deck-master export --project project --purpose review|delivery --out target` | 用途与本地目标 | 输出当前文件、预览/说明；review可未通过且标识，delivery遵循07章 |

不给用户增加六个必须顺序手动执行的阶段。主Skill通过create/continue/task accept在同一个任务内完成正常链路，用户只需要给任务或修改意见。

### 09.2 必要辅助命令

- `task accept --project ... --task-id ... --operation-id ... --produced-against <hash> --result result.json`：接收Host结果，校验并原子应用。
- `task start/status/cancel --project ... --task-id ...`：start带`--execution-ref`实际认领，另一执行者冲突；查看/用户停止不冒充执行。cancel可有原因但不强制长表单。
- `task call begin --project ... --task-id ... --allowance-id ... --execution-ref ...`：调用前原子取得一次许可；重复请求返回already_started，不允许重发外部调用。
- `task call settle --project ... --task-id ... --allowance-id ... --outcome consumed|not_sent|unknown --report report.json`：结算真实调用观察；报告不是永久第六对象，状态由service推导，详见08.6。
- `import asset --project ... --asset-id logo-main --kind logo --file ./logo.svg --external-use allowed`：保存真实媒体为asset Artifact；登记不等于所有页面自动使用；同ID换字节形成新版本。
- `design update --project ... --input design.json --expected-revision ...`：规范化制作配置并提交新Document；不接受任意运行脚本或外链资源。
- `task retry --project ... --task-id ...`：明确对失败/取消任务建立新尝试，沿用真实输入、保留历史，不清零原记录。
- `import draft --project ... --input draft.json`：接收完整Page列表；可用不含旧run的create --draft。
- `import legacy --input old-run --out new-project`：读取/副本导入，原run不写；先inspect dry-run再实际导入，不执行旧脚本。
- `history list/restore --project ... --revision ...`：查看/恢复为新版本，不删除历史。
- `doctor --project ... --step compose|blueprint|compile|render|view|export`：只核实该步实际依赖与安装来源。
- `install/rollback`：维护入口，实际参数由11章指定；不能作为每份成稿前置。

旧93命令不全部搬过来。少量明确别名在下面列出，其余返回旧命令已退出说明与正确的新用例，不执行旧OS，也不自动操作旧数据。

### 09.3 JSON响应与退出码

通用响应：`status, project_id, revision_id, requested_action, result_refs, pending_tasks, findings, next_action, review_url, view_status, evidence_level`。view_status包含service/browser状态及具体原因；无效服务不得输出伪URL。无值用null/空数组，不伪造URL和文件。

| exit code | 含义 |
| --- | --- |
| 0 | 本次请求的本地动作已成功（例如任务成功创建）；须读status区别整稿状态 |
| 2 | 无效命令/参数/输入契约；具体字段与修复方式 |
| 3 | 执行型continue/check因外部Host、工具或真实决定暂不可继续；status awaiting_host/needs_input/needs_tool |
| 4 | 实际执行或检查失败，保留失败产物与位置 |
| 5 | 输入版本冲突/旧结果/已取消，不改当前 |

创建/取消/查看可返回0，而整稿仍pending；自动化不得用进程exit0写“成稿通过”。单独`check`有must_fix返回4，未执行关键审阅返回3。JSON中ready结论统一来自view/review。

错误至少有code、message、page_id/element_id（适用时）、expected/actual、next_action。不从英文异常字符串猜测业务身份，不吞异常后返回空成功对象。

### 09.4 Host输入和输出

Task的Host种类为compose/blueprint/reconstruct/review/repair；compile/render/check是service自己执行的本地动作，不派给Host补“运行回执”。

Task.inputs是实际可读Ref；response另外提供从同一Document解析的工作内容、resolved_design_context、当前允许资产路径及本次安装的method资源路径，避免宿主只能看manifest hash。原图任务直接提供图像路径/引用，Host实际看图。每个任务有scope_pages和produced_against，不能由Host自行缩小必要输入或修改自己的预算证明。

compose.result：完整Page v2数组、明确页面顺序、来源映射及任务相关说明。blueprint.result：实际图片文件、可得工具调用/实际prompt、观察。reconstruct.result：SVG文件和必要绑定；不提交手写Scene。review.result：Review v1观察和具体发现。repair.result按目标Page/SVG/Review输出相应新对象。

`result.json`只是接收信封，判别字段固定为`kind`（不再混写type）；files声明临时文件，其他有效载荷按下文09.7解释；不新增永续结果schema平台。程序根据Task.kind校验对应Page/Artifact/Review，文件必须在该operation批准的staging或显式用户选择路径，不允许借result写任意项目路径。

### 09.5 宿主执行循环与默认工作台出现时机

1. 读取任务和既有决定，create或继续已有项目；有完整稿直接导入。桌面正常任务不要求用户额外手动执行view。
2. **create --draft、import draft或compose结果第一次成功形成至少一页后，主Skill必须立即自动调用`view --open`，在继续逐页制作前给出实际工作台入口。**service响应返回需呈现工作台的next_action；Skill执行该动作，不把任务丢回用户。正文已存在但制作失败，也必须看得到。
3. 同项目后续修改/继续复用原服务和URL，不每次开新端口或重复弹窗。仅服务失效时重启并更新实际URL；不能为了“相同URL”声称失效地址有效。已有有效服务由本安装健康检查确认。
4. 读Task全部相关正文、源资料、实际图片及解析配置，应用本次kind的方法；外部调用前按08.6分配/begin，结果实际结算，不伪造工具行为。执行真实工作并submit；冲突读取新输入，失败按具体错误修改。
5. continue推进实际制作/当前检查；需要Host审阅就实际看原图与产物。每次稿件更新与首份完整候选交付都提供该项目现用入口与相关页链接。零产物、失败、待Host、未评估如实显示。

纯CLI批处理允许`--no-open`：不调用浏览器，但应返回view_available/可执行查看方式，若已启动服务则给真实地址。无桌面浏览器但可提供本地服务时仍启动并返回真实loopback URL，明确它只在该主机可达；禁止自动公网暴露。无权限/端口/进程能力导致服务不可启动时view_status=unavailable、review_url=null并说明原因，保留文件路径，不伪装完整桌面交互已验证。

服务启动请求有界等待/健康检查，不以看不到UI为由无限阻断正文和编译；失败明确进入待修功能。没有后台Host进程，工作台只记录反馈并等待Host，不能假称AI会自行完成。用户可从持久化Task继续，不需每阶段回复“继续”。

### 09.6 旧命令映射

| 旧入口 | 新处理 |
| --- | --- |
| import-plan（完整稿） | 转换v1→v2后import draft，源数据不改；不能丢未知字段 |
| build prepare/run/status | 新项目映射continue/view派生状态；旧项目要求legacy import或固定旧版 |
| next-step/run-state/final-readiness | 新项目返回同一ProjectView；不运行旧state resolver |
| export（本地文件） | 明确purpose；旧approved queue不能代替当前产物 |
| start-conversation/build-brief/build-claim-map/autoplan | 给出create/现有完整稿导入指引；不隐式生成规则稿 |
| search-library/decide-sourcing | 新核心不实现整页库流程；提示用来源文件或显式旧工具 |
| 旧workflow/handoff/approval/team/learning/RC命令 | 明确退役，不转成新任务前置 |
| 其他旧命令 | 受控提示，不继续调用旧main；清单工具列出需要映射的所有真实命令 |

以旧run路径调用新写命令时先识别格式；不得自动就地迁移、初始化新pointer或误把旧completed当新通过。

### 09.7 临时结果信封的唯一形状与采用顺序

信封字段固定为：kind、files、pages、page_order、artifact_specs、reviews、usage_events、notes。可省略当前kind无关字段；未知字段返回具体输入错误，不静默忽略。不是第六个持久schema；解析器按Task.kind进行分支校验，最终只保存五类对象。

- files：`file_id,path,media_type`。path相对于该Task.operation_id的staging，不能包含`..`或跨根符号链接；显式用户外部导入另走import能力，不借Host结果写任意文件。file_id是信封内标识，不是假hash。
- pages：完整Page v2；compose需要全页数组及完整page_order，单页repair只能包含授权scope_pages。不能借更新p09省略其他页将其删除。
- artifact_specs：`file_id,role,page_id,derived_from,provenance,reference_regions?,limitations?`；source实际文件来自files，artifact_id、字节hash和依赖由service核验生成。provenance中提交prompt可以用`submitted_prompt_file_id`引用本信封文件；生成后替换为真实Ref。generated_from_page用已持久化Page Ref，不能补写旧图当时使用新正文。
- reviews：完整Review v1，subjects必须指已保存且实际核查的对象；不能用未知临时别名或自己生成的输出清单代替源预期。
- usage_events：`allowance_id,outcome,invocation_ref,evidence_file_ids`；只报告已有名额的实际观察，不授予额度、不接受覆盖call_allowances。调用事实即使产物接收失败也应通过settle保留，不能把业务事务回滚当作调用没发生。
- notes：普通说明，不进入对外正文或默认质量通过。

接收顺序：校验CLI的task/operation/produced_against与scope→规范化文件/正文/引用并预校验全部结果→保存不可变对象→在项目锁中重新核对依赖、取消与幂等→一次切换当前文档。相同operation同内容返回already_applied；结果不同或输入过期返回5且current不变；仍可结算已经发生的外部调用。

完整compose、blueprint、reconstruct、review及repair信封和往返结果见`examples/roundtrips/result-envelope/README.md`。这些是合成协议范例，不是API已实现或Host已执行。

---

<a id="spec-10"></a>

## 10｜真实审阅工作台与API

### 10.1 首屏不是新管理平台

复用现有可用HTML/CSS/原生JS，重写实际数据接线。不做新商业品牌装修、拖拽画布或内置AI聊天系统。页面包括：左页清单；中间正文/蓝图/SVG/PPT对照；右当前问题与修改反馈。顶部显示项目、当前版本、制作/检查/专业证据状态；在详情显示实际画布、当前有效样式/字体与必要替代说明，数据来自design_context，不由前端自选默认。

没有任何产物时显示等待内容/Host；已有失败PPT就能打开看。没有legacy preview_manifest不能显示0页；Document.pages就是页数。没有人类审阅不能显示已批准，缺审阅或过期报告显示未评估/历史结果。

### 10.2 页面状态与展示

每页卡片显示稳定page_id、标题、顺序、当前可用视图、是否有must_fix、是否等待Host和更新时间。可点击失败/过期产物，并明确历史版本。中间支持单视图、蓝图↔SVG、SVG↔PPT、原文↔实际正文。缩放/平移、适配宽度和下载实际文件；表格/图表注明“可编辑形状与文字，非Office原生数据对象”；不以网页截图替代PPT实际渲染。

正文可编辑结构化文本（标题/段落/条目/表格单元格/脚注等），提交后产生新Page而不是直接修改SVG。视觉修改通过具体指令派发Host；界面不是自由排版器。关系修改可编辑已识别节点/边字段或给指令，必须保留期望语义用于复核。

反馈可指向page_id、element_id或图像归一化区域与文本；不要求所有反馈先分风险等级。点击“提交修改”只显示queued/awaiting_host；真实Host start后才running，收到结果后才有新版本。

### 10.3 API一览（拟实施）

| API | 读取/写入 | 返回与约束 |
| --- | --- | --- |
| GET /api/project | ProjectView | 当前revision、真实页数组、输出、问题、下一动作；只读 |
| GET /api/pages/{id}?revision=... | PageView | 正文、设计、相关Artifact/Review；404不伪造空页 |
| GET /api/artifacts/{id}/file | 实际文件 | 只服务登记的对象；按media type；禁止任意path参数 |
| GET /api/tasks | Task视图 | 当前未完/失败/取消任务，无模型时如实pending |
| GET /api/reviews?page_id=... | 当前/历史审阅 | 显示依赖是否当前，不修改旧pass |
| GET /api/history | 版本摘要 | 稳定ID、动作、可查看/恢复 |
| POST /api/pages/{id}/content | Page编辑补丁 | expected_revision、page_hash、operation_id；409冲突；成功返回新revision |
| POST /api/edits | 修改请求 | 页范围/指令/可选区域，调用service.request_edit |
| POST /api/tasks/{id}/cancel | 停止 | 同一事务检查；不能撤销已经应用的结果 |
| POST /api/check | 实际本地检查或创建review task | 返回已执行/待Host，不假running |
| POST /api/export | 本地导出 | purpose与目标路径经用户明确选择、校验；不外发 |
| POST /api/history/{revision}/restore | 恢复 | 生成新版本并保留当前旧版；冲突明确 |

所有写操作调用同一service/store；不向旧preview/actions再写一份。POST返回最新ProjectView或revision，前端随后重新读取。HTTP冲突409、输入422/400、缺工具503需带typedcode，不展示成任务成功。

### 10.4 服务启动与无Host时的行为

正常桌面主Skill在首次正文页接收后自动调用view --open（09.5），不是等完整候选才给URL，也不要求用户另开终端。create --draft和import draft适用同一规则。之后复用同项目服务，每次稿件更新都给现用入口；非交互、无浏览器和启动失败分开返回实际状态。

`view --open`默认绑定127.0.0.1、自动空闲端口；同一项目已有本安装启动的有效服务则复用。URL包含会话token，浏览器自动打开失败时输出可点击实际URL。命令不必须等待成稿通过才能启动。

服务进程使用本次安装的Python与静态资源，启动信息记录pid/port/version只是可重建缓存；端口陈旧时重新探测，不能杀掉不属于本安装的进程。后台服务是产品实现能力，当前文档并未启动它。

Host没有驻留时，UI只记录任务并提示打开宿主继续；不实现轮询外部模型API。刷新采用简单带revision的轮询即可，无需事件总线。运行中的转换可由已有本地service任务执行，真实开始/结束才改变任务执行状态。

### 10.5 本地服务的必要安全

仅loopback默认、不允许任意来源写入；写接口校验同源Origin和会话token。静态/产物访问只按登记ID解析安全项目内路径，不接受`../`或任意绝对文件。外部来源用于阅读但不默认作为Web文件目录暴露。

来自材料的文字用textContent，不注入HTML。展示SVG采用安全渲染预览或隔离方式，不直接运行来源脚本；编译器已禁止脚本/外链。无需用户账户、RBAC或新登录平台。

### 10.6 交互验收

从自然语言主Skill入口开始，测试者不手动补执行view；首次正文到达便实际启动并打开工作台，失败稿/修改反馈仍可达。非交互/无浏览器/服务无法启动分别核查真实URL或原因。创建普通项目后显示实际页数；完整稿2页+无旧preview时仍2页；失败页面可开；四视图和问题链接指向实际当前文件；同页编辑冲突不丢数据；取消后晚到结果不更新页面；重排后页序与PPT一致；修改后返回同一URL/项目而不是开第二套工作台。

至少在1280×800和1440×900检查导航、表格正文与比较图不被关键按钮遮挡。键盘能切页/提交/取消，状态不只靠颜色。截图证明展示，交互测试证明动作；两者都不能单独证明专业内容通过。

---

<a id="spec-11"></a>

## 11｜包、安装、独立运行与默认入口切换

### 11.1 包结构的具体调整

将pyproject的package-dir改为src发现，仅打包deck_master；console entry为`deck_master.cli:main`。元数据移除Run OS/全部治理ready等旧定位。候选版本用明确预发布标记，正式版本号在用户批准发布时定；文档不宣布2.0已发布。

保留Python3.11/3.12验证和现有jsonschema、python-pptx、Pillow、numpy依赖作为起点；具体锁定范围以候选安装实测确定，不能凭本包放宽到未知最新版。资料PDF/DOCX/PPTX处理按04章选择已有依赖或标准XML工具，任何新增依赖说明用途并在许可证中登记。缺PDF工具只影响相应资料读取，缺renderer不阻断正文编辑。

当前旧scripts包不进入wheel，不把源码整个目录COPY到用户安装充当发行。资源包含五份schema、静态工作台、一个deck-master Skill及内部references。用importlib.resources定位，不借当前工作目录或源码checkout。

### 11.2 Skill资源唯一来源与构建实现

仓库中`skills/deck-master/`为唯一可编辑Skill源。新增一个最小setuptools build hook（`tools/build_hook.py`，由最小`setup.py`注册build_py）在正常PEP517构建时复制它到build_lib/deck_master/resources/skill；源码不维护第二套同义副本。新增`MANIFEST.in`确保sdist包含hook、Skill和资源；wheel包数据配置包括resources。

`pip install .`、从sdist构建、release构建都必须走同一hook，不能只有自定义脚本构建才有方法文件。hook不联网、不生成业务内容、不打包客户资料或字体。tools/build_release.py仅组织构建、检查wheel清单并生成发布归属清单，不引入RC治理平台。

开发第一批即通过隔离虚拟环境安装新候选包以验证src/resource边界；生产当前链接不切换。公开默认安装与文档在WP04切换。`pip install -e`作为可选开发方式不能被当成无源码依赖的安装验收。

### 11.3 最小安装布局

建议沿用可恢复的用户前缀而非重新造安装平台：

```text
<prefix>/.deck-master/
  releases/<release_id>/venv/...
  releases/<release_id>/release.json
  current -> releases/<release_id>
  previous -> releases/<previous_id>
  bin/deck-master                 # 使用current固定解释器
```

prefix可配置，默认用户HOME；不修改系统Python、不要求管理员权限。release.json记录包版本、实际来源SHA/构建资源hash、内核版本、方法版本、入口。它只说明安装内容，不说明专业首稿ready。

安装命令在新release目录完成依赖安装、导入、资源、最小真实编译/渲染工具探针后，用户授权时原子切current。失败不改现有current。rollback切回旧二进制版本，不自动让旧代码写新版Document；不支持格式时明确只读/导出或配套恢复旧项目副本。

### 11.4 真正解除外部绑定

product-capability-manifest、Skill routing、doctor、installer、README、UI统一删除新核心对PPT Master repo/SHA/bind/verify/certification的要求。Library默认完全不加载，不调用检索后假装none；无历史缓存、无库配置的环境应可工作。

通用python-pptx/渲染器仍是正常依赖，不把“不绑定PPT Master”解释为“不依赖任何库”。旧第三方Skill和用户已装PPTMaster不删除，只是不参与新核心。

旧standard/high-density不再是产品两种不同主流程；样式和密度仅参数。CLI旧profile仅在明确可映射到当前设计参数时映射，否则提示退役。不能用一个profile跑通后继续把整体产品ready绑定旧标准后端。

### 11.5 Host Skill安装与移除

仅安装deck-master主Skill到用户选择的Host路径。内部方法不是15个公开专家；不要求全部安装才能使用。安装前读取已有目标：是本安装器拥有的旧链接/未修改文件时可替换；用户修改过或来自第三方时备份并提示，不覆盖。

清理旧deck-*技能只依据本安装器实际ownership manifest/链接目标/hash；名称相同不足以授权删除。旧ppt-master、ppt-library等第三方技能保持原状。不可通过扫描整个.codex/skills递归rm完成减法。

### 11.6 doctor的输出

必须区分：安装包可用、资料格式工具可用、生图Host能力可用、编译可用、渲染可用、工作台可用、当前任务专业证据。最后一项不能由doctor自动判通过。

返回实际Python executable、模块__file__、包版本、源SHA、资源目录、字体匹配、renderer路径/版本。每步required/optional清楚；没有Host图像工具写awaiting_host，不伪装安装失败，也不自动降fixture。

### 11.7 独立安装验收与切换

在隔离HOME、无PPTMaster/Library配置、禁止访问源码checkout、无用户已有缓存下安装候选；从安装后的deck-master create运行。检查method/schema/static资源存在，真实SVG转换/PPT渲染、工作台启动、局部修改、恢复、导出都使用安装模块。

目标平台指定字体与Logo不因移动项目丢失；字体文件不随公开发行打包；缺指定系统字体如实说明。安装验收从自然语言主Skill开始观察自动view，不由测试者额外手工补命令。实际Host调用可在授权的测试会话完成，任务产物通过安装CLI接收；不能从repo临时补.py或资源。产物版本与安装release记录对应。macOS桌面编辑与Linux headless分别报告，不将一个替代另一个。

切换门槛：本包范围内正常入口链路有效、安装无旧依赖、当前UI与文件一致、已知must_fix无未解决、legacy导入/回退明确。切换是用户授权的发布/安装动作，Spec通过不自动授权执行。

### 11.8 CI怎么改

三组：①Python3.11/3.12单元、schema与边界；②真实图形/字体/渲染小样例及实际XML读回；③wheel/sdist隔离安装、资源、启动器、legacy导入与回滚。Host生图和人类业务阅稿不假装在无凭证CI执行，保留单独真实运行记录。

每组报告executed/failed/skipped/unavailable，不把跳过必测称通过。旧测试按12章行为迁移，不要求CI永远运行两个完整OS。引入新包时旧套件结果和新套件结果分列，不能用总数掩盖新链路未执行。

---

<a id="spec-12"></a>

## 12｜旧run、旧流程、旧合同与历史文档退役

### 12.1 只读兼容，而非继续维护第二个产品

新核心能做的兼容：inspect旧目录、读取已知JSON/媒体、把真实正文和可识别资源复制导入新项目；不会调用旧OS自动继续、重签旧审阅或继承旧completed。需要原样继续旧run时，用户明确使用固定旧版安装；两种写入者不能同时操作同一目录。

禁止就地迁移原run。import legacy的out必须是新目录或明确新项目，源目录与其子目录不能作为目标。所有读取只针对允许格式和登记路径，不执行运行目录.py/.sh、不加载pickle、不执行宏/Office自动化。未知版本显示可看原件和无法映射部分，不猜测。

### 12.2 字段迁移表

| 旧内容 | 新落点 | 必须保留/不得推断 |
| --- | --- | --- |
| PagePackage v1 customer_visible | Page v2显式正文块 | 完整副标题、items、表格、labels、footnotes；未知结构返回待规范化 |
| narrative_plan beats/order | Document.pages顺序 | 显式页集合；重复/缺ID冲突不能静默去重 |
| speaker_notes/internal_only | 对应分离字段 | 正常业务备注保留、制作指令不变正文 |
| source/context manifest | Document.sources与source_extract | 原位置/hash/来源说明；没原文就未知，不能用页面正文补证据 |
| original blueprint/prompt | Artifact及provenance | 原生成输入与文件字节；无法核实调用标unknown |
| SVG/PPT/预览 | Artifact legacy_import | 可查看可诊断，不默认通过新当前检查 |
| review/status/approval | 历史说明/参考对象 | 不转成新pass/human-approved；current重新按实际输入检查 |
| MBB/Scene/trace | 辅助解释或诊断附件 | 不作为新内容权威，不自动生成业务事实 |
| 旧Library记录 | 来源线索（明确要求时） | 不重新跑库平台，不承诺原整页混编可继续 |

v1→v2转换分两步：程序转换已知结构并列出未映射路径；Host依据原文完成有歧义正文规范化，再接收成新Page。这个动作属于实际内容迁移，不要求用户逐个填治理字段。未映射信息不能静默丢弃后报告成功。

### 12.3 导入与回退验收

对原目录计算关键文件hash及写入检查；inspect/import前后不变。新项目所有ref应可解析，源断开不影响已复制媒体查看。original_sha256=null/缺省均为合法未知；extract和媒体file的真实hash仍逐字节核对。补回候选原文时，已知hash不符必须新来源版本；未知hash不能声称候选就是旧原文。导入后的语义/视觉状态是未检查或legacy-unverified；实际跑新检查后才能变当前通过。

新版导入失败删除的只能是本次未激活staging；不能回滚时删原run或整个用户output。历史已产出的PPT应保留独立可下载，而不是“无法导入就没有文件”。跨目录移动测试分源资料移动和项目整体移动两种。

### 12.4 合同与代码归档

旧58份docs/contracts在WP05移入`docs/archive/pre-rebuild/contracts/`，保留原字节与版本；新运行时只使用五份schema。legacy若需要识别旧结构用有限读取器或只带必要旧schema，不能import旧engine以获取assert_valid。

旧scripts在替代与调用迁移完成后按177行台账删除；Git保留历史固定引用。原有旧tests的有价值行为迁到tests/rebuild；旧错误产品假设删除；旧完整测试仍可在固定旧版本运行，不为了当前CI绿而随意skip。

旧docs历史不一刀切删除。活动入口改为新Spec和新指南，历史设计文档加索引说明“已被替代”；准确保存当时事实和错误完成声明的更正，不重写原始测试日志或回填通过。

### 12.5 活动文档清单

README、AGENTS、CLAUDE、DESIGN、ROADMAP、CONTRIBUTING、quick-start、user-guide、agent-guide、recovery-playbook、task-index、known-limitations、troubleshooting，以及单Skill与其references必须一致。实际路径存在与引用关系需要Codex核验：存在则改，缺失则按目标新建，不能把计划路径冒充现状。

旧SC-1/P2–P5/Skill OS/RC方案不自动延续为新范围，特别是：用户时间下降30%、所有Skill齐备、PPTMaster认证、固定风险/CTA、团队商机审批、结果自己做蓝图等都不能因历史文档继续被宿主读取而复活。

### 12.6 何时可以删，何时不能删

可删条件不是“新目录已经存在”，而是：目标行为和正反例已通过；默认入口/安装已不引用；旧run读取与必要回退明确；static+runtime资源引用检查没有残留；许可证和历史来源保留。每个旧文件在台账标迁移证据/目标测试，不要求逐行签章。

没有新行为替代的有效取消/事务/内容完整性测试不能删。只检查错误门禁的测试不必为了保留而扭曲新实现。客户资料、模型输出原件、旧run、第三方安装资源不在仓库删除清单，永不通过本轮自动清理。

### 12.7 不把历史保护变成新负担

保留Git历史、必要旧格式读入、用户原文件即可，不要求新用户安装旧release、复制旧schema、运行legacy问卷后才能创建新Deck。新文档不通过数十条“兼容前置”重新制造旧流程。

### 12.8 旧设计资料导入

能够明确读取的画布、样式、字体名称和Logo等映射到design_context；实际保存媒体拷为asset Artifact并保留来源身份。旧style_ref只是未知路径/名称时列明未解析项，不让Host/compiler/UI各用不同默认。原信息确实没有时以可见的导入假设保存默认，并等待需要它的动作确认；查看旧PPT不以新设计配置全部补齐为前置。

不会把旧图片/历史PPT自动升级成Office原生图表/表格。导入Artifact.editability=unknown直到实际核查；先支持既有媒体可查看、正文可继续编辑，证据缺口按具体任务展示。

---

<a id="spec-13"></a>

## 13｜验证矩阵、完整稿证据与最终验收

### 13.1 三层验证，不能互相顶替

工程单元/合同/事务验证，真实制作/安装验证，以及内容业务阅稿分别报告。CSV共 **90 条拟验收行为**，大多数是小型函数/文件反例，不是要求做同等数量的完整Deck，也不是新增benchmark服务。矩阵是开发输入，当前全部planned_not_executed。

每条包含ID、预期、目标测试、责任任务和证据类型。Codex实施时将实际测试函数对应到ID；一个测试可覆盖多条，但不能以一句“已有测试通过”替代。关键内容与图形错误不得被平均分冲淡。

### 13.2 原始事故/纯转换/默认成稿分开

原始坏稿保留作反例；事故两页加表格图用于制作能力验证；D1/D2/P1/H1/H2用于内容与正常主链验证。人工精修的Page不是系统从原材料生成专业首稿的证据。纯SVG编译通过不是蓝图还原通过，蓝图漂亮不是业务事实正确。

输入授权：维护者准备公开/允许使用资料；合成可启动但明确标注。客户材料不得因测试需要自动加入仓库或发布包。未见材料由维护者/阅稿者在冻结后提供；如Host已接触则不声称严格盲测。

### 13.3 同模型公平对照

A=充分材料+清楚任务+合理自查；B=A+公共方法；C=完整候选流程。固定模型版本、参数、输入版本、工具权限、人工介入和合理自查/返修机会。已有Office Hour讨论所有组共用，不能某组多拿任务答案。

起点：D1/D2 A/B，再接入C，共6份；P1 C一份；H1/H2冻结后A/C四份，约11份。归因争议再补对应B。数量不是合格门槛，失败如实保留。不把D1/D2开发成功叫泛化，也不由H1/H2的A/C单独推出公共方法增量。

比较内容用相同只读版式，不让C的精美排版掩盖无观点。整链路再看真实PPT/可编辑/局部修改。记录第一系统交付完整稿；交付前系统内部修订属于流程，外部反馈后人工精修属于新版本，不能倒算。

复用结果必须模型、任务、材料、方法/实现版本、工具、自查条件一致；只同模型不够。冻结后依据H样例改方法，样例变回归；另取未见材料或缩小声明。

### 13.4 谁判断专业性

具备相应业务材料使用/交付经验且未参与本次成稿的人类阅稿者判断：能进入正常业务审阅、需实质重写、未完成任务。记录关键页与理由：是否有任务相关观点、机制、取舍、完整表达；是否必须替系统重建主线。技术结论有争议时由相关技术专家核实，不扩展成每稿一个委员会。

Host/工具/人类的身份和执行范围准确标注。没有人类专业阅稿则交付方法/工程试行，专业业务可用尚未验证；不暂停所有工程工作，不用两个模型一致抵扣。

### 13.5 实际执行方式

拟命令为`python -m pytest tests/rebuild/test_...py`及候选安装CLI；这些命令当前是开发计划，没有执行。CI分单元、真实渲染、隔离安装。需要Host生图/看图与桌面编辑的条目单独记录不可由纯CI声称完成。

正常原始输入、故意删内容/换关系/改字重/极小字、合理渲染差异三类都要验证。规则升级不能只拿当前失败稿证明放宽合理。源图hash与真实生成版本保留，不能canonicalize结果成自己的预期。

### 13.6 切换验收

默认创建、完整稿导入、用户原图、局部修改、恢复、真实工作台、安装无外部绑定、旧run只读导入和默认旧入口退役都达到声明范围。无完整UI/安装的纯内核通过只算组件交付。未实现的Windows、复杂SVG、任意PPT反向编辑等不写成支持。

正式激活/合并/发布需用户明确授权。候选出问题回退二进制，不破坏用户新旧项目；不通过强行混装旧模块恢复。

### 13.7 完成记录格式

普通Markdown表即可：候选SHA/安装源、任务与输入、实际执行者、命令/真实工具、输出hash/位置、当前结论、未执行与原因、关键失败页。不要建证据登记服务、用户计时回报或签章平台。没有反馈不等于满意，未执行不等于不适用。

### 13.8 v1.1必须覆盖的定点反例

R1缺原文null/省略及全零假hash；R2非16:9、指定字体/Logo、项目移动、只改样式；R3T25祖先含T13、T01/T24职责分离，并行额度/未知/取消/内容恢复不清零；R4自然语言入口首次正文即实际自动打开工作台，无浏览器/不可启动分别返回事实；R5形状文字编辑与Office数据对象清楚区分；R6首个小闭环与最终完成依赖分开。

三个接口往返例也要转成实际测试：stable atom改字重排、临时信封文件接收/冲突、fixed替换旧Review并指向实际复查。例文件能通过schema不代表这些跨对象/实际行为已实现。首次最小闭环的原图对照由Host/人类实际完成，不因T11尚未完成而豁免。

### 13.9 验收条目索引

完整CSV/JSON见inventory/acceptance-matrix。以下按行为列出，所有均待实施验证。

| ID | 验证内容 | 期望 | 责任任务 |
| --- | --- | --- | --- |
| AC-C01 | 原文末尾约束 | 关键只读/不可回写放材料末尾；输出正文与设计关系随约束改变，不只写已读 | T03 |
| AC-C02 | 场景结构与短稿 | 同源D1/D2结构/深度/结尾不同；合理短稿不加固定痛点风险CTA | T04 |
| AC-C03 | 全可见正文 | 嵌套职责、标签、副标题、脚注、表格值全部保留；metadata不变正文；稳定atom不依数组顺序/文字hash，重排改字ID不变，复制新条目新ID，旧Pointer导入规范化 | T03 |
| AC-C04 | 不再循环配论点 | 预置正确接口论点不能被数组取模配成公司成立年份；默认入口不调用旧enrich | T04 |
| AC-C05 | 事实/计算/建议区别 | 54÷120可复算；无依据40%提升不当事实；只读条件影响自动化推荐 | T11 |
| AC-C06 | 不依赖库和工作区 | 普通材料目录、无历史库缓存/模板可从create正常进入Host任务 | T04 |
| AC-C07 | 不重复问答 | 无额外约束/不适用有效；只问足以改变本次决定且来源无法回答的缺口 | T04 |
| AC-C08 | 来源形态 | TXT/MD/JSON/PDF/DOCX/PPTX读到相关正文和表格；图页派发阅图；缺工具不空成功 | T03 |
| AC-C09 | 正文完整而非占位 | 内容有业务机制/方案理由/适当深度；制作意图不替代正文 | T21 |
| AC-C10 | 复合Deck | 案例/架构/实施围绕同一任务，不重复拼接、无关章节不凑满 | T21 |
| AC-C11 | 未知输入形态 | 不能静默丢旧body字段；定位待规范化内容，未经检查不强设ready | T03 |
| AC-B01 | 真实prompt全字段 | marker确认subtitle/footnotes/labels/visual_spec等进入实际prompt而非仅中间JSON；同Document有效design_context/style_ref/允许资产投影，不独立补默认 | T06 |
| AC-B02 | 来源诚实 | actual prompt只从真实提交记录取得；未知调用标unknown；文件名/签名不升级真实性 | T06 |
| AC-B03 | 文案往返 | 采纳蓝图新文案产生新Page；原图generated_from与prompt保持原版，小改文字不强制重生 | T07 |
| AC-B04 | 图像实际参与 | 同业务两张显著不同布局源图，SVG几何相应变化，不能只换hash | T10 |
| AC-B05 | 基准方向 | 当前SVG/PPT预览及已知派生图不能成为自己原始参考；重编码不改变角色 | T07 |
| AC-B06 | 单手写源 | 只提交SVG可生成IR；Host无需手写Scene；必要绑定能解析 | T08 |
| AC-B07 | 源图预期独立 | 删除SVG图标登记不缩小源图预期；未识别原图不记满覆盖 | T11 |
| AC-B08 | 结构不重复印字 | edge.target不自动变正文；必要标签保留，关系实际连节点 | T07 |
| AC-B09 | 无假生图降级 | 缺Host工具返回待工具，不走fixture/无字通用图/自动直绘替代任务 | T06 |
| AC-B10 | 原件与重设计 | 明确新设计能建立新参考版本；旧还原失败仍保留，不回填通过 | T07 |
| AC-K01 | 独立转换 | 只给SVG/资产/参数，隔离安装可产PPT，不读旧OS/审批/HOME仓库 | T10 |
| AC-K02 | 负斜率与端点 | 正负斜率及反向line的实际PPT端点方向正确，不只bbox相同 | T09 |
| AC-K03 | 旋转圆边界 | r10圆旋转45度仍20×20；椭圆变换使用正确极值 | T09 |
| AC-K04 | 字体权重 | 800/900不反为normal；记录实际字体匹配/替代，XML与渲染核对 | T09 |
| AC-K05 | 零透明度 | fill/stroke/gradient stop/group opacity=0保留；None才默认 | T09 |
| AC-K06 | 多行中文 | tspan位置/基线/行距/字重/换行保留；无精确字符串掩盖排版损失 | T09 |
| AC-K07 | 圆角和描边 | 缩放圆角矩形、图标描边既有修复不回退；非等比范围明确 | T09 |
| AC-K08 | 实际几何读取 | 从输入SVG+独立Page关系检查实际PPT/XML，不只trace对trace | T10 |
| AC-K09 | 不支持与安全 | 脚本/外部可执行引用拒绝；不支持特性定位对象，不静默删图 | T08 |
| AC-K10 | 可读性 | 1pt/透明补全文层不能过内容覆盖；真实文本溢出有定位 | T10 |
| AC-K11 | 实际渲染 | SVG/PPT分别实际渲染，缺renderer标未验证，旧预览不能充新图 | T10 |
| AC-K12 | 桌面编辑 | 实际目标软件修改当前文字与关键图形/连接，保存重开；headless不代替；仅证明形状/文字编辑，不外推Office原生图表编辑数据或原生Table能力 | T23 |
| AC-K13 | 支持范围 | 线/路径/图标/表格/图片/渐变和画布按子集正确；其余明确限制 | T10 |
| AC-S01 | 事务不半写 | 对象/Document/指针各断点故障，当前仍完整旧版或完整新版 | T02 |
| AC-S02 | 文件安全 | 路径逃逸/符号链接危险写入/坏对象不能覆盖源和历史 | T02 |
| AC-S03 | Task幂等 | 同operation相同输出重复返回同结果；不同输出拒绝 | T12 |
| AC-S04 | 依赖分层 | 预算/备注不让未变SVG失效；实际字体/源事实/全局style改变影响正确范围 | T12 |
| AC-S05 | 局部编辑 | p09修改后无关页原图/SVG hash不变；整PPT允许重装配 | T12 |
| AC-S06 | 多页事实 | 改变共用事实/关系，所有引用处更新，不只修改点选页 | T12 |
| AC-S07 | 页集合 | 增删重排稳定ID，删页历史保留不混回当前PPT | T12 |
| AC-S08 | 并发与冲突 | 不同页读集安全重基；同页冲突不最后写覆盖 | T12 |
| AC-S09 | 取消竞态 | cancel先赢则晚到不写；accept先赢则cancel不删除成品 | T12 |
| AC-S10 | 恢复/重定位 | 恢复新revision不改旧快照；移动项目refs可读，源映射检查hash；design_context相对对象/字体实际指纹恢复；不恢复已消费调用额度 | T12 |
| AC-S11 | 超过三次归档 | 4次及更多原件均保留独立ID；无attempt3覆盖 | T13 |
| AC-S12 | 预算与进展 | 并行Host仅一个取得最后名额；begin/settle幂等；已发失败计消耗，未知占额暂停新外部调用，本地修正继续；取消/重试/restore不清零；明确仅约束产品协议调用 | T13 |
| AC-R01 | 实际成品检查 | 内容/隐藏项/XML/页集合按当前产物检查，工具共享解析但检查意义分开 | T11 |
| AC-R02 | 未评估不是高分 | 没有执行对应检查时not_evaluated，无4/5默认专业分 | T11 |
| AC-R03 | 读写判定一致 | 同一发现和处理，submit/load/UI/export一致；不存在两套if | T11 |
| AC-R04 | 像素差异分流 | 正常抗锯齿、故意删节点、真实字体/圆角丢失三类区分；不两票表决 | T11 |
| AC-R05 | 独立性诚实 | 同一Host两名称不能independence_confirmed；实际执行ref可追溯 | T11 |
| AC-R06 | 返修真完成 | 新Review replaces旧失败，固定finding_id，subjects新产物且有实际复查观察/证据；只改fixed/旧产物/过期证据拒绝；旧记录不改 | T11 |
| AC-R07 | 真实泄漏与业务词 | 正常缩略图/左屏保留，真正内部字段/客户敏感信息被识别 | T11 |
| AC-R08 | 品牌按任务 | 没有品牌库不阻断；已给VI要求实际进入设计和检查 | T06 |
| AC-R09 | 导出用途 | review可看失败稿且标明；delivery拒未解决实质问题，不假人类通过 | T15 |
| AC-R10 | 历史报告 | 依赖变化的旧pass显示历史/过期，不能覆盖当前fail | T11 |
| AC-U01 | 真实页数 | 无preview_manifest也显示Document真实页，不出现可交付+0页+初始化问卷 | T14 |
| AC-U02 | 当前版本统一 | CLI/UI/continue/export读同一revision与检查，修改后一起更新 | T14 |
| AC-U03 | 本地服务 | 自然语言主Skill首次正文接收后自动view --open；有效服务/URL复用；无浏览器返回真实本地地址，服务失败为null+原因；不让用户补命令 | T14 |
| AC-U04 | 四视图 | 原文/蓝图/SVG/PPT显示真实文件和版本，问题能跳转对象/区域 | T14 |
| AC-U05 | 无Host不假运行 | UI提交反馈后awaiting_host，实际start/accept才更新执行与成品 | T14 |
| AC-U06 | 写接口安全 | 同源token/路径白名单/XSS处理；只读浏览不要求团队账号 | T14 |
| AC-U07 | 可用布局 | 1280/1440下导航、比较、反馈可用，键盘可操作，状态不只颜色 | T14 |
| AC-I01 | 包依赖边界 | 新src不import旧命名空间；compiler不反向依赖业务审批 | T16 |
| AC-I02 | 实际doctor | 解释器、模块路径、字体、renderer按步报；不把安装就绪当内容专业 | T16 |
| AC-I03 | 安装回滚 | release先测后原子激活；失败保留current，回滚不让旧代码写未知新格式 | T16 |
| AC-I04 | 唯一入口 | 根Skill/CLI/API/doc/installer指同一路；旧命令明确映射或退役 | T17 |
| AC-I05 | 无外部绑定 | 隔离HOME无PPTMaster/Library配置和缓存仍完整运行 | T20 |
| AC-I06 | 资源完整 | wheel与sdist/pip install路径包含方法/schema/static；不借checkout补文件 | T20 |
| AC-I07 | Skill不误删 | 只替换安装器拥有且未改的旧资源；同名第三方Skill不动 | T16 |
| AC-I08 | 许可证与资料 | source归属保留；release不包含客户run/密钥/外带字体/历史敏感资料 | T19 |
| AC-L01 | 已知旧格式 | v1/HD/PPT/SVG来源可读导入新副本；未知字段明确需要规范化 | T18 |
| AC-L02 | 原run不写 | import前后原文件hash一致，不执行旧.py/.sh，不就地初始化 | T18 |
| AC-L03 | 旧pass不继承 | 原completed/reviewer字符串不变新专业通过，明确legacy未验证 | T18 |
| AC-L04 | 移动与缺源 | 缺原文original_sha256=null/缺省可导入；全零假hash拒绝；extract/媒体真实hash保留可看；未知原hash补文件不追认为旧原文 | T18 |
| AC-L05 | 退役引用 | 旧文件/命令/Skill/合同不在新发行或默认调用，真实引用检查无残留 | T24 |
| AC-L06 | 旧测试取舍 | 可靠性/转换断言有新对应；删除错误门禁断言不靠skip装绿 | T24 |
| AC-V01 | D1/D2公平对照 | 同源同模型条件，A/B/C开发结果分开，第一系统完整稿留存 | T21 |
| AC-V02 | P1提前迁移 | 主链刚可用就运行陌生业务材料，用于改方法后归开发 | T10 |
| AC-V03 | H1/H2未见 | 冻结后A/C，归因争议补B；改方法后样例归回归，不叫泛化完成 | T22 |
| AC-V04 | 人类专业阅稿 | 适合经验的人类判断是否需要重建主线；模型一致不替代 | T23 |
| AC-V05 | 最终安装任务 | 用最终候选实际安装从资料出稿/工作台/修改/导出，不调用repo补丁 | T25 |
| AC-V06 | 诚实交付 | 未验证/失败如实记录，不以对象/测试数量/默认分叫专业通过 | T25 |
| AC-L07 | 建立退役清单 | T01只冻结逐路径处置/引用基线与保留项；此时不要求AC-L05归零，后者由T24完成 | T01 |
| AC-K14 | 画布与设计权威 | 同一Document的4:3/指定物理尺寸、style_ref、字体和Logo被prompt/编译/UI一致采用；无隐藏16:9默认 | T10 |
| AC-K15 | 资产字体重定位 | 移动项目后Logo/icon从对象Ref读取；系统字体实际hash变化报告并重检，缺字体不阻旧媒体查看；不打包字体到发行 | T12 |
| AC-K16 | 编辑能力诚实 | 表格/图表输出声明editable_shapes_and_text；无原生chart数据模型时UI/API/导出不得声称编辑数据；旧文件未知 | T15 |
| AC-S13 | 只改有效样式 | 默认style改动仅影响依赖它的页；独立覆盖页与未用style/asset不重生；同asset_id换字节使相关页失效 | T12 |
| AC-V07 | 最早真实纵向切片 | T03全格式/T09全特性尚未完成也可T10.min真实制作+只读四视图+T12.min单页改；实际阅图必做，不能宣称全产品完成 | T10 |
| AC-S14 | 临时结果完整往返 | compose/blueprint/reconstruct/review/repair信封kind/files/refs一致；真实文件先存再原子采用；重复幂等、旧输入/路径逃逸拒绝 | T04 |

---

<a id="spec-14"></a>

## 14｜执行型AI任务说明、依赖与交付

### 14.1 立即可以执行与尚需授权

当前可以读代码、核对映射、将本包经审核落入文档目录。代码实现、分支创建/切换、安装激活、合并与发布按实际用户授权执行；文档请求不自动授权后几项。已有明确实施授权后，不反复询问普通内部取舍。

实施入口建议`docs/specs/deck-master-rebuild-v1/`完整保存本包（sources可保留引用或经允许复制，不发布客户资料）。它是本轮活动基线，旧SC-1及P2-P5只作历史。先核对差异，不以仓库后来少量变化推翻全部方案。

### 14.2 五包、完整完成依赖与最早切片

保留五包25任务及全部最终范围。`inventory/task-list.depends_on`表示**整项任务宣布完成前**需要完成的任务；新增文档列`start_after`表示可开始实现/试做的最小输入；`early_delivery`表示可先交付的局部能力。二者不能混为“未做完全部依赖就不能开始”或“先跑小样例就把整项标完成”。它们仅是施工表，不进入产品运行模型。

最早序列：T01清单与边界→T02.min基本对象/原子提交→T03.min已知TXT/JSON与完整Page接收＋T04.min正常Host交接→T05.min自动打开的只读四视图→T06/T07.min当前页完整prompt/真实原图及文案往返→T08/T09.min事故页所需受支持SVG子集→T10.min真实PPT与三方对照→T12.min一次单页修改且无关页不重生。

T13.min（同项目名额分配、begin、settle、未知保护）在T06首次真实外部调用前嵌入；不能以T13在WP03为由先无视已指定的限额。基础幂等、取消/晚到保护与原件保存同时具备；完整故障矩阵、所有材料格式和通用SVG缺陷随后补齐。不做名为min的新产品模式，不新增一套永久schema或任务注册。

D1/D2从原材料产生不同正文，与制作切片并行；已精修页面用于验证制作，不抵扣默认成稿。T10.min即使T11统一审阅尚未完成，也必须由Host/人类对照原图→SVG→PPT并记录实际问题；不能跳过阅图。P1在可运行链路首次具备时探路，H1/H2留到冻结后。

T10整体完成仍要求T03/T09完整范围（通过其depends_on链）；T12整体需完成统一审阅和并发恢复。T20显式依赖T13，T25工程交付祖先覆盖T01–T22及T24，另消费T23.04记录；专业和桌面验收由T23另行关闭。T01只完成AC-L07建立清单，AC-L05“退役引用归零”由T24在替代已验证后完成。

并行Agent按目标文件分工：store/models接口由一个负责人维护；编译器Agent不改质量结论；内容Agent不改门禁接受自己稿件；UI只调用service不写另一套状态。整合者执行跨模块测试，不只收集完成声明。75个目标是最终台账，不是首稿前先铺75个文件。

### 14.3 可直接交给Codex的总指令

> 请以本包00–14章、work-packages及inventory为本轮唯一活动基线。先核验B0/K0与本地实际HEAD、安装来源、未提交变更，记录映射差异；不要reset用户工作树、整体合并PR31或替换事故原件。取得实施授权后从WP01开始，在src/deck_master新包实施；常规取舍按本包已定设计执行。每次只交付指定T任务范围，保留源代码归属与正反例。不要把新文件存在、schema通过、fixture出PPT、多个模型一致或空finding当作业务验收。不得修改预期/放宽规则接受当前坏稿，也不得为实现本包新建阶段注册、身份审批、评分或知识平台。提交时提供真实改动清单、实际测试、待核验项与下一依赖。删除旧文件必须满足02/12章并在台账标明替代测试；绝不删除用户run、资料或第三方Skill。

### 14.4 单任务指令模板

```text
任务：Txx（从inventory/task-list取标题与范围）
先读：关联Spec与对应WP；B0/K0提取来源；关联验收ID。
允许修改：任务target_scope与明确依赖接口；其他变更先给具体理由，不能扩大成旧OS全量整改。
必须产出：实现、对应测试、必要文档/清单更新、实际执行记录。
必须保留：用户数据与旧产物；原图/原prompt；输入事实；必要事务/取消/晚到保护。
完成条件：关联AC真实满足；需要Host或人类而未运行的条目保持未验证。
禁止：改测试期待掩盖缺陷，绕源码借用，假独立审阅，默认4分，静默fixture，层层审批。
失败：按任务failure_return返回对应内容/投影/图形/状态/安装层，不加外围门禁。
```

### 14.5 PR切分与提交

建议五个逻辑PR对应五包，内部T任务可多次小提交；依赖未合并可明确stacked，但不能在说明中把未合并分支当主线。纯几何修复可单独可提取提交，便于验证/回退；不要把大段状态系统夹在几何修复中。

PR需要列：输入基线、实际新/改/删路径、对照到T/AC、运行命令与实际结果、没有运行的原因、UI/产物证据与旧兼容边界。最后复审看默认入口真实任务，不只审目录整洁。

### 14.6 方案变更规则

真正发现某接口不可实现时，在本包普通deviation记录中写事实、影响、最小替代与需重验AC；不建设变更审批系统。不得默默回退到“旧profile还能用”，也不得把暂不支持特性改成默认忽略。

如果反例证明某Spec设计本身有误，可修改Spec并用正常/坏/合理差异样例说明，不只为了当前失败结果改验收。模型/工具版本变化分开记录，不能把由换更强模型带来的收益全部记为架构成果。

### 14.7 本包交付与软件交付不同

本包给出了完整开发输入，但没有完成任何项目代码改动。文档schema/链接校验属于文档检查；不会被写入Deck Master测试成绩或专业可用证明。实现/真实运行/安装状态均需要Codex核验。

### 14.8 开工前必须引用的三个往返例

T03/T07先读atom-identity：ID稳定与旧Pointer一次归一化；T04/T06/T12先读result-envelope：五种kind、实际文件Ref、拒绝与幂等响应；T11先读review-fixed：旧失败、新产物、实际复查、新Review的replaces链。见examples/roundtrips/README.md。这些用于消除接口歧义，不增加永久对象；实现若需调整，同步对应文档/例/测试，不由不同模块各作解释。

---

<a id="v11-changes"></a>

## v1.1定向修订说明与Codex复核入口

日期：2026-09-16。依据：[用户转交的Codex v1.0审查](sources/codex-v1.0-review.md)。本次修订不重新研究或重写总体方案；没有访问本地产品仓库、修改产品、删除、安装、创建分支或实施新API。

### 裁决

R1–R6全部接受；对应补充集中到现有五对象、15章、25任务与75项拟建目标。没有新增永久对象、注册/预算平台或原生chart实现。规范与合同名称仍为预实施版本，包版本v1.1取代v1.0作为建议活动基线。

| 审查项 | v1.1明确动作 | 主要落点 | 验收/例 |
| --- | --- | --- | --- |
| R1 来源未知 | original_sha256可null/省略；已保存extract/媒体hash仍真实必填；全零拒绝；未知不能追认补来的候选原件 | 03.2/03.11、12.2–12.3、document schema | AC-L04；missing-source |
| R2 制作输入 | Document.design_context为唯一版本化画布/语言/字体/样式/资产；Page只能明确覆盖；asset角色保存字节；style_ref指ID；临时相对路径只在接收时解析 | 03.3a、05.1、06.1/06.4、08.8；Document/Page/Artifact | AC-K14/K15、AC-S13、AC-B01；design-context |
| R3 依赖/额度 | T20依赖T13，T25工程交付祖先覆盖T01–T22及T24，消费T23.04待验记录；T01用L07建立清单，T24完成L05引用归零；项目事务分配allowance与begin/settle | 08.6、09.2、14.2；Task与task-list | AC-L07、AC-S11/S12；call-allowance |
| R4 UI首次可见 | 主Skill首次正文页被接收就自动view --open；同项目复用；无浏览器与服务失败分别如实；不是等PPT全部完成 | 09.5、10.4/10.6、11.7、Host例 | AC-U03、T05/T14/T20 |
| R5 编辑边界 | 首版为可编辑形状与文字；不承诺Office Chart编辑数据/原生Table行列；PPT Artifact与UI/导出声明 | 00.5、06.7、07.7、10.2；Artifact | AC-K16、AC-K12 |
| R6 最早切片 | start_after/early_delivery允许先试做，depends_on仍为整项完成条件；T10.min真实三方对照与T12.min单页改先行，最终范围不缩水 | 01.8、06.8、14.2；任务/工作包/清单同步 | AC-V07；T10/T12 |
| 分支 | codex/rebuild-mainline-v1，仍未创建 | 01.1 | 仅方案命名 |
| 往返合同 | 稳定atom ID、fixed真实复查replaces链、唯一kind结果信封完整正反例 | 03.10、07.9、09.7、14.8 | AC-C03、AC-R06、AC-S14；roundtrips |

### 本轮额外收紧但不扩项

- 内容版本恢复不回滚已消耗/未知调用或取消事实，防止restore重新获得额度。
- 先实现T13.min再真实外部调用，避免把“提前试做”误解为先忽略用户限额。
- style默认在create时固化；中间模块不各取默认。单PPT物理页尺寸一致；Page样式覆盖不能改变整稿物理尺寸或扩大资产外发权限。
- 字体选择与实际字体文件指纹区分；Spec/公开发行不附字体二进制。
- Review示例和静态信封通过只证明文档格式/引用，未声称实际Host审阅或编译成功。

### 原范围与数量

仍为15章、5工作包、25任务、5类永久schema、177旧scripts、58旧contracts、122旧顶层tests、75项拟建目标。验收矩阵从83条增为90条，新增项用于上述定点缺口，不对应90份Deck。全部产品验收仍planned_not_executed。

### 使用方式

完整v1.1 ZIP替换活动Spec包；原v1.0留作历史，不混用旧合并手册/任务表。先读本文件与START_HERE_FOR_CODEX.md；复核优先看五Schema、08.6、14.2、任务图及roundtrips。

PACK_VALIDATION.json记录本次真正执行的文档检查及边界。它不代表产品测试、安装、字体匹配、自动UI、并发调用限额或专业可用已验证；这些需要Codex在实施后核验。

---

<a id="work-packages"></a>

## 五个工作包与具体任务

### WP01｜新核心、材料与默认成稿

状态：待实施；v1.1合同与施工修订，不是代码已完成。

#### 输入与依赖

先读对应Spec与CHANGELOG-v1.1.md。完整完成依赖与允许开始条件分别列出；T13.min先于真实外部调用，T05.min在首份正文时自动打开工作台，T10.min不等待所有格式和一般化绘制修复。原图实际对照和基础数据安全不可省略。B0/K0现状与运行结果需要Codex核验。

#### T01｜冻结现场与逐文件处置

**完整完成依赖：**—。

**允许开始条件：**—。

**可先交付：**固定来源/清单，当前旧代码和用户资料不删。

**实际文件范围：**`inventory/*;AGENTS.md;docs/planning更正`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**读取B0/K0、本地安装和未提交变更；生成全Git路径处置表；记录事故完成叙述更正；建立新包反向import禁区；仅建立处置清单/引用基线，不要求此时旧引用归零。

**完成判据：**AC-L07。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**本地不可解析基线则只修映射，不reset工作树、不整包合并K0。

#### T02｜五对象与最小原子存储

**完整完成依赖：**T01。

**允许开始条件：**T01边界/目标身份确定。

**可先交付：**T02.min：五对象最小合法子集、不可变blob与原子指针、基础幂等/取消保护。

**实际文件范围：**`models.py;store.py;resources/contracts/*`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**实现五schema/跨引用和不可变对象、current原子提交、基本恢复；增加Document.change幂等记录，不上数据库平台；明确design_context与nullable原始来源hash、asset Ref；基础call_allowance事务字段一起落地。

**完成判据：**AC-S01,AC-S02。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**对象格式/事务未成立先修，不接真实生图或UI写入。

#### T03｜完整材料与Page接收

**完整完成依赖：**T02。

**允许开始条件：**T02.min。

**可先交付：**T03.min：TXT/JSON/完整Page，design_context规范化；其余资料格式随后。

**实际文件范围：**`sources.py;content.py`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**支持来源表、原文/图表定位、v2可见原子、计算/设计关系；整稿预校验，未知字段明确返回；先TXT/JSON与已知Page垂直切片，随后补其余格式；稳定atom与旧Pointer规范化；未知原hash不拦媒体读取。

**完成判据：**AC-C01,AC-C03,AC-C08,AC-C11。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**丢字段回内容映射，缺格式工具明确待处理，不空成功。

#### T04｜宿主默认成稿和主入口

**完整完成依赖：**T03。

**允许开始条件：**T02.min,T03.min。

**可先交付：**T04.min：create/accept/continue及D1/D2正常Host输入，信封与稳定ID。

**实际文件范围：**`tasks.py;service.py;cli.py;skills/deck-master/*`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**实现create/continue/task accept骨架；D1/D2成对方法写进实际Host输入；不再调用规则Planner和循环claim；固定临时结果信封与往返；首次正文后主Skill自动view --open；不需用户额外执行。

**完成判据：**AC-C02,AC-C04,AC-C06,AC-C07,AC-S14。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**正文无机制回方法，不以schema加字段求专业。

#### T05｜最小真实视图与隔离包

**完整完成依赖：**T02,T04。

**允许开始条件：**T02.min,T04.min。

**可先交付：**T05.min：只读四视图/实际页集合/自动view；资源隔离检查随后补全。

**实际文件范围：**`view.py;web.py只读部分;pyproject.toml;setup.py;tools/build_hook.py;MANIFEST.in`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**最小页面列表/正文/文件链接直接读Document；隔离安装验证方法/schema资源，尚不激活用户当前版本；先同项目服务复用/实际URL/四视图槽位及失败稿可看，随后隔离资源验证。

**完成判据：**AC-U01,AC-I01,AC-I06。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**依赖旧preview则修view；源码偷读资源则修打包。

#### 工作包收口

完成关联任务及其范围，不以文件存在或schema通过替代实际结果。不得为已给用户的坏稿改预期、换上游蓝图或伪独立审阅。未执行仍标未验证。T25工程交付的整卡祖先覆盖T01–T22及T24，尤其T13；另消费T23.04分层记录，T23未验AC不因此关闭；T01只建立清单，最终退役引用归零在T24。

### WP02｜蓝图、SVG与原生制作

状态：待实施；v1.1合同与施工修订，不是代码已完成。

#### 输入与依赖

先读对应Spec与CHANGELOG-v1.1.md。完整完成依赖与允许开始条件分别列出；T13.min先于真实外部调用，T05.min在首份正文时自动打开工作台，T10.min不等待所有格式和一般化绘制修复。原图实际对照和基础数据安全不可省略。B0/K0现状与运行结果需要Codex核验。

#### T06｜完整prompt与真实工具任务

**完整完成依赖：**T03,T04。

**允许开始条件：**T03.min,T04.min,T13.min。

**可先交付：**T06.min：当前事故页完整prompt与允许资产真实调用。

**实际文件范围：**`production.py;references/blueprint-svg.md`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**全字段投影；Host真实图像输入/输出；缺工具待执行，不降级；实际prompt来源如实；使用Document解析的画布/字体/style_ref/允许资产；首次真实调用前接T13.min额度。

**完成判据：**AC-B01,AC-B02,AC-B09,AC-R08。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**投影漏项直接修投影，不让后续SVG补假内容。

#### T07｜原图保持与文案往返

**完整完成依赖：**T06,T02。

**允许开始条件：**T06.min,T02.min。

**可先交付：**T07.min：真实原图、最终正文与独立期待。

**实际文件范围：**`production.py;content.py;review.py输入部分`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**记录实际原图区域期待，编辑生成文案为新Page；保留原生成版；禁止已知下游回灌；结构边不重复印字。

**完成判据：**AC-B03,AC-B05,AC-B08,AC-B10。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**内容不成立回T04；原图结构不足重新设计，不能更换验收答案。

#### T08｜纯SVG接口与派生IR

**完整完成依赖：**T01,T02。

**允许开始条件：**T01边界,T02.min。

**可先交付：**T08.min：独立SVG接口与当前事故页实际子集。

**实际文件范围：**`compiler/api.py;compiler/ir.py;compiler/svg.py`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**对比B0/K0提取SVG解析，建立受控子集和纯接口；Host单写SVG；禁止反向import旧engine；首版形状文字可编辑，图表/表格非Office原生数据对象；不要求Host补chart数据接口。

**完成判据：**AC-K09,AC-B06。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**抽取牵出旧状态则切依赖，不整目录搬入。

#### T09｜绘制缺陷逐项修复

**完整完成依赖：**T08。

**允许开始条件：**T08.min。

**可先交付：**T09.min：当前事故页涉及的绘制缺陷先修；不简化原图绕过。

**实际文件范围：**`compiler/geometry.py;paint.py;text.py;drawingml.py`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**修端点/圆边界/800900字重/0透明度/多行与圆角；保留实际PPT XML反例。

**完成判据：**AC-K02,AC-K03,AC-K04,AC-K05,AC-K06,AC-K07。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**内核失败修对应函数，不把源图简化绕过。

#### T10｜真实渲染与首段完整闭环

**完整完成依赖：**T05,T07,T09。

**允许开始条件：**T05.min,T07.min,T08.min,T09.min。

**可先交付：**T10.min：真实PPT、原图/SVG/PPT实际阅图，四视图可见。

**实际文件范围：**`compiler/render.py;readback.py;production.py`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**事故型三页在小UI完整显示，使用真实原图/重构/渲染；同时尽早运行P1，内容与制作证据分开；先在事故页实际子集完成min三方对照，不等所有材料格式/绘制修复；整体完成再覆盖声明子集。

**完成判据：**AC-K01,AC-K08,AC-K10,AC-K11,AC-K13,AC-B04,AC-V02,AC-K14,AC-V07。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**分段找第一丢失点；不先增加平台和评分；P1改方法后归开发。

#### 工作包收口

完成关联任务及其范围，不以文件存在或schema通过替代实际结果。不得为已给用户的坏稿改预期、换上游蓝图或伪独立审阅。未执行仍标未验证。T25工程交付的整卡祖先覆盖T01–T22及T24，尤其T13；另消费T23.04分层记录，T23未验AC不因此关闭；T01只建立清单，最终退役引用归零在T24。

### WP03｜审阅、修改与工作台

状态：待实施；v1.1合同与施工修订，不是代码已完成。

#### 输入与依赖

先读对应Spec与CHANGELOG-v1.1.md。完整完成依赖与允许开始条件分别列出；T13.min先于真实外部调用，T05.min在首份正文时自动打开工作台，T10.min不等待所有格式和一般化绘制修复。原图实际对照和基础数据安全不可省略。B0/K0现状与运行结果需要Codex核验。

#### T11｜统一审阅解释与真返修

**完整完成依赖：**T07,T10。

**允许开始条件：**T07.min,T10.min。

**可先交付：**统一审阅实现；此前T10实际阅图不得省略。

**实际文件范围：**`review.py;references/review-and-repair.md`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**工具/Host/人类证据分级；写读export统一；空集合未知；具体像素差异复核；修复必须指新产物；fixed必须replaces旧Review、指向新产物及实际复查观察，旧失败保留；提供完整往返负例。

**完成判据：**AC-R01,AC-R02,AC-R03,AC-R04,AC-R05,AC-R06,AC-R07,AC-R10,AC-C05,AC-B07。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**误报修规则与三类样例，不只调当前失败到绿。

#### T12｜局部修改与并发恢复

**完整完成依赖：**T02,T10,T11。

**允许开始条件：**T02.min,T10.min。

**可先交付：**T12.min：一次单页修改、旧原件保留/无关页不重生；先实际阅图再补统一自动关联。

**实际文件范围：**`store.py;tasks.py;service.py;production.py`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**读集重基、稳定页ID/增删重排、跨页事实、取消竞态、晚到保护、恢复与重定位；先单页编辑/无关页不重生，再补全并发与恢复；恢复内容不重置调用记录；样式/资产按实际依赖失效。

**完成判据：**AC-S03,AC-S04,AC-S05,AC-S06,AC-S07,AC-S08,AC-S09,AC-S10,AC-K15,AC-S13。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**发现无关重生则修依赖；不清整目录或删除旧产物。

#### T13｜重试历史与真实成本

**完整完成依赖：**T12。

**允许开始条件：**T02.min,T04.min。

**可先交付：**T13.min：首次外部调用前的项目额度事务/begin/settle；随后全并发未知恢复测试。

**实际文件范围：**`tasks.py;service.py`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**外部调用限额与本地修复分开；无进展停止；归档不封顶、不重置历史；项目锁下分配call_allowances；begin/settle幂等，未知保留并暂停新外部调用，本地修复继续；min提前接入。

**完成判据：**AC-S11,AC-S12。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**不通过新增user授权历史平台解决本地格式错误。

#### T14｜完整四视图工作台

**完整完成依赖：**T05,T11,T12。

**允许开始条件：**T05,T11,T12。

**可先交付：**按整项任务依赖执行。

**实际文件范围：**`web.py;view.py;resources/static/*`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**真实页/蓝图/SVG/PPT、反馈、正文更新、取消、冲突；无Host时明确等待；loopback必要安全；自然语言入口无需手动view；同项目URL复用、无浏览器/服务失败真实返回；显示编辑能力范围。

**完成判据：**AC-U01,AC-U02,AC-U03,AC-U04,AC-U05,AC-U06,AC-U07。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**UI实际数据缺失先修service，不能用演示假卡片。

#### T15｜导出与状态汇报收口

**完整完成依赖：**T11,T12,T14。

**允许开始条件：**T11,T12,T14。

**可先交付：**按整项任务依赖执行。

**实际文件范围：**`export.py;view.py;cli.py`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**review/delivery分开；实际当前文件/检查一致；失败稿能查看；Host完成表述遵从真实状态；PPT交付注明editable_shapes_and_text，不能暗示原生图表编辑数据。

**完成判据：**AC-R09,AC-V06,AC-K16。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**不得通过裸completed或旧approval强行放行。

#### 工作包收口

完成关联任务及其范围，不以文件存在或schema通过替代实际结果。不得为已给用户的坏稿改预期、换上游蓝图或伪独立审阅。未执行仍标未验证。T25工程交付的整卡祖先覆盖T01–T22及T24，尤其T13；另消费T23.04分层记录，T23未验AC不因此关闭；T01只建立清单，最终退役引用归零在T24。

### WP04｜安装独立与兼容切换准备

状态：待实施；v1.1合同与施工修订，不是代码已完成。

#### 输入与依赖

先读对应Spec与CHANGELOG-v1.1.md。完整完成依赖与允许开始条件分别列出；T13.min先于真实外部调用，T05.min在首份正文时自动打开工作台，T10.min不等待所有格式和一般化绘制修复。原图实际对照和基础数据安全不可省略。B0/K0现状与运行结果需要Codex核验。

#### T16｜安装器与诊断提取

**完整完成依赖：**T05,T10。

**允许开始条件：**T05,T10。

**可先交付：**按整项任务依赖执行。

**实际文件范围：**`install.py;doctor.py;tools/build_release.py`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**隔离release/固定解释器/原子激活回滚；资源完整、按步骤报告依赖；旧Skillownership清理。

**完成判据：**AC-I01,AC-I02,AC-I03,AC-I07。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**安装失败不改current；不借源码目录补文件。

#### T17｜唯一默认入口与文档

**完整完成依赖：**T15,T16。

**允许开始条件：**T15,T16。

**可先交付：**按整项任务依赖执行。

**实际文件范围：**`cli.py;root-and-config.csv;单Skill与methods`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**新旧命令明确映射/退役，manifest/README/installer/UI共同解除PPTMaster与Library前置。

**完成判据：**AC-I04,AC-C06。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**不能保留永久v2开关把旧默认留在原处。

#### T18｜旧run只读导入

**完整完成依赖：**T03,T12。

**允许开始条件：**T03,T12。

**可先交付：**按整项任务依赖执行。

**实际文件范围：**`legacy.py;tests/rebuild/test_legacy.py`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**已知v1/HD只读规范化，源不写，旧媒体可看，未知状态不继承pass；缺原文original_sha256可空；保留extract/媒体实hash；字体/Logo入design_context，原件不动。

**完成判据：**AC-L01,AC-L02,AC-L03,AC-L04。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**不能就地迁移/执行旧脚本；有歧义返回具体字段规范化。

#### T19｜发布资源与许可证清理

**完整完成依赖：**T01,T16。

**允许开始条件：**T01,T16。

**可先交付：**按整项任务依赖执行。

**实际文件范围：**`LICENSE;NOTICE;THIRD_PARTY_NOTICES.md;.gitignore;build hook`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**跨分支归属、依赖/资源清单、排除客户材料/秘密/字体误打包。

**完成判据：**AC-I08。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**许可或材料授权不明先不随包，不伪称开源可用。

#### T20｜候选隔离安装端到端

**完整完成依赖：**T14,T15,T16,T17,T18,T19,T13。

**允许开始条件：**T14,T15,T16,T17,T18,T19,T13。

**可先交付：**按整项任务依赖执行。

**实际文件范围：**`CI/install smoke及实际候选环境`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**无库/外部后端/源码访问的安装，从材料任务到真产物UI改稿；记精确模块来源；从自然语言主Skill观察自动工作台；指定字体/Logo/非16:9/移动项目；调用限额与未知结算进入验收。

**完成判据：**AC-I05,AC-I06。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**不能用fixture/旧安装/源码运行顶替；修具体依赖/资源。

#### 工作包收口

完成关联任务及其范围，不以文件存在或schema通过替代实际结果。不得为已给用户的坏稿改预期、换上游蓝图或伪独立审阅。未执行仍标未验证。T25工程交付的整卡祖先覆盖T01–T22及T24，尤其T13；另消费T23.04分层记录，T23未验AC不因此关闭；T01只建立清单，最终退役引用归零在T24。

### WP05｜业务验证、退役与默认切换

状态：待实施；v1.1合同与施工修订，不是代码已完成。

#### 输入与依赖

先读对应Spec与CHANGELOG-v1.1.md。完整完成依赖与允许开始条件分别列出；T13.min先于真实外部调用，T05.min在首份正文时自动打开工作台，T10.min不等待所有格式和一般化绘制修复。原图实际对照和基础数据安全不可省略。B0/K0现状与运行结果需要Codex核验。

#### T21｜冻结D1/D2对照

**完整完成依赖：**T10,T15,T20。

**允许开始条件：**T10,T15,T20。

**可先交付：**按整项任务依赖执行。

**实际文件范围：**`验证记录与内容样本`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**冻结同模型输入设置；A/B/C保留第一完整稿，开发增量与精修范例分开。

**完成判据：**AC-V01,AC-C09,AC-C10。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**正文需重建则回T04，之后重新冻结；不挑最佳。

#### T22｜H1/H2迁移验证

**完整完成依赖：**T21。

**允许开始条件：**T21。

**可先交付：**按整项任务依赖执行。

**实际文件范围：**`验证记录与未见材料`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**冻结后A/C，归因不明补B；用后修改即变回归，必要时新材料或收窄承诺。

**完成判据：**AC-V03。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**不称三样例成功=稳定泛化；失败如实记录。

#### T23｜专业阅稿与实际编辑

**完整完成依赖：**T20,T21。

**允许开始条件：**T20,T21。

**可先交付：**按整项任务依赖执行。

**实际文件范围：**`当前成品与人类/桌面观察`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**合格人类检查主线/机制/可用；目标桌面软件编辑文字与关系保存重开；目标应用修改表格/图表形状文字，保存重开；明确未承诺Office编辑数据。

**完成判据：**AC-V04,AC-K12。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**无人审则工程试行；headless不顶替桌面，不暂停全部改进。

#### T24｜旧源/测试/合同退役

**完整完成依赖：**T17,T18,T20。

**允许开始条件：**T17,T18,T20。

**可先交付：**按整项任务依赖执行。

**实际文件范围：**`inventory全部处置；docs/archive`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**逐文件删除前完成行为移植/引用归零；历史文档更正；可靠性测试不skip；负责AC-L05最终引用归零，与T01清单建档分离。

**完成判据：**AC-L05,AC-L06。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**未知消费者先核实/移植；不删用户目录、外部Skill或原证据。

#### T25｜最终默认切换与交付说明

**完整完成依赖：**T22,T24。

**允许开始条件：**T22,T24。

**可先交付：**按整项任务依赖执行。

**实际文件范围：**`最终候选安装及实际运行记录`。未写完整路径的模块均指src/deck_master，方法指skills/deck-master/references；不增加75项目标之外的新平台。

**必须实施：**在明确发布/安装授权后切换唯一入口；正常出稿改稿导出复跑；列未验证边界。

**完成判据：**AC-V05,AC-V06。以acceptance-matrix中的预期行为为准；先做部分切片时列清未完成项。

**产物：**实际实现/测试/必要文档、真实命令结果和未验证项。Host/人类/工程证据分别报告。

**失败去向：**失败保留旧安装/用户数据，撤回候选激活；不回填历史通过。

#### 工作包收口

完成关联任务及其范围，不以文件存在或schema通过替代实际结果。不得为已给用户的坏稿改预期、换上游蓝图或伪独立审阅。未执行仍标未验证。T25工程交付的整卡祖先覆盖T01–T22及T24，尤其T13；另消费T23.04分层记录，T23未验AC不因此关闭；T01只建立清单，最终退役引用归零在T24。

---

<a id="file-list"></a>

## 文件级实施清单 v1.1

全部为拟实施动作，非完成记录。177个旧scripts/75项拟建目标的总体范围不变；本次仅更新相关实施内容。新核心35个文件与其他附属目标不是首个成品前必须铺齐的门槛。

### 全部拟建目标

| 目标 | 动作 | 实施内容 | 工作包 | 拟测试 |
| --- | --- | --- | --- | --- |
| src/deck_master/__init__.py | NEW | 只公开版本与包资源位置；不得导入旧engine | WP01 | tests/rebuild/test_package_boundary.py |
| src/deck_master/__main__.py | NEW | 调用cli.main；不含业务流程 | WP01 | tests/rebuild/test_cli.py |
| src/deck_master/models.py | NEW | validate_document/page/artifact/task/review；只格式/身份不专业评分；v1.1：Document.design_context、未知原hash、asset与Task.call_allowances格式/跨引用 | WP01 | tests/rebuild/test_contracts.py |
| src/deck_master/store.py | EXTRACT_REWRITE | put_blob/read_current/commit_change/restore；不可变对象、读集冲突、取消同锁 | WP01 | tests/rebuild/test_store_transactions.py |
| src/deck_master/sources.py | EXTRACT_REWRITE | register_sources/read_source/locate；全文可达、页/段定位、敏感外发边界；v1.1：缺原文保留未知，extract/asset独立真实hash，项目相对资产 | WP01 | tests/rebuild/test_sources.py |
| src/deck_master/content.py | EXTRACT_REWRITE | normalize_draft/visible_atoms/content_diff；保留必要叶子；不规则配论点；v1.1：稳定atom/旧Pointer规范化；共享设计解析与Page明确覆盖 | WP01 | tests/rebuild/test_content.py |
| src/deck_master/tasks.py | NEW | issue/claim/accept/cancel/retry；按输入依赖稳定身份，支持幂等晚到拒绝；v1.1：项目额度分配/begin/settle与结果信封，未知/取消/恢复不清零 | WP01 | tests/rebuild/test_tasks.py |
| src/deck_master/service.py | NEW | create/continue/edit/check/export；所有CLI/UI共用，不注册阶段平台；v1.1：设计与资产接收、首次正文触发工作台动作、共享有效配置 | WP01 | tests/rebuild/test_service_flow.py |
| src/deck_master/cli.py | REPLACE | 薄参数解析+service调用+标准JSON；兼容命令不能偷走旧链 | WP01 | tests/rebuild/test_cli.py |
| src/deck_master/production.py | EXTRACT_REWRITE | project_prompt/adopt_blueprint/accept_svg/build；正文往返、原图独立、分步失败；v1.1：Document唯一画布/字体/style_ref与允许资产输入，无原生数据图表声明 | WP02 | tests/rebuild/test_production.py |
| src/deck_master/review.py | EXTRACT_REWRITE | measure/evaluate/accept_review/freshness；唯一定义检查结论；v1.1：fixed经新产物真实复查及replaces链，负例明确 | WP03 | tests/rebuild/test_review.py |
| src/deck_master/view.py | NEW | project_view/page_view；只派生，不持久化另一ready | WP01 | tests/rebuild/test_view.py |
| src/deck_master/web.py | REPLACE | serve/open；GET实际产物、POST修改请求；复用service，不含模型服务；v1.1：自动首次启动、服务复用、无浏览器/不可达原因 | WP03 | tests/rebuild/test_web.py |
| src/deck_master/export.py | EXTRACT_REWRITE | export_review/export_delivery；不发邮件，未通过稿可明确标识查看；v1.1：明确形状文字编辑范围和未验证状态 | WP03 | tests/rebuild/test_export.py |
| src/deck_master/legacy.py | EXTRACT_REWRITE | inspect/import_copy；不执行旧脚本、不继承旧pass，原run零写入；v1.1：缺源hash空，旧设计/素材规范化不追认原身份 | WP04 | tests/rebuild/test_legacy.py |
| src/deck_master/doctor.py | EXTRACT_REWRITE | inspect_install/check_step；报告版本/模块/字体/渲染器，不判业务专业 | WP04 | tests/rebuild/test_install.py |
| src/deck_master/install.py | EXTRACT_REWRITE | build_release/install/rollback；固定解释器、资源齐备、旧Skill受控移除 | WP04 | tests/rebuild/test_install.py |
| src/deck_master/compiler/__init__.py | NEW | 不导入service/review/store/Host模型 | WP02 | tests/rebuild/test_package_boundary.py |
| src/deck_master/compiler/api.py | EXTRACT_REWRITE | compile_deck(SvgInput[],CompileOptions,output_dir)->CompileResult | WP02 | tests/rebuild/test_compiler_api.py |
| src/deck_master/compiler/ir.py | EXTRACT_REWRITE | 内部SVG标准化节点/样式/几何；Host不手写 | WP02 | tests/rebuild/test_svg_parser.py |
| src/deck_master/compiler/svg.py | EXTRACT_REWRITE | parse_svg/validate_subset；本地解析，禁外链与脚本，明确不支持 | WP02 | tests/rebuild/test_svg_parser.py |
| src/deck_master/compiler/geometry.py | EXTRACT_REWRITE | affine/bounds/path/connector；修旋转圆/负斜率/圆角/描边 | WP02 | tests/rebuild/test_geometry.py |
| src/deck_master/compiler/paint.py | EXTRACT_REWRITE | fill/stroke/gradient；0与缺值区分 | WP02 | tests/rebuild/test_paint.py |
| src/deck_master/compiler/text.py | EXTRACT_REWRITE | 字体/字重/基线/换行/行距；不可隐形或缩字过检 | WP02 | tests/rebuild/test_text.py |
| src/deck_master/compiler/drawingml.py | EXTRACT_REWRITE | native text/shape/path/connector/image；不改正文与业务边 | WP02 | tests/rebuild/test_drawingml.py |
| src/deck_master/compiler/render.py | EXTRACT_REWRITE | SVG和PPT独立渲染，隔离输出；返回工具版本和实际页图 | WP02 | tests/rebuild/test_render.py |
| src/deck_master/compiler/readback.py | EXTRACT_REWRITE | XML/文本/端点/画笔/字体检查；不得以生成trace作唯一预期 | WP02 | tests/rebuild/test_readback.py |
| src/deck_master/resources/static/index.html | EXTRACT_REWRITE | 三栏实际页面；去掉商机/团队/Skill阶段面板 | WP03 | tests/rebuild/test_workbench_e2e.py |
| src/deck_master/resources/static/app.js | EXTRACT_REWRITE | 版本化API与四视图比较、反馈、改稿、取消和冲突 | WP03 | tests/rebuild/test_workbench_e2e.py |
| src/deck_master/resources/static/style.css | EXTRACT_REWRITE | 复用可用样式，保证1280/1440宽度和文字可读 | WP03 | tests/rebuild/test_workbench_e2e.py |
| src/deck_master/resources/contracts/document.v1.schema.json | NEW | 从本包contracts落地为唯一安装资源，不复制58份旧合同 | WP01 | tests/rebuild/test_contracts.py |
| src/deck_master/resources/contracts/page.v2.schema.json | NEW | 从本包contracts落地为唯一安装资源，不复制58份旧合同 | WP01 | tests/rebuild/test_contracts.py |
| src/deck_master/resources/contracts/artifact.v1.schema.json | NEW | 从本包contracts落地为唯一安装资源，不复制58份旧合同 | WP01 | tests/rebuild/test_contracts.py |
| src/deck_master/resources/contracts/task.v1.schema.json | NEW | 从本包contracts落地为唯一安装资源，不复制58份旧合同 | WP01 | tests/rebuild/test_contracts.py |
| src/deck_master/resources/contracts/review.v1.schema.json | NEW | 从本包contracts落地为唯一安装资源，不复制58份旧合同 | WP01 | tests/rebuild/test_contracts.py |
| setup.py | NEW | 仅注册本地build_py hook；不在安装时访问用户run/网络 | WP01 | tests/rebuild/test_install.py |
| MANIFEST.in | NEW | 纳入src、Skill、hook与许可证；排除运行资料/字体 | WP01 | tests/rebuild/test_install.py |
| tools/build_hook.py | NEW | 把skills/deck-master复制到build_lib资源；源仓不维护第二份 | WP01 | tests/rebuild/test_install.py |
| tools/build_release.py | NEW | 调用相同构建hook并核实wheel实际内容，生成最小release记录 | WP04 | tests/rebuild/test_install.py |
| skills/deck-master/references/source-reading.md | NEW | 提取文字/图表、尾部约束与引用；摘要只导航 | WP01 | tests/rebuild/test_content.py |
| skills/deck-master/references/blueprint-svg.md | NEW | 真实原图/正文往返/忠实SVG；不写第二Scene | WP02 | tests/rebuild/test_production.py |
| skills/deck-master/references/review-and-repair.md | NEW | 看实际成品，分内容/制作/转换，修到新产物 | WP03 | tests/rebuild/test_review.py |
| skills/deck-master/references/content-examples.md | NEW | 从本包examples/content-pair.md提炼；不是固定模板目录 | WP01 | tests/rebuild/test_content.py |
| tests/rebuild/test_cli.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_compiler_api.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_content.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_contracts.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_drawingml.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_export.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_geometry.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_install.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_legacy.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_package_boundary.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_paint.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_production.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_readback.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_render.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_review.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_service_flow.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_sources.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_store_transactions.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_svg_parser.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_tasks.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_text.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_view.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_web.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/test_workbench_e2e.py | NEW | 按AC逐行为实施，移植旧有效断言；当前仅拟建路径，不是已通过测试 | 跨WP | — |
| tests/rebuild/conftest.py | NEW | 合成project、独立HOME、工具缺失/故障注入fixture；不读客户目录 | WP01 | — |
| tests/rebuild/fixtures/content_pair/ | NEW | D1/D2公开合成或脱敏材料与任务；不得含H1/H2答案 | WP01 | — |
| tests/rebuild/fixtures/compiler/ | NEW | 线/圆/文字/画笔/表格原始SVG输入与独立数值期待 | WP02 | — |
| tests/rebuild/fixtures/legacy/ | NEW | 已知v1/HD合成旧run；原件不写/未知字段/旧pass反例 | WP04 | — |
| tests/rebuild/fixtures/review/ | NEW | 正常还原/故意删减/合理渲染差异；不用当前结果反造预期 | WP03 | — |
| docs/specs/deck-master-rebuild-v1/ | NEW | 本包落地目录；活动基线，历史规范不自动继承 | WP01 | — |
| docs/archive/pre-rebuild/README.md | NEW | 旧源版本/旧合同/文档历史索引及退出默认说明 | WP05 | — |
| docs/migration-to-rebuilt-core.md | NEW | 用户旧run读取、导入、安装回退的具体指引 | WP04 | — |

### 旧scripts逐文件处置

| id | source_ref | path | action | target | work_package | stop_new_use | delete_when | change_detail | acceptance | verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OLD-001 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-005 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/adapters/deck_pro_max_to_plan.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-006 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/adapters/ppt_library_to_plan.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-007 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/advisory/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-008 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/advisory/narrative.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-009 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/assets/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-010 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/assets/archetype_tagger.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-011 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/assets/canonical_id.py | EXTRACT_THEN_DELETE | src/deck_master/sources.py | WP01 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 可复用稳定来源/资产标识思想；禁止带回资产治理平台 | AC-C06 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-012 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/assets/feedback.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-013 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/assets/health.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-014 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/assets/ingest_library_results.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-015 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/assets/schema.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-016 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/assets/scoring.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-017 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/benchmark/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-018 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/benchmark/aggregate.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-019 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/benchmark/case.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-020 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/benchmark/checkpoints.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-021 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/benchmark/markdown.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-022 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/benchmark/report.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-023 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/benchmark/runner.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-024 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/benchmark/scoring.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-025 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/build/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-026 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/build/manifest.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-027 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/capabilities/ppt_deck_pro_max.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-028 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/connectors/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-029 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/connectors/import_contract.py | EXTRACT_THEN_DELETE | src/deck_master/sources.py | WP01 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 仅提取来源标识与传入资料接口；不引入连接器平台 | AC-C01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-030 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/context_intake/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-031 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/context_intake/context_pack.py | EXTRACT_THEN_DELETE | src/deck_master/legacy.py;src/deck_master/sources.py | WP04 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 读取旧上下文与来源映射；不导入旧生产判定 | AC-L01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-032 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/context_intake/local_sources.py | EXTRACT_THEN_DELETE | src/deck_master/sources.py | WP01 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 提取文件定位/散列/文本读取；删除截断摘要代替内容理解的用法 | AC-C01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-033 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/conversation/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-034 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/conversation/brief_compiler.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-035 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/conversation/session_builder.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-002 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/deck_master.py | REPLACE | src/deck_master/cli.py | WP04 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 保留原路径为一次版本兼容薄转发；只转发有明确等价的命令，其余明确退役，不运行旧OS | AC-I04 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-036 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/delivery/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-037 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/delivery/outcome.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-038 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/delivery/validate.py | EXTRACT_THEN_DELETE | src/deck_master/export.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 保留实际页集合/文件校验；导出分审阅稿与正式交付，不依赖旧preview | AC-R09 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-004 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/demo.sh | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-039 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/feedback/library_feedback.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-040 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/feedback/record_deal.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-041 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/generation/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-042 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/generation/dispatch.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-043 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/generation/handback.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-044 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/generation/session.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-045 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/generation/task_builder.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-046 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-047 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/blueprint.py | EXTRACT_THEN_DELETE | src/deck_master/production.py | WP02 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 重建生成输入与来源记录；保留实际原图，删除时间/文件名/签章代替真实来源 | AC-B02 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-048 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/blueprint_content_review.py | EXTRACT_THEN_DELETE | src/deck_master/production.py;src/deck_master/review.py | WP02 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 保留阅图/裁切工具；归档不封顶；真正编辑新增文案，不默认空finding通过 | AC-B03 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-049 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/capability.py | EXTRACT_THEN_DELETE | src/deck_master/doctor.py | WP04 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 按实际步骤报告依赖；不把装好工具叫专业ready | AC-I02 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-050 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/content.py | EXTRACT_THEN_DELETE | src/deck_master/content.py;src/deck_master/production.py | WP02 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 提取显式可见内容读取；设计/副标题/脚注/标签完整投影；旧MBB/词元证据/密度分退出 | AC-B01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-051 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/contracts.py | EXTRACT_THEN_DELETE | src/deck_master/models.py;src/deck_master/store.py | WP01 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 只提取路径安全与校验辅助；不导入58个旧合同及整个engine | AC-I01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-052 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/engine.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-053 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/icon_external_acceptance.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-054 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/integrity.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-055 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/main_review.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-056 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/migration.py | EXTRACT_THEN_DELETE | src/deck_master/legacy.py | WP04 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 识别旧格式，不在新核心运行旧MBB迁移审批 | AC-L01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-057 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/pptx.py | EXTRACT_THEN_DELETE | src/deck_master/compiler/drawingml.py;src/deck_master/compiler/text.py;src/deck_master/compiler/readback.py | WP02 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 拆出DrawingML、文字布局和实际读取；不带入审批与自证trace裁决 | AC-K01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-058 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/provider_result.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-059 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/provider_smoke.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-060 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/review_policy.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-061 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/scene.py | EXTRACT_THEN_DELETE | src/deck_master/compiler/ir.py;src/deck_master/content.py | WP02 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 仅提取必要映射；Scene改为派生IR，禁止要求Host双份手写 | AC-B06 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-062 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/self_review.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-063 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/style.py | EXTRACT_THEN_DELETE | src/deck_master/production.py | WP02 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 提取风格输入/配色读取；不强制八选一或用户批准仪式 | AC-B01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-064 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/svg.py | EXTRACT_THEN_DELETE | src/deck_master/compiler/svg.py;src/deck_master/compiler/text.py;src/deck_master/review.py | WP02 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 拆分SVG语法/文字布局检查与审阅；保留实际渲染工具，删除自动审阅通过写入 | AC-R03 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-065 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/svg_native.py | EXTRACT_THEN_DELETE | src/deck_master/compiler/svg.py;src/deck_master/compiler/geometry.py | WP02 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 跨B0/K0比较并提取解析/变换；修负斜率、圆边界、箭头与支持范围 | AC-K02 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-066 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/svg_paint.py | EXTRACT_THEN_DELETE | src/deck_master/compiler/paint.py | WP02 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 提取原生填充/描边/渐变；修0透明度与非等比变换处理 | AC-K05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-067 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/user_decision.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-068 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/visibility.py | EXTRACT_THEN_DELETE | src/deck_master/content.py;src/deck_master/review.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 保留明确内部字段与资料披露边界；不按普通词语全局否决 | AC-R07 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-069 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/high_density/visual.py | EXTRACT_THEN_DELETE | src/deck_master/review.py;src/deck_master/compiler/render.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 提取差异测量和局部图；删除空集合满覆盖/相关指标投票作为业务结论 | AC-R04 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-070 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/learning/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-071 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/learning/pack.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-072 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/metrics/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-073 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/metrics/run_metrics.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-074 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/narrative/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-075 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/narrative/claim_graph.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-076 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/narrative/judgment_builder.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-077 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/orchestrate/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-078 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/orchestrate/build_run.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-079 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/orchestrate/export_queue.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-080 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/orchestrate/preview_builder.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-003 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/page_roles.py | EXTRACT_THEN_DELETE | src/deck_master/content.py | WP01 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 保留语义角色可选标签；不据角色强制内容或最低密度 | AC-C02 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-081 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/planning/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-082 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/planning/brief_intake.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-083 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/planning/claim_map.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-084 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/planning/narrative_planner.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-085 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/planning/page_budget.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-086 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/planning/page_tasks.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-087 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/planning/sourcing_decider.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-088 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/preview/manifest.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-089 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/preview/run_workspace_screenshot_audit.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-090 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/preview/server.py | EXTRACT_THEN_DELETE | src/deck_master/web.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 仅提取本地服务与文件查看经验；新接口直接读DocumentView | AC-U03 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-093 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/preview/static/app.js | EXTRACT_THEN_DELETE | src/deck_master/resources/static/app.js | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 保留可用预览/导航交互，重写数据与动作；不混用旧API | AC-U02 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-094 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/preview/static/index.html | EXTRACT_THEN_DELETE | src/deck_master/resources/static/index.html | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 提取可用三栏外壳；移除SkillOS、商机、批准队列假设 | AC-U01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-095 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/preview/static/style.css | EXTRACT_THEN_DELETE | src/deck_master/resources/static/style.css | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 提取设计样式，不重做无关品牌装修 | AC-U01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-091 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/preview/workspace_api.py | EXTRACT_THEN_DELETE | src/deck_master/view.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 重新实现页清单与状态，不能复制零页/ready推断 | AC-U01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-092 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/preview/workspace_audit_scenarios.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-096 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/production/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-097 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/production/page_package.py | EXTRACT_THEN_DELETE | src/deck_master/content.py;src/deck_master/models.py | WP01 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 可见正文/内部说明分离、身份校验；替换为v2显式正文块，不复制浅层扁平化 | AC-C03 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-098 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-099 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/brand_gate.py | EXTRACT_THEN_DELETE | src/deck_master/review.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 将实际品牌规则作为输入；缺品牌库不阻断正常创作 | AC-R08 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-100 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/confidentiality_gate.py | EXTRACT_THEN_DELETE | src/deck_master/review.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 仅迁移用户声明的真实隐私限制与具体泄漏；不新增审批流程 | AC-R07 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-101 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/context_conflict_gate.py | EXTRACT_THEN_DELETE | src/deck_master/content.py;src/deck_master/review.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 只保留实质来源冲突提示，不把数量/风险标记等价于专业判断 | AC-C05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-102 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/customer_visible_safety.py | EXTRACT_THEN_DELETE | src/deck_master/review.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 明确泄漏定位保留；普通业务术语不再P0；只用实际成品 | AC-R07 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-103 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/draft_gate.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-104 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/draft_gate_v2.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-105 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/evidence_gate.py | EXTRACT_THEN_DELETE | src/deck_master/review.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 来源可达/引用精确及声明性质；移除只按存在即充分的结论 | AC-C05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-106 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/external_review.py | EXTRACT_THEN_DELETE | src/deck_master/review.py;src/deck_master/tasks.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 实际任务与观察可复用，按当前产物版本判断；不继承字符串独立性 | AC-R05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-107 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/gate_freshness.py | EXTRACT_THEN_DELETE | src/deck_master/review.py;src/deck_master/store.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 依赖新鲜度行为迁移到单一实现；不继承管理字段触发全部过期 | AC-S04 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-108 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/gate_policy.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-109 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/gate_runner.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-110 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/overrides.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-111 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/pptx_audit.py | EXTRACT_THEN_DELETE | src/deck_master/compiler/readback.py;src/deck_master/review.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 提取XML文字/隐藏内容/页集合读回；删除空内容计数式专业评分 | AC-R01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-112 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/quality/rubric.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-113 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/review/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-114 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/review/readiness.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-115 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/review/workbench.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-116 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-117 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/artifact_validator.py | EXTRACT_THEN_DELETE | src/deck_master/review.py;src/deck_master/compiler/readback.py | WP03 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 只保留实际文件/页数/可读取检查；不继承旧交付门禁结构 | AC-R01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-118 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/build.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-119 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/builder_backend.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-120 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/events.py | EXTRACT_THEN_DELETE | src/deck_master/tasks.py | WP01 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 只保留必要任务记录字段；事件不成为重放全部项目的另一权威 | AC-S03 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-121 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/final_approval.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-122 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/final_readiness.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-123 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/import_log.py | EXTRACT_THEN_DELETE | src/deck_master/legacy.py | WP04 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 导入来源、版本、未验证限制记录；不保留并行日志审批 | AC-L02 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-124 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/library_status.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-125 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/next_step.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-126 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/orchestration.py | EXTRACT_THEN_DELETE | src/deck_master/store.py;src/deck_master/content.py;src/deck_master/legacy.py | WP01 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 提取整稿接收/页增删重排/恢复行为；用写前验证和原子指针替换全目录备份 | AC-S01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-127 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/rc_gate.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-128 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/render.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-129 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/render_handoff.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-130 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/run_state.py | EXTRACT_THEN_DELETE | src/deck_master/store.py | WP01 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 只提取安全文件读写思想；不复制旧状态文件序列 | AC-S02 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-131 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/run_state_resolver.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-132 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/schema.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-133 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/setup_status.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-134 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/skill_route.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-135 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/sourcing_import.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-136 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/tool_registry.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-137 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/workspace_binding.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-138 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/runtime/workspace_resolver.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-139 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/skills/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-140 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/skills/installer.py | EXTRACT_THEN_DELETE | src/deck_master/install.py | WP04 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 提取释放树/启动器/回滚行为；不继承15Skill齐备/PPTMaster就绪 | AC-I03 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-141 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/skills/manifest.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-142 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/skills/validator.py | EXTRACT_THEN_DELETE | src/deck_master/doctor.py | WP04 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 只检查本包资源/入口；不检查旧阶段合同齐备 | AC-I02 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-143 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/sourcing/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-144 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/sourcing/plan.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-145 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/sourcing/reader.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-146 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/team/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-147 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/team/approval.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-148 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/team/dashboard.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-149 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/team/identity.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-150 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/team/opportunity.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-151 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/team/solution_package.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-152 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/tools/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-153 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/tools/deck_pro_max_client.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-154 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/tools/ppt_library_client.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-155 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/uat/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-156 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/uat/generation_tool.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-157 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/uat/ppt_library.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-158 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/uat/real_workflow_smoke.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-159 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/uat/render_tool.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-160 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/uat/report.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-161 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/validators/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-162 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/validators/companion_tools.py | EXTRACT_THEN_DELETE | src/deck_master/legacy.py | WP04 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 只提取明确旧JSON的只读校验，不重新认证外部后端 | AC-L01 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-163 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workflow/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-164 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workflow/approval.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-165 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workflow/autopilot.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-166 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workflow/decisions.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-167 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workflow/fingerprint.py | EXTRACT_THEN_DELETE | src/deck_master/store.py | WP01 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 选择性提取哈希计算；分别计算正文、视觉、编译和审阅依赖 | AC-S04 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-168 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workflow/handoff.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-169 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workflow/migration.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-170 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workflow/policy.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-171 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workflow/questions.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-172 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workflow/stage_checks.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-173 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workflow/state.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-174 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workflow/validator.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-175 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workspace/__init__.py | DELETE_AFTER_CUTOVER | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 旧包退出；新包不import旧命名空间；无对应业务行为需要迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-176 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workspace/foundation.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |
| OLD-177 | 2a866cf138f6359f853db35e0a926ad79391b691 | scripts/workspace/project_init.py | RETIRE_THEN_DELETE | — | WP05 | WP04默认入口切换（先在新包内禁入） | WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史 | 默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移 | AC-L05 | 路径已核对；具体提取/动态消费者/执行结果需要 Codex 核验 |

### 根配置与活动文档

| path | action | detail | work_package | status | path_basis |
| --- | --- | --- | --- | --- | --- |
| pyproject.toml | ADJUST | src发现；console deck_master.cli:main；限定安装resources；不包scripts旧包；版本为候选而非虚称2.0正式 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| requirements.txt | ADJUST | 与pyproject同源锁依赖范围；资料提取按来源格式声明实际依赖 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| product-capability-manifest.json | REPLACE | 只描述当前单入口、本地工具和Host要求；删除ppt-master backend依赖及生产专业ready | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| skills/manifest.json | REPLACE | 仅deck-master公开入口，内部reference非公开专家Skill；无stage registry加载 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| skills/stage-contracts.json | ARCHIVE_DELETE | 固定旧阶段不随包安装；移历史档案，无新运行消费者后删原路径 | WP05 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| skills/RESOLVER.md | REPLACE | 创建/继续/修改/查看/检查/导出，不是九阶段路由 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| skills/deck-master/SKILL.md | REWRITE | 宿主原文理解与完整成稿为默认；不得autoplan脚手架输出后当专业规划 | WP01/WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| skills/deck-master/references/content-methods.md | REWRITE | 少量方法+完整成对好坏例+选择理由；不复制行业目录 | WP01 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| skills/deck-master/references/agent-instructions.md | REWRITE | 本包任务输入/accept/continue/返修协议，无阶段审批 | WP01/WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| skills/deck-master/references/installation.md | REWRITE | 候选安装验证、版本路径、必要渲染工具和回滚；无PPTMaster授权步骤 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| skills/deck-master/agents/openai.yaml | ADJUST | 保留Host元信息，路由到单一skill；不承诺未验证模型 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| README.md | REWRITE | 正常安装→材料→首稿→工作台→改稿；注明宿主执行、未验证边界 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| AGENTS.md | REWRITE | 当前权威Spec/代码边界/测试路径；旧Spec仅历史 | WP01/WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| CLAUDE.md | REWRITE | 与AGENTS一致的可用命令，不带回旧OS | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| DESIGN.md | REWRITE | 新依赖方向、唯一当前事实、SVG源/IR派生、UI数据链 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| ROADMAP.md | ADJUST | 本轮五包和事实完成状态；旧P2-P5不是待完成义务 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| CHANGELOG.md | ADJUST | 明确破坏性入口变更、迁移方式与旧承诺更正，保留历史 | WP05 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| CONTRIBUTING.md | ADJUST | 新测试/格式/安装复核与PR范围；不能只测fixture | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| SECURITY.md | ADJUST | 本地文件/loopback服务/隐私边界；不声称签章证明业务正确 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| Makefile | ADJUST | lint/test/real-render/install-smoke调用新包；无绑后端命令 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| Dockerfile | ADJUST | 安装实际src包、字体/渲染器声明；不COPY整repo冒充发行包 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| .github/workflows/ci.yml | REWRITE | 纯单元/真实渲染/隔离安装三类；禁止跳过失败并报全绿 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| .github/CODEOWNERS | ADJUST | 新src/resources/tests/rebuild路径责任 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| .github/PULL_REQUEST_TEMPLATE.md | ADJUST | 任务ID、实际改动、源SHA、执行命令结果、待验证边界 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| .devcontainer/devcontainer.json | ADJUST | 新src与必要工具；不安装整套15技能平台 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| .gitignore | ADJUST | 排除真实run/客户资料/下载字体/局部安装与渲染缓存 | WP01 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| docs/specs/README.md | REWRITE | 本包为活动基线，旧规范明确被替代 | WP04 | 拟调整；实际修改需要 Codex 核验 | 目标活动文档路径：存在则改、缺失则新建；需要Codex核验 |
| docs/quick-start.md | REWRITE | 唯一正常入口例子与真实待Host状态 | WP04 | 拟调整；实际修改需要 Codex 核验 | 目标活动文档路径：存在则改、缺失则新建；需要Codex核验 |
| docs/user-guide.md | REWRITE | 来源/四视图/局部修改/导出区别 | WP04 | 拟调整；实际修改需要 Codex 核验 | 目标活动文档路径：存在则改、缺失则新建；需要Codex核验 |
| docs/agent-guide.md | REWRITE | Host具体执行与恢复，不重复用户问卷 | WP04 | 拟调整；实际修改需要 Codex 核验 | 目标活动文档路径：存在则改、缺失则新建；需要Codex核验 |
| docs/agent-recovery-playbook.md | REWRITE | 按失败原因恢复，禁止自签/替换上游基准 | WP04 | 拟调整；实际修改需要 Codex 核验 | 目标活动文档路径：存在则改、缺失则新建；需要Codex核验 |
| docs/agent-task-index.md | REWRITE | 指向新任务协议和本包五个工作包 | WP04 | 拟调整；实际修改需要 Codex 核验 | 目标活动文档路径：存在则改、缺失则新建；需要Codex核验 |
| docs/troubleshooting.md | REWRITE | 实际模块路径、字体、转换错误、待Host、版本冲突 | WP04 | 拟调整；实际修改需要 Codex 核验 | 目标活动文档路径：存在则改、缺失则新建；需要Codex核验 |
| docs/known-limitations.md | REWRITE | SVG子集/平台/无人审等实际限制，不把旧绑定误列新前置 | WP05 | 拟调整；实际修改需要 Codex 核验 | 目标活动文档路径：存在则改、缺失则新建；需要Codex核验 |
| docs/planning/2026-09-15-overdefense-remediation-implementation.md | ADD_CORRECTION | 加显著更正链接保留历史值，撤回被事故否定的验收解释；不重写原始日志 | WP01 | 拟调整；实际修改需要 Codex 核验 | 目标活动文档路径：存在则改、缺失则新建；需要Codex核验 |
| LICENSE | KEEP | 保留原许可证；提取第三方代码合规核对 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| NOTICE | ADJUST_IF_EXTRACTION_REQUIRES | 保留归属并补跨分支/第三方实际来源；不要删除署名 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| THIRD_PARTY_NOTICES.md | ADJUST | 记录实际保留组件/许可证；不把字体文件打入文档包 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| CODE_OF_CONDUCT.md | KEEP | 不属于本轮功能重构 | — | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| .github/dependabot.yml | ADJUST_IF_PACKAGING_CHANGES | 按实际依赖范围维护 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| .github/ISSUE_TEMPLATE/bug_report.md | ADJUST | 增加安装版本和步骤/输入匿名说明 | WP04 | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |
| .github/ISSUE_TEMPLATE/feature_request.md | KEEP | 不扩大本轮功能 | — | 拟调整；实际修改需要 Codex 核验 | B0目录/用户审计确认；具体修改需要Codex核验 |

---

<a id="content-pair"></a>

## 同源成对内容方法示例｜全部为合成，不是生成成绩

### 输入（供方法开发，不作为H1/H2未见材料）

澄川科技：提供资料接入、引用问答、企业权限和只读业务接口集成；可以将知识助手嵌入门户。已有一个设备维修知识检索项目，承担手册/工单接入、权限、问答界面和上线培训，没有经核实的效率提升数据。

嘉禾售后流程：服务点经门户提交问题，总部按型号、固件版本、出厂批次选择资料。当前自由文本提交，版本/批次非必填；手册与通告含适用范围但未统一结构化。120条互斥样本中，36条信息完整可按资料处理，54条需补问版本/批次，30条信息完整仍需专家。本期可改门户字段，身份可对接，工单接口只读，不新增服务点入口。

观点推导：先把信息补齐前移，可能比单独加强搜索更切中当前反复补问；仍需专家的问题应完整交接，而非承诺全部自动解决。45%只是样本中补问记录占比，不是可自动解决率或效率收益。若版本缺失因现场确实无法获取，增加字段不够，需要设备识别/采集方案，这个条件可能改变推荐。

### D1｜首次能力交流：六页完整正文范例

#### 1. 澄川科技｜让产品知识进入一线售后工作流

我们提供技术资料接入、引用式问答与业务系统集成服务，将分散在设备手册、服务通告与维修记录中的知识，带到服务人员实际使用的入口。

对于嘉禾，我们希望先讨论三个具体问题：哪些知识适合帮助一线直接处理，哪些设备条件必须先收集，以及需要总部专家介入时如何减少重复沟通。

#### 2. 我们负责资料、权限与使用入口之间的连接

资料接入：整理手册、通告与已闭环工单，保留版本及引用位置，让使用者能返回原文核对。

应用集成：对接企业身份与资料权限，将查询结果嵌入现有业务门户，不要求人员建立另一套工作习惯。

上线服务：配合业务团队完成资料准备、访问配置、使用培训和问题反馈，让系统能进入日常工作，而不只停在一个问答界面。

#### 3. 项目实例：设备手册与维修工单统一检索

在北澜设备项目中，澄川承担了手册与维修工单接入、访问权限对接、引用问答界面及上线培训。使用者可以从同一入口查找资料，并沿引用返回原文。

这项经验与嘉禾的相关之处，是资料、权限和服务入口需要一同建设。嘉禾特有的设备条件与资料适用范围映射，应在本项目中单独梳理，不能把旧项目原样复制。

#### 4. 嘉禾当前值得先讨论的，是信息在什么时候补齐

120条记录中，54条首次处理需要再问版本或出厂批次。现有资料适用性又依赖这些条件，因此补问并非简单增加检索能力就会消失。

建议把条件收集前移到服务点提交时：先确认型号、版本与问题现象，再匹配适用资料。这样交给总部的，是包含必要上下文的问题，而非只有一段自由描述。

样本也有30条信息完整但仍需专家的记录。首期应同时照顾直接资料帮助和专家接力，而不是将价值全部定义为自动回答率。

#### 5. 可以在现有门户内完成资料帮助与专家接力

服务点填写设备与问题信息；助手提示补齐缺失条件；检索按设备适用范围返回资料并展示引用。可依据资料处理的情况，由人员核对后使用；需要进一步判断的，形成设备条件、问题现象与候选资料摘要交给总部。

已有资料接入、权限和引用问答经验可作为建设起点。设备字段、适用范围映射以及补问体验，是需要结合嘉禾实际工作设计的部分。本期工单只读，处理结果沿现有流程继续，不承诺系统自动写回。

#### 6. 本次能力适配：知识查询与现有售后流程增强

澄川能够参与两类工作：一是将分散资料组织成可检索、可回查的知识应用；二是把知识能力接入已有门户和业务身份，支持一线人员与专家协作。

针对嘉禾，建议先围绕信息完整度和资料适用性判断是否适配：哪些字段在服务点能够取得，哪些资料已标明版本，专家接手时希望看到什么。明确这些条件，比提前承诺某个收益百分比更有助于确定建设内容。

### D2｜已有客户方案评审：六页完整正文范例

#### 1. 建议将“条件补齐＋引用问答”嵌入售后门户

本期优先改变提交与接单之间的信息往返，而不是另建一个独立聊天入口。服务点提交时补齐必要设备条件，查询时按资料适用范围匹配；需要专家的问题带着完整上下文转交。

这一方案符合现有门户可增加字段、身份可对接、工单本期只读的条件。新增工作主要是设备字段与资料版本的映射，以及补问和转交体验。

#### 2. 样本支持把条件收集前移，但不支持自动解决全部问题

36条记录信息完整、可按现有资料处理；54条需要补问版本或批次；30条信息完整仍需专家。54÷120=45%，说明补充条件是值得优先处理的环节，并不证明45%的问题可以自动解决。

首期需要同时建立两种结果：有依据的资料帮助，以及供专家接手的完整问题包。方案验证应分别观察两者，不只统计回答数量。

#### 3. 为什么选择门户增强，而不是先做独立资料搜索

资料搜索增强的优点是建设改动较少：完成资料接入和引用展示即可，但设备条件仍可能在接单后补问。

门户内助手需要多做字段、适用范围映射和补问交互，却能直接改变信息往返的位置。针对当前目标建议采用后者。若字段在现场普遍无法获取，应先补设备识别/采集手段，而不是把更多必填项强加给服务点。

#### 4. 三个环节分别承担什么职责

服务门户负责收集型号、版本或批次、问题现象，并保留用户确认的输入。

知识服务在身份授权和设备适用范围内检索，组织引用式回答；存在冲突版本或缺少适用依据时，不给出确定的维修结论。

总部专家接收完整条件、问题现象和候选资料。工单接口按本期只读约定使用，方案不把“形成摘要”写成已经实现自动回写。

#### 5. 不同信息情况，应进入不同处理路径

条件缺失：提示具体缺哪项，并说明为什么需要；现场无法取得时允许转交，不无限补问。

资料适用且充分：返回可核对的操作依据和引用位置；人员仍能回原文确认。

资料冲突或不足、问题需专家：附带已取得条件和查询到的线索转交。不要把所有异常都显示成模型失败，也不要为了输出答案忽略版本冲突。

#### 6. 先用真实服务记录验证，再决定扩大范围

建设准备先确认字段可获取性、资料版本标记和权限接口。试用时分别观察首次提交完整度、专家重复补问次数、引用的设备/版本适配性，以及摘要是否足以支持接手。

这些指标与本期改变的环节对应，不预设收益百分比。通过当前设备和问题类型验证后，再讨论增加资料范围或其他接口；是否写回仍需业务责任与接口条件另行明确，不属于本期默认承诺。

### 好坏对照与选择理由

坏：本页通过三个维度体现公司实力。好：写出资料接入、权限对接、上线培训实际承担什么；不把制作意图改成“三大核心优势”继续空泛。

坏：公司简介页绑定“误报下降”、接口页绑定“公司成立”。好：案例证明相近交付，接口设计用当前只读约束和集成条件；论点分配由语义负责。

坏：为了显得完整，每份稿加一页风险和一页启动POC。好：本示例在相关内容处说明只读和样本边界；D1以能力适配结束，D2以实施与验证条件结束。

以上是人工撰写的方法样例，不能作为系统默认运行成功结果。验收必须保留同源任务的实际首次输出，允许它与此范例有不同但成立的结构。

## 可落入主Skill内部reference的任务指令草案

这些是拟实施的Host方法，不是已经调用模型。不要原样要求用户逐段填写。

### compose

读取本次任务、已有决定和所列相关原文。摘要仅作导航；核对影响推荐的尾部条件、图表和真实产品能力。先判断受众已知什么、本次要理解/决定什么，再写完整正文和页面设计。用具体业务动作解释机制，有选择时比较真实替代；没有效果数字不阻断合理推理，但不能编造业绩。公司介绍、风险与下一步仅在当前任务需要时呈现。按PagePackage v2输出，内部制作意图放internal_only。不得调用规则autoplan或用模板目录替代思考，不按字段数量判断专业。全部页面写完并自行审稿后交回。主Skill首次接收正文后自动view --open并给真实工作台地址，不等完整PPT才呈现UI。

### blueprint

解析同一Document的design_context/style_ref/允许资产；调用前使用项目分配allowance并begin，真实调用后settle，未知结果暂停新外部调用但本地修正继续。不得直接覆盖Task额度。

读取真实Page全部可见文字和设计关系，用允许的图像工具按页面实际任务设计；保留副标题、脚注、标签和表格空间。不要自改成no readable text，也不要将通用图片套到多页当完成。保存实际返回图像、实际提交prompt与可得调用标识；工具未提供的来源信息保持未知。打开图片，指出必要区域与新增文字，不能空填finding算通过。

### review: blueprint_content

对照Page和真实图片，审阅所有实质新增表达；保留合理说明，修改虚构能力/效果，明确建议和现状。将最终对外文案写回Page，原图的生成输入历史保持不变。识别关键区域/节点/关系作为独立重构期待；未识别的维度不报满覆盖。

### reconstruct

同时查看原图和编辑后的正文。保留实际分区、层级、关键图形与业务连接；不要用三卡片模板替代。输出受支持子集SVG及必要语义绑定，不手写第二份Scene。渲染后对照源图检查；缺内容回编辑、少图形补对应区域、转换限制具体定位。不能藏微字或透明全文补覆盖，不能把结果预览回灌成参考。

### review: final

查看当前真实SVG/PPT渲染、源图与任务必要内容。分别检查业务完整、蓝图忠实、编译损失、可读性及实际编辑范围。指标是定位，不是专业评分；对每项发现说明期待/实际/证据和修复对象。只有真实独立上下文才称独立审阅，没有人类阅稿不代填。能修的交具体repair任务，完成后复查新产物，以新Review的replaces/subjects/evidence关联旧失败和实际新对象。表格/图表的形状文字可编辑不等于Office原生编辑数据。

### repair

只修改具体失败及其真实依赖；保持无关页源图/SVG与历史文件。文本修改产生新Page并保留原生成记录，图形修改针对正确区域与关系；编译器错误不得通过重画简图掩盖。不要修改检查规则/测试以接受本次输出。输入版本冲突时重读，不覆盖新稿。没有新依据或持续无进展时说明未完成，不将停止说成成功。

---

<a id="roundtrips"></a>

## v1.1接口往返例

全部是**合成合同与预期交互**，不是已运行的产品、模型、生图、PPT或业务验收。素材是本包手写的最小SVG测试字节；不包含任何字体文件、客户素材或真实调用凭证。不能将文件存在或样例Review.status=pass登记成真实通过。

| 目录/文件 | 解决的问题 |
| --- | --- |
| missing-source/ | 原hash未知，已保存正文/提取文本/媒体仍可引用；新候选来源不追认历史 |
| design-context/ | Document唯一4:3配置、字体名、Logo字节、样式覆盖、移动项目与只改样式 |
| atom-identity.json | 重排、改字、增条目后的稳定atom；旧Pointer只在导入转换 |
| review-fixed/ | 旧失败→新产物→实际复查→新Review，及只改fixed的负例 |
| result-envelope/ | 五种kind的真实文件引用、采用预期、拒绝与重复响应 |
| call-allowance.json | 两Host最后名额、未知、取消晚到、恢复不清零的状态例 |

JSON与对象引用完整性可以由工具验证。业务语义、真实工具调用、并发调度、实际打开UI及PPT可编辑必须在实现后另做验收。本包不运行新产品来证明这些。

## 验证边界

PACK_VALIDATION.json只记录本包文档结构、合同、合成对象、任务图及例中引用检查。真实代码/编译/Host调用/UI/安装/业务验收未在本轮执行，仍需要Codex核验。


任务卡复审补充：T04.min严格指T04.01–04的核心接口，不包含依赖T05视图的T04.05；T05视图交出后由T04.05接线。T13.min为T13.01–03，完整恢复在T13.06等待T12后验证。早期交接及具名阶段测试见[交接表](task-cards/handoffs.md)。
