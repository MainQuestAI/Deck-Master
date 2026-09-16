# Deck Master 全链路与架构摸排：哪些能保留，是否应重建

核查日期：2026-09-16。源码基线：`codex/professional-first-draft@2a866cf138f6359f853db35e0a926ad79391b691`；本地安装来源：`920dc3c5c3f9772d46d007cbeeea77deda3297b0`。

本轮为只读摸排，未修改产品代码、安装、分支或长期规则。运行副本及诊断文件保存在本目录。覆盖用户提出的内容、结构、图片、SVG、PPT、工作区、外部绑定、Web UI、Skill 分工、遗产取舍及主要调用路径；不宣称逐行验证了全部代码。

## 1. 决策结论

**建议停止按旧架构逐项补丁式扩修，保留经过验证的底层资产，重建 Deck Master 的主流程。可以称为 Deck Master 2.0，但关键是替换默认入口、内容方法、状态来源和交互，而不是再增加一个模式或命令。**

当前不能把任何一条完整生产路径称为已通过专业成稿验收。用户说“整条链都有问题”，就目前实际暴露的结果而言有依据。与此同时，不能从整链失败推出全部代码无价值：完整稿接收、页面集合管理、导入回滚、正文隔离、基础图形处理等存在可复用资产。

不建议从零重写文件解析、所有 SVG 几何与 DrawingML，也不建议把 5 万多行代码全部原样带进下一版。先用可执行的最小完整链路决定资产去留，旧 OS 留作历史读取和参考，不能继续控制新任务。

上一份[蓝图事故诊断与修复方案](../20260916-blueprint-review-deep-diagnosis/repair-plan.md)仍可用于底层缺陷定位，但不足以作为整个项目的实施总计划。它没有解决默认 Planner、Skill OS、Web UI 和产品独立性之间的冲突。

## 2. 项目实际规模与当前状态

按当前 Git 跟踪文件统计物理行，包含空行和注释，不包含二进制；行数不是无效代码数量，也不是预计修改量。

| 范围 | 文件数 | 物理行 |
|---|---:|---:|
| scripts 全部文本文件 | 177 | 58,998 |
| 其中 Python | 173 | 54,491 |
| tests | 141 | 31,805 |
| docs | 440 | 85,774 |
| skills | 56 | 3,477 |

实际 CLI parser 注册 **93 个顶层命令**；产品清单有 **15 个公开 Skill、4 个兼容 Skill**；`docs/contracts/` 有 **58 个 JSON 文件**。这些数字说明表面积较大，不自动说明每个命令或契约多余。

大模块：high_density 11,639 行、runtime 9,051 行、preview 8,984 行、CLI 4,047 行、安装/Skill 管理 3,677 行、quality 2,907 行、workflow 2,598 行、generation 2,022 行。问题不只是图形转换器大，而是交付主链之外的编排、状态、安装和 UI 同时维护自己的产品假设。

当前机器实测：`suite-status.status=ready`，但同一结果中的 `ppt_master_backend`、`render`、`client_delivery` 为 `blocked`；高密度 capability 为 ready。`agent-doctor --mode production` 返回 ready，并把未绑定 PPT Master 列为 warning。这里的 ready 主要说明安装和工具条件，不能证明专业首稿能力。上一轮“suite 整体 blocked”的描述不能代替本次当前结果。

证据：[规模清单](./inventory.json)、[当前就绪结果](./readiness.json)、[定向验证记录](./verification.txt)。

## 3. 实际并存的是几套流程

| 路径 | 实际运行方式 | 与当前目标的关系 |
|---|---|---|
| 旧内容/生产主线 | 文本摘要→规则 Brief/Claim→规则 Narrative→sourcing→generation session→preview→标准 builder／PPT Master | 正常入口、Skill 顺序和 UI 的大量假设仍来自这里。 |
| Agent 完整稿路径 | 外部宿主写完整正文→`import-plan --source agent`→PagePackage→高密度生产 | 能接收 AI 的成稿，但依赖宿主主动选择；没有替换默认 Planner 和全部消费者。 |
| 高密度内部兼容路径 | PagePackage 直通与旧 MBB 内容规划并存→蓝图→Scene→SVG→PPT→读回 | 新路径解除部分旧前置，但保留多个内容投影、回执与审阅状态。 |
| Skill OS 与 Review Desk | 独立阶段契约、问答、handoff、approval、preview 页面队列 | 可以对同一 run 得出与高密度构建/出口不同的状态。 |

根因假设已由复现支持：**新能力不断以旁路和例外加入，旧入口、旧模型、旧状态没有被真正替换。于是每一层都可能“局部正确”，整条用户流程仍然不成立。**

## 4. 结构写死是否解决：只完成了局部修复

### 已经改变的部分

- `target_pages=auto` 不再自动填成 12/15 页。
- `import-plan --source agent` 能以 Agent 提交的页面集合与顺序为准，保留正文，支持增删重排和回滚。
- `content-methods.md` 已写入按场景推导结构、公司介绍/结尾取舍、业务机制、方案比较和实际编辑的方法。

### 仍未解决的部分

正常 `deck-planner` 的 Allowed Commands 仍首先引导 `autoplan`。`plan_narrative()` 的 production 分支没有语义推理过程：从 `must_cover_topics` 逐项生成页面，用“架构/流程/机制/案例”等关键词判角色；用户指定页数大于主题数量时，再从 `GENERIC_BEATS` 补齐。

这不意味着所有 AI 项目都必须在 Python 内调用模型。由 Codex 等宿主推理本来可行。真正的问题是：这里把规则脚手架作为生产规划结果输出，却没有强制把正常新建任务交给已有的宿主成稿方法。

本次函数级复现，输入分别明确写了：

1. 首次面向陌生企业介绍公司能力与经验，不讨论试点；
2. 已合作客户的技术评审，已了解公司，讨论接口、权限与方案选择。

结果：auto 都得到“内容中台、AI智能体”两页；指定 12 页时，两者得到相同目录，并带上“案例与证据、价值与收益、实施路径与推进计划”。任务文字仍会出现在 brief 中，但结构没有按交流任务变化。不能用“支持完整稿导入”宣称默认结构问题已彻底解决。

还有更直接的内容错误：`enrich_narrative_with_claims()` 用 `index % len(claims)` 循环分配论点。隔离复现把“案例降低质检误报”配给公司介绍，把“公司成立于某年”配给接口设计。该逻辑实际在 `write_plan_artifacts()` 被调用，不是只存在于测试。

入口资料处理也仍有旧假设：本地材料 summary 260 字、excerpt 900 字，Brief 主要拆 summary 的前几句。把“工单接口只读、不能回写”放在长材料末尾，自动 Brief 不包含它。原始路径仍被保留，宿主可以补读，因此这不是“所有通道永久丢原文”，而是默认规则链本身不具备完整材料理解能力。

定位：`scripts/planning/brief_intake.py:10`、`scripts/conversation/brief_compiler.py:12`、`scripts/planning/narrative_planner.py:235`、`scripts/planning/page_budget.py:4`、`scripts/deck_master.py:516`、`:578`、`skills/deck-planner/SKILL.md:29`。

处理建议：生产默认入口改成宿主读取原文、应用内容方法、写完整稿；规则 Planner 退出生产默认链，只保留为明确标识的演示/草案辅助。目录不能因用户指定页数又被旧模板接管。

## 5. 生图也有问题：第二页首先是内容不足，同时存在输入接线缺陷

我查看了第二张真实蓝图、PagePackage 和实际生成 prompt。该页只写了两个阶段、各自结果和一句选择理由。它没有展开为什么这些资料优先、一期具体交付什么、哪些条件阻碍回写、何时进入二期。画得更满并不能补上这些判断。

这页更像“实施顺序概述”，不足以完成任务声明中的“给出实施选择、理由和阶段结果”。如果本来就是过渡页，这个密度可以合理；在本次任务中，把它作为高密度方案正文交付缺乏支撑。不能通过通用最低字数或强制图标数解决。

此外，本次确认一条此前诊断未覆盖的代码缺陷：

- `build_page_package_content_lock()` 将设计要求保存在 `enrichment.visual_spec`。
- `_presentation_projection()` 仍读取旧 `enrichment.chart_plan`，不消费 `visual_spec`。
- prompt 中实际出现 `Use this intended visual form: {}`；旧 `Supporting arguments: none`、空 management takeaway 也仍被拼进去。
- 独立 marker 复现进一步确认：`visual_spec`、顶层 `footnotes`、`labels`、`subtitle` 都进入 Content Lock，却没有进入最终 `prompt_text`。后续精确重绘可以恢复部分锁定文字，但生图阶段已经无法据这些内容正确分配视觉空间。

因此，生图链路的问题包含两层：输入正文尚未达到任务所需深度；正确存在的设计要求和部分文字又在投影时漏传。第一张视觉丰富的结果，也不足以证明这条输入链稳定正确；此前额外可见文案仍须审阅。

定位：`scripts/high_density/content.py:250`、`scripts/high_density/blueprint.py:385`、`:418`。

处理建议：正文和页面设计要求一起成为真实生图输入；在写正文阶段补足当前任务所需论证；生图后编辑新增文案。没有资料支撑的效果不靠生图补造。图片只负责视觉参考，不成为业务事实来源。

## 6. PNG→SVG 与 SVG→PPT：两个独立能力缺口

PNG→SVG 当前由宿主 Agent 读取蓝图并编写 Scene/SVG。代码并没有一个能够自动理解并忠实矢量化全部蓝图的通用引擎。Scene 元素合法、文本引用齐全只能约束已声明内容，无法自动发现原图中未登记的模块、图标和层级。把这个环节交给 Agent 没问题，但任务方法、源图覆盖和复核必须真的执行。

SVG→PPT 则有实际原生编译代码，并非完全空壳。基本形状、路径、填色、部分渐变、文字和渲染有实现及回归资产。但上一轮已复现字重、负斜率线段、旋转圆边界等缺陷，多行排版存在风险；原生对象数量不能证明正确还原。

当前的 Scene、SVG、编译 trace、PPT 读回还重复保存部分几何/语义。它们一旦分别成为验收答案，就会自证。下一版要明确：业务正文和原图是期待；SVG 是制作源；PPT 是实际输出；Scene/trace 是映射与调试信息，不能替代期待。

完整缺陷、隔离反例与已修/未修边界见[蓝图事故深度诊断](../20260916-blueprint-review-deep-diagnosis/diagnosis.md)。本轮没有重做成品，也没有宣布后续两次紧急提交已通过实际验收。

## 7. 为什么还绑定 PPT Master：没有完成项目级解绑

这不是用户漏装，也不仅是一个旧名称。当前仍有真实接线：

| 位置 | 当前事实 |
|---|---|
| `product-capability-manifest.json` | `backend_dependencies.deck-builder = ppt-master`，公开 routes 仍声明对应关系。 |
| `scripts/runtime/skill_route.py:69` | 标准 Builder 仍携带 ppt-master dependency。 |
| `scripts/runtime/build.py:137` | production 标准构建要求已认证外部后端，否则报 `needs_builder_backend`。 |
| `scripts/runtime/builder_backend.py:26` | 保留 binding、外部 repo、SHA、manifest、production operations 体系。 |
| `scripts/skills/installer.py:2395` | 整体 production_backend_ready/client_delivery_ready 仍以 PPT Master 为条件。 |
| README 生产步骤 | 仍要求 bind/verify PPT Master。 |
| Web UI | 仍展示外部后端未认证及“先完成 PPT Master 渲染”等提示。 |

高密度路径独立，是一个真实增量；但“某条 profile 不需要 PPT Master”不等于“Deck Master 已独立”。上一轮实施把彻底解绑收缩成了高密度旁路，同时保留标准路线作为兼容路径，没有完成用户的项目目标。

建议：新主流程不再依赖 PPT Master 的 repo、安装、认证或运行状态。旧格式及旧产物可以单独读取/导入；如果确有用户需要调用外部 renderer，未来作为显式可选工具，而不是新 Deck 的默认条件。独立项目仍正常使用 python-pptx、渲染器等通用依赖。

## 8. Web UI 为什么没有出现：入口缺失加上数据模型脱节

UI 代码没有被删除，安装目录也包含 server 和 static 文件。`scripts/preview/` 共有 8,984 行，app.js 2,586 行、server.py 1,702 行、style.css 1,592 行。

但正常 Skill/CLI 的生成交付动作没有统一的启动/打开审阅界面步骤。93 个顶层命令里没有 serve/ui/open 命令；README 单独要求运行 `python scripts/preview/server.py ...`。setup 有 review_cockpit_url 配置，但它不是自动启动服务或打开当前任务的实现。

更严重的是本次实测：

1. 用事故 run 的副本按文档启动单 run UI，直接因 `Missing preview_manifest.json` 失败。新完整稿路径允许不生成这个旧 preview。
2. 改用 Studio 模式可启动，能列出该 run。
3. 选择项目后，顶端显示“可交付”“当前页面、门禁与交付预览已满足交付条件”，页面队列却是 0 页。
4. 同页 Skill OS 显示 `deck-init` 等待两个问题，第一问是材料扫描范围；右侧又显示最终放行检查未通过/未生成。
5. 缩水成品对应的两页没有在页面队列出现。UI 没有消费 PagePackage/高密度页集合；因此无法完成用户需要的蓝图、SVG、PPT 对照。

源码原因：`build_workspace_payload()` 仍以 preview manifest 生成页面卡片；无 manifest 时返回空列表。另一处直接把旧 runtime stage 映射为“可交付”，并套上已满足交付条件的解释。Skill OS 再独立计算自己的阶段。

这不正常。它是产品交互未接入实际生产链，不能以“Agent-first，所以不用 UI”解释掉一个已经做出并承诺承担审阅的功能。此前 Agent 交付时没有主动展示已有审阅入口，也属于执行遗漏；但现在实测，即使打开，当前界面仍不能正确呈现新路线的真实页面。

处理建议：保留可用 UI 外壳，替换数据接口；当前真实页面集合、正文、蓝图、SVG 渲染、PPT 渲染和问题直接进入同一个审阅视图。首稿与修订产物生成后必须给出当前任务的可点击入口；界面不能通过是否存在旧 preview 决定当前有没有页面。浏览审阅和批准出口分开，未通过验收的图也必须能查看。

定位：`scripts/preview/server.py:1654`、`scripts/preview/workspace_api.py:597`、`:812`、`:984`。证据：[UI payload](./ui-workspace.json)、[同 run 的 Skill OS 状态](./ui-skill-os.json)。

## 9. Producer、Produce、Builder、Planner 到底有什么区别

| 名称 | 当前代码职责 | 当前高密度完整稿路径的实际意义 |
|---|---|---|
| deck-planner | `autoplan` 生成 narrative/page tasks/sourcing/preview；主要是规则规划。 | 完整稿导入能取代其输出，但 Skill 正文仍优先引导旧路径。 |
| deck-producer | 管 generation session、dispatch、结果导入、preview 刷新；正式内容由宿主 Agent 或配置的外部生成工具完成。 | 完整稿导入后可绕过它；“Producer”不代表独立的专业内容模型或独立 Agent。 |
| Produce | 当前没有独立名为 `deck-produce` 的 Skill，也没有 `produce` 顶层 CLI 命令。 | 不能把动作名、Producer 和另一个成熟功能算成三份能力。 |
| deck-builder | 标准生产适配器，消费页面包/构建清单并接外部 PPT Master。 | 保留了与独立项目目标冲突的标准路线。 |
| deck-builder-high-density | Content Lock、蓝图任务、Scene/SVG、原生 PPT、渲染读回；在宿主配合下承担实际视觉制作。 | 与 Producer 的页生产职责重叠，是当前唯一在事故中实际跑到可编辑 PPT 的独立路线。 |
| deck-quality / deck-review | 前者执行质量检查与报告；后者处理审阅/交付/出口。 | 内部职责可以区分，用户不需要掌握两套状态和命令来完成一次改稿。 |
| deck-master / deck-autopilot | 路由及推进多个 stage/command；autopilot v2 本身声明不生产内容。 | 多套推进器没有等价于端到端自主制作。 |

这些模块并非逐行重复，但**代码职责不同不等于应该暴露成独立用户 Skill，更不等于每个名称都有独立业务价值**。

新版本建议只有一个主要用户入口 `deck-master`。内容方法、视觉重构、格式转换和审阅作为内部职责/工具；安装和故障诊断可以是维护命令。不要再要求用户理解 Producer 与 Builder 的阶段边界。

定位：各 Skill 的 SKILL.md；`scripts/generation/session.py:469`、`dispatch.py:74`、`scripts/workflow/autopilot.py:1`。正式生产的 bundled generation adapter 会生成 awaiting_agent_execution 的 handoff，这与宿主推理设计相容，但它不是已经完成的内容生成。

## 10. 是否还需要专门工作区

必须区分三个概念：

- **材料目录**：用户现有文档所在的位置，不应为了生成 PPT 被迫迁移或重新分类。
- **制作产物目录**：保存正文、蓝图、SVG、PPT、预览和版本，支持恢复与局部修改。这有直接价值，应自动建立。
- **预设工作区平台**：注册 workspace、初始化客户目录/模板、运行 stage/handoff/approval/learning 等额外仪式。单份 Deck 的生产不需要以这些为前置。

当前已做过减法：`validate_workspace()` 接受没有 manifest 的普通目录，本轮空目录复现为 valid，不能继续说所有旧模板都是硬门槛。但是 production/benchmark 仍要求 workspace 绑定，Playbook 仍要求初始化；`init-project` 会创建多层客户材料目录，随后再创建旧 workspace 目录。UI 的 Skill OS 仍可能追问初始化问题。

建议：用户给资料和输出位置，系统自动维护产物目录。项目级资料复用、品牌与偏好可按需加载；没有这些，不影响正常制作。Web UI 是产物浏览与修订入口，不是必须先建的管理平台。

## 11. 可保留资产与不能继承的完成声明

| 资产 | 可确认的价值 | 保留方式与证据边界 |
|---|---|---|
| PagePackage 的可见正文/内部说明分离 | 已有结构和 strip_internal；完整稿可进入生产。 | 保留概念和可靠读写；不再把合法 schema 当专业内容合格。 |
| 完整稿导入、页集合及回滚 | 已有增删重排、失效处理、导入中断恢复；本轮定向回归通过。 | 提取为小范围文件操作能力，解除旧全链状态依赖。 |
| 无 Library 的新建路径 | 默认 none 路径和定向测试存在，能不搜索历史库。 | 保留；产品清单与全局状态仍需去掉强关联。 |
| SVG 解析、原生路径、部分画笔/圆角 | 已有真实可编辑输出和必要回归资产。 | 选择性提取、修已知几何/文字问题；不能整包标为成熟转换器。 |
| 渲染、解包、文字及对象读回 | 可用于实际观察成品与定位损失。 | 保留测量工具；重写推导整体 pass 的规则。 |
| 文件 hash、路径、版本与来源定位 | 支持追溯和当前版本识别。 | 保留少量必要信息，不能当作内容/视觉质量证明。 |
| 安装、release tree、回滚机制 | 已有部署与恢复框架及测试资产。 | 抽取后重新在独立安装验证，不继承“安装成功等于产品就绪”。 |
| 公共成稿方法和反例 | 方法方向比固定目录更接近业务要求。 | 进入真实默认宿主任务，成对样例验证；不因文档存在就宣称已奏效。 |
| Review Desk 页面布局与部分交互 | 已有可启动的实际界面。 | 保留外壳/可用交互，重接真实页集合和当前状态；旧状态逻辑不继承。 |
| 旧 Library/外部后端适配器 | 可能有既有用户/历史 run 读取价值。 | 冻结为可选兼容材料；不进入新核心，不据此扩大新版本承诺。 |

本轮实际运行：`test_import_full_draft.py`、`test_no_library_path.py`、`test_narrative_planner.py`、`test_high_density_icon_stability.py`，**61 passed in 100.96s**。其中含 fixture 和函数级测试，不能证明真实专业首稿、全链视觉还原或开源泛化。没有运行完整 pytest，没有新生产一份 PPT。

这回答“哪里没问题”：有局部已验证行为；没有证据支持把某条完整业务链、整个转换器或整个 UI 直接宣布为没问题。

## 12. 继续修、局部重建、从零重写的取舍

| 方案 | 优点 | 主要问题 | 判断 |
|---|---|---|---|
| 在当前 OS 上继续补所有问题 | 旧命令和格式维持最多 | 新旧入口及多套状态持续互相牵制，修复很容易再次变成例外和门禁 | 不建议作为主路线 |
| 重建用户主流程，选择性提取资产 | 能移除无业务价值的编排，又不重复制造解析/渲染基础设施 | 必须真的隔离旧入口，不能只是再加一个 v2 开关 | 推荐 |
| 从零写全部代码和图形引擎 | 表面最干净 | 已知转换细节、字体/图形兼容问题会重新经历一次，丢掉可用恢复和回归资产 | 暂无充分理由 |

建议中的“重建”边界：重做默认内容流程、任务调度、统一状态、用户入口与 UI 数据接口；复用经过验证的文件/页面操作和图形工具。旧项目完整保留供追溯，不在取得替代品前大规模删除。

不以修改行数判断取舍。54,491 行 Python 不代表要修 54,491 行；六个首批提取候选源文件（PagePackage、svg_native、svg_paint、pptx、visual、contracts）总计 3,931 行，也不意味着这 3,931 行可以全部照搬。PPT 编译器当前 import 了审阅/验证模块，抽取时必须切开这些依赖。

## 13. 下一版实施顺序与停止继续扩张的条件

### A. 先交付一条小而完整的真实路线

在隔离目录试做新主流程，不新建第二套长期运行 OS。输入保持“资料＋已有讨论＋任务”，宿主写完整内容与设计要求；正常使用图→SVG→PPT，制作后显示真实对照。用事故两页加一张表格/数值图覆盖当前最关键能力。

这一步必须同一次证明：专业正文、设计要求进入生图、原图完整重构、PPT 真实保真、可编辑、当前 UI 能显示并修订。不通过时定位替换具体部件；不先建立注册平台和安装套件。

### B. 确立唯一的内容与产物事实

沿用精简 PagePackage 内容语义，宿主完成场景推理和正文编辑。只保留一个当前页面清单、每页源文件及其当前检查结果；其他状态为派生视图。原图与正文确定期待，Scene 和 trace 不得反向定义验收答案。

### C. 单一用户入口与实际工作台

主要动作是“创建／继续／修改／查看／交付”，不暴露九个生产 Skill 阶段。生成或修改后给出当前页预览及工作台链接。UI 同时提供正文、蓝图、SVG/PPT 对照和具体修改反馈，不能先过验收才允许看失败产物。

### D. 提取底层，移除外部绑定和旧前置

图形转换以 A 的坏样例修复。新主路径、manifest、安装、doctor 和 UI 都不依赖 PPT Master/Library。旧 run 兼容集中在导入/读取边界，不要求新流程先复制旧的 sourcing、preview、approval 和 RC 文件。

### E. 用新任务决定能否正式替换旧版

成对场景验证公司介绍、结构、结尾和详略；使用合理短稿和复合稿；加入陌生材料。验证单页修改、增删重排、跨目录恢复和当前 UI 同步。通过候选安装重跑，不借源码 checkout 补文件。

如果转换器经过针对性修复仍无法在上述真实样例保持文字/几何/可编辑语义，就替换这个独立组件，不能继续用大量外围治理包住它。如果内容方法在充分材料下仍产出空泛正文，先改宿主方法和样例，不用页面密度阈值掩盖。

本轮不批准新框架规模，不承诺未经验证的行数或时间。是否叫 2.0 不影响技术判断；真正的验收是正常任务从默认入口一次进入可用的成稿与修改流程。

## 14. 各目录处置索引

这是架构处置建议，不是逐行死代码清单。行数来自 inventory.json；“提取”不等于原样通过审计。

| 目录/文件 | 行数 | 新主流程处置 |
|---|---:|---|
| high_density | 11,639 | 提取几何/编译/渲染；重做正文投影、源图还原方法和审阅；旧 MBB 与旧状态隔离。 |
| runtime | 9,051 | 提取导入/文件/页面恢复；统一状态；PPT Master binding 与标准外部主线退出新核心。 |
| preview | 8,984 | 保留适用 UI 外壳；页集合、预览、状态与启动入口重接。 |
| deck_master.py | 4,047 | 新默认入口精简；旧命令留兼容边界，不能全部移植为新用户界面。 |
| skills | 3,677 | 精简单入口安装与发布；删除新核心对15 Skill齐备的依赖。 |
| quality | 2,907 | 保留实际文件/数据/可见内容检查；移除不适用的统一专业评分。 |
| workflow | 2,598 | 旧阶段/handoff/approval运行平台不进入新核心。只提取必要恢复事实。 |
| generation | 2,022 | 提取来源和宿主交回结果的必要语义；不保留与高密度并行的强制生产链。 |
| benchmark | 1,811 | 保留资料与运行证据存取；不继承旧时间/阶段完成作为专业价值指标。 |
| tools | 1,360 | Library 和 Pro Max 适配留可选/历史区，不作为生产前置。 |
| uat | 1,221 | 提取真实产物核验方法；旧后端集成UAT按旧路径保留。 |
| review | 1,023 | 与当前真实产物审阅合并，避免另一套批准/就绪事实。 |
| orchestrate | 968 | 旧 preview/export/sourcing编排退出新默认路线。 |
| planning | 951 | 规则Planner移至演示/辅助；生产采用宿主完整成稿。 |
| assets | 936 | 保留资产读取/定位必要部分；暂停整页库平台投入。 |
| team | 684 | 团队身份/审批不进入个人成稿核心。 |
| sourcing | 623 | 可选历史复用；非正常新建的必经阶段。 |
| context_intake | 488 | 保留来源定位和材料输入；替换摘要当理解的默认链。 |
| advisory | 458 | 方法/审阅思路纳入宿主编辑，不追加平行任务队列。 |
| delivery | 451 | 保留最终文件交付与验收事实；不要求用户事后登记才计算价值。 |
| narrative | 431 | 保留来源核对；替换拼句/数量信心等规则推断。 |
| workspace | 410 | 保留普通资料位置和自动产物目录；不强制初始化管理平台。 |
| production | 392 | 保留PagePackage正文/内部信息边界与可靠读写。 |
| build | 302 | 提取装配清单；清单不重新成为固定流程前置。 |
| feedback | 299 | 用户反馈按任务保存；Library反馈为可选。 |
| learning | 263 | 按明确请求使用，不作为成稿前置。 |
| adapters | 222 | 已有格式转换按需要选择；不自动继承全部兼容承诺。 |
| metrics | 190 | 工程观察保留；阶段时长不证明专业价值。 |
| validators | 143 | 保留真正的格式契约检查。 |
| connectors | 121 | 可选资料输入，非生产前置。 |
| conversation | 104 | 复用用户已有讨论；规则摘要Brief退出生产默认。 |
| capabilities | 101 | 仅报实际依赖和可用工具，不能叫专业质量ready。 |
| page_roles.py | 89 | 保留语义分类的有用部分，不据角色套固定目录。 |
| demo.sh | 32 | 明确仅作demo，不作为真实制作验收。 |

## 15. 本轮证据边界

- 新复现：不同场景同目录、显式页数补模板、循环论点错配、材料尾部约束不进入规则Brief、设计/脚注/标签/副标题漏入生图prompt、Web UI零页和矛盾状态。
- 重新核实：当前SHA、实际安装SHA、全局/路线就绪判断、代码规模、公开Skill与命令数。
- 定向回归：61通过，只证明对应机制；没有重新运行完整pytest，也没有新图或新PPT验收。
- 复用上一轮：具体SVG/PPT几何与审阅失效反例，明确仍未关闭。
- 产物：[复现JSON](./reproductions.json)、[UI JSON](./ui-workspace.json)、[UI阶段JSON](./ui-skill-os.json)、[规模JSON](./inventory.json)、[验证记录](./verification.txt)。

最终判断：**能改，但应当改变修法。保留遗产，重建主流程，比继续维护所有旧流程更符合现在的产品目标；没有证据支持把整个项目全部推倒，也没有证据支持继续称当前产品已生产就绪。**
