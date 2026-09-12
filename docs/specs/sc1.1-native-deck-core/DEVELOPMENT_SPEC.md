# Deck Master SC-1.1 · Native Deck Core
## PR #30 后续纠偏与收口完整开发说明书

规格版本SC-1.1-NDC v1.0｜2026-09-07｜基线`4977f89573d18a282c605360dc55f751443a2b21`。

**本包正式撤销旧SC-1 D04的外部PPT Master必选后端约束；以图片蓝图→SVG→内置原生PPTX为新默认，不是只改提示或默认字段。**

本说明书汇总拆分规格和任务。四份机器Schema、六份合成样例、64项本轮计划验收与原88项映射见包内对应目录。所有产品实现、安装、测试及效果需要Codex核验；本包不是测试完成报告。

[文件导航](CONTENTS.md)｜[Codex开工说明](agent/START_HERE.md)


---

<!-- source: specs/00-decisions-and-supersession.md -->

# 00｜产品裁决、规格优先级与完成定义

## 0.1 唯一业务目标

以 PR #30 的 SC-1 工程主线为基础，取消默认生产对完整 PPT Master 产品的运行依赖，把现有图片蓝图→SVG→DrawingML 生产能力变为 Deck Master 内置、默认、可独立验收的主链。用户不再被要求克隆、寻找、绑定或修复 PPT Master，仍保留原生编辑、内容质量与交付校验。

“独立”不表示不用开源库、系统渲染器或外部模型；它表示不依赖另一个产品的目录、安装、命令、配置、工作流和就绪状态。模型由宿主提供，Deck Master 不内置模型 SDK/账户。模型名称和路由记录真实值，不能用字符串包含 Astra/GPT-6 来证明能力；宿主实际图像生成、视觉理解与 SVG 生成能力需要 Codex 核验。

## 0.2 正式替换旧裁决

| 原 SC-1 约束 | 本轮裁决 | 保留不变的部分 |
|---|---|---|
| D04：PPT Master 是标准默认后端，不得用高密度代替 | **撤销。ND-D01：新 Run 默认使用内置 `deck_native` 编译能力。PPT Master 仅为显式旧 Run 兼容选项，不计默认 required。** | 真实编译、渲染、回读和编辑性验收不能取消 |
| D05：高密度仅为可选路径 | **替换。ND-D02：其已存在的视觉生产能力提取为公共能力。内容密度与技术引擎分离。** | 不降级现有视觉、内容、原生 SVG 与回读质量门 |
| D06：标准和高密度各一条、共享内容 | **精化。ND-D03：一个公共编译内核，可有图片蓝图和显式直接 SVG 两种 authoring mode。** | 同一 Narrative、同一 Page Package、单一事实源 |
| D02/D09：统一安装、无库新建 | **强化。ND-D04：没有外部 PPT Master 和历史库时，默认真实生产可以完成。** | 数据与软件隔离；可选资产检索不删除 |
| 00 §0.6 不可取消标准后端、A2 托管整包、P-01 必测外部标准 | 以本包替换表解释“内置原生构建”的等效或更强验证 | 不把取消后端身份误读为取消实际工具证据 |
| 原 Agent 指令中禁止取消标准后端 | 改为禁止重引入完整外部产品的必选依赖；所有入口同步 | 不弱化研究、审查、审批和效果目标 |

**优先级：用户本次确认方向 → 本包产品裁决/替换表 → 其他未冲突 SC-1 正式要求 → 既有实现。** 不以旧约束反对本次纠偏；也不能用本包静默删除 SC-1 的未冲突范围。原始 spec 保留历史，增加 superseded 指向；复制到实际执行目录的 START_HERE、验收表、README 和 agent instruction 必须同步。

包内 `acceptance/SC1_SUPERSESSION_MAP.json` 对原 88 项做逐项映射，不重用编号改写历史结论。PR #30 偏差表中的 W/Q 编号与旧包原文可能含义不一致，以“原包编号+标题+描述”定位，不能只按编号认领完成。[R01][R11][L01]

## 0.3 不再讨论的产品约束

ND-D05：默认编译代码随 Deck Master 发布；不得首次运行动态 clone PPT Master 整库、调用全局同名命令或要求 backend bind。

ND-D06：内容事实来自已确认的上下文/方案及证据；图片只是视觉蓝图。重建时同时读取 Content Lock 与真实图片，不能将图片中的错误抄成事实。

ND-D07：P0/P1 文本必须是可编辑文字；主要业务图形为原生形状、路径、线条和分组。不得整页 PNG/SVG 包装、文字转轮廓、隐藏文本层冒充可编辑。

ND-D08：优先提取现有内核，不重做通用 SVG 浏览器。按支持子集约束模型输出；必要上游代码按最小依赖闭包引入并保留许可。

ND-D09：沿用既有 Run、Handoff、Decision、Approval、Action Envelope、Review 和 Lineage；不另建多 Agent 调度系统。

ND-D10：旧 Run 只读和批准产物保留。继续执行和显式迁移各有确定路由；不能靠目录存在顺序猜新旧引擎。

ND-D11：用户授权和当前产物审批不被替代；专业研究、叙事和技术执行由 Agent 承担；既有有效决定不重复询问。

ND-D12：实际生产成功是发布门，不是后续可选 UAT；客户效果对照另列，不能借缺客户素材免做无客户素材即可完成的真实工具测试。

## 0.4 范围与非目标

必须交付：公共 SVG 编译/回读内核、图片→SVG 主链、任务级就绪、默认路由、公共内容接入、批准/修订一致性、隔离安装、旧 Run 适配、无库主路径、文档及验收更新。

必须保留但不重做：SC-1 Context/Research/Solution/Narrative/Page Package/Diagram/质量/学习和可选 PPT Library。发现上述链路已有实现但入口未接通，补必需接线；不得把主体缺失伪装为只差运行环境。

非目标：重写完整 PPT Master、增加第二套默认后端、引入 PptxGenJS 等第二技术栈替换现有编译器、通用 Office 导入编辑、Excel 数据驱动原生图表编辑、无限 SVG/CSS 兼容、插件市场、新 UI。普通图表由原生对象绘制不等于可在 PowerPoint 编辑数据源，本轮不承诺后者。

## 0.5 完成标准

1. 在隔离 HOME、禁用全局 Skill 与旧后端 PATH、不存在 backend_bindings 的环境中，安装产物能够完成真实默认两页 smoke 和七类页面回归；生产模式不使用 Fixture 和伪造 provider 记录。
2. 从原材料开始的至少一套真实宿主 8—12 页 Solution Deck，在无历史库条件下完成公共内容→图片→SVG→原生 PPTX→语义与视觉检查→批准导出，再完成单页修改闭环。
3. 本包工程 L1/L2 的 mandatory 用例全部执行且通过；未解决的主链问题是 in_progress，不是 outcome_pending。
4. SC-1 三类真实客户方案配对 UAT 及负担/质量目标保留。缺授权素材可以标 outcome_pending；基线不可执行不能当 0 分或“无限提升”。
5. 不宣称 production release/1.0，仅因当前 PR 测试通过；软件版本发布由仓库实际版本策略决定，**需要 Codex 核验**。


---

<!-- source: specs/01-baseline-and-change-map.md -->

# 01｜固定基线、静态事实与修改地图

## 1.1 基线

开发基线：PR #30，分支 `codex/sc1-solution-core`，HEAD `4977f89573d18a282c605360dc55f751443a2b21`。本次在线读取时 PR open/unmerged，base SHA 为 `bcb5b37a4e32b5b98b063ec31e745a8ce017c8f1`。[R01]

PR 描述仍提及旧中间 HEAD `d5c3040`，不作为代码基线。其“1583 passed + 119 subtests”是作者报告，不是本次复跑证据。源码是在连接器按固定 SHA 读取，没有取得完整本地 checkout，也没有执行产品测试；本地能力、环境、状态和效果均**需要 Codex 核验**。

若开始实施时 PR30 已有新提交或已合并：先做差异映射，保留本包已确认裁决；不得自动重置、revert、清理 worktree 或丢弃用户修改。

## 1.2 已看到的代码事实及对应动作

| ID | 远端静态证据 | 本轮应处理 | 不能据此声称 |
|---|---|---|---|
| F-N01 | installer 的 `install_managed_backend()` 复制完整源包后仍提示 bind [R02] | 从默认安装与 required 集移除整包；仅旧兼容保留 | 安装闭环已通过 |
| F-N02 | runtime/build.py 调用 builder_backend_status 与 production_requires_builder_backend [R03] | 新引擎路由先于外部状态查询；禁纯删 if 后伪报 ready | 去掉提示即可独立 |
| F-N03 | high_density/pptx.py 已有 compile/readback 与原生对象输出 [R04][R05] | 先提取函数和依赖，再通过差分测试 | 当前所有真实页面可无后端运行 |
| F-N04 | 高密度协议独立进行 MBB 主线选择及内容锁 [R06] | 公共 Narrative 为新 Run 唯一主线；MBB 成为派生适配 | 修改目录就解决重复规划 |
| F-N05 | next_step 优先发现 high_density/status；常规缺项写死 ppt-master [R07] | 以固定 route 和 canonical revision 解析，不以目录存在优先 | 所有默认入口已一致 |
| F-N06 | next_step 在只缺 semantic review 时仍可能返回 render gate [R07] | 缺语义时返回 prepare/import 语义任务，不重复 render | quality gate 增一枚即可完成 |
| F-N07 | CLI library choices 是 auto/real/fixture，尚无 none [R08] | none 接通 parser、start、autoplan、sourcing、resume、doctor | task_readiness 写了 none 就能用 |
| F-N08 | Schema status=ready_for_build；常规生产消费者要求 ready [R03][R09] | 统一写值并对旧 ready 作受控迁移，不接受任意同义词 | 声称“消费 Package”已足够 |
| F-N09 | semantic gate 用 external_* 前缀匹配；单靠 index 哈希判当前性 [R10] | 精确 scope/type/覆盖与逐文件内容指纹，图/来源联动 | external_visual 可代替 semantic |
| F-N10 | action commit 逐文件 rename、无跨文件提交指针；预算统计已提交项 [R12] | 复用 envelope，但采用 revision 暂存+单指针提交、失败尝试计入预算 | 函数 docstring 的 all-or-nothing 已得到证实 |
| F-N11 | 偏差登记含 HD 公共投影、typed questions 与接线欠项 [R11] | 按真实调用图补必须接线，登记旧案继承状态 | 八个开发段落都写了就已 engineering_complete |

以上静态观察不是本地故障复现。Codex 应补最小可复现实例，再以本包验收验证最终行为。重点是收口，不是扩大为任意 bug 清理工程。

## 1.3 可复用成果

从 PR30 继承 Context 和 Research 结构、Solution Model、公共叙事/Page Package 生产、Diagram View、质量审查契约、反馈接受率修复、安装所有权保护。不得重新声称这些功能全已验收；其真实调用方接入仍需要 Codex 核验。[R01][R11]

内置渲染候选：`scripts/high_density/pptx.py`、`svg_native.py`、`svg_paint.py`、`svg.py`、`visual.py`。内容候选：`high_density/content.py`、`production/page_package.py`、`build/manifest.py`。能力检查/安装/路由候选：`runtime/builder_backend.py`、`skills/installer.py`、`skills/capability_lock.py`、`runtime/next_step.py`。

## 1.4 必查入口与修改面

| 面 | 必查文件（现有路径；完整调用关系需要 Codex 核验） | 要达成的行为 |
|---|---|---|
| CLI/默认配置 | scripts/deck_master.py、product-capability-manifest.json、skills/manifest.json、skills/stage-contracts.json | 一个固定 native 默认，没有外部产品 required |
| 状态 | runtime/setup_status.py、run_state_resolver.py、next_step.py、skill_route.py、final_readiness.py、rc_gate.py | task_ready 与整套安装状态分离；不由旧目录触发错误路由 |
| 构建 | runtime/build.py、runtime/render*.py、build/manifest.py、high_density/engine.py 与编译子模块 | 单写入者、原生编译、两类旧适配 |
| 内容 | planning/narrative_planner.py、production/page_builder.py、page_package.py、diagram_views.py | 不制造第二份主线或事实；状态值一致 |
| 执行 | workflow/actions.py、handoff.py、questions.py、decisions.py、approval.py、现有 autopilot 实现 | 能派发/接受/继续；幂等、权限、版本、预算真实生效 |
| 质量/交付 | quality/gate_policy.py、gate_freshness.py、external_review.py、delivery/validate.py、orchestrate/export_queue.py | 当前语义不能用视觉门替代；输出绑定有效版本批准 |
| 安装/发布 | skills/installer.py、capability_lock.py、pyproject.toml、release 构造、容器/CI入口 | 依赖随产品，旧外部目录不被探测或改写 |
| 指引 | AGENTS.md、CLAUDE.md、README、known-limitations、主 Playbook、两个 Builder Skill、recovery/index | 不再引导默认用户绑定 PPT Master；新旧明确 |

Q0 交付 baseline-diff、call-graph、reuse-vs-replace、old-test-map、host-capability-probe、dependency-closure 六份简报即可；不得以长期文档盘点替代实现。


---

<!-- source: specs/02-architecture-and-truth.md -->

# 02｜目标架构、路由与唯一数据归属

## 2.1 公共链路

原材料 → Context/Research → Brief/Claim Evidence → Solution Model → 公共 Narrative → Page Tasks/Sourcing → Page Packages → Content Lock → 图片蓝图 → Scene+SVG → 内置编译 → PPTX/渲染/回读 → 专业审查/定向修复 → 当前版本批准/导出。

不新增公开 Skill；`deck-builder` 负责新默认构建。现有 `deck-builder-high-density` 继续作为密度/旧 Run 兼容入口，不拥有另一套内容事实和编译器。

## 2.2 正交字段（目标协议，不是当前能力声明）

| 字段 | 值/默认 | 语义 |
|---|---|---|
| engine_id | deck_native（新 Run 默认）；legacy_ppt_master（显式兼容） | 编译执行身份，不以客户选项显示底层项目 |
| authoring_mode | image_blueprint（默认）；direct_svg（显式） | 图形生产来源，二者调用相同原生内核 |
| density | standard/high；已有页面密度可继承 | 页面信息密度，与是否图片蓝图独立 |
| library_mode | none/auto/real；没有授权库时 none | sourcing 行为，不决定编译器身份 |
| origin_run_mode | production/benchmark/fixture/dev | 创建时记录；不可用修改 request 把生产转 fixture 来交付 |
| output_profile | 沿用 production_pptx/client_delivery | 所需产物；不静默少生成声明过的格式 |

`build_route` 随 request 固定，schema 见 contracts/build-route.v1.schema.json。当前 engine_version、SVG 子集版本和 build_revision 在执行计划/产物记录，不让用户手填。

### 路由规则

新 Run 无 profile：native + image_blueprint；新 Run `--profile native` 相同。新 Run 旧 `--profile standard` 映射 native 并给一次兼容说明。新 Run `--profile high-density` 映射 native、density=high，不启用独立后端。

已有 Run：先读已保存 route，再读构建/产物契约推断旧 engine。旧 high_density 由 legacy-HD adapter 消费既有路径；旧 standard 仅在明确历史后端痕迹下认作 legacy_ppt_master。无法判断则只读并给出迁移计划，不默认当新 Run 改写。对旧 Run 指定与其不符的 profile，返回迁移要求；不得在普通 status/doctor 中迁移。

显式 `--profile legacy-ppt-master` 只用于旧模式或明确请求；仅此路由检查旧 binding。缺失它不阻断 native。旧行为作为兼容，不作为发布默认路径必测依赖。

## 2.3 三层内部设计（目标位置可映射）

1. **公共内容与视觉任务层**：复用 SC-1 现有模块；构造宿主任务、生成蓝图、重建与修订。
2. **Native compiler 层**：建议 `scripts/native_pptx/`；纯编译、SVG 解析、样式映射、对象追踪。没有项目业务规划、PPT Master 绑定、HOME 探测或网络调用。
3. **Run adapter / engine 层**：建议 `scripts/build/native_engine.py`；把 Run 的内容锁、Scene、SVG 与资产投影为编译输入，写回标准 artifact/build/render/lineage；宿主动作通过既有 workflow envelope。

目录名是目标建议，Codex 可以调整但必须保持职责、依赖方向和验收。不得复制两份解析器/编译器供新旧路径独立演化。

## 2.4 数据归属与依赖方向

| 对象 | 权威写方 | 下游如何使用 |
|---|---|---|
| Context/证据 | 原材料和经核验研究导入 | 事实/来源；不从图片反填 |
| solution_model | 方案设计任务，经 Runtime 接受 | 问题、机制、组件、边、阶段、取舍 |
| narrative_plan | 公共规划任务及用户有效决定 | 新 Run 唯一主线；推荐不等于用户已选择 |
| page_packages | Producer，经 schema/来源/授权校验 | 唯一页面内容输入；标准状态 ready_for_build |
| content_lock | 根据批准 Package 生成的不可变快照 | 文本/数字/术语与业务限定；不能被视觉任务写 |
| blueprint | 已授权 ImageGen 真实输出及已接收修订 | 视觉来源；内部标注不进入正式页面 |
| scene | 重建任务的语义旁注，经 Runtime 校验 | 元素ID、文本引用、组件映射、编辑目标；不是第二布局真相 |
| approved_svg | 重建任务的视觉源，经规范化和检查 | 几何/样式/z-order 的实际输入 |
| PPTX/trace/readback | 本地编译器与渲染器 | 编译结果，不是新的事实来源 |
| gate/approval/current revision | Runtime | 当前版本有效性与批准；不接受 Agent 宣称已批准 |

新 Run 的 MBB compatibility projection 只从公共 Narrative、证据引用和 Package 投影。原 HD MBB 文件可以继续存在，但加 `derived_from`，不允许独立写入主线。不得先创建空 Package 再要求其作为 Narrative 的起点。暂缺内容时回到 Producer/Planner，不能靠 build 补模板。

## 2.5 当前版本与派生文件

复用现有 build manifest 作为 committed revision 清单，增加单一 `build/current_revision.json` 原子指针（如仓库已有同职责对象则复用并登记）。建议不可变数据位于 `build/revisions/<revision_id>/`。跨文件提交先完整暂存、校验、写 revision manifest，最后在 Run 锁内比较旧 revision 并单次切换指针。

`build/build_manifest.json`、`render_results/render_result.json` 等旧固定位置只做兼容投影。所有新消费者在读取时验证 projection_revision 与 current 一致，不一致必须重建投影，不能把部分投影当有效版本。不能同时把“新 pointer”和“旧固定目录”各当真相。

页序改变影响整 deck fingerprint 和批准；单页颜色修改影响该页视觉、整体 PPTX 与最终批准，不必废弃未变的业务目标决定。来源/方案变化按被引用关系计算影响集。旧 revision 永久保留到用户授权的清理策略，不自动覆盖已批准客户文件。

## 2.6 安装依赖边界

内置组件至少包含编译、验证、回读适配、schemas、方法引用和测试样例；以相对模块导入加载。第三方软件包与系统工具清单随 release 记录版本/来源；用户基础工具缺失由 doctor 给准确动作。不得检测 native 就绪时运行外部 PPT Master 目录探测；可选 Library 与模型运行环境各自报告，不污染本次任务 readiness。


---

<!-- source: specs/03-native-compiler.md -->

# 03｜Native SVG→PPTX 编译内核

## 3.1 复用策略

首选从 `scripts/high_density/pptx.py`、`svg_native.py`、`svg_paint.py` 及测量/回读组件提取现有实现。[R04][R05] 先用现有七类样例做提取前后差分，再改入口和目录。现有 SVG 子集的支持情况以 parser、compiler 和真实回归共同为准；高密度文字说明中“禁止 transform/use”等表述与当前 parser 可能不同，必须一次统一，不能以旧 prose 否定已验证支持或随意扩大支持。[R06][R13]

只有基线样例证实确有缺项时，才按最小依赖闭包吸收上游转换模块。交付 included_files、licenses、upstream_sha、功能映射与回归证据。不能仅复制 wrapper，也不能连 templates/workflows/完整项目管理一起托管。许可证条款和来源固定值需要 Codex 核验；本包不预填“已合规”。

## 3.2 内部 API（目标）

```python
compile_svg_deck(request: NativeCompileRequest, output_root: Path) -> NativeCompileResult
render_pptx(result: NativeCompileResult, renderer: RendererConfig) -> RenderResult
readback_pptx(result: NativeCompileResult, expected: ContentSnapshot) -> ReadbackReport
```

编译器不接收 backend binding，不依赖某个 high_density 路径。Run adapter 解析相对文件，校验哈希后传入。内容锁/Scene/asset manifest 可以由请求引用，但跨 Run、路径逃逸、哈希不匹配、未批准 SVG 不得接受。任意单独 SVG 文件并不自动具备客户交付资格。

API 的输出身份、页序、输入文件指纹、engine_version、subset_version 和实际对象 trace 必须完整。compile_result 只表示编译成功/失败，不含 `client_delivery_ready=true`。Render/Readback/Gates/Approval 独立完成后才导出。

## 3.3 SVG 支持矩阵

| 类型 | 本轮要求 | 原生输出/失败处理 |
|---|---|---|
| text/tspan | 必需；支持中英文、段落、字号/加粗、基本对齐 | PowerPoint 文本框与文字 runs；不得转路径；缺字体准确报告 |
| rect/circle/ellipse | 必需 | 原生形状、填充、描边与透明度 |
| line/polyline/polygon | 必需 | 原生线/自由形状；方向标记正确；不能画成单张图 |
| path M/L/H/V/C/S/Q/T/A/Z | 以现有规范化实现为基线保留回归 | 支持曲线规范化到可编译路径；不支持参数给 element_id 和恢复动作 |
| groups/z-order | 必需 | 真分组和可独立对象；ID/层次/遮挡一致 |
| local transform/use | 保留基线通过的子集，不新增任意 SVG 引用能力 | 编译与验证共同规范化；禁止外部 use、递归循环及不支持的变换 |
| gradients/opacity | 保留已支持可控渐变；含 0 opacity/0 stop alpha 反例 | DrawingML 原生填充；不能用 value or 1 把零值变一 |
| shadow/glow | 保留已支持受控子集 | 原生效果；其他滤镜不静默栅格化 |
| image/photo | 仅明确登记资产 | 单独图片对象，有 asset/hash/许可/裁剪记录 |
| foreignObject/脚本/外部资源/CSS任意滤镜 | 不支持 | 明确阻断，返给 Agent 改为子集；无静默丢失 |
| 原生表格/带数据的chart | 不作为本轮扩展要求 | 可用原生文字+形状表达；不得宣称具备数据表联动编辑 |

矩阵每项标记 supported / normalized / unsupported，并有可执行样例。不得依赖浏览器“看起来支持”推断 PPTX 编译支持。

## 3.4 坐标、字体与文本

新 Run 统一 slide 尺寸 16:9；viewBox 可不同，由一个显式 contain transform 映射，禁止横纵不同比例拉伸。保留旧 1672×941 样例的既有映射以免无端迁移失真；新规范画布建议 1600×900，若沿用旧画布必须明确内接框和映射，不把近似比例当严格 16:9。

长度统一转换为点/EMU，stroke/effect/文本 bbox 使用同一转换函数。新旧 renderer 与 QA 坐标要可回算。字体清单和实际 fallback 记录；未验证 fallback 不允许通过标题/关键段落回读。测试要覆盖中文标点、英文字体、长行、换行、数字、小数、负数、百分比和上标（不支持时有声明）。

文字比较只允许事先声明的排版归一化（如 Unicode NFC 和段落换行）；不得删标点、数字或单位来提高匹配率。业务限定与客户名同样来自 Content Lock。

## 3.5 编辑性定义

全部 P0/P1 文本可作为文字编辑；全部非照片型业务节点、箭头、线条、图例和数据图形有独立原生对象。像素大面积照片可以保留图片；不得把包含业务文字的局部截图包装为“照片资产”。

除全文检查外，用演示软件实际改变一个中文文本框、一组架构节点、一条路径/箭头、一项颜色，保存并重新打开/渲染。容器里的 XML 检查不能替代该项应用侧编辑检查。具体演示软件与字体环境需要 Codex 核验，不声称通过所有 Office 版本。

## 3.6 差分与可重复性

提取前后使用相同 SVG/Scene/Lock/assets，比较标准化对象 inventory、文字、几何、分组、层序、样式及渲染。PPTX ZIP 时间戳不稳定时不以二进制 hash 完全一致为唯一回归标准；实际产物 hash 仍必须用于 lineage。编译器版本变化产生新构建 revision，不复用旧 readback/批准。

保留现有规范化 SVG→PPTX 文字屏蔽 SSIM≥0.97、P0/P1几何误差≤0.75pt 的已定义基线，用固定 renderer/字体/画布测量。[R06] 如真实 renderer 差异需调整，先给差分证据与校准结果，由正常规格偏差流程裁决，不能仅为过门放宽阈值。图片→SVG 不复用 0.97 作为唯一指标，见质量规格。

## 3.7 错误输出

至少明确 `NDC_SVG_UNSUPPORTED`、`NDC_FONT_UNAVAILABLE`、`NDC_ASSET_UNREGISTERED`、`NDC_TEXT_MISMATCH`、`NDC_COMPILE_FAILED`、`NDC_RENDERER_UNAVAILABLE`、`NDC_READBACK_FAILED`。每项含 page_id、element_id（可定位时）、expected/actual、input hash 和恢复动作；禁止“成功但漏对象”，禁止全页图自动降级。


---

<!-- source: specs/04-host-visual-production.md -->

# 04｜图片蓝图、SVG 重建与宿主任务

## 4.1 默认端到端行为

新 Run 选 native 时，默认 authoring_mode=image_blueprint。Agent 先从现有材料完成方案和页面内容，不要求用户提供逐页稿。公共主线和风格已有有效授权时直接复用。生产进入 Builder 后不能重新开展一轮独立 MBB 访谈。

阶段动作依次为：validate_content → prepare_blueprint → awaiting_agent_imagegen → review_blueprint → awaiting_agent_reconstruct → validate_svg → visual_review → compile → readback → quality_review → awaiting_final_approval / deliverable。它们是既有 deck-builder 内部动作，不是第二套公共工作流。

先完成两张代表页（通常为封面/结论页之一与架构/信息密集页之一）验证风格与可编译性；风格已锁定无需再次向用户索要同一确认。通过后批量处理 pending_pages，失败只返回失败页。代表页选择由 Agent 根据任务判断，不增加必须用户拍板的技术步骤。

## 4.2 ImageGen 输入与事实边界

仅给批准后的 customer-visible 投影：精确标题、结论、正文、数据、必要限定、组件关系、视觉意图、风格/字体、画布。内部证据ID、工具路径、SCR/MBB标签、动作指令、调试说明不得进入图片。需要保留的业务条件和数据口径不能被当作“内部注释”删掉。

Page Package/Content Lock 是文本和事实来源；Diagram View 是组件/关系来源；图片是视觉来源。图片错字、错误数字、箭头反向、漏限定不得回写成新事实。Agent 应按内容锁修复，必要时重生蓝图，不让用户重填材料。

页码/页ID不交给 ImageGen 猜。沿用本项目默认图片蓝图无生产标注；需要客户可见页码时由构建器在明确授权的正式页脚中生成，并进入内容/版式检查。不得趁本轮改架构取消既有客户安全规则。

## 4.3 宿主能力与来源证据

不新增内置 Provider/模型服务，也不强绑具体模型名称。至少检测宿主是否实际提供图片生成、图片阅读、文件回传/写入、SVG生成与工具调用；注册 Skill 不代表工具可用。首次能力状态 unknown 时发真实轻量探针或报告 unknown，不能自动标 ready。

复用现有 blueprint prompt/manifest/provider receipt，区分：

- `host_tool_observed`：宿主确实执行工具并由可信适配器记录输出文件/实际元数据；缺 provider request_id 的宿主写 null 及 metadata_level，不能制造 ID。
- `provider_verified`：工具提供可验证请求/响应字段，按可用字段校验。
- `imported_reference`：用户已有图片；可用于明确的还原任务，但不能充当新 ImageGen smoke。
- `fixture`：仅 deterministic regression，不进入生产或真实能力证据。

以上是 provenance 目标语义，不是增加四个 Provider。Runtime 的本地签名仅证明本地绑定完整性，不声称证明外部服务真实性。若实际工具无法回显任意 nonce，不得要求用户提供服务签名密钥或伪造回显；使用 Runtime action_id、输入hash和宿主观测收据完成绑定，明确证据等级。可疑、无观察或只写“已生成”的结果不能满足 fresh provider smoke。

实际模型名、请求ID和调用时刻来自宿主可得信息；若不可得则 null+reason，不把用户所说“GPT-6 Astra”填写成已验证执行来源。探针与操作证据需要 Codex 核验。

## 4.4 蓝图检查与修复

检查全页、标题、正文、页脚、角落及架构/图表局部。错字、漏字、无依据数字、内部文字、关键关系错误分别记录。小范围文字缺陷可在 SVG 重建中按锁定文本修正，并保存 `approved_delta`（允许的视觉差异）；严重布局/结构问题必须重新生成。不能为了像素一致复制错误，也不能借文字修正任意改掉批准风格。

默认每页每类动作最多3次尝试（首次+2次修复），失败、超时和取消前已经调用的成本计入预算；幂等重复接收同一结果不再次计费/计次数。宿主无法提供 token/cost 时记录 calls 和 elapsed，不虚构金额。预算内可修复问题由 Agent 继续，不要求用户重复说继续；预算耗尽保留已完成页和可读报告。

## 4.5 图片到 SVG 的生成合同

必须加载 `methods/IMAGE_TO_SVG.md` 与当前 compiler-supported subset。输出真实 SVG 和 Scene 旁注，同时保留 stable element_id、component/model_ref、text_ref、asset_ref、layer/group 等映射。SVG 几何与 Scene 的几何约束必须一致；Scene 不得脱离 SVG 独立生成 PPTX。

文本从 Content Lock 拷入，不 OCR 后作为新文本；图像读取用于确定布局和视觉。架构箭头方向同时与 Diagram View 比较。照片/插画为独立登记资产；禁止把整页图片、分块整页图片或业务文字裁片放进 SVG。所有主要图形必须存在可编译原生元素。

Agent 对不支持的 SVG 元素改写为支持子集，不能要求用户安装完整 PPT Master。重建成功后运行真实 SVG renderer、与蓝图比较、原生编辑目标检查；仅写 JSON pass 不算完成。

## 4.6 直接 SVG 与局部修改

`direct_svg` 是明确选择的补充模式，与默认图片蓝图共用 compiler。无 ImageGen 时准确报告缺项，并给出已有可选模式；不能静默切换，也不能伪造一张图片冒充生成完成。用户已提前授权的 direct_svg 路径可直接继续。

单页改字/颜色时，根据用户变更复用原布局，不强制重新 ImageGen。旧蓝图保留为视觉参考，明确新 Content Lock 和允许差异；修改了结构、主要数据或主视觉则重新生成受影响页。无关页面、有效业务决定与历史批准文件不变；当前整套PPTX改动仍需要新版最终批准。


---

<!-- source: specs/05-runtime-readiness-installation.md -->

# 05｜默认路由、任务就绪、安装与执行闭环

## 5.1 能力判断必须按任务

| 任务 | 必需 | 不得作为阻断 |
|---|---|---|
| 原材料理解/方案设计 | 已授权材料读取与文本推理；关键研究需要实际研究工具 | PPT Master、图片生成、历史库、PPTX renderer |
| 默认新页 image_blueprint | 原生编译、图片生成/读取/SVG宿主动作、SVG/PPTX renderer、字体 | 外部 PPT Master 绑定、独立 ppt-* Skill、未使用的 Library |
| 明确 direct_svg | 原生编译、SVG编写/读取、renderer、字体 | ImageGen、外部 PPT Master |
| 编译已有批准 SVG | compiler、当前锁/scene/asset | Web、ImageGen、用户重做主线 |
| 导出当前批准文件 | 文件及当前质量/批准有效 | 无关新生成工具；但新的校验实际需要的依赖不能忽略 |
| 旧 PPT Master Run 继续 | 该 Run 显式记录的旧后端 | 只影响该 legacy 任务，不影响新 native |
| library=none | 无库生产决策 | ppt-lib 可执行程序与资产索引 |
| library=real/auto且已选库 | 实际检索程序、授权索引 | 未使用的旧 PPT Master |

任务就绪输出必须分别有 local_runtime、host_tools、content_inputs、required_missing、optional_unavailable 和 status。`unknown` 不能当 true；`installed`/`contract_declared` 不等于 `verified`。环境变量的 true 或一个 reviewer/skill 名称不能代替真实能力证据。

一份 status 同时说明“软件内核已就绪”和“当前宿主没有图片工具”是合法状态；不得把它混成“需要绑定 PPT Master”。

## 5.2 默认安装与发布树

新默认安装只发布 Deck Master 代码、compiler、contracts、method references 和明确依赖清单；不包含整套 PPT Master runtime/template/workflow、旧同名 Skill 必需链接或默认后端绑定。

source/editable/release-tree/installed launcher 均须走同一 native 路由。`product-capability-manifest.json`、skills/manifest、installer SUITE_SKILLS、release lock、suite-status、setup-status、agent-doctor、rc-gate 的 required 策略统一。

去掉默认外部后端 required 时，新增真实 native capability probe，而不是删除验证或把 backend_ready 写常量 true。native 状态只依赖本次引擎版本、依赖、renderer/字体和真实 probe。更换二进制、SVG子集或环境指纹后旧 probe 失效；用户资料不参与全局软件能力证明。

依赖解析不得 fallback 到 `~/.codex/skills/ppt-master`、外部项目路径或 PATH 中的 `svg_to_pptx.py`。可选 Library 程序按原 SC-1 托管逻辑继续，和用户索引分开；历史资产缺失的无库新建保持正常生产。

## 5.3 CLI 目标增量

以下为需要实现/扩展的接口，不是当前已可执行命令：

```bash
deck-master build prepare --run-dir <run> --profile native --authoring-mode image-blueprint
deck-master build run --run-dir <run> --profile native
deck-master build status --run-dir <run> --output json
deck-master build retry --run-dir <run> --page-id P001 --stage svg
deck-master agent-doctor --mode production --run-dir <run> --output json
deck-master autoplan --run-dir <run> --library-mode none
deck-master build migrate --run-dir <old-run> --to-profile native --dry-run
```

profile/authoring CLI 参数用横线、内部 JSON 用下划线，集中标准化一次。已有 flags 的可用性与命令分组需要 Codex 核验；若仓库有等价入口可复用但必须记录规范示例和测试，不允许只实现内部函数不接 CLI。

`none` 必须出现在共享 parser 及所有 auto/workflow 参数传递，并由 sourcing 输出每页 generate/adapt（仅使用已批准资产时）等真实决策；不写一个空 imported/real selection 骗过 downstream。模式 auto 的运行错误和合法0命中仍要区分。

## 5.4 主状态和入口一致性

`next-step`、`run-state`、`workflow status`、`agent-doctor`、Review Desk、`final-readiness` 读取同一 route/current revision 和 gate resolver。不得新链 completed 但全局仍 needs_builder_backend，再由 final-readiness 强制覆盖成 ready。

返回 awaiting_agent_* 时携带可执行 action：action_id、kind、run_id、build_revision、scope_pages、input_refs/hashes、output contract、acceptance_command、resume_command、remaining_budget、required_tools。现有 action envelope 是承载点，不另建 action 服务。

只缺 semantic_review 时，返回准备/执行/导入语义审查动作，不再返回 render gate。只缺最终批准时，不再重新询问主线/风格。待 Agent 工作与待用户决定严格区分。

## 5.5 原子性、幂等与边界

使用每 Run 写锁或等效并发控制，结果提交时重新计算 input fingerprint（不能相信调用方传来的字符串）。在一个锁周期内比较 expected revision、验证权限/停止状态、验证所有 staged files、切换 committed revision，再生成事件/投影。逐文件 rename 不保证整批原子，必须通过中断测试。[R12]

action_id/run_id/page_id 必须安全且由 Runtime 分配或校验；禁止路径穿越、absolute output、跨run/symlink escape。scope_pages 不能只被写进日志而不被检查；内容任务不能写审批/来源/已批准归档。相同 action+输入+输出重复幂等，相同 action 不同输出冲突拒绝。取消/旧输入的晚到结果留审计，不激活。

多页动作中第2个文件失败、marker写入失败、进程终止后，读取者只能看到完整旧 revision 或完整新 revision。异常应可恢复，不要求用户手工改 events 或 manifest。

## 5.6 问题归属和批准

只补本链路所需 typed questions：已给 Brief 信息、核心主张/反方疑问/证明顺序、主线选择、风格、真实范围与最终导出。专业问题归 Agent；用户真实决定不能以自动推荐代填。合法否定/false/空禁词列表按各自类型接受，不能用全局 vague token 规则拒绝。

问题依赖精确到决定影响的字段/版本；单页配色不能废弃客户目标。已有明确用户选择可以通过 Runtime 写入引用，不重复访谈。不存在授权才提问，不能以“少问”为由跳过最终批准。


---

<!-- source: specs/06-quality-repair-and-delivery.md -->

# 06｜内容、视觉、编辑性与当前版本交付

## 6.1 四种判断不可互相代替

1. 内容成立：方案机制、论证、证据、客户针对性、实施具体度与业务限定。
2. 蓝图→SVG还原：构图、层级、色彩、关键元素、关系方向与批准的允许差异。
3. SVG→PPTX编译：文本/对象/分组/几何/样式是否保持，是否原生可编辑。
4. 正式交付：当前文件是否经过有效安全扫描、语义/视觉评审以及对应版本的用户批准。

图片漂亮不等于内容正确；SSIM高不等于箭头方向正确；PPTX能打开不等于原生编辑；门禁报告存在不等于检查当前版本。

## 6.2 必需门与精确匹配

新 native production/benchmark/client_delivery 保留当前 render、delivery、customer_visible_safety，并必需当前 `semantic_review` 和完成的 native readback/visual proof（可通过既有render/delivery门消费，不要求再造并行门框架）。

语义门只接受 explicit scope=semantic、受支持 schema、完整六维/页覆盖、当前内容指纹的报告。不得用 `external_*` 名称前缀接受 external_visual/external_evidence 为语义通过；不得仅 reviewer+pass。语义审查调用必须真正接到宿主，不能靠工程计数模拟专业判断。[R10]

P0/P1 findings 优先于 summary；P0不可豁免。P1仅按明确既有政策、当前版本与真实用户授权可覆盖，并保留记录。结构性缺失（关键文字/关系丢失、整页图片冒充、未知执行结果）不能当普通风格偏好豁免。

## 6.3 当前性指纹

内容审查指纹包含实际被引用的 Page Package 文件内容、Narrative/Solution/Diagram相关版本和来源快照，不仅 index.json。修改package但不更新index必须判stale。

视觉检查指纹包含内容锁、style、approved_delta、blueprint实际图hash、SVG、scene、assets、renderer/字体配置。编译/回读再绑定 compiler/subset版本、PPTXhash、page order和trace。最终批准绑定整套导出文件的hash集合及revision。

索引不一致属于输入损坏，不忽略坏文件或丢失页面继续生产。历史结果/门禁只读，不以重写timestamp“刷新”。

## 6.4 视觉测量与人工量规

蓝图→SVG应组合全页感知结构、文字屏蔽比较、关键区位置、图标轮廓/方向、图表关系、业务文字与内容锁一致性；不得由某单一分数代替人工/视觉模型的语义判断。允许的文字纠错差异来自用户改动或内容锁纠错任务，必须明确列出。

SVG→PPTX沿用固定环境0.97 text-masked SSIM和0.75pt关键几何基线，并做精确文字、对象类型/数量/分组/层序回读。[R06] 这些数字是保留的规范阈值，不是本轮已经测得的结果。

新图片→SVG效果量规采用1—5分：构图层级、图形关系、文字可读性、风格一致性、整体可用性。真实七类样页平均≥4.0、各页≥3.5；不得有关键内容/关系错误；这是本轮目标，未测结果不能填通过。数据故事与架构至少一页必须人工检查箭头/数值/单位，不能只看缩略图。

## 6.5 受控资产与图片占比

保留既有高密度对整页图、隐藏文字层和未登记资产的限制。新 native 先继承已有35%单资产/50%合计的严谨默认，不在提取时放宽；纯照片型封面确有需要时，以已批准资产策略例外单列且不能含业务文字/图形。所有例外属于可解释页面类型，不是“主要内容都图片化”的通行证。

图片中的数据、标签、箭头如果属于主要业务表达，应重建为原生对象。外部图片可以作为照片/插画对象保留，不承诺它的像素天然可编辑。

## 6.6 修复闭环

findings 必须含对象、输入版本、观察、依据、严重级别、修复归属、允许修改页、期望状态和重验动作。处理顺序：事实/关系→内容→结构→视觉→编辑性→安全/交付。Agent主动完成预算内修复，用户只处理真实业务取舍。

证据不足可补研究、缩小主张、标明工作假设、移除不支持数字；不能编造来源。架构关系改动必须检查相关正文/实施页；局部视觉改动仅重建受影响页和整 deck 聚合，不重新规划全套。

预算计失败工具调用与编译/重建重试，不只统计 commit。新动作ID不重置同finding预算。达到上限返回 blocker、已尝试策略、影响与可继续的明确动作；不跳过失败页或自动改fixture。

## 6.7 正式文件安全与批准

PPTX可见文本、备注、隐藏页、元数据、alt text、关系引用均在正式导出扫描范围。内部命令/绝对路径/原始私有证据不落客户文件。必要业务条件和可公开引用允许安全呈现；不得为了清理生产标记一并删除其业务意义。

内容批准、风格批准和最终文件批准分开。final-readiness ready/awaiting_approval 的准确语义与export权限统一；file存在、质量通过不能冒充用户最终批准。批准后改字、页序或编译版本会产生新文件，旧批准不迁移到新hash。旧批准文件仍可下载/导出其原版本，但清楚标识不是最新修订。

Review Desk只补状态/产物/审批绑定展示，不引入视觉重设计。原生PPTX修改后的文件回读应作为同一Run新revision进入，而不是用户手工覆盖历史文件。


---

<!-- source: specs/07-migration-compatibility.md -->

# 07｜旧 Run、安装目录与审批的无损迁移

## 7.1 新旧分流

| 对象 | 默认动作 | 可选继续方式 |
|---|---|---|
| 新 Run | 固定native+image_blueprint | 用户显式direct_svg；不存在隐式外部fallback |
| 旧高密度Run/已批准SVG | 只读旧schema/路径及批准文件，能力内核复用 | legacy-HD adapter继续旧路径；显式迁移native |
| 旧标准PPT Master Run | 展示旧engine，不触发绑定安装 | 明确继续legacy或迁移；只有legacy需要其绑定 |
| 无法判定旧profile | 只读且提示migration_required | 给证据和计划，不猜测覆盖 |
| 用户已有PPT Master目录/全局Skill | 不探测用于默认生产，不删除、不占有 | 用户单独使用；迁移计划显式列明所有权 |
| 已批准客户产物 | 文件和hash/approval保持 | 迁移后生成新revision并重新批准 |
| 历史库/客户源材料 | 原位置受授权策略管理 | 不因软件升级/卸载删除 |

兼容不是继续把 legacy 后端标为全局required。旧目录名中有ppt-master或HD不意味着新Run应使用它。只读diagnosis/export历史文件不得执行旧backend副作用。

## 7.2 dry-run → apply → verify

迁移计划列出源Run/schema/指纹、目标route、字段与路径映射、缺失证据、保留对象、将失效的gate/approval、新revision位置和回滚方法。计划哈希绑定源版本；执行时输入变更则拒绝旧计划。

apply在副本/新revision中执行，不改源归档。全部合同和原生构建通过后才更新current，失败保持原版本。migration不继承已过期报告，不重新签旧provider来源，不把模板/自证的旧证据变supported。歧义source/evidence引用先报告，不猜测。

## 7.3 Page Package 与 MBB 映射

Canonical Page Package status使用已发布schema的`ready_for_build`；SC-1 生产写方/消费者的`ready`差异必须由单一adapter解释。旧ready只在package结构完整、对应批准/来源证据有效时转换；没有证据不能通过状态改名升级为生产就绪。[R03][R09]

公共Narrative→Content Lock→MBB projection保持page/claim/component ID映射，旧MBB用户选择只有在输入候选集合/内容仍一致时可作为引用；推荐候选并不自动成为用户批准。迁移说明列出不再执行的重复MBB动作。

HD新旧错误码可兼容映射，但同一错误只由一个核心解析器和校验器判定。旧Scene/锁定版本继续可读；必须升级时使用显式adapter，不能静默丢字段。

## 7.4 发布、回滚与安装所有权

新release移除默认外部后端required链接和发现逻辑；旧managed backend保留数据标识，可独立清理但不自动删除。manifest中legacy entries标optional/compatibility并从默认required分离。不能把第三方已有real dir替换成Deck Master链接。

激活新release前运行真实内置compiler+render smoke；来源指纹或依赖检查不满足不切current。release回滚只回软件；新schema数据不逆向改写。旧程序不能安全写新数据时只读并给明确信息，不能覆盖新数据。

## 7.5 原 SC-1 验收处理

本包替换：A-03从“托管PPT Master”改“内置原生真构建”；A-08从“标准无需ImageGen”改“显式direct_svg无需ImageGen”；P-03从两产品后端一致改为同内核两authoring方式内容一致。其余涉及后端身份的条件按映射表替换。

保留：真实Library、研究、材料深读、语义质量、用户投入和三类真实方案配对目标。不是只保留一个短smoke就宣布SC-1全部accepted。原88项都有retain/replace/clarify映射；执行结果另填，禁止把superseded当passed。


---

<!-- source: specs/08-delivery-and-acceptance.md -->

# 08｜交付工作包、验收与状态

## 8.1 三个工作包

WP-N1 内核独立：产品约束/manifest/readiness修改，编译器提取，干净安装真构建。

WP-N2 默认生产：公共Narrative/Package→Content Lock、图片蓝图、SVG重建、调用方接线、none路径、低输入交互。

WP-N3 交付收口：当前语义与视觉门、原子修订、批准、旧Run迁移、真实UAT和文档。

所有工作包共同负责默认全链路；不得把WP-N1安装成功当整轮完成。代码可以五个PR或同一修订分支多提交，详见tasks/DELIVERY_PLAN.md。

## 8.2 验收层级

L1：纯代码/合同/状态/异常回归；允许显式fixtures，用来检查输入和不变量。
L2：真实编译、实际SVG/PPTX渲染、原生编辑、宿主工具生成与还原、隔离安装、完整入口。内容可合成，工具执行必须真实，不需要客户敏感数据。
L3：真实授权客户样本的质量/用户投入配对；沿用SC-1方法与阈值。

没有ImageGen/桌面编辑工具可以如实blocked对应L2，不能把fixture结果填为pass。没有客户素材只影响相应L3，不影响用合成内容跑真实工具的责任。

## 8.3 必测真实场景

T1 干净安装+两页：封面/结论页和架构页，native默认，不存在外部PPT Master、绑定、独立Skill。真实ImageGen→SVG→PPTX→渲染/回读。

T2 七类固定样页：framework、process、table、comparison、architecture、data_story、dense_narrative；继承既有回归并增加中文长文本、半透明/0值、分组/方向等压力样例。

T3 完整8—12页Solution Deck：只有原材料/目标/授权；无历史库；真实研究缺口由宿主处理；Agent完成内容、图形和定向修订，用户最终批准。用户不得先提供逐页稿来补系统能力。合成授权案例即可验证L2，不计真实客户效果。

T4 单页修改+并发迟到：修改标题/颜色与修改架构关系两种；检查影响集、无关页保留、旧结果拒绝、取消/预算、最终批准失效。

T5 旧HD和旧standard迁移：只有批准文件时可读；有源SVG时受控迁移；无backend的新native不受legacy缺失影响。

T6 显式direct_svg：没有ImageGen也可完成明确授权模式，不能拿它替代T1默认图片链验收。

## 8.4 发布证据

每条记录源码SHA、安装来源/清单、OS/Python/依赖/字体/renderer版本、宿主实际能力、输入和输出hash、命令/工具日志、失败与重试、原生编辑证据、gate/approval绑定。公开仓只提交安全摘要；原始客户资料和provider返回留授权本地。

所有case初始not_run；spec自检只验证目标schema/examples/引用，不得自动改产品验收状态。作者报告或远端CI也不能替代干净环境与本地宿主L2证据。

## 8.5 SC-1内容效果验收继承

原三类真实案例×两次配对保留：用户主动时间中位数下降≥30%，初稿实质可保留页≥70%，六维评分总体+0.5/5；基线高分天花板规则沿用原文。[L01]

若旧标准被后端阻断，不安装/绑定它只为制造本次baseline；优先使用有可追溯材料的历史实际流程或旧HD有效产出，明确对照条件。没有可比baseline标N/A及outcome_pending，不能把失败算0并宣称超额提升。不得变更对照对象后仍声称是相同模型/预算配对。

## 8.6 状态表达

- in_progress：native内核、默认图片链、公共内容接线、当前gate/approval、必要迁移或任何工程mandatory case未闭环。
- engineering_complete / outcome_pending：全部本包mandatory L1/L2真实执行通过，仅SC-1真实客户效果L3未闭环。
- accepted：本包工程通过且被继承的SC-1质量/用户投入要求按真实证据完成。

若用户只批准工程里程碑，记录该里程碑，不把整轮状态改accepted。最后交付报告必须清楚写“外部PPT Master不再必需”的实际隔离证据及仍需的宿主/系统工具。

## 8.7 被继承工程项的状态

原SC-1映射中retain/clarify的工程要求也必须有可核验通过证据，或在本轮补测；可复用与实际代码版本匹配的既有证据，不重复开发，但不能仅凭PR正文认领。若这些必需工程项仍欠实现/接线，不得因本包64项通过就宣布完整SC-1工程完成。可选Library任务未执行不得宣称“历史资产链已独立验收”；其影响范围和里程碑单列，不能用none替代全部Library承诺。


---

<!-- source: tasks/DELIVERY_PLAN.md -->

# 开发组织｜三个工作包、五个增量PR

## 分支策略

本次在线基线中PR30尚未合并。优先从`4977f89`或其已核验最新后继建立新worktree/修订分支，以PR30 HEAD为增量评审基线；若PR30未合并，采用stacked PR，说明依赖，不把base-to-main的全部SC-1代码再次当成本轮新增。若PR30已合并，从包含其成果的main开发。

不得因需要新baseline强制合并PR30；不得自动push/merge、force push、清理旧分支或删除未提交工作。用户要求的是本轮Spec，不是已授权修改仓库。实际开发时按仓库贡献流程提交。

## 五个建议PR

| 交付段 | 任务 | 依赖 | 必须有的合并证据 |
|---|---|---|---|
| N1 内核提取与契约 | ND-01 | Q0 | compiler不读HOME/不调用PPT Master；七类差分；状态与契约映射 |
| N2 默认路由与独立安装 | ND-02 | N1 | native默认；manifest/doctor/next-step一致；none真实CLI；无外部目录/绑定的安装真编译 |
| N3 公共内容到图片/SVG主链 | ND-03 | N1+N2 | public narrative/Package→lock→图片→SVG，不重复MBB；真实宿主两页；已批准SVG不再问图工具 |
| N4 门禁、修订和审批 | ND-04 | N3；部分测试可并行 | 精确语义门、实际内容指纹、缺门路由；多文件原子、迟到/取消、预算、最终批准 |
| N5 迁移与整轮验收 | ND-05 | N1—N4 | 8—12页实际Solution流程、七类页、原生编辑、旧Run/数据回滚；SC-1验收映射 |

五段是执行建议，不是必须创建五个远端PR；若并为一个PR，仍需独立可审查提交和上述证据。每个PR展示已经完成/待验证/未实现，不因单元测试绿灯提前宣布整轮完成。

## Q0（开工检查，不单独扩成长期项目）

核对HEAD差异、用户修改、PR30真实测试基线；绘出新默认入口到实际函数的调用图；盘点高密度纯编译依赖；确认schemas与ready状态冲突；记录宿主/renderer/字体/真实素材可用性；登记全部旧约束替换位置。先加反例测试（无binding、none parser、语义误匹配、第二文件中断），再实施修复。

## Agent分工

Compiler Agent只改native core与兼容adapter；Workflow Agent负责CLI、route、questions、actions和state；Quality Agent负责readback/gates/approval联动；集成负责人单点收口共享manifest、stage-contracts、CLI、final-readiness与release。不得并行各写一套registry或编译器。

并行工作基于稳定编译contract，业务事实/主线contract不复制。每段交付source SHA、文件、入口调用、测试、差异、已知未闭环与验收ID。真实工具缺失要列实际依赖，不允许以PPT Master绑定作为native替代条件。


---

<!-- source: tasks/ND-01.md -->

# ND-01｜公共原生编译内核

责任工作包：WP-N1。具体文件落位与本地调用关系**需要 Codex 核验**。

## 输入与依赖
现有high_density编译、SVG parser/paint、visual/readback和七类样例。

## 实现要求
提取单一native编译包；Run/旧HD使用薄adapter；支持矩阵+版本+fonts/canvas；原生文字/形状/group/path；输出真实trace。

## 修改边界
只改compiler/normalizer/adapter和相关测试；涉及业务规划/审批由集成方协调。

## 禁止替代
不能调用外部PPT Master；不能整页图或text→path；不能删既有可验证SVG特性；不能用复制两套代码代替提取。

## 验收
对应本包 CMP-01—CMP-10，GOV-02，IND-01。每个实际执行case填写commit、真实命令/工具、环境、输入输出hash、结果与限制。Schema自检不计产品case。

## 交付物
提交实际调用方接线、生产/失败测试、更新的方法/合同映射、最小回滚方案与未闭环说明。对既有功能先保留回归，再证明新路径真正在CLI/Agent操作下被执行。仅实现模块但无调用方，不算本任务完成。


---

<!-- source: tasks/ND-02.md -->

# ND-02｜默认路由、任务就绪与无库入口

责任工作包：WP-N1。具体文件落位与本地调用关系**需要 Codex 核验**。

## 输入与依赖
ND-01窄接口与Q0调用图。

## 实现要求
新Run默认deck_native/image_blueprint；旧profile分流；task_readiness一致；none parser至sourcing全接通；发布/安装不要求ppt-*入口或整包；读取旧外部环境不影响native。

## 修改边界
CLI/registry/installer/setup/doctor/next-step/rc由集成负责人单点合并。

## 禁止替代
不能只取消门禁；不能把安装有SKILL等同host有工具；不能静默direct_svg或fixture fallback。

## 验收
对应本包 IND-01—IND-08，WF-01—WF-02。每个实际执行case填写commit、真实命令/工具、环境、输入输出hash、结果与限制。Schema自检不计产品case。

## 交付物
提交实际调用方接线、生产/失败测试、更新的方法/合同映射、最小回滚方案与未闭环说明。对既有功能先保留回归，再证明新路径真正在CLI/Agent操作下被执行。仅实现模块但无调用方，不算本任务完成。


---

<!-- source: tasks/ND-03.md -->

# ND-03｜公共内容→图片→SVG真实生产

责任工作包：WP-N2。具体文件落位与本地调用关系**需要 Codex 核验**。

## 输入与依赖
ND-01+ND-02，保留PR30内容成果。

## 实现要求
规范ready_for_build、Content Lock公共来源、MBB派生；宿主实际ImageGen/图像读取/SVG重建；按真实subset方法执行；支持代表页与批量pending；已知决定不重复问。

## 修改边界
Producer/Planner/HD适配、Blueprint/Scene/方法稿；不重写方案体系。

## 禁止替代
不能从图片创建事实；不能要求用户先写逐页稿；不能为可用工具伪造request ID；推荐主线不能当已批准。

## 验收
对应本包 CNT-01—CNT-07，HST-01—HST-07，WF-03。每个实际执行case填写commit、真实命令/工具、环境、输入输出hash、结果与限制。Schema自检不计产品case。

## 交付物
提交实际调用方接线、生产/失败测试、更新的方法/合同映射、最小回滚方案与未闭环说明。对既有功能先保留回归，再证明新路径真正在CLI/Agent操作下被执行。仅实现模块但无调用方，不算本任务完成。


---

<!-- source: tasks/ND-04.md -->

# ND-04｜当前质量、版本修复与批准

责任工作包：WP-N3。具体文件落位与本地调用关系**需要 Codex 核验**。

## 输入与依赖
ND-03主链，可提前写反例。

## 实现要求
semantic精确类型/覆盖、逐文件hash、next-step缺门动作；作用域权限/CAS/不可变revision+原子pointer；失败预算；旧结果/取消；备注/隐藏页/metadata扫描与当前批准。

## 修改边界
workflow.actions/gates/final-readiness/delivery/review及最小UI状态；复用现有envelope。

## 禁止替代
不能把逐文件rename说成整批原子；不能用外部视觉审查满足语义门；不能复用旧批准导出新文件。

## 验收
对应本包 WF-04—WF-08，QA-01—QA-08。每个实际执行case填写commit、真实命令/工具、环境、输入输出hash、结果与限制。Schema自检不计产品case。

## 交付物
提交实际调用方接线、生产/失败测试、更新的方法/合同映射、最小回滚方案与未闭环说明。对既有功能先保留回归，再证明新路径真正在CLI/Agent操作下被执行。仅实现模块但无调用方，不算本任务完成。


---

<!-- source: tasks/ND-05.md -->

# ND-05｜迁移、真实验收和文档收口

责任工作包：WP-N3。具体文件落位与本地调用关系**需要 Codex 核验**。

## 输入与依赖
ND-01—ND-04。

## 实现要求
旧HD与standard只读/继续/显式迁移，失败回滚；真实8—12页+七类页+桌面编辑；补主Playbook/AGENTS/旧Spec指向；原88项映射逐条认领；记录SC-1真实效果状态。

## 修改边界
migration/release/acceptance/docs及必须修复；不新建团队功能。

## 禁止替代
不能把取消external backend验收当删除真实生产验收；不能以缺客户资料免做合成内容真工具测试；不能擅删旧目录/客户数据。

## 验收
对应本包 GOV-01—GOV-04，MIG-01—MIG-06，UAT-01—UAT-06。每个实际执行case填写commit、真实命令/工具、环境、输入输出hash、结果与限制。Schema自检不计产品case。

## 交付物
提交实际调用方接线、生产/失败测试、更新的方法/合同映射、最小回滚方案与未闭环说明。对既有功能先保留回归，再证明新路径真正在CLI/Agent操作下被执行。仅实现模块但无调用方，不算本任务完成。


---

<!-- source: contracts/README.md -->

# 目标契约与接口

本目录四份 JSON Schema 是本轮需要实现的窄接口，不代表 PR #30 已有这些接口。其余 Context/Narrative/Page Package/Scene/Content Lock/Blueprint/Review/Render 等继续复用现有合同，必要字段见 [EXTENSION_DELTAS](contracts/EXTENSION_DELTAS.md)。不把整个仓库所有schema重写一遍。

| 目标合同 | 用途 | 持久化/调用边界 |
|---|---|---|
| deck_build_route.v1 | 固定引擎、authoring模式、密度和原运行模式 | request中的build_route；Runtime拥有 |
| deck_native_compile_request.v1 | 单次确定性SVG编译的输入集合 | Run adapter→compiler；只读已批准文件引用 |
| deck_native_compile_result.v1 | 编译结果、逐页对象摘要与trace | compiler→Run adapter；不能授权导出 |
| deck_task_readiness.v1 | 按任务区分必需、未知和可选依赖 | doctor/status等共用投影 |

所有文件引用相对明确的Run/bundle根，需检查路径真实解析、symlink逃逸、run_id/hash/版本/批准；JSON Schema 只做结构校验，不能代替文件存在和语义检查。

四份合同不需要新的外部服务，既有Runtime负责生成与接受。目标文件名可按仓库惯例调整并登记，但枚举/必要字段/边界和验收不能丢失。现有manifest/schema若additionalProperties:false，必须同步版本/引用/消费方；不能假设新增键天然兼容。

`examples/`中的文件均为合成结构示例；其中的hash、receipt和路径未对应真实产品产物，仅验证Schema。真实smoke必须重新生成并记录真实文件。


---

<!-- source: contracts/EXTENSION_DELTAS.md -->

# 既有合同的最小增量与接线要求

| 对象 | 本轮字段/语义 | 写方和校验 |
|---|---|---|
| request | build_route；创建时origin_run_mode和策略不可被Agent重写 | Runtime；旧Run读取adapter；新默认native |
| build_manifest | engine_id/version/subset_version、build_revision、canonical_revision_ref、per-page输入hash与产物 | Run adapter；编译完成不等于delivery_ready |
| render_result.v2 / artifact_manifest | 来自同一committed revision、相对产物路径、实际文件hash、render/compile状态与native编辑属性 | 引擎；现有字段映射，不新建第二套正式导出产物 |
| narrative_plan | 新Run的唯一选定主线；基于资料、方案与用户有效决定 | 公共Planner；recommended≠approved |
| Page Package v1 | canonical status=ready_for_build；现有claim/evidence/design/diagram refs真实 | Producer；有条件迁移legacy ready；坏文件不忽略 |
| content_lock | narrative_ref/hash、package_ref/hash、source_refs、精确文字、style/ref、visibility与版本 | Runtime快照；不允许蓝图任务修改事实 |
| MBB旧投影 | derived_from narrative/lock及hash、projection_only=true等效标识 | 单向adapter；无独立新主线写权 |
| blueprint manifest/receipt | authoring origin、host实际执行证据等级、actual_image_hash、content/style/action绑定、allowed_delta | 既有receipt扩展；null元数据不得虚构；签名不代表服务真实性 |
| page_scene | 引用同一SVG/Content Lock、node/edge/model_ref、text/asset/editability、geometry校验 | 重建Agent；SVG仍是实际视觉源 |
| external review v2 | scope严格semantic、review coverage、逐package内容hash与方案/来源依赖 | 独立审查任务；不是前缀匹配或声明pass |
| action envelope | run_id/revision、输入与输出hash、scope、permission、attempt预算、cancel/supersede状态 | 既有workflow.actions扩展；CAS与写锁在真实调用方生效 |
| approval / final lineage | current revision + export artifact hash集合；批准人来源 | 用户决定+Runtime；不接受模型代批准 |
| capability lock / suite registry | bundled deck_native；legacy ppt-master标optional compatibility | 发布/安装；系统工具与宿主状态分开 |

## Canonical status兼容

新写入只写ready_for_build。读legacy ready时先检查来源/合同/批准有效性；通过后在迁移revision写规范值并保留original_status。draft/blocked/stale不能通过字符串替换变成ready_for_build。额外的original_status放入既有兼容metadata或迁移报告，不强行塞进不允许额外字段的schema。

## 构建revision与指纹

定义`content_fingerprint`为带顺序的page_id+各实际Package内容hash+公共Narrative/Solution/Diagram及使用来源指纹集合；`visual_fingerprint`再加入blueprint/svg/scene/assets/style/allowed_delta；`build_fingerprint`再加入compiler/subset/字体/renderer与输出profile。hash算法和canonical serialization固定并测试。

不得使用时间戳、文件名或仅index hash代替内容依赖；也不要因无关材料添加导致所有内容决定失效。核心内容变更和视觉变更分别决定需重跑哪些检查，但新的整体PPTX必须绑定新的最终批准。

## 状态动作输出（既有状态的目标扩展）

返回`awaiting_agent_build`/既有同义状态时，next_action含kind、run_id、action_id、expected_revision、scope_pages、input_refs、output_refs、required_schema、acceptance_command、resume_command和budget。缺真实工具返回blocked+capability明细；缺业务决定返回awaiting_user_decision+一个具体问题。保持旧状态兼容映射，不增加平行Run状态机。

## 小型内部编译边界

compiler只读批准输入、产生PPTX和trace。它不读用户HOME、不联网、不调用PPT Master、不选择主线、不处理审批。render adapter处理真实渲染。最终文件识别仍由Deck Master现有artifacts/lineage接口承接。

## 内容批准与逐页人工操作

编译请求中的approval_ref可引用符合现有政策的内容批准或预授权记录；不新增每页必须用户手工签字的关卡。Runtime验证该记录作用域、来源与当前内容hash。最终交付仍需当前整套文件的用户批准，技术内容校验不得冒充最终批准。


---

<!-- source: methods/IMAGE_TO_SVG.md -->

# 生产方法｜从真实图片蓝图重建可编辑SVG

由既有deck-builder按阶段加载；这是方法参考，不是新增公开Skill。执行前只检查本次变动相关的输入和工具，不重做已确认主线访谈。

## 输入

当前Content Lock、实际图片（不是文件名描述）、style lock、Diagram View（适用时）、asset manifest、compiler-supported SVG subset、page_id/action_id/revision与修复范围。关键输入缺失返回可定位任务，禁止凭空补齐。

## 执行

先读完整图片理解层级、网格、留白、背景和主要组件；再检查标题/正文/关系图和角落。提取的是视觉组织，不从图片重新认定事实。所有文字、数字、符号、单位和业务限定从Content Lock读取并定位text_ref。

按语义组件建立group与stable element_id，文字用text/tspan，框和业务图形用shape/path，连线/箭头用原生路径；Scene携带component/model_ref及必要几何。照片单独绑定登记资产；不得用整页或拼图截图替代主要内容。

仅输出支持子集。复杂效果优先用可编译的简化视觉，不改变事实与层级；需要明显改变已批准设计时给出差异，不静默转换为位图。路径的绝对/相对坐标、transform和样式由公共normalizer检查。

重建后实际渲染SVG，逐项核对：关键文字是否全在、关系方向是否正确、图表值与单位是否一致、重点层级与蓝图是否一致、有没有溢出/非法覆盖/内部文字、是否每个主要业务对象都可单独编辑。蓝图本身有错时，按锁纠正并记录allowed_delta，不抄错。

## 返修

只修当前pending/rework页面。已完成无关页的内容/几何/hash不改。小型文字或颜色改动复用视觉结构；结构性变动返回新蓝图阶段。失败记录问题位置、观察、改动和下一次验证，预算内继续；预算耗尽留已完成页并报告，而不是要求用户从头解释任务。

## 输出

approved候选SVG、Scene语义旁注、生成/修复结果指纹和实际验证记录，由acceptance_command接收；Agent不写runtime seal、approval或正式current pointer。不能仅写pass。完成接受后执行resume_command，直到交付批准点或真实阻断。


---

<!-- source: methods/QUALITY_REPAIR.md -->

# 生产方法｜专业审查与定向修订

先明确审查对象与版本，读取当前内容、来源、方案关系、实际SVG和最终PPTX渲染。内容、视觉、编译、交付四类问题分别记录，不以“好看”代替业务判断。

合格finding示例（合成）：

“P004/edge.crm_to_country 的箭头与 diagram view 的总部向国家市场发布方向相反；目前图上是国家→总部。保留节点和布局，仅将该边方向修正，并核对正文仍表达总部发布、国家本地化。重验该边SVG、PPTX对象方向与相关P003文字；不改其他页。”

不合格：“架构不专业，请优化。”

缺依据时明确是事实无支撑、仅设计前提、数字口径不符，还是用户真实取舍未决；分派到研究、方案、内容或图形任务。不能把缺证据问题一律扔回用户，也不能为过门虚构来源。

修复后独立检查具体finding是否解决，并检查相邻对象是否回归。仅变更部分页面可复用未变页的已绑定检查，但整deck的新文件hash仍需当前版本最终批准。

审查报告必须覆盖必要页面和六维内容量规，引用观察和版本。仅改reviewer字符串不是独立审查；以独立执行任务/上下文和完整输入记录支撑，宿主无法提供时准确报告证据等级，不伪造身份或签名。


---

<!-- source: acceptance/MATRIX.md -->

# SC-1.1 Native Deck Core 验收矩阵

共64项；全部初始not_run。L1允许显式fixtures；L2必须真实工具；L3为真实客户效果。产品测试、环境与证据需要Codex核验。

| ID | 目标 | 层级 | 输入/动作 | 必须结果 |
|---|---|---|---|---|
| GOV-01 | 旧约束正式替换 | L1 | 原SC1 D04及多处Agent/验收指引；比对所有执行入口 | 默认不再要求PPT Master；旧文有superseded指向；未冲突要求保留 |
| GOV-02 | 没有整库换名内置 | L2 | 默认release安装树；核对依赖闭包和运行调用轨迹 | 仅本仓公共内核/必要组件；无完整上游workflow/后端项目运行依赖 |
| GOV-03 | PR30基线保护 | L1 | PR30仍open或已有后继、用户未提交修改；建立增量工作分支和差异图 | 不擅merge/reset/revert或删除用户内容；明确实际基线 |
| GOV-04 | 工程与效果状态分离 | L1 | 存在未执行L2与仅缺L3两种情况；生成交付总结 | 前者in_progress；仅全部工程闭环后可outcome_pending；superseded不当passed |
| IND-01 | 隔离默认安装真编译 | L2 | 新HOME，无外部PPT Master/Skill/binding/PATH fallback；安装release并真实native compile/render | 主要对象原生且有实际产物；未读取/安装/绑定外部产品 |
| IND-02 | 不隐式克隆或调用外部产品 | L2 | 默认任务已授权宿主工具，外部后端路径设为哨兵；运行默认链并记录文件/进程访问 | 无git clone PPT Master、无外部svg_to_pptx命令、无哨兵访问 |
| IND-03 | 默认入口一致 | L2 | 同一新Run；分别CLI、主Skill、next-step、doctor、Review Desk、final-readiness | 统一native route与revision；无backend bind提示或例外强行覆盖ready |
| IND-04 | library none真入口 | L2 | 没有ppt-lib和索引；CLI autoplan --library-mode none并resume/autopilot | 参数被接受；不调用库/不产生伪real selection/不使用fixture；每页生产决策真实 |
| IND-05 | 宿主未知不伪报就绪 | L1 | 只存在Skill声明，没有真实工具检测；查询image_blueprint task readiness | host=unknown/blocked；软件已装不等于图片工具可用 |
| IND-06 | 可选依赖不污染任务 | L1 | native必要依赖齐，legacy/backend/library缺失；查询编译、无库新建和旧Run继续三任务 | 前两不被legacy阻断；旧任务缺项明确只影响其自身 |
| IND-07 | 安装产物可脱离源码目录 | L2 | release已安装，原checkout隔离；从installed launcher运行编译/图形方法/schema检查 | 包内引用可达；无源码绝对路径；没有缺schemas/methods |
| IND-08 | 显式direct与禁止静默fallback | L2 | ImageGen缺失，有SVG能力；分别默认image与已授权direct_svg | 默认准确阻断；direct执行真实内核；不伪造图片来源 |
| CNT-01 | Package状态规范 | L1 | ready_for_build、legacy ready、draft三组；按producer→build真实接口验证 | 规范值通过；legacy有凭据才迁移；draft不被字符串洗白 |
| CNT-02 | 消费当前真实内容 | L2 | Package正文改变、旧preview未变；默认native build并回读 | 最终文字来自新Package，不使用旧preview/模板占位 |
| CNT-03 | 内容锁只由公共内容产生 | L1 | 批准Narrative/Package与图片中错误文字；建立锁并重建SVG | 不从图片回填事实或证据；仅修复图片表达 |
| CNT-04 | MBB单向投影 | L2 | 已有有效公共主线和用户选择；进入默认Builder及兼容HD | 无新MBB访谈/第二主线；projection hash追随公共源 |
| CNT-05 | 推荐不等于选择 | L1 | 有recommended candidate但无必要用户选择；推进须用户裁决的叙事取舍 | 不把推荐自动签成批准；已有明确选择不重复问 |
| CNT-06 | 架构和数字跨视图一致 | L2 | 蓝图边方向错误、单位与锁不一致；Agent重建+回读+内容检查 | 按模型/锁纠正并记录delta；PPTX和正文一致 |
| CNT-07 | 原材料冷启动无循环 | L2 | 仅已有原材料/目标/授权，无逐页稿/Package；主入口运行至页面生产 | 先实际形成方案/主线再产出非空Package；不要求空Package作前置 |
| CMP-01 | 单内核提取差分 | L2 | 相同七类SVG/Scene/Lock/assets；提取前后编译比较对象/视觉 | 语义/几何/层序无非授权退步；不靠ZIPhash唯一判等 |
| CMP-02 | 文字真正原生 | L2 | 中文长文本、英文、数字和单位；编译/桌面编辑一个文字框/保存再开 | 文字可改，不是轮廓/图片；关键文字完整准确 |
| CMP-03 | 主要形状路径原生 | L2 | 架构节点、箭头、曲线、图例；编译并编辑节点与路径 | 独立原生对象；关系/方向可追踪 |
| CMP-04 | 分组与层序 | L2 | 嵌套分组/遮挡/透明叠层；编译回读并修改group | 分组真实、层序/几何一致；主元素不丢 |
| CMP-05 | 零透明度等边界 | L1 | opacity=0、gradient stop alpha=0和正常渐变；共享parser→compiler→paint inventory | 零值不变一；验证与编译支持同一子集 |
| CMP-06 | 支持矩阵与unsupported | L1 | 支持的path/transform/use与脚本/外链/非法滤镜；校验和编译 | 已支持子集回归不退；不支持精确报element；不静默删/栅格化 |
| CMP-07 | 坐标和非16比9源 | L2 | 不同viewBox和旧1672x941样例；统一contain映射到16:9 | 无拉伸/错比例；文字stroke和effect坐标一致 |
| CMP-08 | 资产和路径边界 | L1 | 未登记图、跨Run、../、absolute、symlink逃逸；导入编译请求 | 输入拒绝且不访问越界；登记照片为独立对象 |
| CMP-09 | 无整页套壳 | L2 | 整页PNG、SVG图嵌入、分块拼图、隐藏字层和正常原生页；对象检查和实际编辑 | 伪编辑全部拒绝，主要业务图形原生页通过 |
| CMP-10 | 编译与回读错误不伪完成 | L2 | 字体/renderer缺失、对象漏失、PPTX渲染失败；真实构建与失败注入 | 准确blocked/failed，无completed/客户ready；实际trace有效 |
| HST-01 | 新图片真实生成 | L2 | 批准内容与具备图片工具的宿主；实际生成蓝图再读取 | 保留真实输出hash/action与可得元数据；fixture/旧参考不计fresh |
| HST-02 | 不伪造服务元数据 | L1 | 宿主无request_id或nonce回显；接受host观测产物 | null+证据等级可解释；不造ID/签名；无观测声明不算真实执行 |
| HST-03 | 锁定内容与蓝图隔离 | L2 | 图片错字/漏限定/含内部标注；蓝图审查与SVG重建 | 纠正事实/标注，保留业务限定；证据ID/路径不露出 |
| HST-04 | 图片与SVG实际比较 | L2 | 有实际蓝图和一次布局失败SVG；渲染全页与关键局部比较 | 识别失败并定向修复，不能只写pass |
| HST-05 | 代表页与批量继续 | L2 | 锁定风格，代表页通过，其余页部分失败；处理pending/rework | 仅失败页重试；无重复用户确认/无关页重做 |
| HST-06 | 已有SVG编译不要求新ImageGen | L2 | 已批准SVG/内容，当前图片工具不可用；执行compile_approved_svg | 按实际编译能力继续；不新生成，不伪报fresh图片 |
| HST-07 | 有限图片修复 | L2 | 同一页ImageGen/重建连续失败；执行3次尝试后继续 | 计失败/超时，达到上限停且保留成果；不换action ID重置预算 |
| WF-01 | 固定route优先 | L1 | 新native Run残留旧HD目录，旧Run已有manifest；status/next-step | 按route/current解析；不因目录存在自动走错引擎 |
| WF-02 | 缺语义门正确动作 | L1 | render/delivery/safety已过，semantic缺失；next-step→执行→import→resume | 派发语义审查，不无限执行render gate |
| WF-03 | Agent专业动作真接线 | L2 | 材料中已有答案、缺专业主张，工具授权齐；autopilot连续执行 | 提取/推理/写回真实调用，无只helper存在未调用；合法否定接受 |
| WF-04 | 迟到及同ID冲突 | L1 | 旧revision action晚到、同ID同hash和异hash；并发接受结果 | 旧拒绝；同内容幂等；不同输出冲突，不覆盖新版本 |
| WF-05 | 第二文件中断整批一致 | L1 | 一次动作含SVG/Scene/manifest；第2文件/marker/激活处故障及重启 | 读者只见完整旧或完整新revision，不接受逐文件rename解释 |
| WF-06 | 权限和停止有效 | L1 | 只授权P001，尝试改其他页或停止后回传；action acceptance | scope/path/permission/cancel检查实际生效；不写批准/锁定事实 |
| WF-07 | 预算包含失败 | L1 | 同finding有failed/timeout/dispatched未commit尝试；重试或换action ID | 预算真实消耗，不能只数committed；明确剩余 |
| WF-08 | 精准失效与局部修改 | L2 | 单页配色变更及跨页组件变更两组；impact→repair→build | 前者只影响视觉/产物/最终批准；后者影响相关正文/图/阶段；无关决定保留 |
| QA-01 | 语义门精确匹配 | L1 | 只有external_visual/evidence的pass；计算semantic required gate | 不满足语义；必须真实scope=semantic且完整覆盖 |
| QA-02 | Package改而index不变 | L1 | 已审查后直接改变一个Package正文；gate freshness/final-readiness | 旧语义过期；不能只看indexhash |
| QA-03 | 空pass和漏页拒绝 | L1 | 仅reviewer/pass或缺六维/页覆盖；导入review v2 | 拒绝并指出缺项；不能靠声明通过 |
| QA-04 | 严重问题压过summary | L1 | summary pass且存在P0/P1；aggregate gates与override | 按finding阻断；P0不可覆盖；P1按当前政策授权 |
| QA-05 | 视觉与编译证明分层 | L2 | 高像素相似但箭头反向，另一组SVG→PPTX误差超限；完整visual/readback评估 | 两组分别识别；不单用SSIM或内容正确替代其他门 |
| QA-06 | 正式文件完整扫描 | L2 | notes/隐藏页/alt text/metadata有内部路径，正文有必要业务限定；客户投影与导出检查 | 清理/阻断内部内容但不删业务限定；当前hash再验 |
| QA-07 | 批准绑定实际新版 | L2 | 批准后改字/页序/重编译；导出新版及旧版 | 新版需对应批准；旧已批准文件保留且标历史 |
| QA-08 | 修复后复审闭环 | L2 | 已定位具体对象finding且Agent可修复；自动定向修订/渲染/复审 | 问题被实际验证解决；未修复不因新summary过门 |
| MIG-01 | 旧HD可读与同核复用 | L2 | 旧HD产物/批准SVG和旧路径；只读/兼容继续/显式迁移 | 旧数据保留，内核共用，无新双写主线 |
| MIG-02 | 旧standard隔离 | L2 | 旧PPT Master Run无backend，新native Run依赖齐；分别diagnose/继续/新建 | 旧状态如实；不影响native，不自动安装绑定 |
| MIG-03 | 迁移输入改变 | L1 | dry-run后源文件改变；apply旧计划 | 拒绝过时计划，源批准文件不变 |
| MIG-04 | 迁移故障回滚 | L2 | 新revision任一编译/校验失败；迁移/激活 | 旧current完整保留；无伪新seal/approval |
| MIG-05 | 安装所有权与数据保护 | L2 | 独立ppt-* real dir、资产与索引存在；安装升级卸载 | 只动自有软件/链接，不删除外部或客户数据 |
| MIG-06 | 软件回滚不改新数据 | L2 | 新格式Run已生成后回滚软件；旧程序读取/尝试写 | 新数据保留；不支持安全写则明确只读，无破坏转换 |
| UAT-01 | 真实默认两页冷启动 | L2 | 干净安装与合成批准内容/真实宿主，无外部后端；image→SVG→PPTX→回读 | 真实默认链通过；有输出和执行证据，不用direct替代 |
| UAT-02 | 真实七类页面与编辑 | L2 | 七类样页含架构/表格/数据/高密中文；真实宿主重建、编译、桌面编辑 | 平均视觉≥4且各页≥3.5，内容/关系无关键错；编辑实证 |
| UAT-03 | 原材料完整Solution Deck | L2 | 仅原材料/目标/授权，无逐页稿，无历史库；默认8—12页全链到批准导出 | Agent承担内容/图形/修复；无外部绑定；必要研究真实执行 |
| UAT-04 | 局部修改端到端 | L2 | UAT已批准deck；请求单页修订及关系变更，再导出 | 只处理影响集，旧版保留，新版经当前检查和批准 |
| UAT-05 | 继承真实客户配对 | L3 | 原SC1三类授权客户素材与可比baseline；每类两次配对/冻结首稿/记录主动投入 | 按SC1投入/可保留页/六维阈值验收；失败全记录；不可比标N/A |
| UAT-06 | 结果与证据不洗白 | L3 | 工程完成但真实对照缺失/基线被阻断；聚合/最终发布报告 | outcome_pending；不当0分或无限提升；私有证据脱敏且完整 |


---

<!-- source: acceptance/SC1_SUPERSESSION_MAP.md -->

# 原SC-1 88项验收逐项继承/替换

以用户提供原包编号+标题为准，不按PR偏差表中可能不同的编号描述直接合并。全部verification_status=unverified；本表不是接受或通过清单。

| SC-1 ID | 原标题 | 处理 | 解释 | 新锚点 |
|---|---|---|---|---|
| A-01 | 隔离全新安装 | clarify | 完整安装改为内置原生能力；不要求外部整包 | IND-01 |
| A-02 | 锁定版本可重现 | clarify | 固定内置引擎/基础依赖/可选组件版本，仍需可重复 | IND-07 |
| A-03 | 标准真实 build/render | replace | 以native真实构建/回读/编辑替代PPT Master身份 | UAT-01 |
| A-04 | 不信任环境 ready 覆盖 | clarify | 不信任env恒真要求保留，针对native probe | IND-05 |
| A-05 | 托管 Library 真检索 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| A-06 | 索引数据隔离 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| A-07 | 无历史库真实新建 | clarify | none必须真正贯通CLI与source决策；native默认 | IND-04 |
| A-08 | 标准不强依赖 ImageGen | replace | 仅显式direct_svg不要求ImageGen；默认图片模式必须真实工具 | IND-08 |
| A-09 | 必需能力缺失不伪报 | clarify | 所需能力以native/host/renderer为准 | IND-05 |
| A-10 | 故障与无命中区分 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| A-11 | 组件来源与再分发 | clarify | 只审实际分发的必要组件与方法；不要求引入完整后端 | GOV-02 |
| A-12 | 兼容入口不依赖旧方法 | clarify | deck-*方法自包含，不要求legacy ppt-*别名必须安装 | IND-07 |
| I-01 | 后置关键约束 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| I-02 | 混合资料接入 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| I-03 | 部分读取不可假完成 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| I-04 | 幂等导入 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| I-05 | 证据ID消歧 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| I-06 | 精确定位与内容匹配 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| I-07 | 冲突不静默覆盖 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| R-01 | 定向真实研究 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| R-02 | 查询授权与脱敏 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| R-03 | 反证和适用边界 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| R-04 | 无结果终态 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| R-05 | 无工具/无网终态 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| R-06 | 研究预算与重启 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| S-01 | 无risk标记不自证 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| S-02 | 目标不冒充根因 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| S-03 | 同数字不同口径 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| S-04 | 页面不得自证 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| S-05 | 问题机制验收连通 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| S-06 | 现有与拟建区分 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| S-07 | 方案备选有实质差异 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| S-08 | 单一可行路径 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| N-01 | 公共主线非模板拼贴 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| N-02 | 无PagePackage循环依赖 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| N-03 | 已选主线不重复问 | clarify | 主线决定在公共层复用，native不再次MBB访谈 | CNT-04 |
| N-04 | MBB兼容单一写源 | clarify | 新native与旧HD适配的MBB均为公共主线派生 | CNT-04 |
| N-05 | 旧高密度Run可读 | clarify | 旧HD只读/adapter/显式迁移保留 | MIG-01 |
| P-01 | 标准真实消费Package | replace | 实际native消费当前Package，不以外部backend身份验收 | CNT-02 |
| P-02 | 无Placeholder完整生产 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| P-03 | 两个Builder内容一致 | replace | 同一内核image_blueprint/direct_svg的内容一致，不维护两套必需引擎 | CNT-02 |
| P-04 | 高密度保护不降级 | clarify | HD保护上移公共内核，默认图片真实证据不得取消 | HST-01 |
| P-05 | 可编辑性真实检查 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| P-06 | 客户文件全内容扫描 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| D-01 | 四类视图表达 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| D-02 | 孤儿节点 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| D-03 | 关系方向 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| D-04 | 节点聚合映射 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| D-05 | 模型改变的影响集 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| D-06 | 图表口径一致 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| W-01 | 复用材料已给答案 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| W-02 | Agent拥有专业问题 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| W-03 | 真实决定不能代填 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| W-04 | 布尔否定有效 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| W-05 | 决定精准失效 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| W-06 | 阶段内继续执行 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| W-07 | 迟到结果拒绝 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| W-08 | 幂等与冲突 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| W-09 | 跨文件中断恢复 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| W-10 | 局部权限与停止 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| Q-01 | 空pass不代表审查 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| Q-02 | 审查覆盖完整 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| Q-03 | 独立性不是改名 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| Q-04 | 当前输入绑定 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| Q-05 | 发现结果压过summary | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| Q-06 | 具体返修动作 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| Q-07 | 修复预算耗尽 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| Q-08 | 修订后定向复审 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| Q-09 | 正式必需门一致 | clarify | native与保留legacy产物遵守各明确合同，当前生产语义要求保留 | QA-01 |
| Q-10 | 模式降级不可绕过 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| Q-11 | 批准绑定当前版本 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| Q-12 | P0与P1处理 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| L-01 | 通过率口径 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| L-02 | 重复事件去重 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| L-03 | 旧事件不猜测 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| L-04 | 经验适用边界 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| E-01 | 配对样本与条件 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| E-02 | 初稿冻结 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| E-03 | 用户主动投入 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| E-04 | 缺失与失败不伪算 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| E-05 | 真实效果阈值 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| E-06 | 证据脱敏与完整性 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| M-01 | 外部目录不被占有 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| M-02 | 只卸载自有入口 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| M-03 | 升级失败原子回退 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| M-04 | 旧Run无损映射 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| M-05 | 新策略不洗白旧结果 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |
| M-06 | 软件回滚与数据分离 | retain | 未与后端选择冲突，原要求继续生效；需要核验既有证据或补测 | 继承原验收 |


---

<!-- source: acceptance/UAT_PROTOCOL.md -->

# 真实UAT与证据操作规程

## A. 先证明不依赖外部产品

创建隔离用户目录与运行环境；保留宿主必要工具授权但隔离旧Skill、PPT Master repo、绑定文件和后端PATH。记录允许存在的基础依赖。安装发布树而非只从开发checkout运行；隐藏checkout后运行一次。不得通过复制全套上游仓库到新的“native”目录来满足隔离。

先用已批准合成内容测试compiler和真实render；再用同类内容实际调用ImageGen、图像理解/SVG重建，完成两页默认生产。记录文件/进程访问，确认没有旧后端发现与调用。没有客户素材不能成为跳过该步骤的理由。

## B. 验证编译与真实编辑

七类页面与复杂中文/路径/透明度样例先做差分，再在实际支持的演示软件打开PPTX。修改一个中文标题、一个架构group、一条箭头/路径及一项颜色，保存再开并渲染，确认不是图片或隐藏覆盖。记录软件/版本/OS/字体，不推断其他平台支持。

SVG→PPTX保持既有固定环境测量门；图片→SVG按五维视觉量规评分，保留实际图与逐页理由。critical文字和业务关系任何错误都不能被平均分掩盖。材料/图源使用授权范围；公开报告只含脱敏hash和摘要。

## C. 原材料完整生产与修订

准备8—12页的合成授权业务场景，输入是原材料/目标/边界，而非逐页稿。材料后部放关键约束；设一个可公开研究缺口和一个不能靠公开研究得到的客户事实。让Agent完成Context→Solution→Narrative→Package→图片/SVG/PPTX→审查/修复；观察是否仍反复要求用户提供专业内容。

在明确的用户批准动作后导出。再只修改某页配色/文字，验证无关页hash与业务决定保留；再改跨页组件关系，验证完整影响集。每次新文件最终批准不复用；旧批准文件保持。

## D. 三类真实客户效果

继续原SC-1三类样本×两次配对，冻结首次完整稿，记录主动阅读/补写/纠错/审批时间、新增字符、无谓澄清、改写页数、首稿可保留页和六维评分。不能用返修后的稿当首稿；失败/所有重试保留。

对照条件包括材料、宿主模型、授权工具、预算与风格范围。旧标准后端无法运行时，不为满足旧身份要求强行绑定PPT Master；使用可验证的历史实际流程/旧HD，明确非等价条件。缺可比对照不得算提升；继续报告outcome_pending。

## E. 证据文件最小字段

case_id、source_sha、environment、install_manifest_hash、run_id_safe、origin_mode、engine/subset版本、authoring_mode、input_hashes、output_hashes、tool_observation、actual_commands、result、failure/retry_counts、reviewer与范围、approval_revision、限制、私有证据位置引用（公开报告脱敏）。

本包JSON样例不能导入作为真实smoke/审批；代码测试可用其结构，必须单独构造test evidence。状态必须区分not_run、blocked、failed、passed；“未执行”不写成“发现运行故障”，也不写成passed。


---

<!-- source: acceptance/VISUAL_RUBRIC.md -->

# 本轮视觉与编辑性量规（目标）

图片→SVG五维：构图层级、图形关系、文字可读性、风格一致性、整体可用性。每维1—5整数分，均值为页分；七类页等权平均。两名独立评阅者分别记录实际观察，分差>1须对照具体元素复核；不能只取较高分。至少一位由真实人类审阅；宿主视觉模型评分是辅助，不作为唯一效果证据。

| 分值 | 观察锚点 |
|---|---|
| 1 | 主要内容或结构无法使用，严重错位/遗漏/错误关系 |
| 2 | 需要大范围重建，层级/图文组织与参考显著不一致 |
| 3 | 基本可读但需要实质修订，关键版式/对齐或整体一致性仍弱 |
| 4 | 可用于业务讨论，只需少量不改变主体的修订，主要视觉意图和内容正确 |
| 5 | 可直接用于既定交付场景，层级清晰、结构准确、细节稳定，无必要修订 |

目标：七类页平均≥4.0、每页≥3.5；关键文字/事实/关系错误为独立阻断，不因其他维度高分豁免。允许的文字纠错与用户显式修改要先列allowed_delta，不因正确纠错造成像素不同而扣为失败。

SVG→PPTX采用既有受控环境指标与精确对象/文字回读，二者不和上面的主观量规混算。演示软件编辑检查独立pass/fail，包含文字、节点/分组、路径/箭头、颜色修改后保存再开。图表的形状可编辑不等于底层数据可编辑；报告须准确说明。

SC-1六维专业内容评分仍沿用原包，不用本视觉五维替代。评阅日期、版本、输入hash、软件/字体、逐页理由与失败重试必须留证。


---

<!-- source: agent/START_HERE.md -->

# 给 Codex 的执行说明｜SC-1.1 Native Deck Core

你正在继续MainQuestAI/Deck-Master。基础是PR #30 @ `4977f89573d18a282c605360dc55f751443a2b21`，不是回到PR29或重做SC-1。

**最重要的产品修正：原SC-1 D04“必须保留PPT Master默认后端”已被本包00正式撤销。用户要求取消该产品的必选依赖；默认路线是批准内容→图片蓝图→宿主视觉模型重建SVG→内置原生PPTX→回读。不要再让用户安装或绑定完整PPT Master作为开工/验收前提。**

## 开工顺序

读仓库AGENTS、再读本包00、01、02、tasks/DELIVERY_PLAN和acceptance映射。执行Q0，确认本地HEAD/未提交修改/真实调用图。将本包按仓库惯例放入建议目录`docs/specs/sc1.1-native-deck-core/`，写实际映射；该路径是建议，是否已存在需要你核验。

随后按ND-01→ND-02→ND-03→ND-04→ND-05实施。基于PR30后继做增量，不撤销其Context/Research/Solution/PagePackage/质量/反馈成果。若PR30尚未合并可stacked开发，不能为了开工擅自合并或force push。

## 必须贯彻

编译器优先从现有high_density代码提取，不能只是目录改名、复制两套或将整库静默捆绑。新默认route不得查询外部PPT Master绑定；保留显式旧Run兼容。doctor报告实际本次必需工具；缺ImageGen如实报告，不能静默切direct_svg/fixture。

检查并补CLI none、PagePackage ready_for_build一致性、公共Narrative→ContentLock/MBB单向投影、semantic精确类型、实际package内容指纹、next-step缺语义的动作、原子action提交和失败预算。不要把PR描述或函数注释当作已经通过的实际行为。

不要要求用户提供逐页稿、重做已确认主线或风格。专业工作由Agent执行；真实范围与最终文件批准仍由用户。新模型与图片能力用实际host probe证明，不硬编码模型名当可用性。

## 验收与交付

先固定原测试基线并加失败用例，随后补真实native两页/七类/8—12页全链路和桌面编辑。客户素材缺失只影响客户L3；合成内容真实工具L2仍需完成。对不能执行项准确标blocked/not_run。

每个增量提交输出：文件与调用方、相关验收ID、测试命令/结果、产物和hash证据、仍未实现/未验证、兼容及回滚。完成前重读旧88项映射，禁止遗漏未冲突SC-1要求。

不得擅自删旧Skill/后端/资产、重写events、伪造provider/quality receipt、降低门禁或把旧批准给新文件。全部本地事实、工具、测试和效果由你核验；没有证据不得填写passed。


---

<!-- source: agent/REVIEW_PR.md -->

# 独立评审指令

以本轮实际执行后的Spec+明确偏差记录为基线；本包已正式替换SC-1 D04。不要再以“缺PPT Master绑定”否决native路径，也不要因为该绑定要求取消就放过实际编译与质量检查。

核对：默认CLI/Agent/doctor/next-step/preview/final-readiness是否同一路由；是否真的未读取外部目录；compiler是否内置且无隐藏调用；图片是否真实生成；Scene/SVG/ContentLock是否同源；公共MBB是不是派生；PagePackage状态/Schema一致；缺语义时是否执行正确任务；external_visual不能满足semantic；改package不改index仍使审查过期；逐文件中断能否保持完整版本；失败是否耗预算；作用域和取消/迟到是否被执行；当前批准是否绑定实际文件。

要求真实干净安装、真实编译/渲染/编辑、真实宿主两页/完整deck和旧Run迁移证据。测试数量不是产品效果指标。仅抽测内部helper不足以证明调用方已接线。

将发现分成产品裁决违背、确定性bug、接线欠缺、证据未执行与未来建议。前三类必须给文件/行、触发条件、影响、修复建议、测试；未执行不写成确定故障，未来建议不自动扩大本轮。

检查所有原SC-1 88项retain/replace/clarify映射。旧测试不再适用应写superseded及新case，不当passed。批准本PR工程里程碑与宣布整轮accepted分开。


---

<!-- source: agent/DEVIATION_LOG_TEMPLATE.md -->

# 规格偏差记录模板

| 日期 | Task/Commit | 原条款 | 实际方式 | 代码/实验证据 | 兼容与效果影响 | 对应验收 | 状态 |
|---|---|---|---|---|---|---|---|
| 待执行 | — | — | — | 需要Codex核验 | — | — | open |

可自行记录并执行：目标目录名、等价既有接口复用、内部字段版本、PR拆分、非破坏封装。

不可自行弱化：重新要求完整PPT Master、隐藏clone/外部命令fallback、取消真实图片默认链、取消原生编辑/语义/审批、以fixture代真工具、为减少输入要求用户先写页面、删除旧用户数据、以缺真实素材免做工程接线。

运行环境缺失记录为验收blocked，不是修改产品目标的理由。实际无法取得授权工具时交付已完成工程和明确缺口，不能虚报accepted。


---

<!-- source: sources/BASELINE_EVIDENCE.md -->

# 来源、证据边界与本地待核验

**本包以用户提供的SC-1 Spec及PR #30固定SHA为依据。目标架构/新增接口/测试阈值属于本轮建议与约束，不是声称当前已经实现。**

远端代码是静态读取，不是完整checkout运行。尝试取得源码归档未成功，因此没有在本环境复跑产品测试；后续全部本地文件/安装/能力/测试/效果需要Codex核验。此前历史P2—P5评估不是本轮实现基线。

| 标识 | 来源 | 支持范围 | 证据等级 |
|---|---|---|---|
| R01 | [PR #30 metadata](https://github.com/MainQuestAI/Deck-Master/pull/30) | 本次在线读取HEAD=4977f89573d18a282c605360dc55f751443a2b21；open/unmerged，base=bcb5b37；PR正文中间HEAD和作者测试数字不作本次实测。 | 本次连接器读取 |
| R02 | [scripts/skills/installer.py](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/skills/installer.py#L1408-L1436) | install_managed_backend仍接受完整源包并提示backend bind。 | 本次连接器固定SHA读取 |
| R03 | [scripts/runtime/build.py](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/runtime/build.py) | 生产路径仍关联外部builder_backend；Package消费者要求ready，准备manifest与当前source fingerprint。 | 本次连接器固定SHA读取 |
| R04 | [scripts/high_density/pptx.py compile_pptx](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/high_density/pptx.py) | 编译函数以本地SVG/Scene/ContentLock生成原生Presentation及trace；路径提取和整体运行仍需Codex核验。 | 同对话上一轮已读取同SHA；本次补读同文件回读部分 |
| R05 | [scripts/high_density/pptx.py readback/render](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/high_density/pptx.py#L990-L1175) | 实际soffice/pdftoppm渲染调用、对象类型/文字/trace/几何和hash回读。 | 本次连接器固定SHA读取 |
| R06 | [skills/deck-builder-high-density/references/stage-protocol.md](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/skills/deck-builder-high-density/references/stage-protocol.md) | 既有MBB/ImageGen/Scene/SVG/PPTX阶段、原生对象/视觉指标与真实工具要求；不是已通过的效果报告。 | 本次连接器固定SHA读取 |
| R07 | [scripts/runtime/next_step.py](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/runtime/next_step.py#L1-L235) | HD目录优先分支、ppt-master missing项、缺semantic时quality command选择。 | 本次连接器固定SHA读取 |
| R08 | [scripts/deck_master.py library args](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/deck_master.py#L3045-L3070) | 共享library choices当前只有auto/real/fixture。 | 本次连接器固定SHA读取 |
| R09 | [docs/contracts/page-package.v1.schema.json](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/docs/contracts/page-package.v1.schema.json#L1-L150) | status枚举含ready_for_build而非ready；实际消费者差异需用调用链复现。 | 本次连接器固定SHA读取 |
| R10 | [scripts/quality/gate_policy.py](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/quality/gate_policy.py#L1-L130) | semantic gate接受external_*前缀；语义input_current检查index hash。 | 本次连接器固定SHA读取 |
| R11 | [SC-1 implementation/deviation-log.md](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/docs/specs/sc1-solution-core-independence/implementation/deviation-log.md) | HD公共投影、问题类型和action调用方接线等偏差记录；状态以实际代码/测试为准。 | 同对话上一轮已读取同SHA；本次PR metadata再次提及欠项 |
| R12 | [scripts/workflow/actions.py](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/workflow/actions.py#L1-L265) | staging后逐文件rename、applied marker、scope声明与预算计已提交；不能仅靠docstring证明批次原子。 | 本次连接器固定SHA读取 |
| R13 | [scripts/high_density/svg_native.py](https://github.com/MainQuestAI/Deck-Master/blob/4977f89573d18a282c605360dc55f751443a2b21/scripts/high_density/svg_native.py) | 已有共享SVG parser、path/transform/use支持子集；与旧prose存在需核对范围。 | 同对话上一轮已读取同SHA |
| L01 | 用户提供 SC-1 完整 Spec 与 88 项验收（原 ZIP 附件） | 读取原规格D04/D05/任务与原88项JSON；继承效果阈值并逐项映射，不使用过时P2—P5材料替代。 | 本次从附件本地读取 |

## 本地必须核验的事项

实际HEAD与当前PR状态、未提交改动、compiler依赖闭包/许可、所有核心schemas和consumer状态值、安装launcher与release内容、宿主工具观测接口、OS/Python/字体/renderer、原生编辑软件、真实生成与视觉质量、旧Run和客户资产位置、所有测试命令及结果。

## 来源优先级

用户本次明确纠偏→本包正式替换条款→原SC-1未冲突要求→固定SHA源代码事实。代码当前如何实现不决定产品必须继续如此；旧规格中已被撤销的backend身份不能继续当不可改变约束。

## 审查边界

本包不是完整PR30 code review，也不宣布PR30可合并；所列静态接线问题用于形成增量实现目标，确定性复现和本地修复需要Codex核验。Schema自检只证明四个目标窄合同及样例的结构，不证明底层图形引擎、真实性、安全性或交付能力。
