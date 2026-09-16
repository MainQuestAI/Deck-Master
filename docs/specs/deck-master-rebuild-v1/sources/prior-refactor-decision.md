# Deck Master 代码复核与主流程重建裁决

日期：2026-09-16。

## 0. 决策摘要

建议直接启动**主流程重建＋选择性资产提取**。不建议继续把现有九阶段 OS 当作必须兼容的主干逐项扩修，也不建议从零重写 SVG/PPTX 转换、文件恢复和所有 UI。

这里的“直接”是现在确定替换旧主干，而不是在替代链路验证前删除旧仓库、覆盖安装或把未完成的新核心切给用户。它也不是只换目录的保行为重构：默认内容生产、状态解释、入口和部分兼容承诺都需要有意改变。

最重要的验收不是代码少了多少，而是：**用户从正常入口给材料和任务，能拿到达到专业审阅门槛的完整稿、忠实制作的可编辑文件，并在同一工作台完成局部修改；不需要主动跳到另一条旁路，或替系统维护多套批准、阶段和清单。**

## 1. 本次证据及边界

### 1.1 实际读取的基线

- 当前附件对应远端分支：`codex/professional-first-draft@2a866cf138f6359f853db35e0a926ad79391b691`。
- GitHub 当前 `main`：`bcb5b37a4e32b5b98b063ec31e745a8ce017c8f1`。
- 上一轮 PR31 分支：`codex/sc1.1-native-core@2c5a4c50048b2641739356e72ddc1d6fea1d962f`；本次查询仍 open、未 merged。
- 用户安装版本 `920dc3c…` 来自附件，不是本次直接读取用户机器所得。

本次读完三份附件，并从 GitHub 重新读取当前分支关键内容、制作、审阅、UI、文件恢复和默认 Skill 的源码片段；额外读取 PR31 的 `native_pptx/api.py` 作提取候选比较。当前分支 `scripts/build` 的目录读取仅返回 `__init__.py`、`manifest.py`。因此上一轮对 PR31 `native_engine/native_budget/native_content` 的判断不能直接套在当前分支。

### 1.2 实际执行

在本会话沙箱对远端函数摘录执行四组隔离探针：提示词字段传递、既有论点被循环覆盖、渐变透明度 0、第四次归档覆盖第三次。结果见 `probe_results.json`；完整可运行工具为 `probe_review.py + source_excerpts.py`。

**未执行：**完整仓库 pytest、用户安装 CLI、原事故 run、真实生图、整份 PPT 渲染和桌面编辑。本次无法下载完整仓库，但已通过 GitHub 连接读取固定提交的目标源码；不是仅依据附件转述。所有用户本地文件、已安装模块、完整测试和修复效果，**需要 Codex 核验**。附件中的“61 passed”、真实 UI 运行画面和事故日志，在本报告中仍属于附件提供的结果，不升级成本轮实测。

## 2. 为什么应当改变修法

### 2.1 好的内容方法没有成为默认入口

`skills/deck-master/SKILL.md` 把新建指向 Brief → Planner；`deck-planner/SKILL.md` 允许命令首先为 `autoplan`。默认 playbook 的第6步仍为 Autoplan，完整稿导入放在6b，前提是完整稿“已经写好”。

当前 `plan_narrative()` 把 `must_cover_topics` 铺成页面，再按“架构/流程/机制/案例”等关键词判角色；指定页数超出主题数后，仍从通用章节补齐。`write_plan_artifacts()` 调用 `enrich_narrative_with_claims()`，按 `index % len(claims)` 分配核心论点，并覆盖已有 `core_claim`。

这不是 Python 必须内置大模型的问题。宿主 Agent 推理完全符合本项目方向。问题是默认任务还在把规则脚手架当作生产结构，而宿主完整成稿变成用户或 Agent 主动绕行才能使用的能力。

**处置：**重写默认成稿入口和宿主方法。规则 Planner 退出新生产链；完整稿/页面更新成为常规写入，而不叫“override”。撤销循环配论点。代码可查真实引用是否存在，不能靠数组位置替专业判断。

定位：S01、S02、S03、S04、S05。

### 2.2 内容合同更新了，制作输入没有一起更新

`build_page_package_content_lock()` 已经把设计要求放入 `enrichment.visual_spec`。`_presentation_projection()` 却读取 `enrichment.chart_plan`；`build_blueprint_prompt()` 又遗漏已进入 projection 的 subtitle。顶层 labels、footnotes 也未进入最终 prompt。

本次隔离探针：title/body/callouts 均进入 prompt；subtitle/footnotes/labels/visual_spec 四个不同 marker 均未进入。正文与设计完整不是同一个层面的校验，必须检查实际交给宿主生图的输入。

**处置：**保留 PagePackage 的对外正文与内部说明分离；替换成一个明确的内容到制作投影。正文与设计指令分开传递：设计要求可以被模型理解，但不应直接作为页面可见文案。提示词测试检查完整输入的传递，而不是仅检查生成了一份 JSON。

定位：S06、S07、S08。

### 2.3 多套状态并不是同一事实的不同展示

`build_high_density_status()` 读取持久化 status；`compute_final_readiness()` 自己将部分旧 runtime stage 改写为 ready，再另外检查视觉失败；UI 的 `build_workspace_payload()` 仍基于 preview manifest 生成页面卡片，无 manifest 分支直接给 `cards=[]`。

所以问题不能靠新增一个“总 ready”字段解决。底层编译成功、某个版本的审阅通过、用户看到哪些页、某次任务是否仍在运行，是不同事实；它们目前又被不同模块各自推断。

**处置：**当前页集合及版本只有一个权威；检查结论绑定被检查的输入/产物版本；可交付性由同一函数派生；任务执行进度独立表达。CLI、UI 和出口消费这个相同视图，不再分别判断。历史 completed 和 pass 可以保留，不能自动显示为当前通过。

定位：S09、S10、S11。

### 2.4 转换器值得提取，但当前模块边界不适合直接搬迁

`high_density/pptx.py` 导入 `.svg` 的校验及 `.visual` 的测量；`high_density/__init__.py` 导入整个 engine。完整稿导入的 schema 校验还在注释中明确承认导入 high_density 会牵入 builder runtime。

这意味着“复制几份核心文件＋保留原 imports”会把旧审批、目录布局、蓝图规则和状态依赖带回新核心。PR31 已有较独立的 `native_pptx/api.py`，但接口仍要求 Scene、Lock 和外部注入的 business validation，不能直接认定为与业务流程无关的纯转换器。

**处置：**选择性提取解析、绘制、文字、渲染、读回；再切断对旧 OS 和审阅政策的反向依赖。底层 API 只接收具体制作输入并返回文件、对象映射与诊断，不负责判定客户可交付。

定位：S12、S13、S14、S15、S21。

### 2.5 既有恢复机制有价值，但粒度不适合原样继承

`import_plan()` 在写入前备份，并在失败时恢复，这是应保留的行为。但 `_backup_downstream_for_import()` 会复制整套 `build/render_results/high_density_build/quality_reports`。即便以后只改一页，也不应默认复制整个任务下游。

同时 `next_attempt_index()` 的 `min(3,count+1)` 使连续四次归档得到 `[1,2,3,3]`。本次用真实文件操作和函数摘录复现，第四份 marker 内容覆盖了 attempt-3 中的第三份内容。

**处置：**保留稳定 page_id、旧版本和失败恢复；写入不可变新页版本，组装新的页清单后原子切换当前指针。备份次数不封顶复用同一路径；不必为此引入新的分布式事务平台。具体并发模型及旧机制提取范围，**需要 Codex 核验**。

定位：S15、S16、S17。

### 2.6 “减少防御”与“修复错误”必须分开

当前审阅写入器对 failed regions、failed objects 或多项相似度问题拒绝通过；读取器额外拒绝条件只覆盖 severe mismatch 和 failed objects。附件对读写条件不一致的判断与本次源码吻合。本次未构造完整 run 绕过读取器。

编译器也仍有真实绘制错误：800/900 字重没有进入加粗集合；负斜率线在归一化中只剩 bbox，下游按左上到右下绘制；圆的变换边界只采四个点。本次另发现并通过函数摘录验证：`_append_gradient()` 中 `stop.get('opacity') or 1` 把 0 透明度转为 1，生成的 DrawingML alpha=100000，而不是0。

**处置：**这些错误不能通过放宽阈值解决。保留正常输入与故意破坏样例；把客观输出缺失、测量告警、实际视觉审阅区分开，用同一结论解释函数供写入、读取和展示调用。

定位：S12、S14、S18、S19。

## 3. 对附件方案的独立裁决

总体赞成《rebuild-plan.md》的方向，但实施前应补齐五个边界。

| 附件方向 | 本次裁决与收紧 |
|---|---|
| 保留底层、重建主流程 | 赞成，但提取资产要比较当前分支与未合并 PR31，不能忽略另一分支成果，也不能整包合并 PR31。 |
| 第一批事故两页＋表格页跑通 | 保留为转换能力探针；另用原始材料从默认入口生成，不能把手工精修 PagePackage 输入误当专业首稿验证。 |
| 一个当前页面清单、统一状态 | 赞成；不是增加一个汇总旧状态的总管理器，也不是一个单独 completed 字段统治所有语义。 |
| Scene/trace 不作验收答案 | 赞成；不等于删除转换中间表示。应删除 Agent 手工维护的重复几何，IR 由 SVG 派生。业务要求和蓝图独立作为期待。 |
| 旧 OS 不进入新核心 | 赞成；原子提交、取消、晚到结果拒绝、输入版本识别仍需提取。删除复杂 OS 不能删除恢复与协作正确性。 |

## 4. 建议的新边界：薄宿主方法，薄任务层，独立制作工具

### 4.1 宿主 Agent 负责什么

继续使用 Codex 等宿主，不内置新的 LLM provider，不建设新的 Agent harness。宿主负责阅读相关原文、判断交流任务、组织叙事、撰写完整正文、确定页面设计、调用图像工具、按图重构 SVG、实际审阅并修改。

公共方法不能只写“专业、深入”：要给出如何从任务决定公司介绍、对比、实施细节及结尾的原则与正反例；同一材料在首次能力交流和既有客户技术评审中，必须产生不同且成立的表达。摘要是导航，不代替关键原文；代码不循环替用户配论点。

不把“当前没有效果数字”解释成所有建议无法作出；明确区分事实、推导、方案建议和目标。

### 4.2 最小应用层负责什么

只维护一份当前页集合与页版本、实际产物引用、短任务记录、检查结果及反馈。建议的内部动作是创建、读取、提交页面更新、运行制作、查看、导出；名称不是当前已存在命令。

支持几个真实约束即可：
- 同一动作重复提交不重复生效。
- 已取消动作不再写回当前结果。
- 晚到结果必须检查对应页面的内容/设计依赖是否还是原输入。
- 多页更改完整落盘后再切换当前清单，不让 UI 看到半套新旧混合。
- 单页修改不让无关页面的任务因全局版本号变化失效。

不建设可配置九阶段工作流、角色权限平台或通用事件溯源系统。单机可用的短锁、不可变文件及原子指针更新优先。

### 4.3 制作内核负责什么

概念接口：`SVG＋资产＋画布/字体配置 → PPTX＋对象映射＋转换诊断`，随后单独渲染和读取实际 PPT。

原型实现允许暂时保留必要的旧适配，但最终提取接口不应查询 workspace、PPT Master binding、故事线审批或审阅签章。支持的 SVG 子集明确；不支持的特性按页/对象返回诊断，不能悄悄丢弃或无授权转成整页图。

文字布局、连线端点、曲线、分组、透明度和字体权重使用输入 SVG 的语义。IR 机械派生；不得要求宿主手写一份 SVG 再写一份几何完全相同的 Scene。

可编辑不只是“每个碎片能选中”：至少核验文字修改、关键形状/连线操作和合理分组。是否必须为 Office 原生表格/原生数据图表，应按具体交付要求验收，不能从形状可编辑推出数据可编辑。

### 4.4 审阅与工作台负责什么

相同当前文档视图支撑 CLI 和 UI。最小 UI 必须能显示正文、蓝图、SVG渲染、PPT渲染、当前问题和版本；首稿生成或修改后回到同一任务链接。不能先检查通过才允许看失败产物。

保留可用 UI 布局，而不是承诺必须保留全部旧前端代码。先修数据接口；不用为了重构重做配色、路由体系或设计系统。

检查有三个对象：
1. 任务/材料与最终内容之间：要求、事实、关系有没有丢或改变。
2. 参考蓝图与 SVG 之间：布局、关键区域、视觉对象是否忠实。
3. SVG 与实际 PPT 之间：文字、几何、字体、透明度、连线方向及编辑能力。

某条简单页面真的没有图标是“不适用”；没有识别过原图是“未评估”；空列表不是满分。不同 reviewer 名称不是独立执行证明。宿主有独立执行上下文就使用；没有则如实标为自审，不新建签章服务来装作独立。

## 5. 数据事实：保留少量语义，不再平行维护答案

| 事实 | 唯一来源 | 可以派生但不得反向覆盖它的内容 |
|---|---|---|
| 当前有哪些页、顺序与版本 | 当前文档清单 | UI卡片、编译顺序、页数汇总 |
| 对外正文与设计要求 | 相应版本的 PagePackage | Prompt、文字覆盖要求、制作任务 |
| 原始视觉参考 | 实際生成/导入的图及当时输入记录 | SVG、PPT、预览、相似度结果 |
| 可编辑制作源 | 已提交 SVG | 派生IR、DrawingML、对象trace |
| 当前检查结果 | 绑定输入/输出版本的观察 | UI状态、是否可交付、下一项修复 |
| 当前执行进度 | 对应页的任务记录 | 运行中、等待工具、已取消等显示 |

保留蓝图“生成时输入”与最终编辑正文之间的区别。改正一个词可以复用原图布局并重绘 SVG，不必强迫再生图；也不能重写历史 prompt 冒充新正文当时已输入。

不得用当前 SVG 预览静默替换比较基准。确需重新设计时，明确形成新视觉版本，再进行新比较；不以禁止所有相同hash代替来源关系判断。

## 6. 具体代码处置

| 范围 | 新核心处理 | 不应继承的部分 |
|---|---|---|
| `production/page_package.py` | 保留稳定页面身份、对外/内部信息隔离，精简读写与内容语义 | 字段齐全等于专业合格；重复page_id/beat_id/order的多方权威 |
| `runtime/orchestration.py` | 提取页面集合验证、更新差异、回滚行为 | 全目录备份、旧sourcing/preview序列、把常规写作叫override |
| `planning/*` 与 `deck_master.py` 规则规划 | 生产默认替换为宿主成稿；必要示例留演示区 | 关键词铺页、补通用目录、数组循环配论点 |
| `high_density/content.py`、`blueprint.py` | 一个正确的正文/设计输入投影，保留真实图像来源 | 旧MBB模型决定新字段；漏传再靠下游修复 |
| `high_density/svg_native.py`、`svg_paint.py`、`pptx.py`及PR31内核 | 逐功能对照后提取；修文字、几何和透明度 | 整包复制及对审阅/工作区/绑定的反向依赖 |
| `high_density/visual.py`、读回 | 提取测量与真实PPT解析 | trace决定全部预期，指标默认等于专业判断 |
| `high_density/svg.py` 审阅部分 | 统一发现解释和结论读取 | 写/读分别维护规则、换名字自证独立 |
| `runtime/*state*`、`next_step`、`final_readiness`、`workflow/state` | 新核心只保留一个当前状态派生器；必要任务恢复单独提取 | 多个模块互相修正stage、completed或pass |
| `preview/workspace_api.py` | 重写为当前文档/产物视图 | preview缺失就0页；直接继承旧runtime“可交付”标签 |
| Skill / CLI / 安装清单 / doctor / README | 一个主要用户入口，同一个默认制作路径 | 标准PPT Master绑定为默认前置，旧Planner悄悄复活 |
| Library、旧标准后端、团队与学习平台 | 历史/可选边界；先不进入新核心 | 仅因代码已存在就列为新版必须齐备能力 |

## 7. 实施顺序：按完整结果拆，不按九个技术阶段拆

### R0：固定基线与提取清单，不扩修旧主干

保留当前分支、旧安装和事故原件；确认安装入口与模块来源。形成“当前分支可取用 / PR31可取用 / 不带入新核心”的小清单。不要整包合并PR31，也不另建PPT Master必绑关系。

只有防止旧版本继续误放行、修复备份覆盖等必要止血进入旧链；其余投入转向替代路线。源码发布与用户日常安装的切换分别处理，**需要 Codex 核验**。

### R1：两种试验并行验证一条小型完整链

**制作试验：**用事故页和一张包含数值、单位、负斜率连线、文字/图标的页面，提供已确认的内容与参考图，验证图→SVG→PPT→工作台。

**内容试验：**用同一批原始材料，分别提出首次能力交流和已有客户技术评审，直接从默认入口产生正文和设计输入。输入中的“接口只读、不得回写”等条件必须改变推荐和图示。

两种试验分别回答“底层能不能保真”和“默认内容是不是专业”。禁止把手工润色好的三个页面导入成功包装成专业首稿通过。

这一批已有小型真实查看入口，不等第三批才有UI。提取组件同时用最小隔离安装/运行目录执行，尽早发现源码checkout依赖；这不等于提前建设完整发布治理。没有必要先设计全部平台。

### R2：加入一次真实局部修改和故障恢复

至少验证：改正文一项、改关系/连线一项、增删重排、取消/晚到结果、写入中断恢复。

只改一页时，不重新生图或重绘其他未受影响页面；整份PPT重新组装及相关文件级复核是合理的，不承诺成品PPT字节完全不变。页码、跨页引用、共享样式、总计等变化属于明确的共享依赖，应被真实更新。

UI 与 CLI 必须同时看到相同的新版本及问题；旧图、旧稿和先前的失败观察仍可查看。不能把“所有文件都备份了一遍”当作局部修改已经高效成立。

### R3：切换唯一默认入口与独立安装

替换根 Skill、新建playbook、CLI默认路由、安装清单、doctor和UI入口。未配置PPT Master/Library时，使用真实安装包完成创建、修改、查看和导出；阻止从源码checkout补文件来伪装安装完整。

旧流程只通过显式legacy读取/导入或固定旧版继续，不与新流程共同写同一个run。尚未验证的旧格式不承诺“自动无损迁移”；保留原始产物。

### R4：陌生任务与正式收口

增加一组未参与方法调优的材料、合理短稿与复合方案。不把所有行业和类型纳入首版承诺。通过正常使用者的专业审阅判断可用性；不把模型间一致当客户验收。

删掉只给错误旧行为背书的测试，同时迁移正文完整性、文件恢复和图形反例。阶段结束意味着默认入口替换、旧权威退出；不能只报告“新模块所有测试通过”。

## 8. 最小验收矩阵

| 用例 | 判据 |
|---|---|
| 新建任务 | 给材料/目标即可进入成稿，不要求先创建组织、阶段批准和全套模板 |
| 同材料不同交流场景 | 公司介绍、架构深度、实施安排和结尾随真实任务改变 |
| 关键条件在材料尾部 | 条件被读到并进入推荐/图示，不靠摘要是否包含关键词 |
| 生图输入 | 对外文字无漏项，设计意图被消费，内部说明不被印成正文 |
| 原图重构 | 原图关键区域/关系/层级保留；删关键对象能定位 |
| 原生转换 | 字重800/900、线段方向、旋转曲线、透明渐变、多行文本有独立预期与实际输出核对 |
| 正确内容与自证区分 | Scene/trace不能把缺失对象从期待集合中抹掉；不得更换基准再判原任务通过 |
| 真实审阅 | 查看过本版实际图像并给出具体发现；不能换两个名称声明独立 |
| 单页修订 | 无关页面无需重做；有关共享依赖会更新；整稿可重新组装 |
| 取消/重放/中断 | 不覆写新稿、不重复应用、不丢旧稿、不显示半套新旧状态 |
| UI一致性 | 有真实页面就能看；失败也能看；无“0页＋可交付” |
| 独立安装 | 无PPT Master/Library前提，不从源码目录临时补资源；版本与模块来源一致 |

## 9. 四组本次探针结果

| 探针 | 本次结果 | 能证明和不能证明 |
|---|---|---|
| Prompt字段 | title/body/callouts进入；subtitle/footnotes/labels/visual_spec不进入 | 证明这两个投影函数的传递缺陷，不等于完整宿主绝不补读其他文件 |
| 循环配论点 | 公司介绍被覆盖为案例效果，接口设计被覆盖为公司成立年份 | 证明函数按数组位置覆盖语义，不等于所有成稿都走该函数 |
| 透明渐变 | stop.opacity=0，输出DrawingML alpha=100000；0.5与1正常 | 证明绘制函数错误默认值，不宣称已渲染整份PPT复现其全部视觉影响 |
| 归档 | [1,2,3,3]，attempt-3内容成为第4份 | 证明该归档函数会覆盖第3份，不等于所有版本保存系统都失效 |

## 10. 收口裁决

应启动重建，但重建对象是**入口、应用编排、状态权威、内容投影和审阅接线**；转换与恢复工具按证据修正后取用。

第一项交付是可被业务人员打开、对照和修改的真稿，不是一份新框架或目录。后续判断哪个组件值得留，只看它是否在独立样例中可靠减少真实失败。无法达到已声明SVG范围要求的转换组件，才进行独立替换；不用外围签章和更多schema补偿。

不承诺削减某个代码比例，不继承“安装ready即专业可用”的完成声明。也不将单机开发中同一执行者可改源码的问题升级成需要身份平台或密码学审阅服务。

---

## 源码定位索引（本次实际读取）

以下链接固定提交；读取有的是完整短文件，有的是相关范围，不代表逐行审计整仓。

- S01 [根Skill](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/skills/deck-master/SKILL.md)
- S02 [Planner Skill](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/skills/deck-planner/SKILL.md)
- S03 [新建playbook](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/skills/deck-master/playbooks/codex-run-solution-deck.md)
- S04 [规则Planner](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/planning/narrative_planner.py#L235-L380)
- S05 [CLI规划写入及循环论点](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/deck_master.py#L516-L595)
- S06 [PagePackage](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/production/page_package.py#L1-L220)
- S07 [Content Lock投影](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/high_density/content.py#L250-L324)
- S08 [图像制作投影及Prompt](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/high_density/blueprint.py#L385-L514)
- S09 [UI页面/状态数据](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/preview/workspace_api.py#L812-L1055)
- S10 [高密度完成与状态读取](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/high_density/engine.py#L1465-L1560)
- S11 [最终就绪对旧stage的再解释](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/runtime/final_readiness.py#L243-L310)
- S12 [PPT编译模块依赖、渐变](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/high_density/pptx.py#L1-L120)
- S13 [high_density包初始化](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/high_density/__init__.py)
- S14 [字重与线段绘制](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/high_density/pptx.py#L235-L313)
- S15 [完整稿导入/恢复](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/runtime/orchestration.py#L153-L280)
- S16 [导入校验、变化字段与下游备份](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/runtime/orchestration.py#L560-L850)
- S17 [蓝图归档](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/high_density/blueprint_content_review.py#L1-L78)
- S18 [审阅写入条件](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/high_density/svg.py#L990-L1120)
- S19 [审阅读取条件](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/high_density/svg.py#L1300-L1400)
- S20 [SVG几何归一化](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/high_density/svg_native.py#L596-L670)
- S21 [PR31内核候选API，另一分支](https://github.com/MainQuestAI/Deck-Master/blob/2c5a4c50048b2641739356e72ddc1d6fea1d962f/scripts/native_pptx/api.py#L1-L245)
- S22 [当前普通工作区已不要求模板齐备](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/workspace/foundation.py#L142-L189)
- S23 [当前标准构建外部后端条件](https://github.com/MainQuestAI/Deck-Master/blob/2a866cf138f6359f853db35e0a926ad79391b691/scripts/runtime/build.py#L137-L145)

附件依据：《architecture-audit.md》《rebuild-plan.md》《diagnosis.md》。附件建议不是用户已批准实施范围；本文给出独立建议，未修改产品代码或仓库。
