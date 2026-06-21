# Deck Master Web UI 前端迭代 Spec — Round 1

日期：2026-06-21
状态：实现 Spec v1（待执行）
范围：`scripts/preview/static/` 的 localhost Web UI 本轮重构

## 1. 目标与边界

### 1.1 目标一句话
把当前“信息很多的项目工作台”落地改造成“围绕当前页的严肃审查台”，并应用 `DESIGN.md` 设计系统。

### 1.2 本轮做什么
- 重构 `index.html` DOM 骨架，对齐 `docs/2026-06-21-web-ui-ia-v1.md` §3 的新布局：顶部一条状态带 + 三栏（左窄/中大/右决策台）+ 底部抽屉。
- 落地 `DESIGN.md` 全部 token：字体（Satoshi/Geist/IBM Plex Mono）、色（冷墨底+琥珀铜单点）、去玻璃改发丝实面、间距 4px compact、极克制圆角。
- 动作收敛为“一个主动作 + 若干次动作”，P0/P1 强阻断联动三处。
- run 级信息（就绪度/论点覆盖/活动流）从首屏常驻移入底部抽屉 Tabs。
- 实现中英双语切换，遵守 spec §12（同屏不混排、代码形态保留英文）。
- 补 skeleton loading、强阻断态、完成态三类状态。

### 1.3 本轮不做
- 不改后端 API、不改 run 状态机、不改数据模型。
- 不引入新框架/构建工具（保持原生 HTML/CSS/JS 单页）。
- 不做移动端主路径（仅避免明显破版）。
- 不动 Agent 主会话流程。
- 不做大面积动效。
- 不改 `docs/2026-06-10-web-ui-design-spec.md` 本身（它是产品 spec，本轮只实现其与 IA/DESIGN 一致的部分）。

## 2. 成功标准（可验证）

结构层：
- [ ] 首屏不再出现 run 级三块常驻面板（就绪度/论点覆盖/活动流）。
- [ ] 顶部为一条状态带，阻断标记单独成点，可展开查看 C 层。
- [ ] 右栏动作区只有一个主动作，其余为次动作。
- [ ] P0/P1 风险联动顶部阻断标记、中栏主动作条、右栏风险块三处。
- [ ] 底部抽屉默认收起，失败或阻断时可自动提示展开。

视觉层：
- [ ] 全页无 frosted glass / `.glass-panel` 玻璃效果残留（背景模糊与半透面板全部移除）。
- [ ] `.ambient-light-container` 光球装饰删除。
- [ ] 仅一个强调色 `#E09043`，且只出现在主动作/阻断/当前态。
- [ ] 字体：标题 Satoshi、正文 Geist、数据 IBM Plex Mono；Inter 不再加载。
- [ ] 预览图成为中栏唯一视觉张力点，外围容器收窄。

交互/状态层：
- [ ] skeleton loading 替代“载入中”文字等待（至少页面列表、预览、决策三处）。
- [ ] P0/P1 直接控制主动作条状态与说明文案。
- [ ] 某页通过后给出明确“下一页建议”，而非仅更新状态。

双语层：
- [ ] 中英两套语言包完整覆盖用户可见文案。
- [ ] 同一屏不出现中英文混排。
- [ ] 切换语言后，状态枚举/页码/run id/source id 保持英文。

回归层（spec §17 不回退）：
- [ ] 用户 5 秒内能判断 run 是否可继续。
- [ ] 用户 30 秒内能找到所有阻断页。
- [ ] 首次打开 run 直接进入第一页；重新打开恢复上次查看页。
- [ ] 页面列表默认按 Deck 页码顺序排序。
- [ ] 审批状态只使用 `needs_review / approved / rejected`。
- [ ] 页面操作不绕过 Draft Gate 阻断。

## 3. 前置依据

- 问题诊断：`docs/2026-06-21-web-ui-redesign-audit.md`
- 信息架构与落地映射：`docs/2026-06-21-web-ui-ia-v1.md`（§4 节点处置表、§7 旧→新容器映射）
- 设计系统：`DESIGN.md`
- 产品 spec：`docs/2026-06-10-web-ui-design-spec.md`
- 预览参考：`/tmp/deck-master-design-preview.html`（字体+色板+审查台 mockup，含中英切换）
- 当前实现：`scripts/preview/static/{index.html(259),style.css(937),app.js(1153)}`

## 4. 实现总览

按依赖顺序分 7 批，每批可独立在浏览器验证，建议逐批 commit。

| 批次 | 主题 | 主改文件 | 依赖 |
|---|---|---|---|
| B1 | 设计 token 与字体落地 | style.css + index.html `<head>` | 无 |
| B2 | 骨架重构：状态带 / 三栏权重 / 底部抽屉 | index.html + app.js `els` | B1 |
| B3 | 右栏决策台 + 主动作条 | index.html + app.js render* | B2 |
| B4 | 底部抽屉 Tabs + run 级信息迁移 | index.html + app.js | B2 |
| B5 | 双语 i18n | 新增 lang 包 + app.js + index.html | B2 |
| B6 | 状态覆盖：skeleton / 强阻断 / 完成态 | style.css + app.js | B3 |
| B7 | 视觉张力收尾 + 去玻璃清残 | style.css | B1–B6 |

---

## 批次 B1：设计 token 与字体落地

**目标**：建立 CSS 变量层，引入三套字体，移除 Inter 与玻璃语言基础。

**改动**：
- `index.html` `<head>`：
  - 加 Google Fonts `<link>`：Geist（300/400/500/600/700）、IBM Plex Mono（400/500/600）。
  - 加 Fontshare `<link>`：Satoshi（400/500/700/900）。
  - 移除现有 Inter 引用（若存在）。
- `style.css` `:root`：落地 `DESIGN.md` Color 全部 token（ink-base/surface-1/2/3/hairline/hairline-soft/text-*/accent/accent-soft/accent-line/success/warning/danger/info/p0–p3）。
- `style.css` `[data-theme="light"]`：落地浅色 token（见预览页）。
- `style.css` 字体变量：`--font-display: Satoshi`、`--font-body: Geist`、`--font-mono: IBM Plex Mono`。

**验证点**：
- 打开页面，DevTools Computed 能看到全部 token 变量。
- 标题渲染为 Satoshi，正文 Geist，mono 处为 IBM Plex Mono（Network 面板确认三套字体已加载、Inter 不再请求）。
- 此批不要求视觉完整，只要求 token 与字体就位。

---

## 批次 B2：骨架重构

**目标**：DOM 从“顶部四卡 + 三栏 + 底部三块常驻”改为“顶部状态带 + 三栏 + 底部抽屉”。对齐 IA v1 §3 与 §7。

**改动 `index.html`**：
- `header.workspace-header` → 拆为 `.status-bar`（一条带）+ 可展开 `.status-drawer`。
  - 删除 `.header-grid` 四张同权 `.header-card`。
  - 保留的信息：Workspace、Run 标题+id、阶段、下一步、阻断标记、Draft Gate、导出、语言。
  - 状态计数（原 `.metrics-card`）移到左栏 `#queue-summary` 上方。
- `.workspace-grid` 三栏权重重排：左栏收窄、中栏放大、右栏改决策台。
- `.center-column .workspace-bottom-grid` → 删除常驻，新建 `.bottom-drawer`（默认收起，含 Tabs 容器）。
- 中栏预览顶加 `.action-bar`（主动作条）容器。
- 删除 `.ambient-light-container`。

**改动 `app.js`**：
- `els` 对象同步重映射：移除已删节点（`metricPages` 等四卡相关项按新结构收敛），新增 `.status-bar`、`.status-drawer`、`.bottom-drawer`、`.action-bar` 对应引用。
- 所有 `render*` 函数中引用被删节点的，改为写入新节点或留空待 B3/B4 填充。
- `updateLocation` / 状态读取逻辑不动。

**验证点**：
- 页面骨架为一条状态带 + 三栏 + 收起的底部抽屉，无四卡、无底部三块常驻、无光球。
- 所有原有数据仍能渲染到新节点（哪怕位置变了），不出现 undefined / 空白关键信息。
- 控制台无 `Cannot read property of null`（`els` 映射完整）。

---

## 批次 B3：右栏决策台 + 主动作条

**目标**：右栏重排为“职责→来源·证据→风险→审批(主动作)→次动作→备注”；中栏预览顶加主动作条，动作收敛。

**改动 `index.html` + `app.js`**：
- 右栏 `.decision-rail` 内 `.decision-block` 重排顺序：页面职责 → 来源·证据（合并 `#page-source-content` + `#page-evidence-content`）→ 风险 → 审批 → 次动作 → 备注。
- 主动作条 `.action-bar`：承载当前页建议动作。P0/P1 时主动作反映阻断后果（如“先补证据”而非“批准”）。
- 动作收敛（对准现有按钮 id）：
  - 主动作：`#approve-page` / `#request-evidence` / `#reject-page`（按当前页状态切换为唯一主动作）。
  - 次动作区：`替换来源 / 转生成页 / 锁定历史页`（视觉权重低于主动作）。
  - `#submit-run-approval`、`#mark-delivered`：降为次入口，仅 export_ready 阶段升为顶部唯一高权重按钮。
- `#critical-alerts` 提权到中栏预览顶，且联动顶部阻断标记与右栏风险块。

**验证点**：
- 右栏只有一个主动作按钮高亮（琥珀铜），其余次动作为 ghost + hairline。
- 切换不同状态的页面时，主动作条文案与可用性随状态变化。
- P0/P1 页面：主动作条直接显示阻断说明，顶部阻断标记点亮，右栏风险块可见。

---

## 批次 B4：底部抽屉 Tabs + run 级信息迁移

**目标**：就绪度/论点覆盖/活动流 + 事件日志/Build Skill/Artifact/Export 全部收进底部抽屉。

**改动 `index.html` + `app.js`**：
- `.bottom-drawer` Tabs：就绪度 · 论点覆盖 · 事件日志 · Build Skill · Artifact · Export queue。
- 迁移：
  - `#run-readiness` / `#readiness-pill` → 抽屉“就绪度”Tab。
  - `#claim-coverage` / `#claim-summary-chip` → 抽屉“论点覆盖”Tab。
  - `#activity-list` / `#activity-count` → 抽屉“事件日志”Tab。
  - Build Skill 步骤 / Artifact handback / Export queue → 对应 Tab（若现状已有结构则迁移，无则留空态占位）。
- 抽屉默认收起；失败或阻断时自动提示展开（badge 提示）。
- 抽屉展开时不遮挡右栏决策台（推高度或 overlay 视实现，优先推高度避免遮挡）。

**验证点**：
- 首屏无 run 级三块常驻。
- 点 Tab 能切到对应 run 级信息，数据不丢失。
- 阻断时抽屉有提示标记。

---

## 批次 B5：双语 i18n

**目标**：中英两套完整语言包，切换实时，同屏不混排。

**改动**：
- 新增 `scripts/preview/static/lang/{zh,en}.js`（或在 app.js 内置 `I18N` 对象，二选一，优先独立文件便于维护）。
- `index.html`：所有用户可见文案节点加 `data-i18n="key"`（纯文本）或 `data-i18n-html="key"`（含标记）。代码形态内容（页码、状态枚举、run id、source id、hex、文件名）不加 key，保持英文。
- `app.js`：render 函数渲染文案时走 `t(key)` 而非硬编码；切换语言时遍历 `[data-i18n]` 重渲。
- 语言 toggle：顶部状态带 + 抽屉外各一个入口；显式切换写入本地偏好，优先级高于浏览器语言（spec §12）。

**语言包必须覆盖**（spec §12）：按钮、标题、导航、空状态、错误提示、操作说明、审批文案、质量风险说明。

**验证点**：
- 切换中英，整页文案切换，无残留。
- 状态枚举（review/approved/rejected）、页码、run id、source id 切换后仍为英文。
- 刷新后保留上次语言偏好。

---

## 批次 B6：状态覆盖

**目标**：补 skeleton / 强阻断 / 完成态，替代文字等待与单纯状态更新。

**改动 `style.css` + `app.js`**：
- skeleton loading：页面列表、预览、决策三处加骨架屏样式（surface-2 块 + 微弱呼吸动效，符合 minimal-functional motion）。
- 强阻断态：P0/P1 时，主动作条状态与说明由风险驱动（B3 已搭结构，本批补样式与文案规则）。
- 完成态：某页 approved 后，主动作条/预览底给出“下一页建议”（指向下一个 needs_review 或阻断页）。

**验证点**：
- 慢网络或刷新瞬间，三处出现骨架而非空白或“载入中”文字。
- P0 页面：主动作条禁用批准或改为“先补证据”，说明可见。
- 批准一页后：出现明确的下一页建议。

---

## 批次 B7：视觉张力收尾 + 去玻璃清残

**目标**：清掉所有玻璃残留，强化预览视觉张力，拉开标题层级。

**改动 `style.css`**：
- 全局搜索 `.glass-panel` / `backdrop-filter` / `rgba(...)` 半透面板：全部改为 surface 实面 + hairline 边框。
- `.preview-stage` 外围容器收窄，让预览图成为中栏唯一张力点。
- 标题层级拉开：display 用 Satoshi 900 + 负字距；中级标题（section head / decision label）加强统领感。
- 圆角统一到 DESIGN.md 极克制标准（sm 2px / md 4px），清掉 bubble 圆角。
- 检查无残留橙色滥用（accent 只在主动作/阻断/当前态）。

**验证点**：
- DevTools 搜 `backdrop-filter` 结果为空。
- 预览图视觉主导，外围无多余大容器。
- 标题层级清晰，中级标题有统领感。

---

## 5. 双语实现约束（贯穿 B5，影响各批）

- 任何 B1–B4 新增的用户可见文案，都要预留 i18n key，不要硬编码中英文。
- 代码形态保留英文：文件名、状态枚举、命令、artifact id、run id、source id。
- 同屏不混排：切换是整页切换，不是逐句切换。

## 6. 状态覆盖矩阵（spec §15 不回退）

本轮需保证以下状态在新结构下仍成立：

| 功能 | 加载中 | 空状态 | 错误 | 成功 | 部分完成 |
|---|---|---|---|---|---|
| 页面列表 | skeleton | 提示无 manifest | 显示错误 | 显示页面 | 标记缺图/阻断/待生成 |
| 页面预览 | skeleton | 提示选择页面 | 显示缺资产+恢复建议 | 显示预览 | 占位图+生成状态 |
| 审批 | 保存中 | 待审查 | 保存失败可重试 | 保存成功 | 页面已审 run 未完成 |
| Draft Gate | 检查中 | 未运行 | 失败原因 | 通过 | 条件通过+修复建议 |

## 7. 验收清单（交付前自检）

- [ ] §2 全部成功标准勾选通过。
- [ ] 无 `console.log` / `debugger` / `TODO` / `FIXME` 残留。
- [ ] 无无关改动混入（只动 `scripts/preview/static/` 与新增 lang 文件）。
- [ ] 字体仅加载 Satoshi / Geist / IBM Plex Mono。
- [ ] 强调色仅 `#E09043`，仅用于主动作/阻断/当前态。
- [ ] 无 `backdrop-filter` / `.glass-panel` / `.ambient-light-container` 残留。
- [ ] 中英语言包完整，同屏不混排。
- [ ] 现有验收标准不回退（§2 回归层）。
- [ ] 本地 `python3 -m unittest discover -s tests` 通过（若涉及后端契约未改，应全绿）。
- [ ] `http://127.0.0.1:5050` 本地起服，浏览器走一遍 golden path + 边缘态。

## 8. 风险与回退

- **风险1**：app.js `els` 映射与 DOM 不同步 → null 引用。缓解：B2 先确保映射完整再删旧节点；每批浏览器控制台零错误才算过。
- **风险2**：去玻璃后部分用户觉得“不够现代”。这是 DESIGN.md 已记录的 RISK 代价，符合记忆点，不回退。
- **风险3**：双语包遗漏导致混排。缓解：B5 用 `data-i18n` 全量标记 + 切换后 grep 残留中文。
- **回退**：每批独立 commit，必要时可 `git revert` 单批而不影响其他。

## 9. 交付物

- 改造后的 `scripts/preview/static/{index.html,style.css,app.js}`。
- 新增 `scripts/preview/static/lang/{zh,en}.js`（若选独立文件方案）。
- 本 Spec 标记完成。
- 截图级 `design-review` 报告（实现后另起）。

---

## 10. Design Review 修订（2026-06-21）

本节为 `/plan-design-review` 7-pass 审查后补入的设计决策。原批次 B1–B7 不变，以下内容作为各批次的细化约束，实现时一并遵守。

### 10.1 Pass 1 补充：首屏 3 件事（constraint worship）

首屏 5 秒内用户必须看懂且仅看懂三件事，其余降权：
1. 当前在哪一页（页码 + 页面标题，中栏视觉中心）。
2. 这页能不能过（主动作条 + 风险块，右栏）。
3. 整 run 还差什么（顶部状态带阻断标记 + 下一步）。

任何新增首屏元素若不直接服务这三件事，降权到抽屉或移除。

### 10.2 Pass 2 补充：完整交互状态表 + 空态风格

**空态风格（已拍板）**：冷峻文案 + 明确主动作。文案简短不煽情（如“暂无待审查页”），但每个空态/错态必须带一个主动作入口（如“回到首页”“创建 run”“重试”“查看恢复建议”）。满足 audit 原则1“空态是功能”，不破坏严肃工具感。

| 功能 | LOADING | EMPTY | ERROR | SUCCESS | PARTIAL |
|---|---|---|---|---|---|
| Workspace | skeleton | “未选择 workspace” + [选择/创建] | 显示路径+修复建议 + [重试] | 显示名称 | 标记缺失配置 |
| Run 列表 | skeleton | “还没有 run” + [从 Agent 创建] | “runs 读取失败” + [重试] | 显示最近 run | 标记 pending run |
| 页面列表 | skeleton（3 行占位） | “还没有 preview manifest” + [在 Agent 生成] | 显示 manifest 错误 + [重试] | 显示页面 | 标记缺图/阻断/待生成 |
| 页面预览 | skeleton（预览框占位） | “选择一页开始审查” + [跳第一页] | 显示缺资产路径 + [查看恢复建议] | 显示预览 | 占位图 + 生成状态 |
| 审批 | 保存中（按钮禁用+skeleton） | 待审查 | “保存失败” + [重试] | “已保存” + [下一页] | 页面已审 run 未完成 |
| Draft Gate | 检查中 | 未运行 | 显示失败原因 + [查看修复] | 通过 | 条件通过 + 修复建议 |
| Build Skill | 运行中步骤 | 未开始 | 失败步骤+日志摘要 + [查看日志] | 产物路径 | 部分页面完成 |
| 导出 | 生成中 | “无已批准页” + [回审查] | 导出失败 + [重试] | approved_queue | 部分可导出 |

### 10.3 Pass 3 补充：审查台 emotional arc storyboard

| 步骤 | 用户做什么 | 用户应感受 | plan 如何支撑 |
|---|---|---|---|
| 1 打开 run | 进入首屏 | “立刻知道看哪页” | 首屏 3 件事 + 中栏预览中心 |
| 2 扫描页面 | 找阻断页 | “30 秒内找到所有阻断” | 左栏阻断标记 + 顶部阻断计数 |
| 3 审单页 | 判断能不能过 | “信息够我决策” | 右栏职责→来源·证据→风险→主动作 |
| 4 遇阻断 | 处理阻断 | “知道先做什么” | 主动作条状态驱动 + 强阻断说明 |
| 5 批准 | 完成一页 | “知道下一页” | 完成态下一页建议 |
| 6 推进 run | 看整体进度 | “知道还差什么” | 顶部状态带 + 抽屉就绪度 |

时间维度：5 秒 visceral（冷峻仪器感）/ 5 分钟 behavioral（高效审查无摩擦）/ 长期 reflective（可信、不花哨、每次都好用）。

### 10.4 Pass 4 补充：anti-slop 验收点

分类：APP UI（workspace 驱动、数据密集、任务聚焦），适用 App UI Rules + Universal Rules。

实现后逐项验证（任一命中即不通过）：
- [ ] 无 3 列 feature grid + 圆圈图标模板。
- [ ] 无紫/靛蓝渐变背景。
- [ ] 无装饰光球 / floating blobs / wavy dividers（`.ambient-light-container` 已删）。
- [ ] 无 emoji 作设计元素。
- [ ] 无卡片彩色左边框装饰（`border-left: 3px solid accent` 仅当前态可用，不作装饰）。
- [ ] 无 system-ui / -apple-system 作主字体（已用 Satoshi/Geist/IBM Plex Mono）。
- [ ] 无统一 bubble 圆角（圆角 sm 2px / md 4px，仅 pill 用 9999px）。
- [ ] 卡片仅在“卡片即交互”时使用（左栏页卡、抽屉项算交互卡，可保留；纯装饰卡禁用）。
- [ ] section heading 说明区域是什么或能做什么（如“当前页”“页面职责”），非 mood 文案。
- [ ] body 文本 ≥ 16px 且对比度 ≥ 4.5:1。

### 10.5 Pass 5 补充：标题 scale → 元素映射 + i18n key 规则

**Scale → 元素映射**（DESIGN.md scale 落到具体元素）：

| 级别 | px | 用途 |
|---|---|---|
| 72 / clamp | hero 标题 | 预览页内 frame 大标题、全屏查看标题 |
| 56 | display | preview 页 hero（不用于 app 内） |
| 40 | h1 | 模态标题 |
| 28 | h2 | block 标题（字体系统/色彩系统等） |
| 22 | h3 sub | 预览 frame 副标题 |
| 18 | 中栏页面标题 | mock-actionbar `.ptitle` |
| 16 | body | 正文、右栏 dval |
| 14 | UI | 按钮、表单 |
| 13 | 左栏页卡标题 | page-item `.pt` |
| 12 | mono 标签 | dlabel / eyebrow |
| 11 | mono 微 | 状态带、pmeta |
| 10 | mono 极微 | filter chip、ftop |

**i18n key 命名规则**：
- 命名空间用点分：`{区域}.{元素}.{状态}`，如 `statusbar.next_step`、`rightrail.page_role.label`、`empty.page_list`、`btn.approve`。
- 区域前缀：`statusbar` / `leftrail` / `center` / `rightrail` / `drawer` / `modal` / `empty` / `error` / `btn` / `pill` / `common`。
- 纯文本用 `data-i18n`，含 HTML 标记用 `data-i18n-html`。
- 代码形态内容（页码、状态枚举 review/approved/rejected、run id、source id、hex、文件名、命令）不加 key。
- 缺 key 回退：`t(key)` 找不到时回退到 key 本身并 `console.warn`（开发期可见，生产不崩）。中英两包 key 集合必须一致，构建期可加一致性校验脚本。

### 10.6 Pass 6 补充：响应式断点 + a11y 规范

**响应式断点（已拍板：三档 1280/1024）**：

| 视口 | 左栏 | 中栏 | 右栏 | 底部抽屉 |
|---|---|---|---|---|
| ≥1280px | 全显（找页+筛选+状态计数） | 预览+主动作条 | 决策台全显 | 收起 |
| 1024–1279px | 折叠为图标条（仅页码+风险点），点击展开覆盖层 | 预览+主动作条（不变） | 决策台保留 | 收起 |
| <1024px | 抽屉化（从左滑入） | 预览+主动作条 | 改下堆（在预览下方） | 收起 |

13–16 寸笔记本为主路径；<1024 仅避免破版，不承诺审查体验。

**a11y 规范**：
- 键盘导航：Tab 顺序 = 顶部状态带 → 左栏页列表 → 中栏主动作条 → 右栏决策台 → 底部抽屉。页列表支持 ↑/↓ 切页、Enter 选中。
- focus ring：所有可交互元素 focus 时显示 `2px solid var(--accent)` 外环 + `2px offset`，不依赖 hover。
- ARIA landmarks：`<header role="banner">`、`<main>`、左栏 `<nav aria-label="页面列表">`、右栏 `<aside aria-label="当前页审查">`、抽屉 `role="tabpanel"`。
- 对比度：body ≥ 4.5:1，大字 ≥ 3:1。`#E09043` on `#0B0E12` 验证通过（对比约 5.9:1）；`text-muted #8A93A0` on ink-base 验证（约 5.3:1）；`text-faint #5A626C` 仅用于非文本装饰或 ≥3:1 大字，不用于 body。
- 触达目标：所有可点击元素 ≥ 44×44px。
- 状态变化：P0/P1 风险出现时用 `aria-live="polite"` 朗读，不抢焦点。
- 颜色不作为唯一信息：风险级别除颜色外有文字标签（P0/P1/P2/P3）。

### 10.7 Pass 7 补充：未决决策落地

**主动作条状态机（已拍板：状态驱动）**：

| 页面状态 | 风险 | 主动作 | 主动作可用性 | 说明 |
|---|---|---|---|---|
| needs_review | 无 | 批准页面 | 启用 | 次动作：驳回/请求补证据 |
| needs_review | P1 | 批准页面 | 启用但需确认 | 主动作条提示“P1 待处理” |
| needs_review | P0 | 先处理阻断 | 禁用批准 | 主动作条提示阻断+引导补证据；次动作：请求补证据升为候选主动作 |
| 证据不足 | — | 请求补证据 | 启用 | 作为候选主动作出现 |
| approved | — | 下一页 | 启用 | 点击跳下一个 needs_review/阻断页 |
| rejected | — | 重新审查 | 启用 | — |

`升级审批` 仅在 approved 后出现为次动作。`确认交付` 仅在 export_ready 阶段升为顶部唯一高权重按钮。

**底部抽屉展开方式（已拍板：推高度不覆盖）**：
- 抽屉展开时推高页面底部，不覆盖右栏决策台与中栏预览。
- 展开高度默认 280px，可拖拽调整（最小 160 / 最大视口 50%）。
- Tab 切换无动效跳变，仅内容替换（minimal-functional motion）。
- 阻断/失败时抽屉标签出现 badge 提示，但不自动展开（避免抢焦点）；badge 可点击展开。

**完成态“下一页建议”逻辑**：
- 优先级：阻断页（P0 > P1）> needs_review 页 > 无。
- 全部 approved 时：主动作条显示“run 审查完成，可进入交付”，引导 export_ready。
- 无可推荐时：主动作条显示“已是最后一页”。

**loading skeleton 规范**：
- 结构：surface-2 块 + 1px hairline 边框，模拟目标内容的形状（页卡用扁横条、预览用 16:10 框、决策用 3–4 行短条）。
- 动效：微弱呼吸（opacity 0.6↔1.0，1.2s ease-in-out 循环），符合 minimal-functional。
- 颜色：surface-2 底 + surface-3 高光条，不引入新色。
- 时长：>300ms 才显示 skeleton（避免闪烁）；<300ms 直接渲染内容。

### 10.8 NOT in scope（本轮明确不做）

- 移动端主路径审查体验（<1024 仅避免破版）。
- 完整 Web 工作台 / 长期知识管理 / 实时飞书拉取 / 多 Build Skill 并行调度界面。
- 高保真品牌视觉稿。
- 后端 API / run 状态机 / 数据模型改动。
- 新框架 / 构建工具引入。

### 10.9 What already exists（复用）

- `app.js` `els` 映射 + `render*`/`format*` 函数族（架构不重写）。
- 审批状态枚举 `needs_review/approved/rejected`（spec §17）。
- Draft Gate / Build Skill / Export 状态语义。
- 视觉参考 `/tmp/deck-master-design-preview.html`（mockup 替代）。
- `DESIGN.md` 设计系统、`docs/2026-06-21-web-ui-ia-v1.md` 落地映射。

---

## 11. Eng Review 修订（2026-06-21）

本节为 `/plan-eng-review` 4-section 审查后补入的工程决策。原批次 B1–B7 不变，以下作为工程约束与新增批次，实现时一并遵守。

### 11.1 工程风险与评分

| Section | 评分 | 关键 finding |
|---|---|---|
| Architecture | 7/10 | A1 els 重映射 null 引用；A2 i18n 动态内容不更新；A3 CSS 硬编码并存 |
| Code Quality | 7/10 | C1 零前端测试无兜底；C2 状态恢复路径无保护 |
| Tests | 2/10 | 前端零测试，REGRESSION RULE 触发 |
| Performance | 8/10 | P1 i18n 切换全页重渲闪烁（中置信） |

### 11.2 已拍板工程决策（4 项）

1. **B2.5 验证闸**（A1）：B2 骨架重构后、进 B3 前，必须过闸：浏览器控制台零错误 + 所有 `render*` 函数无 null 引用 + `els` 映射 60+ 节点全部命中现存 DOM。闸不通过不进 B3。这是系统性崩溃的最高防线。
2. **i18n 双轨**（A2）：静态节点用 `data-i18n`/`data-i18n-html`；`render*` 函数内动态生成的文案全部走 `t(key)` 调用而非硬编码。语言切换时：遍历 `[data-i18n]` 重渲 + 触发一次全量 `renderAll()` 让动态内容刷新。spec §10.5 key 规则不变，补此双轨机制说明。
3. **Playwright 关键流测试**（C1）：引入 Playwright（全局 CLAUDE.md 已定为默认 Web 自动化能力）覆盖关键流：开页→选页→审批→状态恢复→语言切换→阻断联动。作为新增批次 B8。
4. **跳过 outside voice**：已有 design review + eng review 双视角，直接出报告。

### 11.3 明显修复（直接补入）

- **A3 CSS 硬编码替换**：B1 落地 token 时，style.css 937 行中现有硬编码颜色/玻璃值必须全量替换为 token 变量，不留新旧两套并存。B1 验证点加：DevTools 搜 `#` 硬编码色与 `backdrop-filter` 结果为空（除 token 定义本身）。
- **C2 状态恢复保护**：B2 改骨架不得破坏 `updateLocation`/“重新打开恢复上次页”（spec §17）。B8 测试覆盖此路径作为回归断言。
- **P1 i18n debounce**：语言切换触发全量重渲，用 `requestAnimationFrame` 合并，避免连续切换闪烁。切换瞬态可加极短 opacity 过渡（符合 minimal-functional motion）。

### 11.4 新增批次 B8：Playwright 关键流测试

**目标**：为零测试前端补回归兜底，覆盖重构高风险路径。

**测试范围**（关键流，非全覆盖）：
- 开页首屏：首次打开进入第一页（spec §17）。
- 选页与筛选：左栏点页切换、阻断筛选。
- 审批闭环：批准→状态变 approved→主动作条变“下一页”。
- 状态恢复：刷新后恢复上次查看页。
- 语言切换：中英切换后动态内容（render* 生成）同步更新，无混排。
- 阻断联动：P0 页面主动作禁用、顶部阻断标记点亮、右栏风险块可见，三处一致。

**改动**：
- 新增 `scripts/preview/static/tests/`（或 repo 既有 tests 目录下加 `test_webui_*.py` 若用 subprocess 起 preview server；优先 Playwright JS spec）。
- 配置：`playwright.config` 指向 `http://127.0.0.1:5050`。
- 纳入 B2.5 闸：B2.5 验证闸可调用其中“开页+无 null 引用”断言。

**验证点**：
- `npx playwright test` 全绿。
- B2.5 闸引用其断言。

### 11.5 Failure modes（每个新 codepath 一个）

| Codepath | 失败场景 | 测试覆盖 | 错误处理 | 用户可见 |
|---|---|---|---|---|
| els 重映射 | 节点删除后 querySelector 返回 null | B8 + B2.5 闸 | render 函数 null 检查兜底空态 | 控制台报错 + 空块 |
| i18n 切换 | key 缺失 | B8 语言切换断言 | t(key) 回退 key 本身 + console.warn | 文案显示 key（不崩） |
| 状态恢复 | localStorage / URL 状态被改骨架破坏 | B8 状态恢复断言 | 回退第一页 | 落第一页（不白屏） |
| 阻断联动 | P0 页主动作未禁用 | B8 阻断断言 | 主动作 disabled 属性 | 批准按钮灰显+说明 |

无“无测试+无错误处理+静默失败”的 critical gap。

### 11.6 Worktree 并行化策略

批次依赖链：B1 → B2 → B2.5 闸 → {B3, B4} → B5 → B6 → B7 → B8。

- **Lane A（主重构）**：B1→B2→B2.5→B3→B4→B5→B6→B7，全部触 `scripts/preview/static/`，**强串行，无并行机会**（共享 app.js/index.html/style.css）。
- **Lane B（测试）**：B8 可在 B2.5 闸确立后与 B3–B7 部分并行（测试代码独立目录），但断言依赖主重构产物，建议 B7 后跑全量。

**结论**：Sequential implementation，主路径无并行化机会。B8 测试可后期并行编写但运行需主路径就绪。

---

## 12. 实现进度 Handoff（2026-06-21）

本节记录实现执行状态，供下一位 agent 接手。详细执行路径见 `/Users/dingcheng/.claude/plans/spec-encapsulated-metcalfe.md`（含 Explore 发现的 6 处 spec 修正）。

### 12.1 已完成（commit 7f25acb）

| 批次 | 状态 | 验证 |
|---|---|---|
| B1 设计 token 与字体 | ✅ done | DevTools token 生效、三字体加载零 Inter |
| B2 骨架重构 | ✅ done | status-bar + queue-metrics + action-bar + bottom-drawer 6 tabs |
| B2.5 验证闸 | ✅ passed | node --check、72 els id 全命中、console 零错误、renderAll 5 projects 渲染 |
| B3 右栏决策台 + 主动作条 | ✅ done | renderActionBar 状态机 + renderBlockFlag + findNextReviewOrBlockedPage，批准→已批准→下一页流程过 |

文档基线另在 commit 5f59936（audit + IA v1 + DESIGN.md + 本 spec + AGENTS.md）。

### 12.2 剩余批次（B4-B8，按依赖顺序）

| 批次 | 状态 | 要点 |
|---|---|---|
| **B4** 底部抽屉 tab 切换接线 | ⏳ 待做 | B2 已建 6-tab 结构（`#bottom-drawer` collapsed + tablist + `.bottom-drawer-panel`）。B4 接：tab 切换（仅一 panel 可见）、展开/收起 toggle、阻断 badge（复用 renderBlockFlag 信号，**不自动展开**只 badge）。spec §4 B4 + §10.7。 |
| **B5** 双语 i18n | ⏳ 待做（最大工作量） | 从零建双轨：`lang/zh.js`+`en.js` + `t(key)`（缺 key 回退+warn）。静态节点 data-i18n，render* 动态文案走 t(key)，切换触发全量 renderAll。~80 字符串 + 6 个 format* 函数。一次性 pass 不与 B3/B4 交错。**stage label 保持 API 中文不经 t()**（eng review 风险#3）。spec §10.5 key 规则 + §11.2。 |
| **B6** 状态覆盖 | ⏳ 待做 | skeleton（页面列表/预览/决策，>300ms 才显示）、强阻断态（P0/P1 驱动主动作条）、完成态下一页建议（B3 已搭 findNextReviewOrBlockedPage，B6 补 skeleton 样式 + 文案规则）。依赖 B5 稳定。spec §10.7。 |
| **B7a** CSS 玻璃清残 + token 全量替换 | ⏳ 待做 | style.css 46 个 rgba + 16 hex 全替换为 token var()；删 .glass-panel backdrop-filter 改实面+hairline；删 .ambient-light-container 样式（index.html 已删 div，CSS 残留 lines 75-104）。spec §11.3 A3。 |
| **B7b** 标题层级 scale→元素 | ⏳ 待做 | 应用 §10.5 scale→元素映射。注意 .pt 13px/.dlabel 12px 不回归可读性（label 豁免 body 16px）。 |
| **B8** Playwright 关键流测试 | ⏳ 待做 | 从零建 Node 项目（package.json + playwright + config，放 `scripts/preview/static/tests/e2e/`，与 Python tests/ 隔离）。webServer 自动起 `python scripts/preview/server.py`。6 关键流：开页/选页/审批闭环/状态恢复(URL param)/语言切换/阻断联动三处。format* 6 纯函数 bonus Node assert 单测。spec §11.4。 |

### 12.3 交接关键提醒（下位 agent 必读）

1. **dev server 用 5052，不是 5050**。5050 是 launchd 部署副本（`~/.deck-master/current`，服务旧 index.html）。起 dev server：`python3 scripts/preview/server.py --host 127.0.0.1 --port 5052 --runs-dir ~/.deck-master/runs --library-mode fixture`。验证 URL：`http://127.0.0.1:5052/?run=yunnan-baiyao-ai-foundation-deck-v1`。
2. **阶段限制是既有逻辑，非 bug**：当前 run 阶段"生成中"触发 `isStageWorkspace()`，renderActionStates（~line 1025）把 canReviewPage 设 false（"生成中"不在可审阶段数组 `["待审阅","待补依据","待审批","可交付","已交付"]`）。前端审批按钮禁用但 API 接受。B3 的 action-bar 主操作复用此限制（禁用 + 提示）。要从前端点测审批，需切换到"待审阅"等阶段的 run，或直接 API 测。
3. **三风险守卫**（eng review §11.2）：① els 重映射 → B2.5 闸 + null 守卫（已加全 render*）。② `[data-approval-action]` 重绑（renderPageDecisionRail 779-791 作用域 #approval-content）→ B3 未动这些按钮位置，仍工作；B4/B5 若动需复查。③ stage label 保持中文不经 t()（B5 必守）。
4. **6 处 spec 修正**已在 plan 文件记录（`~/.claude/plans/spec-encapsulated-metcalfe.md`），实现时以 plan 为准：状态恢复=URL param 非 localStorage；Inter 仅 CSS 引用；B8 从零建 Node；Build Skill/Export 是新建非迁移；#critical-alerts 已在中栏不提权；B7 拆 B7a/B7b。
5. **浏览器验证**：用 chrome-devtools MCP，导航超时 10s 是 load 事件慢（预览图加载）非 bug，用 evaluate_script 检查运行时 state 更可靠（snapshot 抓 busy 中间态会误判）。
6. **截图路径**：chrome-devtools 截图限 workspace root（repo 内），存 `docs/qa/<批次>/`。`$CLAUDE_JOB_DIR` 变量在截图 filePath 不展开，别用。

### 12.4 验收闸（全部完成后）

- §2 成功标准全勾 + §7 验收清单 + spec §17 回归层不回退。
- `npx playwright test` 全绿（B8）。
- `python3 -m unittest discover -s tests` 保持绿（后端契约未改）。
- `/design-review` 截图级视觉 QA。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAN | Arch 7/10, CQ 7/10, Tests 2/10→covered via B8, Perf 8/10; 4 decisions, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAN | score: 7/10 → 9/10, 9 decisions, 4 user-confirmed |

- **VERDICT:** Design + Eng CLEARED — plan ready to implement. Eng Review added B2.5 verification gate (els remap), i18n dual-track, B8 Playwright critical-flow tests. Run `/design-review` after implementation for live visual QA. Ship gate satisfied.

NO UNRESOLVED DECISIONS
