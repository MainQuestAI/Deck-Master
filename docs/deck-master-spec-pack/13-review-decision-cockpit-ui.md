# Deck Master Spec Pack

## 18. Spec 13：Review & Decision Cockpit UI

### 18.1 目标

提供本地 Web UI，用于专业方案人员审查页面、来源、证据、质量风险和审批状态。

### 18.2 信息架构

```text
Top Status Bar
  - Run title
  - Current status
  - Quality status
  - Page count
  - Approved / rejected / needs_review count
  - Next step

Left Page Rail
  - Page order
  - Page title
  - Role
  - Review status
  - Source decision
  - Quality badge
  - Filters

Center Preview
  - Page preview
  - Asset missing state
  - Zoom controls
  - Source preview metadata

Right Review Panel
  - Core claim
  - Decision intent
  - Source decision and reason
  - Selected candidate
  - Alternatives
  - Evidence needs and gaps
  - Quality findings
  - Generation task status
  - Review actions

Bottom Status Drawer
  - Events
  - Build Skill tasks
  - Export readiness
  - Repair plan
```

### 18.3 首版功能

必须实现：

- 中文 / 英文语言包。
- 跟随浏览器语言。
- 显式语言切换。
- 用户语言偏好 localStorage。
- 顶部 run 状态条。
- 左侧页面列表和筛选。
- 中央页面预览。
- 右侧页面审查面板。
- 底部状态抽屉。
- Draft Gate 阻断显示。
- Build Skill 状态显示。
- 页面审批、拒绝、备注。
- 替换来源。
- 转生成页。
- 锁定历史页。

### 18.4 用户可见状态

Review status：

- `needs_review`
- `approved`
- `rejected`

Source decision：

- `reuse`
- `adapt`
- `generate`
- `manual_placeholder`

Quality status：

- `not_run`
- `pass`
- `conditional_pass`
- `rework_required`

Build status：

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`

### 18.5 操作规则

- Approve：只有非 P0/P1 阻断页面可直接 approve；否则需要 override。
- Reject：任何页面都可 reject，必须记录 note 或默认 reason。
- Replace source：只能从 alternatives 中选。
- Convert to generate：更新 sourcing decision，并刷新 generation task。
- Lock source：阻止后续自动 sourcing 覆盖该页来源。
- Manual placeholder：只能作为内部任务提醒，不作为最终交付页。

### 18.6 I18n

文件：

```text
scripts/preview/static/i18n/zh-CN.json
scripts/preview/static/i18n/en-US.json
```

所有用户可见字段必须从 i18n 读取。

### 18.7 验收

- 无同屏中英混排。
- 页面级 findings 可见。
- run-level quality status 可见。
- approve/reject 后 manifest 更新。
- event log 记录人工操作。
- 旧 manifest 可迁移或兼容读取。

---
