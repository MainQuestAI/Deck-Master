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
