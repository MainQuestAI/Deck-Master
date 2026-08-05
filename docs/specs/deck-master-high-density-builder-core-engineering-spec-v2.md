# Deck Master High-Density Builder Core Engineering Spec v2

日期：2026-08-05
状态：Active Development Spec
适用范围：独立 `deck-builder-high-density` Skill 的核心生产链重建、验证和发布验收
目标基线：`main@551c581`
前置结论：PR #15 只提供工程外壳，不计入核心能力完成度

## 0. 执行结论

本轮开发按“核心引擎重新实现”立项，不按补丁修复立项。

上一轮已经形成的 CLI、Skill 注册、合同骨架、状态文件、Canonical Handback 和基础 PPTX 读回可以保留。以下四项产品核心能力均未达到可验收状态，必须在本轮完整实现：

1. CyberPPT 的 NBB 内容分析与内容丰富能力。
2. 基于真实页面内容的 ImageGen 蓝图生成与可复现 lineage。
3. 从蓝图图片到原生 SVG 的高保真重绘、溢出控制和视觉 QA。
4. 以已批准 SVG 为真实输入的 SVG-to-DrawingML PPTX 编译和读回验证。

本轮唯一目标生产链：

```text
Page Package + upstream evidence/narrative context
-> NBB content enrichment
-> content_lock.v2
-> content-aware ImageGen prompt
-> approved blueprint image
-> measured visual reconstruction
-> page_scene.v2 + native SVG
-> blueprint vs SVG visual gate
-> SVG-to-DrawingML compiler
-> editable PPTX
-> SVG vs PPTX render/readback gate
-> high_density_manifest.v2
-> canonical handback
-> deck-quality
```

该链路由独立 `deck-builder-high-density` Skill 完整承接。CyberPPT、`native-svg-redraw`、Product Design `image-to-code` 和 PPT Master 继续作为方法、行为和验收参考，不作为运行时依赖。

## 1. Spec 权威性与历史文档状态

### 1.1 当前权威文档

本文件是 High-density Builder 下一轮开发的唯一工程权威 Spec。

发生冲突时按以下顺序执行：

1. 本文件。
2. `docs/specs/high-density-ppt-builder-skill-requirements.md` 中的用户需求和参考能力记录。
3. `docs/specs/deck-master-high-density-builder-next-iteration-spec.md` 中的历史设计讨论。
4. `docs/specs/deck-master-high-density-builder-engineering-spec-v1.md` 中仍未被本文件覆盖的背景信息。

### 1.2 旧工程 Spec 处理

`deck-master-high-density-builder-engineering-spec-v1.md` 降级为历史基线。其合同、任务状态和 First Engineering Acceptance 不再用于判断当前实现是否完成。

旧版内部高密度合同视为 preview contracts：

- `deck_content_lock.v1`
- `deck_blueprint_manifest.v1`
- `deck_page_scene.v1`
- `deck_high_density_manifest.v1`
- `deck_high_density_status.v1`

它们可用于迁移测试和历史 run 识别，不能进入 v2 生产完成态。旧 run 需要从 Page Package 重新 `prepare`，不做过程件原地升级。

## 2. 当前真实基线

### 2.1 可保留基础

| Area | 当前状态 | 本轮处理 |
| --- | --- | --- |
| 独立 Skill 注册 | 已有 `deck-builder-high-density` 清单与路由 | 保留，补安装与依赖验收 |
| CLI profile | 已有 `--profile high-density` | 保留，补 `--watch` 和 Agent 连续执行 |
| Build Manifest | 已接入 `deck_build_manifest.v2` | 保留，修正更新与 fingerprint |
| 状态与错误外壳 | 已有 stage/page/error 基础字段 | 升级为 v2 页级状态模型 |
| Canonical Handback | 已能写 artifact/render/build 结果 | 保留接口，收紧完成条件 |
| PPTX 基础导出 | 能从 Scene 生成可编辑形状 | 仅作实验代码参考，不保留为最终编译路径 |
| 7 页 fixture | 能验证 schema、导出和读回骨架 | 重做为行为和视觉 fixture |

### 2.2 必须重写或新增

| Core Area | 当前实现 | 本轮目标 |
| --- | --- | --- |
| NBB | 只计算字符、数字和 block 数量 | 形成证据绑定、论证、caveat、SO WHAT、组件计划和低密度阻断 |
| Blueprint prompt | 只有页面类型、密度、风格 | 写入页面结论、锁定内容、证据、组件、语言、视觉系统和禁止项 |
| ImageGen lineage | 图片生成后补 prompt hash | 先冻结 prompt，再调用 ImageGen，记录可核验生成链 |
| Image-to-SVG | fixture 使用固定卡片模板 | Agent 基于真实蓝图量测并原生重绘 |
| Scene coverage | 只校验已出现文本 | 对锁定内容和组件做反向覆盖校验 |
| Visual QA | fixture 直接写 `SSIM=1.0` | 从真实渲染图计算并保存原始证据 |
| SVG-to-PPTX | Scene 与 SVG 并行输出 | PPTX 编译器必须读取已批准 SVG |
| Asset policy | 仅拦截精确整页图片 | 面积、覆盖、z-order、文字重叠和来源共同约束 |
| Security | retry 接受任意 page ID | 所有路径只接受 manifest 内已登记页面 |
| Lineage | 内容变化后存在旧 fingerprint | 任一上游变化都必须重建下游 lineage |

### 2.3 核心完成度口径

当前核心完成度按产品价值计为 `0/4`：

| Capability | 当前验收状态 |
| --- | --- |
| NBB content enrichment | 未通过 |
| Content-aware ImageGen | 未通过 |
| Image-to-native-SVG | 未通过 |
| SVG-to-DrawingML PPTX | 未通过 |

合同或结构测试通过只能说明工程外壳可运行，不能提高上述完成度。

## 3. 本轮目标与边界

### 3.1 产品目标

本轮完成后，用户应能从现有 Deck Master Page Packages 启动一次 High-density build，并得到：

- 经过 NBB 方法增强且证据可追溯的逐页内容锁。
- 由真实页面内容驱动的高密度 ImageGen 蓝图。
- 对蓝图进行原生 SVG 重绘后的可检查页面。
- 关键文字、数字、表格、图表和关系可编辑的 PPTX。
- 蓝图、SVG 和 PPTX 三层视觉对照证据。
- 可恢复、可重跑、可审计的完整 lineage。

### 3.2 首版产品约束

- 单一 `high-density` profile。
- 单一 16:9 canonical canvas：`1672 x 941 px`。
- 单一 SVG-to-DrawingML 编译器实现。
- ImageGen 通过当前 Agent 环境调用，不在仓库中绑定固定模型 SDK。
- 语义理解、内容丰富、蓝图生成和复杂视觉拆解由 Skill 驱动 Agent 完成。
- 合同、状态、文件安全、渲染、量测、比较、编译和读回由仓库代码确定性执行。
- 每一页独立通过后才能进入 deck 合并与 handback。

### 3.3 本轮不做

- 多 ImageGen provider 抽象。
- `fast / standard / max-quality` 多档质量模式。
- 风格市场或用户自定义风格编辑器。
- Native PowerPoint SmartArt。
- 全量原生数据 Chart/Table 对象；首版允许用可编辑 DrawingML shape group 表达。
- 高级动画、转场和音频。
- OfficeCLI 自动美化策略；OfficeCLI 保留为交付后的编辑、检查和运营工具。
- 旧 v1 高密度过程件的原地迁移。
- 无 Agent 视觉能力的纯脚本自动重绘。

## 4. 不可妥协原则

1. Page Package 是事实、数字和证据的唯一上游真相源。
2. NBB 在本项目中指 CyberPPT MBB 级内容分析链的仓库内实现，禁止缩减成字符计数或模板填充。
3. ImageGen 只能提供视觉构图、层级、组件密度和设计语言，不能提供事实。
4. 已批准蓝图是 Image-to-SVG 阶段的视觉基准。
5. 已批准 SVG 是 PPTX 页面视觉和几何的真实编译输入。
6. `page_scene.v2` 是语义、量测、文字引用和验收 sidecar，不能绕过 SVG 直接生成最终 PPTX。
7. 所有可见主要文字、关键数字、SO WHAT、来源和脚注必须来自 `content_lock.v2`。
8. 主要信息不得通过整页或近整页图片承载。
9. 结构可编辑和视觉语义保真必须同时通过。
10. 任何指标都必须由工具实际计算并绑定输入 hash，Agent 只能记录审阅结论。
11. 任一必需 artifact、证据、依赖或页面失败时，全 deck 不得进入 completed。
12. 标准 `deck-builder` 路线不受本轮内部合同变化影响。

## 5. Agent 与仓库代码的责任边界

### 5.1 Agent-owned actions

独立 Skill 负责驱动 Agent 完成：

- NBB 证据审计和内容丰富。
- 逐页内容结构、caveat、SO WHAT 和组件规划。
- 读取冻结 prompt 并调用 ImageGen。
- 目视拆解真实蓝图。
- 编写 `page_scene.v2` 和原生 SVG。
- 根据工具生成的视觉差异证据返修 SVG。
- producer self-review 和 main review。

Agent 不得自行写入通过指标，不得修改工具计算结果，不得跳过状态机直接写 completed。

### 5.2 Repository-owned deterministic actions

仓库代码负责：

- schema validation。
- hash、fingerprint 和 invalidation。
- 安全路径解析和页面身份校验。
- prompt artifact 的确定性序列化。
- 蓝图画布、slide frame 和 transform 校验。
- SVG XML、元素、文字引用、资产和溢出校验。
- SVG 和 PPTX 渲染。
- 图像相似度、颜色、边界和 bbox 差异计算。
- SVG-to-DrawingML 编译。
- OOXML readback 和 SVG/PPTX 渲染对照。
- canonical handback 和 `deck-quality` 路由。

### 5.3 Agent continuation contract

`deck-master build run --profile high-density` 在需要 Agent 行动时返回以下 action kind 之一：

```text
agent_nbb_enrich
agent_imagegen
agent_visual_reconstruct
agent_svg_repair
agent_self_review
agent_main_review
```

每个 action 必须包含：

- `run_id`
- `page_id` 或 deck scope
- `input_refs`
- `output_refs`
- `required_schema`
- `acceptance_command`
- `resume_command`
- `reason`

同一次 Skill 调用应持续消费 action，直到 `completed`、`blocked` 或需要用户决策的稳定状态。

## 6. 目标目录与 artifact

```text
<run_dir>/
  page_packages/
  build/
    build_manifest.json
    artifact_manifest.json
  high_density_build/
    status.json
    style/
      style_options.json
      style_lock.json
    nbb/
      nbb_plan.json
      evidence_coverage.json
    content_locks/
      P001.content_lock.json
    prompts/
      P001.blueprint_prompt.json
    blueprints/
      P001.png
      P001.blueprint_manifest.json
      P001.normalized.png
    scenes/
      P001.page_scene.json
    svg/
      P001.svg
    previews/
      P001.svg.png
      P001.pptx.png
    comparisons/
      P001.blueprint-vs-svg.png
      P001.svg-vs-pptx.png
      P001.regions/
    reviews/
      P001.metrics.json
      P001.self_review.json
      P001.main_review.json
    traces/
      P001.svg_to_drawingml.json
    readback/
      P001.readback.json
      deck.readback.json
    pptx/
      pages/
        P001.pptx
      deck_high_density.pptx
    high_density_manifest.json
  render_results/
    render_result.json
```

禁止把客户源材料、私有 73 页蓝图、未脱敏图片或原始 benchmark 复制进仓库。

## 7. v2 合同模型

### 7.1 保持不变的公共合同

- `deck_page_package.v1`
- `deck_build_manifest.v2`
- `deck_artifact_manifest.v1`
- `deck_render_result.v2`
- Deck Master stage contract 和 canonical handback 路径

### 7.2 新增内部合同

| Contract | Scope | Purpose |
| --- | --- | --- |
| `deck_high_density_style_lock.v1` | deck | 固定视觉样式、色板、网格、字体、图表和页面表面系统 |
| `deck_nbb_plan.v1` | deck | NBB 证据审计、故事线、SCR、页面物料池和密度计划 |
| `deck_content_lock.v2` | page | 内容冻结、受控丰富、证据 lineage、组件和覆盖要求 |
| `deck_blueprint_prompt.v1` | page | 完整 ImageGen prompt 和所有输入 hash |
| `deck_blueprint_manifest.v2` | page | prompt-first 生成记录、图片、画布、frame、transform 和批准状态 |
| `deck_page_scene.v2` | page | 组件签名、视觉元素、量测、文字引用、z-order 和 SVG 映射 |
| `deck_visual_metrics.v1` | page | 工具计算的 blueprint/SVG/PPTX 差异 |
| `deck_visual_review.v2` | page/reviewer | 自审、主审、问题、返修和最终视觉裁决 |
| `deck_svg_to_drawingml_trace.v1` | page | SVG 元素到 OOXML shape 的映射 |
| `deck_pptx_readback.v2` | page/deck | 文本、几何、媒体、notes、关系和渲染验证 |
| `deck_high_density_manifest.v2` | deck | 全链 lineage 和最终完成态 |
| `deck_high_density_status.v2` | deck/page | 页级 stage、action、重试和 watch 状态 |

### 7.3 Hash 和时间字段规则

- artifact hash 只覆盖稳定业务字段，不包含 `created_at`、`updated_at` 和绝对路径。
- 所有路径必须是 run-relative path。
- 每个 page artifact 同时绑定 `run_id`、`page_id` 和直接上游 hash。
- deck fingerprint 由排序后的 Page Package hash、style lock hash、NBB plan hash 和 profile version 组成。
- 任一直接上游 hash 变化时，所有下游 artifact 必须删除或标记 stale。
- stale artifact 永远不能被 handback 引用。

## 8. Runtime Stage A：NBB 内容分析与内容锁

### 8.1 输入

- 全部 `ready_for_build` Page Packages。
- Page Package 内证据、claim、visual requirement 和语言字段。
- 可选的已批准 deck brief、narrative plan、SCR 或 evidence index。
- style intent 仅用于组件建议，不能影响事实。

### 8.2 `nbb_plan.v1` 必须产出

- 证据底表和每条证据的来源、期间、单位、置信度、冲突、caveat、含义。
- 已批准叙事存在时的叙事审计结果。
- 已批准叙事缺失时的 2-3 条故事线候选、issue tree 或 hypothesis tree、推荐理由。
- deck 级 SCR。
- 逐页角色、结论、论证、证据、caveat、业务含义和承接关系。
- 逐页页面物料池。
- 逐页密度目标和组件清单。
- 缺失证据和 blocked pages。

### 8.3 `content_lock.v2` 必须产出

- 标题、副标题和语境说明。
- 结论、支撑论点和完整解释结构。
- 关键数字、指标、单位、期间和比较口径。
- 表格行列结构和核心单元格。
- 图表系列、类别、值、图例和注释。
- caveat、来源、脚注和 evidence ID。
- SO WHAT 标题、区域和要点。
- 页面组件清单和 `required_component_ids`。
- `required_text_refs` 和每个 ref 的 priority。
- `density_target`：信息区、组件数、证据数、数值数、主辅区比例。
- `target_language`、`effective_language` 和受控覆盖。
- 每条新增内容的 `origin`：`source`、`derived`、`structural_label`。
- derived 内容的 evidence refs 和 derivation note。

### 8.4 NBB 内容丰富规则

允许：

- 从已有证据形成比较、归纳、排序、原因链、影响链和管理含义。
- 把零散证据组织成可讲述的页面结构。
- 增加结构标签、分区名、关系描述和过渡句。
- 提出显式 caveat、缺口和待验证问题。

禁止：

- 新增来源中没有的数字、客户事实、Logo、引语或市场判断。
- 将常识或 ImageGen 文字当成证据。
- 覆盖 Page Package 中已经批准的结论或数字。
- 为达到密度目标重复同一观点。

### 8.5 NBB 硬门

- 所有事实、数字和具体判断的 evidence coverage 为 100%。
- 所有 derived factual claim 至少有一个 evidence ref。
- 低密度页面在蓝图前阻断，返回缺失信息和可行动建议。
- `required_component_ids` 为空时阻断。
- Page Package、NBB plan 和 content lock 的 run/page/hash 必须一致。
- 同一稳定输入重复运行得到同一稳定 hash。

## 9. Runtime Stage B：内容驱动的 ImageGen 蓝图

### 9.1 Style lock resolution

Style lock 按以下优先级确定：

1. Deck Master 上游已经批准的 design/style lock。
2. 用户在本次 High-density build 中选择的 CyberPPT 固定样式。
3. fixture/dev 模式下明确指定的固定测试样式。

生产模式缺少已批准 style lock 时，Skill 必须生成并展示 8 套固定视觉样式供用户选择，不能静默随机选择。

`style_lock.v1` 至少记录：

- style ID、名称和来源。
- palette 和颜色角色。
- canvas、safe area 和 grid。
- 标题、正文、注释和数字 typography。
- chart、table、card、connector 和 icon language。
- surface、background、header、footer 和 source system。
- density rules。
- 禁止页码和内部标注。
- approval、approver、artifact hash 和 created_at。

Style lock 只约束视觉表达，不能增加或修改事实。全 deck 默认使用同一个 style lock；页级覆盖必须显式登记并重新生成对应 prompt 和下游 artifact。

### 9.2 Prompt-first 规则

蓝图生成前必须先写 `blueprint_prompt.v1`。Prompt artifact 必须包含：

- 完整 prompt text。
- prompt template version。
- content lock path/hash。
- NBB plan path/hash。
- style lock path/hash。
- 页面角色、结论和目标语言。
- 必需组件和信息区数量。
- 主图、侧栏、表格、图例、微图表、注释和 SO WHAT 要求。
- 证据 ID 和真实内容摘要。
- 色板、网格、标题层级、图表语言、表格语言和页面表面系统。
- 禁止页码、内部标签、prompt 标签、wireframe 标签和执行元数据。
- 禁止 ImageGen 自行补事实。

图片生成完成后再补写 prompt 或只记录 hash，均判定 lineage 失败。

### 9.3 ImageGen 执行

- Skill 读取冻结 prompt artifact 后调用当前 Agent 的 ImageGen 能力。
- 生成文件先写临时路径，成功校验后原子移动到目标路径。
- 记录 provider/tool 名称、可用 model 标识、request ID、生成时间和错误信息；工具未返回的字段明确写 `unavailable`。
- 记录 prompt SHA、image SHA、图片尺寸和内容锁 SHA。
- 图片必须经过 Agent 目视确认和 manifest approval。
- 文件扩展名不能触发自动批准。

### 9.4 画布和 slide frame

- canonical 目标比例为 16:9。
- provider 图片比例不同时，通过画布内接 16:9 `slide_frame` 进行映射。
- 宽图：以源图高度计算 frame width，水平居中。
- 高图：以源图宽度计算 frame height，垂直居中。
- frame 必须完全位于源图画布内。
- 禁止非等比拉伸。
- `source_to_scene_transform` 必须记录 scale、offset、crop 和 rounding policy。

### 9.5 Blueprint hard gate

- Prompt 必须实际包含页面 title、结论或唯一内容摘要。
- 不同内容锁在相同 style 下不能产生相同 prompt hash。
- Style lock hash 必须写入 prompt 和 blueprint lineage。
- 同一 deck 的页面视觉语言必须通过 style drift 检查。
- image hash 必须和磁盘文件一致。
- prompt/image/content/style lineage 必须完整。
- slide frame 和 transform 必须有效。
- 图片存在页码、内部生产标注或大面积异常文字时返回重生成。
- 每个必需组件在蓝图中必须有可识别区域，否则返回重生成或 content-lock repair。

## 10. Runtime Stage C：图片到原生 SVG

### 10.1 执行模式

Image-to-SVG 使用“Agent 视觉理解 + 仓库确定性校验”的组合方式：

1. Agent 查看实际蓝图和内容锁。
2. Agent 建立组件签名、visual element registry 和 measurement table。
3. Agent 编写原生 SVG，并同步写入 `page_scene.v2`。
4. 工具渲染、测量和比较。
5. Agent 按差异返修。
6. producer self-review 通过后进入 main review。
7. main review 通过后冻结 approved SVG。

### 10.2 `page_scene.v2` 必需字段

- canonical canvas。
- blueprint source canvas、slide frame 和完整 transform。
- `component_signature`。
- `required_component_ids` 覆盖结果。
- `visual_elements[]`：
  - stable element ID
  - component ID
  - kind
  - role
  - priority
  - source blueprint bbox
  - target SVG bbox
  - target PPT bbox
  - z-order
  - style summary
  - content lock text ref
  - editability target
  - tolerance
  - asset policy
- text fit policy。
- overflow policy。
- unresolved visual elements。

### 10.3 原生 SVG 规则

首版支持：

- `<svg>`、`<g>`、`<defs>`。
- `<rect>`、`<circle>`、`<ellipse>`、`<line>`、`<polyline>`、`<polygon>`。
- `<path>`，包含直线、二次和三次贝塞尔曲线。
- `<text>` 和直接子 `<tspan>`。
- 受控 `<symbol>/<use>`，编译前展开。
- solid fill、linear/radial gradient、stroke、opacity。
- 可映射的简单 shadow/glow。
- 经批准的独立 raster/SVG asset。

首版禁止：

- 整页或近整页蓝图图片。
- 用图片承载主要文字、数字、来源、脚注或 SO WHAT。
- `foreignObject`、script、iframe、外部 CSS 和网络资源。
- 未登记的 data URI。
- 不能被编译器稳定映射的 mask、clip、pattern 和复杂 filter。
- 通过隐藏文字层掩盖上层图片内容。

### 10.4 锁定内容覆盖

校验必须从 `content_lock.v2` 反向遍历：

- `required_text_refs` 覆盖率 100%。
- `required_component_ids` 覆盖率 100%。
- P0/P1 元素全部存在且可见。
- 每个 text ref 只能解析到锁定内容。
- 允许按政策换行，禁止静默删词、截断或改写。
- SVG text 的规范化内容和锁定文本必须一致。

### 10.5 文字与容器溢出

处理顺序：

1. 使用锁定字体层级和目标字号。
2. 调整换行和 line spacing。
3. 在政策范围内调整 padding 和容器尺寸。
4. 在声明的 minimum font size 以内缩放。
5. 仍然溢出时返回 Scene/SVG repair。
6. 页面结构无法承载时返回 content-lock repair 或拆页决策。

禁止通过极小字号、隐藏 overflow、透明文字、移出画布或图片化解决溢出。

### 10.6 图片资产策略

每个 image asset 必须记录来源、hash、用途和批准状态，并满足：

- 单个图片面积不得超过画布的 35%。
- 全页图片累计面积默认不得超过画布的 50%。
- 图片不能覆盖任何 P0/P1 text bbox。
- 图片不能位于隐藏的完整文字层上方。
- 图片边界与蓝图对应区域一致。
- Logo、照片和复杂非文字资产可进入 registered asset。
- 页面截图、蓝图截图和带主要信息的复合截图永远禁止。

超过面积限制需要显式 `asset_exception`，并由 main review 判定。整页和近整页图片不能获得例外。

### 10.7 复杂图形

曲线、流带、弧线、地图、复杂图标和异形需要：

- source crop。
- measurement/control points。
- trace debug preview。
- SVG preview crop。
- 局部 comparison。
- unresolved issue 记录。

P0/P1 复杂图形不能用无关通用符号或少量折线静默简化。

## 11. Runtime Stage D：Blueprint vs SVG 视觉 QA

### 11.1 两层渲染

进入 PPTX 编译前，每页生成同尺寸 PNG：

1. 归一化后的 blueprint。
2. SVG preview。

所有比较必须绑定：

- renderer 名称和版本。
- source artifact hash。
- output image hash。
- canvas size。
- mask 和 region definition hash。

### 11.2 Blueprint vs SVG

工具必须计算：

- text-masked SSIM。
- P0/P1 region SSIM。
- region color difference。
- element bbox delta。
- edge/layout similarity。
- content/component coverage。
- overflow and overlap findings。

初始门槛：

- 全页 text-masked SSIM `>= 0.92`。
- 每个 P0 region SSIM `>= 0.92`。
- P0/P1 bbox 每条边差异 `<= 2 px`。
- P0/P1 内容和组件覆盖率 `100%`。
- unresolved overflow、overlap、wrong-anchor 和 wrong-direction 为 `0`。

阈值必须存放在 versioned quality policy 中。调整阈值需要 fixture 和 benchmark 证据。

### 11.3 Review evidence

producer self-review 和 main review 都必须读取实际图片证据。

每个 review artifact 至少包含：

- reviewer role。
- blueprint、SVG、preview 和 comparison 路径/hash。
- metrics path/hash。
- full-page checks。
- high-density region checks。
- icon/curve/table checks。
- issues found。
- revisions made。
- unresolved issues。
- verdict。

main review 不能只读取 self-review 结论。`unresolved_issues` 非空时禁止通过。

## 12. Runtime Stage E：SVG-to-DrawingML PPTX 与最终 QA

### 12.1 编译输入权威性

编译器输入固定为：

- approved native SVG。
- `page_scene.v2` semantic sidecar。
- content lock notes 和 text validation refs。
- registered asset map。

几何、样式和 z-order 必须从 SVG 读取。Scene 只提供语义、预期 bbox、文字引用和验收信息。

以下行为直接判定架构失败：

- 从 Scene 单独生成 PPTX。
- SVG 只用于 preview。
- 修改 SVG 后 PPTX 内容不变化。
- 编译器遇到不支持元素时静默忽略或简化。

### 12.2 首版编译器能力

仓库内重新实现受控 SVG 子集到 DrawingML 的转换：

- text/tspan -> editable text box and runs。
- rect/circle/ellipse -> native shape。
- line/polyline/polygon -> native connector/freeform。
- path -> native freeform/custom geometry。
- fill/stroke/opacity/gradient -> DrawingML style。
- supported shadow/glow -> DrawingML effect。
- registered image -> picture relationship。
- group -> stable logical trace；首版允许在 OOXML 中展开为相邻 shapes。
- notes -> native speaker notes。

实现可以使用 `python-pptx` 管理 package 和通用关系，同时通过仓库内 XML writer 补充 freeform、gradient、effect 和精确文本属性。

### 12.3 Trace contract

每个 SVG 可见元素必须映射到：

- SVG element ID。
- OOXML slide part。
- shape ID/name。
- object type。
- source bbox。
- output bbox。
- style summary。
- text ref 或 asset ID。
- conversion status。

P0/P1 元素 trace coverage 为 100%。不支持元素必须在编译前阻断。

### 12.4 Readback

OOXML readback 至少验证：

- slide count 和 page order。
- notes count 和 notes text。
- P0/P1 text exactness。
- shape count、type、name、bbox 和 z-order。
- media relationships 和 asset hash。
- 整页或近整页图片缺失。
- 不存在隐藏文字层覆盖策略。
- SVG-to-PPTX trace 完整。
- PPTX 可由 LibreOffice 打开并渲染。
- PPTX render 通过 SVG vs PPTX visual gate。

### 12.5 SVG vs PPTX visual parity

PPTX 编译和 readback 完成后，每页生成 PPTX page render，并与同页 SVG preview 在相同尺寸下比较：

- text-masked SSIM `>= 0.97`。
- P0/P1 geometry delta `<= 0.75 pt`。
- P0 文本规范化精确匹配。
- P1 文本完整存在且无截断。
- shape z-order 与 SVG DOM 顺序一致。
- gradient、opacity、stroke、shadow 和 path 在支持范围内保持一致。
- 注册图片数量、关系和 hash 一致。

比较结果写入工具生成的 metrics artifact。任一项失败时返回 SVG compiler repair 或 SVG repair，不得进入 handback。

## 13. 状态、恢复和安全

### 13.1 Fail-closed input loading

- `page_packages/*.json` 任一文件损坏时整个 prepare 阻断。
- Page Package 的 `run_id` 必须等于 run directory state 的 `run_id`。
- page ID 必须符合安全标识符格式，并存在于 build manifest。
- 重复 page ID、order 冲突或 index 不一致时阻断。
- 不得静默跳过页面。

### 13.2 Safe retry

- retry 只能接收 build manifest 中的 page ID。
- 所有路径先通过 run-relative resolver。
- 删除前必须验证目标位于当前 run directory。
- retry 只删除目标 stage 及其下游 artifact。
- 任何 deck 级 artifact 被影响时必须重建 fingerprint 和 manifest。

### 13.3 Invalidation

| Changed input | Invalidated artifacts |
| --- | --- |
| Page Package | NBB plan、content lock 及该页全部下游 |
| NBB plan | content lock、prompt、blueprint、scene、SVG、PPTX、handback |
| Content lock | prompt 及该页全部下游 |
| Style lock | prompt、blueprint、scene、SVG、PPTX、handback |
| Prompt | blueprint 及全部下游 |
| Blueprint | scene、SVG、reviews、PPTX、handback |
| Scene/SVG | reviews、PPTX、readback、handback |
| Compiler version | PPTX、readback、handback |

### 13.4 Watch

`build status --watch` 必须：

- 每次状态变化输出新的 page/stage/action。
- 支持 JSON lines 或最终 JSON summary。
- 在 `completed`、`blocked`、`failed`、`awaiting_user_decision` 时退出。
- `prepared`、`building` 和 `awaiting_agent_build` 不能被当成完成态。
- 支持 timeout 和 Ctrl-C，无状态文件损坏。

### 13.5 Capability readiness

`suite-status --capability deck_master.build.high_density.v1` 必须检查：

- Skill 文件和 profile route。
- runtime package。
- 全部 v2 schemas。
- Python 版本。
- `jsonschema`、`python-pptx`、Pillow/NumPy 或最终确定的视觉比较依赖。
- `rsvg-convert` 或选定的 SVG renderer。
- LibreOffice 或选定的 PPTX renderer。
- 字体可用性。
- Agent ImageGen readiness 可核验时报告；不可核验时返回明确的 Agent action requirement。

缺失任一生产必需依赖时，capability 不能返回 ready。

## 14. 反伪实现验收矩阵

下列探针属于强制测试。任何一项失败，都不能用普通 fixture pass 覆盖。

| ID | Probe | Required result |
| --- | --- | --- |
| AF-01 | 低密度且缺证据 Page Package | 在蓝图前阻断 |
| AF-02 | 含无来源 `42%` 的事实性文字 | 阻断并指出 evidence gap |
| AF-03 | 两页角色/风格相同、内容不同 | prompt text/hash 必须不同 |
| AF-04 | 图片先存在、prompt 后生成 | lineage 失败 |
| AF-05 | 两张视觉完全不同的蓝图 | Scene/SVG 和 visual metrics 必须显著不同 |
| AF-06 | 从 Scene 删除锁定 callout | Scene coverage 失败 |
| AF-07 | SVG 删除必需组件 | SVG coverage 失败 |
| AF-08 | 手工写 `SSIM=1.0` | 因缺工具证据或 hash 不匹配而失败 |
| AF-09 | 1px 边距近整页图片 | asset policy 失败 |
| AF-10 | 图片覆盖 P0 文字、底层保留隐藏文字 | asset/z-order policy 失败 |
| AF-11 | 修改 approved SVG 的颜色或几何 | PPTX hash、trace 和 render 必须变化 |
| AF-12 | Scene 改变、SVG 不变 | PPTX 几何和视觉不得变化；sidecar 不可成为视觉源 |
| AF-13 | unsupported SVG element | 编译前阻断并返回元素 ID |
| AF-14 | Page Package 更新 | deck/page fingerprint 和全部下游 lineage 更新 |
| AF-15 | 损坏的 Page Package JSON | 整个 prepare 阻断，不得少页继续 |
| AF-16 | run ID 与 package run ID 不一致 | 阻断 |
| AF-17 | retry page ID=`../../../victim` | 安全拒绝，目录外文件保持不变 |
| AF-18 | 缺少 renderer 依赖 | capability 不得 ready |
| AF-19 | `build status --watch` 处于 prepared | 持续等待或超时，不能立即成功退出 |
| AF-20 | 宽图和高图蓝图 | 默认 frame 位于源画布内且保持 16:9 |

## 15. 测试体系

### 15.1 Unit tests

- NBB evidence and claim coverage。
- content lock deterministic hash。
- prompt serialization and content sensitivity。
- slide frame and transform。
- safe path and retry target validation。
- SVG parser whitelist。
- text coverage and overflow。
- image area/overlap/z-order policy。
- visual metric calculation and stale evidence。
- SVG element to DrawingML mapping。
- OOXML readback。

### 15.2 Metamorphic tests

测试输入发生受控变化后，输出必须按预期变化：

- 改标题 -> prompt、SVG text、PPTX text、hash 变化。
- 改 style lock -> prompt、blueprint lineage、SVG/PPTX visual 变化。
- 改蓝图视觉 -> Scene、SVG 和 metrics 变化。
- 改 SVG -> PPTX、trace 和 render 变化。
- 只改 timestamp -> 稳定业务 hash 不变化。

### 15.3 Hermetic fixture

仓库内提供 7 页脱敏 fixture，覆盖：

1. 高密度叙事页。
2. KPI + 趋势页。
3. 对比矩阵或表格页。
4. 复杂流程/架构页。
5. 时间线/路线图页。
6. 曲线、流带或多连接关系页。
7. 图片资产和长文本压力页。

每页使用不同蓝图和预期结构，禁止复用一张通用三矩形蓝图。

### 15.4 Provider smoke

Release acceptance 必须运行一页 fresh ImageGen：

- 使用新的 prompt 和新的输出图片。
- 记录真实 prompt/image lineage。
- 完成 blueprint -> SVG -> PPTX。
- 通过视觉和读回门。
- provider smoke 不放进无网络 CI，但结果必须进入 release evidence。

### 15.5 External 73-page benchmark

73 页历史项目作为外部产品验收，不提交私有原图：

- 全量运行新 Skill。
- 记录页面成功率、平均返修次数、阻断原因、图片资产比例和总耗时。
- 全页做自动指标。
- 至少抽查每类页面 2 页，并覆盖全部高复杂页面。
- 所有 P0/P1 内容和组件覆盖率 100%。
- 不允许通过旧手工 SVG 或旧 PPTX 直接填充结果。
- 仓库只保存脱敏 evidence index、指标摘要和失败分类。

## 16. Phase 0-3 开发顺序

### Phase 0：重新建立可信基线

目标：清除会制造假完成的合同、状态和安全问题，为核心开发建立 fail-closed 基础。

开发项：

- 将 v1 工程 Spec 标记为 superseded。
- 新增 v2 contracts 和 schema validation。
- 标记现有高密度 v1 artifact 为 preview-only。
- 修复安全 page ID、损坏 JSON、run ID、manifest 更新和 invalidation。
- 实现真实 `--watch`。
- 实现 dependency-aware capability readiness。
- 将 fixture 的 synthetic visual pass 移出生产验收。

最小验收：

- AF-15 至 AF-19 全部通过。
- v1 artifacts 不能进入 v2 completed。
- standard build regression 全绿。
- High-density capability 在缺依赖时明确 blocked。

停止点：

- schema 版本和兼容策略未通过工程 Review。
- 任一目录穿越或静默页面丢失仍可复现。

### Phase 1：NBB + Content-aware ImageGen

目标：把 CyberPPT 的内容密度和生图核心真实迁入独立 Skill。

开发项：

- 实现固定 8 样式 registry、展示资产和 `style_lock.v1`。
- 实现 `nbb_plan.v1` 和 `content_lock.v2`。
- 重写 `scripts/high_density/content.py`。
- 重写 prompt builder 和 blueprint manifest。
- 补 Agent action contract 和 Skill continuation。
- 加入 live provider smoke runner/evidence template。

最小验收：

- AF-01 至 AF-04 和 AF-20 全部通过。
- 生产模式缺少 style lock 时进入明确的用户选择状态。
- 8 套固定样式均有可见样张和稳定 ID。
- sparse but evidenced fixture 能形成明确结论、论证、caveat、SO WHAT 和组件计划。
- unsupported facts 被阻断。
- 一页 fresh ImageGen 记录完整 lineage。

停止点：

- Prompt 仍可在缺少页面真实内容时生成。
- NBB 输出只有统计字段或泛化模板。
- Agent action 需要用户手工拼接隐含参数。

### Phase 2：Image-to-native-SVG

目标：完成真实蓝图驱动的视觉拆解、原生 SVG 重绘和量化 QA。

开发项：

- 重写 `scripts/high_density/scene.py`。
- 重写 `scripts/high_density/svg.py`。
- 新增视觉 metrics、comparison 和 review 模块。
- 实现组件、文字、图片、z-order、overflow 和 transform 校验。
- 建立不同视觉类型的 7 页 fixture。

最小验收：

- AF-05 至 AF-10 全部通过。
- 3 类复杂页面完成至少一次返修闭环。
- 每页 metrics 来自真实渲染并绑定 hash。
- self-review 和 main review evidence 完整。

停止点：

- 蓝图变化不能稳定影响 SVG。
- 仍存在手工填写相似度通过的入口。
- 锁定内容或必需组件可以静默遗漏。

### Phase 3：SVG-to-DrawingML + Handback

目标：让已批准 SVG 真正成为可编辑 PPTX 的编译来源，并完成质量闭环。

开发项：

- 重写 `scripts/high_density/pptx.py` 为 SVG parser/compiler。
- 新增 DrawingML writer 和 conversion trace。
- 新增 OOXML readback 和 SVG/PPTX render comparison。
- 单页 PPTX 通过后合并完整 deck。
- 接回 canonical handback、`next-step` 和 `deck-quality`。
- 运行 7 页 fixture、provider smoke 和 73 页外部 benchmark。

最小验收：

- AF-11 至 AF-13 全部通过。
- approved SVG 的任何可见变化都能进入 PPTX。
- 7 页 fixture 全部通过 SVG/PPTX 双视觉门和 readback。
- 一页 fresh provider smoke 端到端完成。
- external benchmark 形成可审计结果。

停止点：

- PPTX 仍可绕过 SVG 生成。
- unsupported SVG 元素被静默丢弃或降级。
- PPTX 结构通过但 render 与 SVG 显著不一致。

## 17. 工程任务包

| Task | Scope | Primary files | Exit evidence |
| --- | --- | --- | --- |
| HD2-000 | Spec、旧口径和 capability 状态重置 | docs、skill manifest | v2 成为 active spec |
| HD2-001 | v2 contracts 和 schema registry | `docs/contracts/`, `contracts.py` | schema tests |
| HD2-002 | input/path/lineage hardening | `content.py`, `engine.py` | AF-14 至 AF-17 |
| HD2-003 | watch 和 capability dependencies | `deck_master.py`, `installer.py` | AF-18、AF-19 |
| HD2-100 | 8 样式 registry 和 style lock | Skill assets、contracts、engine | style selection gate |
| HD2-101 | NBB plan 和 content lock | `content.py`, Skill instructions | AF-01、AF-02 |
| HD2-102 | content-aware prompt 和 blueprint lineage | `blueprint.py` | AF-03、AF-04、AF-20 |
| HD2-103 | Agent continuation | Skill、engine status/action | single invocation smoke |
| HD2-201 | visual registry 和 scene v2 | `scene.py` | AF-05、AF-06 |
| HD2-202 | native SVG authoring contract | `svg.py`, Skill references | AF-07、AF-09、AF-10 |
| HD2-203 | measured visual QA | new visual QA module | AF-08、real metrics |
| HD2-301 | SVG parser 和 DrawingML compiler | `pptx.py`, new compiler package | AF-11 至 AF-13 |
| HD2-302 | OOXML readback 和 render parity | readback module | page/deck readback |
| HD2-303 | handback/retry/quality integration | `engine.py`, runtime | canonical contracts pass |
| HD2-304 | fixture/provider/73-page acceptance | tests、release evidence | final acceptance report |

任务必须按 Phase 顺序推进。Phase 1 未通过时不得提前大规模开发编译器；Phase 2 未通过时不得把 PPTX 可编辑性当作产品完成证据。

### 17.1 首批 failing tests 与验证命令

Phase 0 首批 failing tests：

```text
test_prepare_rejects_malformed_page_package
test_prepare_rejects_cross_run_page_package
test_retry_rejects_unknown_or_unsafe_page_id
test_watch_waits_until_stable_end_state
test_capability_blocks_missing_visual_dependency
```

验证命令：

```bash
.venv/bin/python -m pytest -q tests/test_high_density_phase0.py
```

Phase 1 首批 failing tests：

```text
test_production_requires_approved_style_lock
test_style_lock_change_invalidates_blueprints
test_nbb_blocks_low_density_without_evidence
test_nbb_rejects_unsupported_factual_claim
test_content_lock_contains_required_components_and_text_refs
test_blueprint_prompt_changes_with_locked_content
test_blueprint_manifest_requires_prompt_before_image
```

验证命令：

```bash
.venv/bin/python -m pytest -q tests/test_high_density_nbb.py tests/test_high_density_blueprint.py
```

Phase 2 首批 failing tests：

```text
test_distinct_blueprints_produce_distinct_svg
test_scene_rejects_missing_required_content
test_svg_rejects_missing_required_component
test_visual_metrics_are_computed_from_artifacts
test_near_full_image_is_blocked
test_image_cannot_cover_p0_text
```

验证命令：

```bash
.venv/bin/python -m pytest -q tests/test_high_density_reconstruction.py tests/test_high_density_visual_qa.py
```

Phase 3 首批 failing tests：

```text
test_svg_mutation_changes_pptx_trace_and_render
test_scene_mutation_without_svg_change_does_not_change_pptx
test_unsupported_svg_element_blocks_compile
test_pptx_readback_matches_svg_text_and_geometry
test_seven_page_high_density_end_to_end
```

验证命令：

```bash
.venv/bin/python -m pytest -q tests/test_high_density_drawingml.py tests/test_high_density_end_to_end.py
```

每张工程卡必须记录：

- 限定修改文件。
- 首个 failing test。
- 实现后的最小验证命令。
- 失败停点。
- checkpoint commit。
- 下一张卡的 resume prompt。

## 18. Pull Request 切分

推荐 4 个主 PR，每个 PR 都能独立验证：

1. `HD2-Phase0`: contracts、security、lineage、watch、capability。
2. `HD2-Phase1`: NBB、content lock、prompt、ImageGen lineage、Agent continuation。
3. `HD2-Phase2`: visual registry、Scene、native SVG、measured visual QA。
4. `HD2-Phase3`: SVG-to-DrawingML、readback、handback、完整 acceptance。

规则：

- 不允许把四个 PR 各自做成只有接口的空壳。
- 每个 PR 必须包含该 Phase 的正向、负向和 metamorphic tests。
- Phase 退出证据缺失时，后续 PR 只能保持 draft。
- 最终 PR 合并前重新执行全部反伪实现探针。

## 19. GStack / AutoPlan 评审产物

工程实现开始前必须连续完成：

### 19.1 `office-hours`

产出：

- 核心链路和 Agent/代码边界确认。
- v2 contract 版本决策。
- SVG compiler 支持范围决策。
- 视觉指标和 73 页 benchmark 边界确认。

### 19.2 `plan-ceo-review`

产出：

- 产品目标和首版完成口径。
- 本轮不做清单。
- 四阶段 PR 范围锁。
- 产品验收和外部 benchmark 的 go/no-go 条件。

### 19.3 `plan-eng-review`

产出：

- 文件级实现计划。
- schema 和状态迁移计划。
- renderer/compiler 依赖决策。
- 安全、性能、恢复和回归风险。
- 每个任务的首个 failing test、验证命令和停点。

### 19.4 `qa-only`

产出：

- 反伪实现矩阵结果。
- 7 页 fixture 结果。
- provider smoke 结果。
- SVG/PPTX 视觉对照报告。
- 73 页外部 benchmark 摘要。
- final go/no-go。

## 20. First Core Engineering Acceptance

本轮只有同时满足以下条件，才能声明 High-density Builder 核心引擎完成：

1. 四项核心能力全部达到 `4/4`。
2. Phase 0-3 各自最小验收全部通过。
3. AF-01 至 AF-20 全部通过。
4. 7 页 fixture 使用不同蓝图并完成端到端验证。
5. 一页 fresh provider smoke 完成 prompt -> blueprint -> SVG -> PPTX。
6. NBB 产出能证明内容结构和解释深度真实增加，所有事实保留证据 lineage。
7. Blueprint 由页面真实内容驱动，prompt/image lineage 完整。
8. SVG 由实际蓝图驱动，真实 metrics 和双角色 Review 通过。
9. PPTX 由 approved SVG 编译，修改 SVG 会改变 PPTX。
10. P0/P1 锁定文本、组件和 trace coverage 为 100%。
11. SVG/PPTX 双视觉门和 OOXML readback 通过。
12. retry、watch、invalidation、capability 和 `next-step` 可恢复。
13. canonical handback 可被 `deck-quality` 消费。
14. 外部 73 页 benchmark 完成并形成脱敏结果摘要。
15. standard profile 全量回归通过。

以下证据不能单独支持完成声明：

- schema validation 通过。
- SVG XML 可解析。
- PPTX 文件成功生成。
- `pictures=0`。
- 现有 14 个结构测试通过。
- 手工填写的视觉 review JSON。
- 旧 73 页手工 MVP 已完成。

## 21. 发布与回退

- v2 未通过 First Core Engineering Acceptance 前，capability 状态保持 `experimental` 或 `external_adoptable`。
- standard profile 始终保留为默认路径。
- High-density v2 失败时不能自动回退到 standard 并伪装成功。
- 允许用户显式重新选择 standard profile。
- v2 release 需要独立 release note、contract matrix 和 migration note。
- 回退版本时保留旧 run，只禁止其进入 v2 completed。

## 22. 最终交付清单

- Active v2 Spec。
- v2 contract schemas。
- 更新后的独立 Skill instructions。
- NBB/content lock implementation。
- Prompt/ImageGen lineage implementation。
- Image-to-SVG workflow and validators。
- Measured visual QA implementation。
- SVG-to-DrawingML compiler。
- OOXML readback and render parity gate。
- 7 页 sanitized fixture。
- Provider smoke evidence。
- 73 页 external benchmark summary。
- QA final report。
- Release and migration notes。

本轮开发结束的判断依据是核心链路的真实行为和证据，不以文件数量、接口数量或结构测试数量代替。

## 23. 参考能力迁移与冲突裁决

### 23.1 迁移矩阵

| Reference | 必须迁移的行为 | 新实现位置 | 禁止照搬的路径 |
| --- | --- | --- | --- |
| CyberPPT | MBB/NBB 证据表、故事线、SCR、页面物料池、密度与组件清单、8 样式、内容锁、内容驱动 ImageGen | Runtime Stage A/B、Skill instructions、style registry | hybrid Image-to-PPT 直接生产、ImageGen 事实化、低密度大纲 |
| `native-svg-redraw` | 全元素登记、量测、原生 SVG、图标/曲线检查、self-review、main review、批次状态权限 | Runtime Stage C/D、visual contracts、review evidence | 运行时调用外部 Skill、只做 XML 检查、整页图片封装 |
| Product Design `image-to-code` | 锁定唯一参考图、同尺寸实现、真实渲染、逐轮 design QA、参考图与结果同状态比较 | Blueprint normalization、comparison、metamorphic tests | 前端 DOM/CSS 实现方式、与 PPT 无关的交互和响应式逻辑 |
| PPT Master | SVG 作为生成 PPTX 的输入、受控 SVG 子集、DrawingML/native object、trace、真实渲染和 package postflight | Runtime Stage E、仓库内 compiler/readback | 运行时依赖 PPT Master Skill、复制完整 pipeline、Scene 旁路编译 |
| OfficeCLI | PPTX 结构检查、后续颜色/排版/文字调整、交付后运营 | `deck-quality` 后的可选流程 | 用后处理掩盖上游 SVG 或编译器失真 |

### 23.2 核心冲突裁决

| Conflict | Decision |
| --- | --- |
| CyberPPT 复杂视觉图片化 vs 全量可编辑 | 主要信息原生化；小范围无文字复杂资产可注册，受面积、覆盖和来源门控制 |
| Blueprint 随机文字 vs 真实内容 | Blueprint 文字只用于区域提示；最终文字全部来自 content lock |
| Scene 语义便利 vs SVG 权威输入 | Scene 作为 sidecar；SVG 决定 PPTX 几何、样式和 z-order |
| 高还原度 vs 编译器支持范围 | 支持范围内原生重建；不支持元素显式阻断，禁止静默简化 |
| 自动指标 vs Agent 视觉判断 | 工具负责量化指标，Agent 负责语义裁决，两类证据都必须存在 |
| 批量效率 vs 逐页质量 | 可并行生成，逐页门独立；所有页面通过后才能 deck handback |
| 独立 Skill vs 参考代码复用 | 迁移行为、合同思想和测试方法；仓库内重新实现，不建立运行时导入或软链接 |

### 23.3 需求追踪

| User requirement | Spec coverage | Acceptance evidence |
| --- | --- | --- |
| 沿袭 CyberPPT NBB 内容丰富 | §8、§16 Phase 1 | AF-01/02、NBB fixture、provider smoke |
| 保留 CyberPPT 生图完成度 | §9、§23.1 | prompt/image lineage、8 style lock、fresh blueprint |
| 图片到 SVG 高还原 | §10、§11 | AF-05 至 AF-10、真实 metrics、双角色 review |
| 解决文字/视觉/比例漂移 | §9.4、§10.4-10.7、§11 | frame transform、overflow、bbox、SSIM |
| SVG 转可编辑 PPTX | §12 | AF-11 至 AF-13、trace、OOXML readback |
| 独立干净 Skill | §0、§5、§23 | suite capability、无外部 Skill runtime imports |
| OfficeCLI 后链路可编辑 | §3.3、§23.1 | approved PPTX 进入可选 post-processing |
| 73 页 MVP 路线工程化 | §15.5、§20 | external benchmark summary |

### 23.4 代码复用边界

- 可以复用 Deck Master 已有公共合同、Run OS、CLI、canonical handback 和测试工具。
- 可以参考外部 Skill 的行为、提示词结构、SVG 支持语义和 QA 方法。
- 新核心模块必须位于 Deck Master 仓库并由本仓库测试覆盖。
- 任何源代码迁移都需要单独记录来源、许可证和重写范围；默认按重新实现执行。
- `deck-builder-high-density` 的 production runtime 不得 import 或 shell-out 到 CyberPPT、`native-svg-redraw`、Product Design plugin 或 PPT Master Skill。
