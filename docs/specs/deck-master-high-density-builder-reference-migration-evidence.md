# High-Density Builder Reference Migration Evidence

日期：2026-08-05
适用实现：`deck-builder-high-density` v2  转载方式：行为提取与仓库内重写

## 结论

新 Builder 只迁移参考 Skill 的方法、输出约束和验收思想。运行时只依赖 Deck Master 自身的 contracts、Run OS、Pillow、NumPy、`rsvg-convert`、`soffice`、`pdftoppm` 和仓库内 SVG-to-DrawingML compiler。

外部 Skill 不通过 import、软链接、路径扫描或运行时命令调用进入生产链。

## 证据矩阵

| 参考文件 | 已确认的可迁移行为 | Deck Master 重写落点 | 冲突处理 |
| --- | --- | --- | --- |
| `/Users/dingcheng/.codex/skills/cyber-ppt/SKILL.md` | 内容先行、页面高密度、图片蓝图、禁止页码和内部生成标记、逐页生产 | `scripts/high_density/content.py`、`blueprint.py`、`style.py`、`skills/deck-builder-high-density/SKILL.md` | ImageGen 只提供构图证据，事实和文字回到 content lock |
| `/Users/dingcheng/.codex/skills/cyber-ppt/references/source-analysis.md` | source inventory、证据整理、素材与页面意图分离 | `content_lock.v2` 的 evidence ledger、source fingerprint | Page Package 成为唯一事实源 |
| `/Users/dingcheng/.codex/skills/cyber-ppt/references/storyline.md` | storyline、SCR、页面结论、论据、caveat、SO WHAT | `build_mbb_page()`、`mbb_plan.v1`、`content_lock.v2` | 由仓库内 MBB 实现确定性固化，禁止只保留字符计数 |
| `/Users/dingcheng/.codex/skills/cyber-ppt/references/visual-system.md` | 颜色、网格、排版、表格/图表语言和密度规则 | `CYBER_PPT_STYLES` 八套 registry、`style_lock.v1` | style lock 必须在生产 ImageGen 前批准 |
| `/Users/dingcheng/.codex/skills/ppt-master/SKILL.md` | SVG 作为页面作者源、可编辑导出、真实渲染和质量复核 | `scripts/high_density/pptx.py`、`visual.py`、handback | 不运行外部 Skill，不复用其运行时 pipeline |
| `/Users/dingcheng/.codex/skills/ppt-master/workflows/generate-pptx.md` | prompt/asset manifest 先于生成、SVG 逐页生产、渲染后检查、notes 与 package postflight | `blueprint_prompt.v1`、`svg_to_drawingml_trace.v1`、`pptx_readback.v2` | OfficeCLI 只保留给 deck-quality 之后的可选后处理 |
| `/Users/dingcheng/.codex/skills/ppt-master/references/executor-chart.md` | chart/table 的结构化绘制和可编辑对象要求 | Scene component signature、SVG 受控子集、DrawingML shape/freeform | 首版不承诺 PowerPoint 原生 Chart/Table，允许可编辑 shape group |
| `/Users/dingcheng/.codex/skills/ppt-master/references/svg-image-embedding.md` | 图片资产来源、媒体包检查、整页图片风险 | registered asset map、SVG image policy、PPTX media readback | 小范围授权资产允许，整页/近整页和覆盖 P0 文字阻断 |
| `/Users/dingcheng/.codex/skills/ppt-master/scripts/svg_to_pptx.py` | wrapper、canvas、package 和导出入口的行为参考 | `compile_pptx()` 的输入/输出合同 | 只参考接口边界，重新实现 compiler |
| `/Users/dingcheng/.codex/skills/ppt-master/scripts/svg_to_pptx/drawingml/` | text/tspan、shape、path、style、opacity 和 package XML 的拆分方式 | `scripts/high_density/pptx.py` 的 parser/compiler/trace/readback | 不复制代码；当前实现先覆盖受控 SVG 子集，unsupported element 明确阻断 |
| `/Users/dingcheng/.codex/skills/native-svg-redraw/SKILL.md` | 全元素登记、原生 text/shape/path、禁止整页 image、self-review/main-review、批次权限 | `page_scene.v2`、SVG validator、`visual_review.v2` | Agent 负责语义重绘和 Review，工具负责 hash、渲染、指标和门禁 |
| `/Users/dingcheng/.codex/skills/native-svg-redraw/references/redraw-contract.md` | 画布、标题、网格、卡片、连接、结论区、脚注逐项登记；文字使用 text/tspan | Scene element registry、bbox、z-order、text refs、overflow policy | SVG 是唯一页面视觉源，Scene 只做 sidecar |
| `/Users/dingcheng/.codex/plugins/cache/openai-curated-remote/product-design/0.1.52/skills/image-to-code/SKILL.md` | 单一参考图、同尺寸实现、真实渲染、并排比较、逐轮 QA | blueprint normalize、blueprint/SVG metrics、SVG/PPTX metrics、metamorphic tests | 只迁移视觉比对流程，不迁移前端 DOM/CSS 实现方式 |
| `/Users/dingcheng/.agents/skills/officecli/SKILL.md` | PPTX 结构查询、文字/颜色/布局后处理、交付前检查 | `deck-quality` handback 之后的可选工具边界 | 不用 OfficeCLI 掩盖 SVG 或编译器失真 |

## 迁移边界

### 保留

- CyberPPT 的 MBB 内容丰富框架：证据表、故事线/SCR、页面物料池、结论、论据、caveat、SO WHAT、组件计划和密度控制。
- CyberPPT 的高密度蓝图工作流：真实内容进入 prompt，prompt 先落盘，图片作为布局参考，禁止页码和内部标注。
- `native-svg-redraw` 的原生元素合同、逐元素登记、溢出阻断、self-review/main-review 证据。
- Product Design image-to-code 的同尺寸渲染比较和迭代 QA。
- PPT Master 的受控 SVG 子集、DrawingML 原生对象、trace、真实渲染和 package/readback 检查。

### 重写

- 所有 MBB、style lock、prompt、Scene、SVG validator、视觉 metrics、DrawingML compiler 和 readback 都在本仓库实现。
- 所有上游/下游 lineage 由 v2 contracts 和 hash 重新计算。
- 所有 Agent continuation action 通过 Deck Master status/next-step 合同表达。

### 明确排除

- CyberPPT 的 Image-to-PPT 直达路径。
- 以整页图片作为 PPTX 主要内容载体。
- Scene 绕过 approved SVG 直接生成 PPTX。
- 手工写 SSIM、视觉 review 或 completed 状态。
- 运行时导入外部 Skill 的脚本、软链接或缓存实现。

## 可验证证据

- `tests/test_high_density_builder.py`：既有 14 个高密度回归。
- `tests/test_high_density_builder_v2.py`：Phase 0 至 Phase 3 的 fail-closed、MBB、prompt、SVG、visual metrics、DrawingML 和 metamorphic 探针。
- `docs/contracts/*v2*.schema.json` 与 `contracts.py`：v2 生产合同和 v1 preview 识别边界。
- `high_density_build/reviews/*.metrics.json`：实际渲染输入 hash、遮罩 hash、局部 SSIM、bbox、颜色和 coverage。
- `high_density_build/traces/pptx_trace.json` 与 `readback/readback_report.json`：SVG 到 DrawingML 的逐元素 trace、文本、几何、notes、媒体和最终渲染读回。

73 页原始材料、原始蓝图和 provider payload 不进入仓库；最终发布只保留脱敏 evidence index、指标摘要和失败分类。
