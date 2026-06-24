# Deck Master Review Desk 并行评审结论

日期：2026-06-23  
状态：passed  
适用范围：Review Desk 修复迭代 v0.3

## 1. 总结

并行评审分两条线：

1. 设计线：passed
2. 实现线：passed

当前结论：v0.3 四个主问题已关闭，可以进入合并前最终回归。

## 2. 设计线结论

设计线直接引用本轮设计 QA：

- [2026-06-23-review-desk-design-qa.md](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/docs/qa/2026-06-23-review-desk-design-qa.md)

评分：

| 维度 | 评分 | 结论 |
|---|---:|---|
| 首屏信息架构 | 8/10 | 顶部已压缩，中央焦点稳定 |
| 当前页主舞台 | 8/10 | 预览重新成为首屏主视觉 |
| 右侧决策流 | 8/10 | 顺序已固定为定位、依据、风险、审批、动作 |
| 阶段工作区 | 8/10 | 已收口到单一主叙事 |
| 产品语言一致性 | 8/10 | 前台主语已收口为 `审稿桌` |

设计线主结论：

- 本轮结构问题已按 v0.3 修复。

## 3. 实现线结论

实现线围绕当前代码和测试做了一轮结构审查，结论为 `passed`。

### [P1] 前台直接消费机器字段，导致命令和路径上屏

位置：

- [scripts/preview/static/app.js](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/scripts/preview/static/app.js)

观察：

- `deriveShellState()` 在 `待准备 / 生成中` 直接使用 `runState.next_command`
- setup 入口和若干补充块也直接回显 `setup.next_command`

状态：closed

结果：

- 已新增展示层字段。
- 前端已补安全清洗函数。
- `next_command` 保留为机器字段和诊断信息。

### [P1] 顶部和右栏的问题已经固化在 DOM 结构里

位置：

- [scripts/preview/static/index.html](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/scripts/preview/static/index.html)
- [scripts/preview/static/style.css](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/scripts/preview/static/style.css)

观察：

- 顶部是多块总览卡 + 全高动作列
- 右栏把动作区放在页面定位前面

状态：closed

结果：

- 顶部状态带已压缩。
- 右栏动作区已移到风险、审批之后。

### [P1] 文档真源分裂，会把实现继续带偏

位置：

- [docs/2026-06-21-web-ui-design-spec-v0.2.md](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/docs/2026-06-21-web-ui-design-spec-v0.2.md)
- [docs/specs/web-ui/design-system.md](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/docs/specs/web-ui/design-system.md)

观察：

- v0.2 仍把前台产品名写成 `方案项目工作台`
- 设计系统已经转到 Review Desk 定位

状态：closed

结果：

- v0.2 设计文档已增加 v0.3 覆盖说明。
- 前台主语已统一为 `审稿桌`。

### [P1] 测试当前挡不住这类回退

位置：

- [tests/test_preview_static_contract.py](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/tests/test_preview_static_contract.py)
- [tests/test_review_cockpit.py](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/tests/test_review_cockpit.py)
- [tests/test_preview_server.py](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/tests/test_preview_server.py)

观察：

- 现有测试覆盖了结构入口和部分状态
- 还没有把“前台不得展示命令和绝对路径”“主语必须收口为审稿桌”“右栏固定顺序”写成硬约束

状态：closed

结果：

- 已补静态契约测试。
- 已补 workspace API 展示字段安全测试。
- 截图审计脚本已对齐新版文案。

## 4. 并行评审后的统一修复顺序

1. 可见文案安全边界已修复。
2. 顶部状态带已压缩。
3. 右栏决策流已重排。
4. 待准备阶段工作区和中央舞台权重已修复。
5. 单测与截图审计已通过。

## 5. 本轮进入实现前的真源文件

1. [review-desk-remediation-spec-v0.3.md](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/docs/specs/web-ui/review-desk-remediation-spec-v0.3.md)
2. [design-system.md](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/docs/specs/web-ui/design-system.md)
3. [implementation-guidelines.md](/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/docs/specs/web-ui/implementation-guidelines.md)

## 6. 结论

这轮结构修复已经完成。最新截图矩阵位于 `/private/tmp/deck-master-review-desk-v03-audit/`，共 8 个场景、24 张桌面截图。
