# NOVA p09 下游最小交付

用户要求继续交付 SVG、可编辑单页 PPTX 和实际渲染，当前工作树实现并跑通这一页。

- 新接口：`compiler.compile_deck(SvgInput[], CompileOptions, output_dir)`。显式注入 Node 与 Artifact Tool 模块，不读取旧 OS。受控 SVG → 派生 IR → 原生形状/文字，不维护第二份手工 Scene。
- `resources/compiler/native.mjs` 为当前 Artifact Tool 新适配层，不是旧 B0/K0 代码提取。B0/K0 完整迁移比较尚未完成，不能关闭 T08.01。
- 支持当前页所需 rect/circle/ellipse/line/polygon/polyline/path(M/L/H/V/C/Q/Z)/text/tspan。曲线派生为原生多段线，当前精度0.2像素。外链、脚本、变换、渐变等当前不支持；不是通用 SVG 实现。
- PPT 原生文字、路径、图元可编辑；表格由图元构成。透明/分组/复杂继承更广反例仍由 T09 完整验收负责。
- 4:3 的真实单页编译、包校验、文字回读、LibreOffice 实际渲染和原图/SVG/PPT对照通过。未声称 PowerPoint 应用验证或多页完成。
- tests/rebuild 111 passed，源码基线 `1c2bb80` 加未提交工作树。
- 外部产物：`/Users/dingcheng/Downloads/Deck-Master-single-page-20260916/`，见 README、readback.json、build/final-validation.json。

T07/T08/T09/T10 仅有本页最小交付证据；其他子任务、完整状态机接线与 AC 仍保持未完成。T06 整卡仍待 T04 依赖。
