# Deck Master Review Desk 修复迭代 Spec v0.3

日期：2026-06-23  
状态：已实现  
适用范围：`scripts/preview/static/`、`scripts/preview/server.py`、`scripts/preview/workspace_api.py`、相关测试

## 1. 结论

当前 Review Desk 已经完成 v0.3 修复：首屏层级、前台用语、安全边界和决策流已按本 Spec 收口。

本轮迭代目标只有一个：把当前 localhost Web UI 从“信息很多的项目工作台”收回到“能快速做页级判断的审稿桌”。

本轮实现后，用户进入首屏 5 秒内必须能明确四件事：

1. 现在在审哪个方案项目。
2. 当前卡在哪个阶段。
3. 下一步该推进什么。
4. 当前页是否能做决定。

## 2. 本轮要修的四类问题

### 2.1 顶部状态带过重

当前顶部做成了大面积总览卡片，吃掉了首屏有效高度，中央预览和当前页判断被压下去。

### 2.2 待准备态泄露内部执行语言

当前待准备态直接把 `next_command` 和本机路径带到前台，已经越过用户可见安全边界。

### 2.3 右侧决策流顺序失真

当前右栏把动作块放得过早、层级过多、标题重复，用户需要先拆界面，再做判断。

### 2.4 产品命名和文档真源不一致

现有 v0.2 设计稿、实现文档、设计系统和设计 QA 对前台主语存在分裂：有的写 `方案项目工作台`，有的写 `Review Desk / 审稿桌`。继续实现会放大歧义。

## 3. 根因判断

| 问题 | 根因 | 直接影响面 |
|---|---|---|
| 顶部过重 | DOM 结构和网格布局本身就是多卡片总览形态 | `index.html`、`style.css` |
| 命令和路径上屏 | 前台直接消费底层 `next_command` | `app.js`、`workspace_api.py`、`server.py` |
| 右栏失真 | 决策顺序没有锁死，动作、备注、定位、风险同时抢主位 | `index.html`、`style.css`、`app.js` |
| 预览权重不足 | 首屏 run 级信息仍然占太多位置 | `style.css`、`app.js` |
| 命名漂移 | 缺少当前迭代唯一真源 | `docs/2026-06-21-web-ui-design-spec-v0.2.md`、`docs/specs/web-ui/*` |
| 回归反复 | 现有测试对“可见文案安全”和“审稿桌结构”覆盖不够 | `tests/test_preview_static_contract.py`、`tests/test_review_cockpit.py`、截图审计流程 |

## 4. 本轮冻结决策

### 4.1 前台产品主语

- 前台产品名统一收口为：`审稿桌`
- `方案项目` 只表示当前正在处理的对象
- `工作台` 可以保留在少量辅助描述中，不能继续作为首屏主标题

### 4.2 首屏结构

- 顶部固定为紧凑状态带
- 左侧固定为任务目录
- 中央固定为当前页主舞台
- 右侧固定为当前页决策流
- 底部抽屉只承接 run 级补充信息

### 4.3 可见内容安全边界

- 所有用户可见区域禁止直接展示：
  - 原始命令
  - 本机绝对路径
  - `run` / `audit` / 内部状态串
  - 调试级 contract 字段名
- `next_command` 保留给机器执行和诊断链路
- 前台只能消费安全改写后的展示字段

### 4.4 决策动作层级

- 每个页面只有一个主动作
- 次动作最多两个
- 备注输入框放到动作后面，不能抢占页面定位和风险信息的位置

## 5. v0.3 体验目标

### 5.1 审稿态

进入 `待审阅 / 待补依据 / 待审批` 后：

- 中央预览成为首屏最强视觉焦点
- 顶部状态带压缩成短信息条
- 右栏顺序固定为：
  1. 页面定位
  2. 来源与依据
  3. 风险与缺口
  4. 处理动作与审批记录

### 5.2 待准备态

进入 `待准备 / 生成中` 后：

- 中央显示单一主叙事的阶段工作区
- 主信息固定回答：
  - 当前卡点
  - 责任对象
  - 建议动作
  - 预期结果
- 用户看到的是业务语言，例如“先生成首版页面与预览”
- 任何可复制命令都只允许放进诊断入口，默认隐藏

### 5.3 交付态

进入 `可交付 / 已交付` 后：

- 顶部保留交付阻断摘要
- 中央允许切到真实交付预览
- 右栏动作收口到交付判断与返修说明

## 6. 契约改造要求

### 6.1 新增展示层字段

本轮给聚合 payload 增加一组展示层字段，前台优先消费它们：

```json
{
  "display_stage_label": "待准备",
  "display_stage_definition": "项目已创建，正在补齐首版页面与预览。",
  "display_next_step_title": "下一步",
  "display_next_step_detail": "先生成首版页面与预览",
  "display_blocker_summary": "当前缺少预览文件",
  "display_primary_action_label": "等待预览就绪"
}
```

要求：

- 这些字段只承载用户可读语言
- `next_command` 继续存在，但归入机器字段
- 如果新字段缺失，前端必须经过安全改写后再展示，不能裸露原值

### 6.2 安全改写规则

前端和聚合层都要共享一套最小安全改写规则：

1. 命令前缀命中 `deck-master `、`python3 `、`/private/`、`/Users/` 时，不能直出。
2. 出现 `--run-dir`、`.json`、绝对路径片段时，默认走改写文案。
3. 改写失败时，退回固定业务提示：
   - `待准备` → `先生成首版页面与预览`
   - `生成中` → `等待生成和预览完成`
   - `待补依据` → `先补齐当前页关键依据`
   - `待审批` → `等待审批结论`

### 6.3 诊断入口边界

- 原始命令只允许出现在底部抽屉的诊断区域
- 诊断区域文案必须明确标识为“供执行器或维护排查使用”
- 默认折叠，不放到首屏

## 7. 结构改造要求

### 7.1 顶部状态带

目标：从“大总览卡片”收成“紧凑状态带”。

必须做到：

- 主标题缩成一行主语
- 阶段、下一步、阻断、Draft Gate、导出状态改成短 token
- 项目切换区收成紧凑控件
- 新建项目、提交审批、确认交付不再占整列大卡片

禁止继续保留：

- 全高项目切换卡
- 大标题 + 长副标题 + 多块等权信息卡的组合
- 暖色大面积填充的操作区

### 7.2 右侧决策流

目标：让右栏一眼看懂“这页是什么、有什么风险、现在能做什么”。

必须做到：

1. 先显示页面定位
2. 再显示来源与依据
3. 紧接风险与缺口
4. 最后显示主动作、次动作、审批记录、备注

禁止继续保留：

- 页面标题重复出现两次
- 备注框排在页面上下文前面
- 多层圆角卡片把决策流切碎

### 7.3 中央主舞台

目标：把预览重新抬回首屏主位。

必须做到：

- 审稿态首屏优先看到预览框
- action bar 压缩
- 低频 badge、统计和说明文案下沉
- 底部抽屉保持可用，但不能挤压当前页主舞台

### 7.4 待准备阶段工作区

目标：用一个主叙事区讲清楚“为什么还没进入页级处理”。

必须做到：

- 一个主卡说明当前卡点
- 一个短清单说明阻断
- 一个短块说明责任对象和预期结果

不继续保留：

- 多块等权暗色卡片
- 把同一层级信息拆成三四个相似模块

## 8. 文档真源调整

本轮覆盖主题以内，文档优先级固定如下：

1. 本文 `review-desk-remediation-spec-v0.3.md`
2. `docs/specs/web-ui/design-system.md`
3. `docs/specs/web-ui/implementation-guidelines.md`
4. `docs/2026-06-21-web-ui-design-spec-v0.2.md` 作为上轮基线

本轮需要同步更新的历史文档：

- `docs/2026-06-21-web-ui-design-spec-v0.2.md`
  - 把前台主语调整到 `审稿桌`
  - 标记 v0.3 对顶部状态带、待准备态安全边界、右栏顺序的覆盖关系

## 9. 实施分段

### A1：可见文案安全边界

目标：

- 前台不再直出 `next_command`
- planned run / setup / no-preview shell 统一走安全文案

涉及：

- `scripts/preview/workspace_api.py`
- `scripts/preview/server.py`
- `scripts/preview/static/app.js`
- 相关测试

### A2：顶部状态带压缩

目标：

- 顶部回到紧凑状态带
- 项目切换和动作区压缩

涉及：

- `scripts/preview/static/index.html`
- `scripts/preview/static/style.css`

### A3：右栏决策流重排

目标：

- 固定四段顺序
- 主动作单点突出
- 备注降级

涉及：

- `scripts/preview/static/index.html`
- `scripts/preview/static/style.css`
- `scripts/preview/static/app.js`

### A4：待准备工作区与预览主位

目标：

- 阶段工作区只有一个主叙事
- 审稿态预览重新成为首屏焦点

涉及：

- `scripts/preview/static/app.js`
- `scripts/preview/static/style.css`

### A5：回归与双线评审

目标：

- 单测补齐
- 截图审计补齐
- 设计线和实现线都过门禁

涉及：

- `tests/test_preview_static_contract.py`
- `tests/test_review_cockpit.py`
- `tests/test_preview_server.py`
- 设计 QA 和并行评审文档

## 10. 验收标准

### 10.1 体验验收

1. `待准备 / 生成中` 首屏不出现原始命令和本机路径。
2. `待审阅` 后中央预览重新成为首屏主视觉。
3. 右栏能按固定顺序完成“看定位 → 看依据 → 看风险 → 做决定”。
4. 顶部状态带能在 5 秒内讲清当前阶段、下一步和阻断。
5. 前台产品主语收口为 `审稿桌`。

### 10.2 安全验收

1. 所有首屏可见区域不出现绝对路径。
2. 所有首屏可见区域不出现原始命令。
3. planned run / setup / no-preview shell 只返回安全文案。

### 10.3 回归验收

1. 现有 Review Cockpit API 契约不回退。
2. `final_readiness`、`customer_visible_safety`、`deck-builder` 相关表达不回退。
3. planned run、needs-review、delivery-preview 三类桌面场景都能过截图审计。

## 11. 测试计划

本轮至少补以下验证：

- `tests/test_preview_static_contract.py`
  - 审稿桌主语存在
  - 顶部状态带使用紧凑结构
  - 右栏固定顺序存在
- `tests/test_review_cockpit.py`
  - 展示字段优先级
  - 待准备态不会把 `next_command` 直接回显到用户文案
- `tests/test_preview_server.py`
  - planned run / no-preview shell 返回安全 payload
  - 不含绝对路径
- 截图审计
  - `needs-review`
  - `run-init-wait-preview`
  - `delivered-review`

## 12. 并行评审门禁

本轮必须同时通过两条线：

1. 设计线：信息架构、视觉层级、交互路径
2. 实现线：契约安全、文案边界、回归风险

任一条线仍是 `blocked`，本轮都不能判定完成。
