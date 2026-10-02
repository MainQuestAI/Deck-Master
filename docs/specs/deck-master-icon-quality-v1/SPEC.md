# 图标质量规格与复审修订

## 复审结论

原建议缺少 SVG 对象边界、范围外不变的核心检查、候选实际 PPT 预览、固定图标许可和跨页语义确认。PR91 将这五项落实为可追溯的图标方案、零生图调用试作及明确采用。

## 用户工作流

在 SVG/PPT 单页框选并保存意见，在“优化图标”选入意见、选择忠实重绘/标准替换/已采用样例复用，将固定要求交给 Agent。复制表示交接材料已复制，不表示任务已经启动。Agent 使用 `icons inspect` 读取真实对象，再 `icons propose` 提交对象对应和处理建议。UI 显示原图区域与 SVG 区域的固定版本局部对照，用户确认范围及方式后选择本次页面并预览、提交现有 changes 计划。

Host 按工作单执行 repair，完整返回 SVG，核心校验非目标对象不变；只有用户采用后替换当前稿。候选工作面提供原图、基准和候选局部对照，可切换 SVG/实际 PPT。工程检查、待视觉确认及真正采用保持不同状态。缺少工具、失败、未请求都如实显示。

跨页需先采用一个样例。Agent 提议明确使用页、语义、独立对象范围与尺寸；用户默认不勾选任何页，同页多个图标合并为一个候选。批量采用沿用 all-or-none CAS。采纳后继续已有页面审查和整稿制作，不绕过最终审查。

## 核心边界

- 唯一 schema 来源仍为 `src/deck_master/resources/contracts/`。`icon_input.v1` 包含项目/基准/意见/目标；每目标固定 Page、SVG、原图引用，每图标保存两组独立区域、语义、对象定位、方式和样式。
- 定位为固定 SVG 引用、XML 元素路径和子树 SHA。缺失/重复 ID 不影响身份；多个对象不得嵌套。文本、图像、根、共享定义或含正文的分组不可替换。
- 对选区外 XML 结构、属性、顺序和文本做规范化比较。新对象只允许显式原生几何；不得引入图片、脚本、外部引用或修改共享定义。范围内也必须保持所确认标准资产/复用样例及目标显示区域。
- `icon_recipe.v1` 是用户确认后的不可变对象，通过 operations 事务存入 Document。未确认建议仅在派生 inbox 展示，不是已提交事实。
- 第一次确认提升 `minimum_writer=icon-quality.v1`；旧核心拒绝该指针，新核心读取旧项目不迁移。图标任务要求 `icon_repair` capability。
- `icons plan` 固定 `mode=trial/stage=repair/max_calls=0`，复用 changes commit、task accept、candidate plan/adopt 与取消、迟到、回执恢复机制。普通候选与旧批注不改变语义。

## 标准资产

随包 Lucide 1.49.0：file-text、folder、database、server、cloud、cpu、network、workflow、git-branch、bot、users、user、shield-check、lock、search、chart-no-axes-combined、chart-pie、settings、circle-check、circle-alert、refresh-cw、upload、download、layers。

保留来源、每文件 SHA、上游完整 ISC/适用 Feather MIT 许可，离线使用。标准图标等比放置，颜色/线宽在方案中明确，圆端点与圆连接保留。标准资产的许可标记保存在 SVG，并嵌入编译 PPT 的文档说明。页面图标不套用工作台控件图标规格。品牌标志与业务专用图形不自动标准化。

## 真实候选检查

`candidate-preview request/status` 在独立目录编译单页并真实渲染、回读。缓存绑定候选、Page、画布、字体、资产和工具链；每项目串行、重复请求合并；只写派生检查缓存，不切换当前稿。图标采用在核心中重新验证范围与检查结果，采用回执与采用历史保存检查证明及内容寻址的 PNG/SVG/PPT/回读文件，缓存清理后仍可工程恢复。候选或工具链变化不能复用旧结果；不存在 PNG 时不得用 SVG 冒充。

工程结果不证明图标语义和美观。精细度不足按本次用户决定为可优化；未检查不能标记通过，用户视觉认可需独立真实记录。

## 接口

CLI `deck-master icons inspect/catalog/list/propose/confirm/plan/draft`；`draft` 只给 Host 构造标准/复用几何，仍必须领取任务并提交结果。派生 `/api/icons/preview` POST 提供固定建议 SVG，明确区别于候选及实际 PPT。HTTP `/api/icons/inspect|catalog|list` 为读，`propose|confirm|plan` 为受保护 POST。候选检查有 CLI `candidate-preview request/status` 与同名 HTTP，文件只通过已验证缓存白名单读取。UI capability 为 `icon_quality.v1`。

不包含通用矢量编辑器、自动语义巡检、任意外部资产导入和在线市场。
