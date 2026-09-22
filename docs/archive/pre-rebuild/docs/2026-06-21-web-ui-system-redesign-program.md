# Deck Master localhost Web UI 系统级重构方案

日期：2026-06-21
状态：规划稿 v1.0
适用范围：Deck Master localhost Web UI 的产品级重构
文档角色：本稿是上位重构方案；[2026-06-21-web-ui-design-spec-v0.2.md](/docs/2026-06-21-web-ui-design-spec-v0.2.md) 降为其中的界面级子稿

## 1. 结论

你的判断是对的。Deck Master 当前 Web UI 属于一次完整的产品级重构，不适合按“小迭代优化”来处理。

原因很直接：

1. 当前界面仍处在 demo / prototype 阶段。
2. 之前的设计文档主要在修“现状哪里不对”，还没有定义“成熟产品应该怎样运作”。
3. 真正缺失的层，不只是一层布局，而是五层系统：
   - 产品任务定义
   - 用户故事和操作路径
   - 前端语言系统
   - 交互与状态系统
   - 视觉与品牌化设计标准

所以这轮不能再把 Web UI 当成 `Review Cockpit` 的壳层收口。它需要被重新定义成：

> Deck Master Run OS 在浏览器中的专业操作界面，用来承接一次 Deck run 从理解状态、审查页面、处理证据与风险，到推进审批闭环的核心用户体验。

## 2. 为什么上一版不够

上一版 `v0.2` 只完成了三件事：

- 证明当前原型首屏有明显问题。
- 把首屏信息架构和局部模块关系讲清楚。
- 给出下一轮 UI 重排方向。

它没有完成这些更关键的事情：

- 没有把 Web UI 放回 Deck Master 的总产品地图里。
- 没有定义完整 user story。
- 没有定义不同角色和不同任务阶段。
- 没有定义语言系统应该怎样承接 Run OS。
- 没有定义交互设计原则和失败路径。
- 没有定义视觉系统是否符合 `Main Crystal Design`。
- 没有定义这轮到底是 `review-only`，还是 `review + steering + approval` 的操作台。

换句话说，`v0.2` 更像“局部设计诊断”，还不能作为这次大迭代的总设计方案。

## 3. 本轮重构的真实目标

这轮重构要解决的核心，不在“UI 看起来像不像成熟产品”这一层，而在下面四个更深的问题：

1. Web UI 在 Deck Master 体系里到底承担什么职责。
2. 用户在一次 run 中真正要完成哪些任务。
3. 这些任务该如何被组织成清晰、可信、专业的前端体验。
4. 这个体验的语言、交互、视觉和状态表达，是否匹配 Deck Master 的高端专业定位。

因此，这轮重构的目标应改写为：

> 重建 Deck Master localhost Web UI，使其从 demo 级审查面板升级为 Run OS 的专业操作界面，能够支撑用户理解 run、审查页面、处理证据和风险、完成审批闭环，并在语言、交互、视觉和状态表达上达到成熟产品标准。

## 4. 重构对象的上位定位

### 4.1 Web UI 不是孤立页面

Web UI 是 Deck Master 的三大操作面之一：

- Agent：负责讨论、追问、解释、调度、恢复。
- Runtime / CLI：负责执行、生成、状态落盘、质量检查。
- Web UI：负责可视化理解、页面级判断、审批推进和风险处理。

### 4.2 Web UI 的职责边界

Web UI 本轮应负责：

- 理解一次 run 的当前状态。
- 识别下一步应该处理什么。
- 查看页面是否成立。
- 理解来源、证据、质量风险和审批状态。
- 推进审批闭环。
- 让用户对“这个 run 离可交付还有多远”形成判断。

Web UI 本轮不负责：

- 复杂对话。
- 长期知识浏览。
- 多项目后台。
- 完整 PPT 编辑。
- 团队协同管理。

### 4.3 Web UI 的产品形态

本轮重构后，Web UI 的产品形态不应再叫“预览 UI”，也不只是“Review Cockpit”。

更准确的定义应该是：

> Run Workspace Interface

它既有审查任务，也有推进任务；既是看板，也是一套有限但高价值的操作界面。

## 5. 这轮必须补齐的六层系统

## 5.1 用户系统

第一用户仍是售前解决方案架构师，但在 Web UI 里要进一步拆成三种使用心态：

1. 审稿心态
我想判断这页能不能过。

2. 交付心态
我想知道这一套 Deck 离可交付还有多远。

3. 返工心态
我想知道下一步该补什么、改什么、重跑什么。

Web UI 的成熟度，取决于它能否同时服务这三种心态。

## 5.2 用户故事系统

本轮至少要明确以下用户故事：

### A. 打开 run 的用户故事

作为售前解决方案架构师，我打开一个 run 后，希望在 5 秒内知道：

- 这套 Deck 当前是否可继续。
- 当前最严重的问题是什么。
- 我应该先看哪一页或哪一类问题。

### B. 单页审查的用户故事

作为主审人，我打开一页后，希望在 30 秒内判断：

- 这页讲什么。
- 为什么是这页。
- 它的来源是否可信。
- 它缺什么证据。
- 它现在能不能批准。

### C. 返工推进的用户故事

作为推进者，我希望系统明确告诉我：

- 哪些页只是待审。
- 哪些页是缺证据。
- 哪些页是质量阻断。
- 哪些页需要重新生成。

### D. 交付判断的用户故事

作为最终交付前把关人，我希望知道：

- 当前能导出哪些页。
- 哪些页会卡住交付。
- 风险是否已被显式处理。

### E. 恢复工作流的用户故事

作为中断后回来的用户，我希望重新打开 Web UI 时：

- 回到上次的 run。
- 回到上次的页。
- 延续上次的判断上下文。

## 5.3 任务系统

Web UI 里的任务不能再平铺。应分成四条任务线：

1. `Run Orientation`
   - 看清 run 当前状态
   - 看清下一步
   - 看清总体风险

2. `Page Review`
   - 看预览
   - 看职责
   - 看来源
   - 看证据
   - 看质量
   - 审批 / 备注

3. `Remediation`
   - 处理缺证据
   - 处理待生成
   - 处理质量阻断
   - 明确返工路径

4. `Delivery Readiness`
   - 看 approved queue
   - 看 blocked queue
   - 看 override
   - 判断是否可进入导出

这四条任务线决定了界面的骨架，也决定了导航结构。

## 5.4 语言系统

当前 Web UI 最大的问题之一是语言层没有产品化。

本轮需要单独定义前端语言系统：

### 语言系统原则

1. 用户看到的是业务语言，不是运行时字段。
2. 首屏语言必须帮助判断，不负责暴露底层实现细节。
3. 中文和英文都必须是完整语言，而不是“中文说明 + 英文状态枚举”拼接。
4. 所有关键状态都要有“用户能懂的名字”和“系统内部名字”两层。

### 语言层分层

- `L1 任务语言`
  - 当前最该做什么
  - 这页能不能过
  - 哪些页面卡住交付

- `L2 解释语言`
  - 为什么被阻断
  - 缺什么证据
  - 为什么建议重跑

- `L3 系统语言`
  - run id
  - source id
  - artifact 名称
  - 枚举值

### 典型改写例子

当前写法：

```text
preview_ready · needs_generation_session
```

成熟写法：

```text
预览已就绪
仍需创建生成会话，当前生成链路还未完成
```

## 5.5 交互系统

当前界面的问题不在“有没有按钮”，关键在交互层没有层级。

本轮需要把交互拆成三层：

### 一级交互：主任务动作

- 进入某页
- approve
- reject
- request evidence
- add note

### 二级交互：推进动作

- rerun generation
- jump to blocked page
- open claim coverage detail
- open export blocked detail

### 三级交互：高级控制动作

- replace source
- convert to generate
- lock source
- override quality block

原则：

- 一级动作永远直接可见。
- 二级动作放在上下文区域内。
- 三级动作默认折叠，避免污染主审查路径。

### 必须定义的交互态

- loading
- empty
- partial
- blocked
- success
- save in progress
- save failed
- stale data warning

### 必须定义的中断处理

- run 不存在
- preview 丢失
- manifest 损坏
- page action 失败
- generation 未完成
- export 被 P0/P1 阻断

## 5.6 视觉系统

现在这层已经不再悬空。老板已经明确指定使用 MainQuest 的 MQDS v4.1 体系，这一层的品牌基线已经锁定。

所以这轮要把视觉系统分成两部分：

### A. 可直接定义的 Deck Master 视觉原则

- 高信任感
- 高信息密度但不拥挤
- 专业操作工具感
- 克制，不做 SaaS 模板味
- 页面预览优先，系统信息服务判断

### B. `MainQuest VI / MQDS v4.1` 对齐层

这部分已经有正式规范，当前采用：

- 品牌系统：MainQuest AI Visual Identity System (MQDS) v4.1
- localhost Web UI 模式：Dark Mode `Glass Terminal`
- 参考文件：[2026-06-21-mainquest-web-ui-visual-alignment-spec.md](/docs/2026-06-21-mainquest-web-ui-visual-alignment-spec.md)

这一层现在需要做的，已经从“猜测标准”变成“把标准映射到 Deck Master 的 Run Workspace”。

## 6. 推荐的产品结构重构

### 6.1 从“预览页”升级为“Run Workspace”

建议新结构：

```text
Run Workspace
├── Run Header
│   ├── Run identity
│   ├── Current status
│   ├── Next step
│   ├── Risk summary
│   └── Delivery summary
├── Left Rail
│   ├── Run switcher
│   ├── Task filters
│   ├── Page queue
│   └── Counts
├── Main Stage
│   ├── Preview
│   ├── Page summary
│   └── Critical alerts
├── Decision Rail
│   ├── Role / claim
│   ├── Source / evidence
│   ├── Quality
│   └── Approval
└── Deep Panels
    ├── Claim coverage
    ├── Export readiness
    ├── External reviews
    └── Event log
```

### 6.2 从“模块堆叠”改为“任务流驱动”

当前页面更像：

> 把所有 API 面板都摆上来

重构后的产品应该更像：

> 先让用户判断 run，再判断页，再推进返工和审批

## 7. 本轮大迭代应该产出的正式设计包

这次不应只输出一个 Web UI spec。应该输出一整包设计材料：

### 7.1 Product Redesign Brief

回答：

- 为什么要重构
- 这轮重构改变什么
- 用户价值是什么
- 非目标是什么

### 7.2 User Story & Task Flow Spec

回答：

- 哪些角色
- 哪些核心任务
- 哪些关键路径
- 哪些失败路径

### 7.3 Information Architecture Spec

回答：

- 页面结构
- 导航层级
- 模块优先级
- 数据进入首屏还是深层面板

### 7.4 Frontend Language Spec

回答：

- 中文 / 英文术语表
- 状态文案规则
- 错误解释规则
- 操作按钮命名规则

### 7.5 Interaction Spec

回答：

- 主动作 / 次动作 / 高级动作
- 状态变化
- 保存反馈
- 阻断与确认机制

### 7.6 Visual System / Main Crystal Alignment Spec

回答：

- 字体
- 配色
- 层级
- 卡片和边框原则
- 预览画布原则
- 动效原则
- 与 Main Crystal 的对齐方式

### 7.7 Validation Pack

回答：

- 验收标准
- 截图审计计划
- 关键用户路径 smoke 清单

## 8. 这轮规划的实现分期建议

## Phase A：产品定义重构

先做清楚：

- 上位定位
- 用户故事
- 任务流
- 页面边界
- 语言系统

如果这一步没做完，后面的 UI 重画只会反复推倒。

## Phase B：设计系统重构

再做：

- 信息架构
- 交互系统
- 视觉系统
- Main Crystal 对齐

## Phase C：界面级设计稿

最后才是：

- 首屏布局
- 页面队列
- 审查面板
- drawer
- 状态页
- 多语言稿

## Phase D：实现计划

等前三层锁定后，再写开发实现边界：

- 哪些属于 P0
- 哪些属于 P1
- 哪些继续延后

## 9. 当前最关键的缺口

这轮要继续往前，当前有三个最关键缺口：

### 缺口 1：没有完整的前端语言设计

这会导致 UI 永远带着内部系统味，而不是成熟产品味。

### 缺口 2：没有从用户任务出发的完整故事板

这会导致界面继续从 API 拼接出发，而不是从用户要完成什么出发。

### 缺口 3：还没有把 MQDS v4.1 映射成 Deck Master 专属组件规范

品牌基线已经有了，但 Deck Master 仍需要自己的组件映射和产品语义。

## 10. 我建议的下一步

下一步不要直接继续改 `v0.2` 的局部布局。

更合理的路径是：

1. 先确认这轮升级为“系统级 Web UI 重构”。
2. 先补一份上位 `Redesign Brief`。
3. 再单独出：
   - user story spec
   - language spec
   - interaction spec
   - visual / MQDS alignment spec
4. 最后再重写界面级 `Web UI Design Spec v1.0`。

## 11. 当前已锁定的决定

这轮规划里，视觉层已经锁定以下决定：

1. 使用 MainQuest MQDS v4.1。
2. localhost Web UI 采用 Dark Mode `Glass Terminal`。
3. Light Mode `Paper Architecture` 本期不进入主审查路径。
4. 后续所有界面级 spec 默认继承 MQDS Dark token、组件语法和验收清单。
