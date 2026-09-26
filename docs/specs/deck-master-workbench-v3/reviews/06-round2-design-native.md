# Round 2 · 独立设计与浏览器 Review

日期：2026-09-26。分类：**OPERATE / 桌面制作工具**。这是原型评审，不是生产运行或真实 Host 验收。主 Agent 统一执行 design-review 的 skill-start 与 outside voice；本报告是独立原生审阅，未改原型。

**结论：整稿观看、跨层诊断、先试—交接—比较这条主线已经能理解；仍有 1 项 P1、2 项 P2，需要修复后复核。** 最重要的问题是“添加材料或调整要求”接收输入，却没有把输入保存到请求中。前一轮 SVG 候选与风格保留/再试修复已经实际走通，未复述旧错误。

## 输入与实际覆盖

| 输入 | 审查开始 SHA-256 |
|---|---|
| `prototype/index.html` | `eaad72febcf38cd5d801f971e17898358ae9ad262ffc71e005d03471e42c51fc` |
| `prototype/style.css` | `ac19349dd55c44b77ba46126e03ef6886fa8c9161a578168961026214c47b82f` |
| `prototype/app.js` | `4fcba39cd61412282415874f5fdc3bd172c7b7bd29ebae1e5b14973581649034` |
| `UI-SPEC.md` | `b8ba4c6c8a885a2c9abef8aa2fdda1bb6d387c0e156fb564800ee456b63eec31` |
| `WALKTHROUGH.md` | `d4d53e8a22f4a8923b94b144ff191ba600b1b9eee0ffbae4b59dda515d1213e9` |

DESIGN.md、UI-SPEC.md 已对照。WALKTHROUGH.md 审查时包含上一版 P12 限制；主 Agent 已安排并行更新，因此不作为本轮待修新缺陷。原型源码在本轮取证期间保持冻结。完整统一输入见 [06-round2-input.json](06-round2-input.json)。

使用 Python Playwright / Chromium，新建隔离 context，访问 `http://127.0.0.1:8766/`。实际视口 **1440×900、1280×800**。浏览了总览、画廊、单页原图与谱系、风格校准、P12 SVG、项目入口、运行与交付，并补查材料更新和 P19 缺失提示词。

两视口实际操作：风格请求→复制→模拟接手→返回→保留当前→调整要求再试；P12 保存意见→仅重建 SVG→接手→返回→固定 SVG v2/v3 比较；新建项目空字段验证；矩阵与画廊键盘；材料要求输入→请求→剪贴板。14 个初始视图均无文档横向溢出，操作过程中没有 pageerror。风格再试保留旧请求并新增第二条；P12 的 v2 反向箭头和 v3 正向箭头可见。

每个结论基于真实 DOM/操作记录；下述截图均通过 view_image 亲自查看。全部图片仍为合成样本。

## 第一印象与信息结构

我首先看到“把24页，作为一份方案来做”，然后是右上“看24页原图”，再看到“需要你处理”的第8、9页。它传达的是正在制作的一整份方案，有一条可立即执行的浏览动作。左侧五个模块把内容、图件、校准和执行分开，保持同一项目身份。冷墨底、琥珀动作、实线面板与克制圆角符合 DESIGN.md，没有营销网站装饰。

总览、画廊、项目入口的 trunk test 为 6/6；单页、风格校准、运行与交付为 5/6（页面身份/选项/位置清晰，但没有局部搜索；在当前单对象范围内不是阻断）。没有发现“这块区域不知用途”的主区域。画廊完整保留 16:9，缺项也保留同尺寸位置，确实解决逐文件观看的基本痛点。

## 可复现发现

### R2-N01 · P1 / high · 材料要求被静默丢弃

- **复现**：内容与来源→“添加材料或调整要求”→输入“请新增面向售后主管的北区上线约束，要求保留2026年10月开始试点”→“创建影响判断请求”→查看运行记录并复制文本。
- **实际**：任务 note 和剪贴板都仅保留硬编码“读取试点范围补充（合成），列出受影响的章节与页面；未经采用不改写当前内容。”用户刚输入的内容完全不在请求里；关闭对话框后也无法找回。
- **影响**：这个动作的用途就是提交新的材料约束。即使是模拟原型，收到的反馈也会使用户误以为自己的要求已经交接，破坏核心工作流的信任。
- **定位**：`prototype/app.js:134–135`，`#material-note` 被渲染，但 `material-impact` 分支不读取其值。
- **建议**：保存并展示用户输入到独立请求快照；保留任务的影响判断性质和合成标识。空值就地提示，不创建一个看似接受输入的固定请求。
- **证据**：[输入前](round2-native-evidence/material-before-1280.png)、[创建后](round2-native-evidence/material-after-1280.png)、[flows.json](round2-native-evidence/flows.json) 的 `materialTask.note` 与 `materialClipboard`。两视口一致。

### R2-N02 · P2 / medium · 切换工作区局部选项后键盘焦点回到入口

- **复现**：画廊，把焦点放到“SVG 16/24”按钮，按 Enter，再按 Tab。
- **实际**：Enter 后 activeElement 是 BODY；下一 Tab 到侧栏“←全部项目”，必须重新遍历导航才能回到画廊控件。
- **影响**：用户本来连续比较同一份稿的不同层，切换一次就失去操作位置。可见 focus ring 存在，但无法支持连续键盘工作。
- **定位**：`prototype/app.js:76,92`，`render()` 替换整个 `#app`；类似 `layout-*` 分支也采用相同整页重绘方式。报告只对本次实际复现的画廊切层作确定性结论。
- **建议**：局部重绘，或按稳定 action key 恢复被操作控件的焦点；页面导航则显式移动到新标题/工作区，不回 BODY。
- **证据**：[下一Tab落回全部项目](round2-native-evidence/gallery-focus-reset-1280.png)、[flows.json](round2-native-evidence/flows.json) 的 `galleryFocusAfterChange` 与 `galleryFocusAfterTab`。

### R2-N03 · P2 / medium · 总览矩阵形成144个Tab停靠点，状态按钮没有页和层身份

- **复现**：总览的矩阵第一格聚焦，按 ArrowRight 后仍停在原处；按 Tab 进入“✓已就绪”。继续 Tab 逐个穿过全部格子。
- **实际**：24行 × 每行6个按钮，共144个 tabindex=0；状态按钮 DOM 如 `<button class="cell-btn" data-action="page-1-script">✓ 已就绪</button>`，无 aria-label、页号或层名。UI-SPEC明确要求一次Tab进入、方向键移动，当前未呈现。
- **影响**：看屏用户能靠行列理解，键盘和读屏用户很难快速到达某页某层；逐个读“已就绪”也无法知道将打开什么。
- **定位**：`prototype/app.js:51` 的 `matrixRows()`；`app.js:144` 仅处理单页左右翻页，无矩阵键盘规约。
- **建议**：保留紧凑表格，补页/标题/层/状态的 accessible name；通过 roving tabindex 或合适的单入口网格实现方向键、Enter、Esc与回焦，不必把每格都撑成大按钮。
- **证据**：[矩阵键盘焦点](round2-native-evidence/matrix-keyboard-1440.png)、[flows.json](round2-native-evidence/flows.json) 的 `matrixButtons=144`、[DOM测量](round2-native-evidence/a11y-type-probes.json)。

## 额外测量与外部观点核验

以下测量在原生三个发现完成后按主 Agent 请求补查，**不冒充独立发现**，由总报告与外部 R2-E 条目合并归属：

| 项目 | 浏览器实测 | 判断 |
|---|---|---|
| 主动作高度 | “看24页原图”41px；固定双层比较/仅重建SVG均41px | 小于 UI-SPEC 的主要动作44px；桌面仍可点，属规格差距，不能记作通过 |
| 链路文字 | `.chain-number`、`.chain-state`均11px | 状态承载必要信息，小于12px下限，建议修正 |
| 提示词正文 | `.prompt-block p`14px，行高24.5px | 小于规格的正文/提示词16px；多段阅读可读性应提高 |
| 1280风格比较 | 两幅SVG约320×180和319×179px | 可以看色板与大结构，细字和数字难核对；当前没有放大动作，因此“保留本页事实”判断支撑不足 |
| P19提示词 | 左右两栏同样出现“历史未记录执行提示词”及“建立新提示词草稿” | 两个同级主按钮会让用户分不清为何有两份相同信息；宜在左侧呈现原图或单一缺口说明，右侧放唯一下一步 |
| 原生dialog键盘 | P12候选初始聚焦“关闭”，六次Tab仍在dialog内，Esc关闭后回“查看候选并比较” | **实际通过圈焦与回焦**，不接受“所有dialog都无焦点管理”的泛化；但dialog没有 aria-labelledby/aria-label，命名语义仍应补 |

证据：[候选320px画布](round2-native-evidence/candidate-width-1280.png)、[P19双份缺口](round2-native-evidence/prompt19-1280.png)、[a11y/type测量](round2-native-evidence/a11y-type-probes.json)、[补充DOM](round2-native-evidence/outside-corroboration-probes.json)。补充DOM中的 `prompt19DuplicateCount=0` 是脚本用错了精确匹配字符串（查的是规格文字“这张图的实际提示词未记录”）；应以完整 `prompt19Text` 和截图中的两份“历史未记录执行提示词”为准，不能用该计数否定重复。

## 十类别评分

评分是设计师对当前合成原型的**主观判断**，不是用户调研、可访问性认证或性能验收。采用 GStack 类别；每类从A开始，有影响发现扣分，额外测量中的规格差距纳入相关类别。整体 **B**；AI套路分 **A**。

| 类别 | 分数 | 依据 |
|---|---|---|
| 视觉层级 | A− / 8.5 | 主任务明确，P19重复主动作需收束 |
| 字体与阅读 | B / 8 | 层级稳，但11px状态和14px提示词偏小 |
| 间距与布局 | A− / 8.5 | 双桌面视口无溢出；1280候选细节不足 |
| 颜色与对比 | A / 9 | 冷墨与琥珀一致，状态同时有文字；未执行全色对比自动审计 |
| 交互状态 | B / 7.5 | 候选可保留/再试，dialog正确；材料输入丢失与焦点重置需修 |
| 响应式 | A− / 8.5 | 正式两视口可用；窄屏编辑不在本次范围 |
| 内容与文案 | B / 8 | “谁做下一步”清晰；材料请求未反映用户内容 |
| AI套路 | A / 9 | 工具布局、内容驱动，无营销卡片/渐变装饰 |
| 动效 | A / 9 | 克制状态提示，CSS支持 reduced-motion；未做设备级动画测试 |
| 性能感受 | A / 9 | 24页样本即时响应，仅本地CSS/JS请求；不是大图或300页性能证据 |

主观 goodwill：70→总览主动作80→同层画廊85→交接状态清楚90→保留/再试95→键盘回到入口85→矩阵连续Tab75→材料输入丢失50。这个数值只解释阻力的来源，不是测量结果。

## 已证实与未覆盖

已证实：两正式桌面尺寸的视觉与实际动作；P12固定同层SVG比较；风格候选保留并新建请求；原生dialog圈焦与Esc回焦；项目必填错误就地出现；没有横向溢出或pageerror。第一眼与跨页一致性总体成立。

未覆盖：VoiceOver真实朗读、自动WCAG全扫描、真实材料上传/目录选择/Host、保存未知/冲突/断线注入、多项目跨端恢复、真实图像缓存与300页压力、正常安装/字体包/导出文件。无外部资源请求是该合成原型的观察，不能推广为最终安装包证明。没有运行GStack自动视觉规则detector，`detector.mode=none`。

Recommendation: Fix the lost material requirements and keyboard context before accepting this prototype because these defects interrupt the user's next action and make the saved request differ from what the user entered.
