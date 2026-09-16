# 06｜独立SVG→PPTX内核与具体修复

## 06.1 API与依赖边界

拟接口：`compile_deck(inputs: Sequence[SvgInput], options: CompileOptions, output_dir: Path) -> CompileResult`。

SvgInput含page_id、SVG路径或字节、明确资产映射。CompileOptions含从Document.design_context解析的canvas、slide_size、实际字体与资产映射及受支持特性策略。adapter将有效配置显式传入纯内核；内核不得自己从HOME或另一配置文件选择默认。CompileResult含真实PPT路径、trace路径、每页对象映射、diagnostics、工具/内核版本。编译器不返回client_ready，不读取用户HOME，不读取故事线批准、content_lock签章或PPTMaster绑定。

`render_deck(pptx_path, output_dir, options)`实际生成预览；`readback(pptx_path, inputs, expected_content, expected_relations)`读取文件并对独立期待核验。解析trace可用于对象定位，但不是完整预期。文件IO、schema、图形语法与业务判断分开。

输入一致性由调用方固定字节或内容hash；读取期间文件发生变化应拒绝本次结果，不将混合输入登记完成。编译输出写新目录，成功后由store统一采用，不能覆盖已交付文件。

## 06.2 首轮SVG子集

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

## 06.3 必修缺陷与实现方向

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

## 06.4 字体、画布与可读性

默认画布只在Document创建时持久化为13⅓×7.5英寸/1600×900、contain。编译读取03.3a的有效配置，坐标按输入SVG viewBox计算，不硬编码1672/941。非16:9按Document明确设置；同一PPT不混合物理页尺寸。比例不同等比contain并报告留白，不暗中拉伸或裁切。

生产样式从任务指定和可用字体取得；默认中文字体通过doctor报告是否存在。缺字体不得静默替换后称完全保真。规范中的“字号可读”以实际PPT尺寸判断，不能仅大于0。首轮默认正文建议范围16–24pt、辅助文字10–14pt只是设计起点，不是强制所有页面统一字号；实际必须能在目标展示方式读清。业务关键字不得1pt/透明藏字；放不下时修改布局或内容页分配，不自动无限缩小。

当硬阈值无法判定可读性，报告明确对象和实际字号/截图供审阅，不因为低于某一通用阈值自动删正文。用户明确密集打印用途可用较小字，但仍需实际阅读验证。

## 06.5 单元与真实转换验收

纯函数测试覆盖几何端点、圆极值、颜色alpha、字重映射。XML测试检查真实DrawingML里的内容、端点、path/connector、透明度、字体。真实渲染测试分别渲染输入SVG与输出PPT，比较局部特征与文字；不是只查trace。

桌面编辑验收：用目标PPT应用打开实际当前产物，修改一处关键文字和一条关键关系/图形，保存重开确认。LibreOffice headless成功不是PowerPoint桌面编辑已验证；无法进入桌面时标pending，保留工程结果不越级。

图标/曲线/表格/文字都可有局部误差诊断；核心业务节点、数字、端点错误必须修。原生对象数量与“图片数0”不是成功标准；产品照片作为图片正常，关键正文整页图片不等价可编辑交付。

## 06.6 实施落点与失败后的去向

先在compiler/内完成独立可调用接口和测试，再由production调用；不把质量审批注入compile_deck要求它读业务批准。unsupported对象返回code/page_id/element_id/feature/recovery；上层请求对应SVG修改或替换转换组件，不能悄悄退fixture。

相同语义SVG的字体或line错误，修内核后只重编译受影响输出；不得为适应bug把原图重画成没有图标/连线的卡片。内核替换必须遵守同一接口与坏样例，不另造一套runtime。

## 06.7 首版可编辑能力承诺

首版承诺高保真的**可编辑形状、路径与文字**。表格用可编辑形状/文字组成，Page.table保留行列和值以便工作台修改后重生成，但不承诺Office原生Table的增删行列操作。图表可按SVG画成可编辑形状组，首版不实现原生Chart数据序列/嵌入工作簿接口，不承诺PowerPoint“编辑数据”。“原生PPT对象”在此指DrawingML形状/文字，不等于原生数据图表。

PPT Artifact.editability为editable_shapes_and_text；导入旧文件且未核验为unknown。该字段不自动证明实际对象可编辑，必须按06.5在目标应用修改文字与图形。UI、README、导出说明同样写清“可编辑形状/文字；非原生数据图表/表格”。不能通过默认提供chart模型或新增编译接口悄悄扩大本轮范围。

用户任务明确要求Office原生图表编辑数据时，说明首版不支持，不能把形状组当作满足。后续若纳入，需单独数据/单位/序列与编辑验收，不挤入本次修订。

## 06.8 最小制作切片与最终支持范围

T08/T09/T10可在当前事故页实际需要的子集上先交付真实成品：该页需要的圆角/文字/线条问题必须修好，不能先删去原图对象以缩小子集。暂时未实现且本页不涉及的通用SVG特性、全部材料格式，不阻止T10.min试做；T10整体完成仍需06.2最终范围验收。早期同一工作台至少显示正文、原始蓝图、SVG预览与PPT真实渲染，Host/人类实际对照不可省略。
