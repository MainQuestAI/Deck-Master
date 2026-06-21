# Design System — Deck Master Review Desk

> 设计系统源真相。所有视觉与 UI 决策以本文件为准。任何字体、颜色、间距、审美方向的偏离都需老板明确批准。
> 生成依据：`docs/2026-06-21-web-ui-redesign-audit.md` + `docs/2026-06-21-web-ui-ia-v1.md` + `/design-consultation`。
> 日期：2026-06-21 · v1

## Product Context

- **What this is:** Deck Master 的 localhost Web UI——Agent 唤起式 run 审查面板，围绕一次 Deck run 做页面预览、来源审查、质量风险判断、页面级操作、审批与导出前确认。
- **Who it's for:** 售前解决方案架构师、专业顾问、高质量 Solution Deck 创作者。第一场景是会后客户 deck 草案审查。
- **Space/industry:** 售前 / 解决方案交付工具，无公开市场直接视觉对标。
- **Project type:** 桌面 Web app（审查台），13–16 寸笔记本。首版不承诺移动端。

## Aesthetic Direction

- **Direction:** Industrial / Utilitarian × Brutally Minimal。仪器面板，非 SaaS 营销页。
- **Decoration level:** minimal。排版与面层对比承担全部层次。删除一切玻璃面板与装饰光球（`.ambient-light-container`）。唯一例外：主动作与强阻断态用单点暖光点亮，作为“这里需要你”的信号点。
- **Mood:** 严肃工具感。给认真做事的人的审查台，冷峻、克制、可信。第一眼应读出“这是一台仪器”，而不是“这是一个现代 SaaS”。
- **Memorable thing:** 严肃工具感。后续每个设计决策服务于此。

## Typography

- **Display/Hero:** Satoshi（Fontshare）— 比 Geist 多一分人文几何感，标题统领感更强，避免全 Geist 的 Linear 复刻感。权重 900，字距 -0.025em。
- **Body/UI:** Geist（Google Fonts）— Things/Linear 质感，技术、干净，tabular-nums 支持数字。权重 400/500。
- **UI/Labels:** 同 body（Geist）。
- **Data/Tables:** IBM Plex Mono（Google Fonts）— 页码、状态枚举、置信度、run id。必须支持 tabular-nums。mono 是结构身份标记，是“工具感”的关键来源。权重 400/500/600。
- **Code:** IBM Plex Mono。
- **Loading:** CDN（Google Fonts + Fontshare）。生产可后续自托管。
- **Scale:** 12 / 13 / 14 / 16 / 18 / 22 / 28 / 40 / 56 / 72（clamp 用于 hero）。
- **禁用为主字体:** Inter / Roboto / Arial / Helvetica / Open Sans / Lato / Montserrat / Poppins / Space Grotesk（AI 收敛陷阱）。Geist 因老板明确引用 Things/Linear 质感而采用，但仅作 body，不作 display。

## Color

- **Approach:** restrained——1 个琥珀铜强调色 + 冷调墨色中性。冷底暖点的张力是刻意的。
- **Primary (accent):** `#E09043` 琥珀铜。仅用于主动作、阻断信号、当前态。绝不用于大面积填充或装饰。
- **accent-soft:** `rgba(224,144,67,.12)`——强调底，低饱和。
- **accent-line:** `rgba(224,144,67,.32)`——强调边。
- **Neutrals (cool ink):**
  - ink-base `#0B0E12` 深底（冷调墨黑，非纯黑）
  - surface-1 `#11151B` 实面面板
  - surface-2 `#161B22` 抬升面 / 悬停
  - surface-3 `#1B212A` 嵌套面
  - hairline `#232A33` 1px 发丝边框
  - hairline-soft `#1A2029` 弱分隔
  - text-primary `#E6E9EE` 主文字（微冷白）
  - text-muted `#8A93A0` 次级
  - text-faint `#5A626C` 弱化 / 占位
- **Semantic:** success `#6FAE6F`（已批准）/ warning `#D9A441`（P1、待处理）/ danger `#C75450`（P0、驳回、阻断）/ info `#5B8DB8`。
- **Severity:** P0 `#C75450` / P1 `#D9A441` / P2 `#7A8694` / P3 `#5A626C`。
- **Dark mode:** 深色为默认（主路径）。深色即上述 token。
- **Light mode:** 反相为冷调纸感，降低饱和度 10–20%，保持严肃。ink-base `#EAECF0` / surface-1 `#FFFFFF` / accent `#C2742F` 等（见 preview 页 `[data-theme="light"]`）。Light 不做亮色营销感。

## Spacing

- **Base unit:** 4px。
- **Density:** compact。审查台数据密集，行高压缩，发丝边框分隔而非阴影。
- **Scale:** 2xs(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(48) 3xl(64)。

## Layout

- **Approach:** grid-disciplined。桌面三栏严格对齐，与 `docs/2026-06-21-web-ui-ia-v1.md` 一致。
- **Grid:** 左窄(找页+筛选+状态计数) / 中大(预览+主动作条) / 右决策台(职责→来源·证据→风险→审批)。
- **Max content width:** 1240px。
- **Border radius:** 极克制。sm 2px / md 4px。不做大圆角与“bubble”一切。按钮可直角微圆 2px。唯一例外 pill 状态用 9999px。
- **分隔语言:** 1px hairline 实线分隔，取代阴影与玻璃。阴影仅用于浮层/抽屉。

## Motion

- **Approach:** minimal-functional。只保留帮助理解的过渡：状态切换、阻断出现、主动作反馈。严肃工具不弹跳。
- **Easing:** enter ease-out / exit ease-in / move ease-in-out。
- **Duration:** micro 50–100ms / short 120ms（主用）/ medium 250–400ms / long 400–700ms。

## Interaction

- 动作结构：一个主动作 + 若干次动作。主动作随当前页状态切换（批准 / 请求补证据 / 驳回并说明）。`升级审批` 仅在初审完成后出现。`确认交付` 仅在 export_ready 阶段升为顶部唯一高权重按钮。
- 强阻断态：P0/P1 直接控制主动作条状态与说明，联动顶部阻断标记、中栏主动作条、右栏风险块三处。
- skeleton loading 替代“载入中”文字等待。
- 完成态：某页通过后给出明确“下一页建议”。

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-21 | 首屏主视角围绕当前页 | 老板确认；最高频问题是页级（先看哪页/能不能过），run 级降为顶部状态带+抽屉。见 IA v1。 |
| 2026-06-21 | 记忆点 = 严肃工具感 | 老板确认；偏 Linear/Things 专业冷酷，后续所有视觉决策服务于此。 |
| 2026-06-21 | Aesthetic = Industrial × Brutally Minimal | 去模板感；仪器面板而非 SaaS 营销页。 |
| 2026-06-21 | 字体 Satoshi / Geist / IBM Plex Mono | 老板引用 Things/Linear 质感→Geist body；Satoshi display 避全 Geist 复刻；IBM Plex Mono 作数据身份标记强化工具感。 |
| 2026-06-21 | 强调色单一琥珀铜 #E09043，冷墨底 | 冷底暖点张力；颜色稀缺才有信号价值。 |
| 2026-06-21 | 去玻璃、改实面+1px 发丝边框 | RISK：去模板感代价是失去“高级发光感”，符合记忆点。 |
| 2026-06-21 | mono 承担页码/状态/置信度/run id | RISK：结构身份标记；长串枚举略慢读但本场景均为短 token，可接受。 |

## Risks (deliberate departures from category norms)

1. **冷墨底 + 暖铜点 的冷暖张力**。同类工具要么纯冷单色（Linear），要么整体暖。冷底配单点暖铜，让“需要你处理”的位置成为唯一暖色信号。代价：暖色若滥用会破坏冷峻基调——必须严格只用于主动作/阻断/当前态。
2. **mono 作为全屏数据身份标记**。多数 SaaS 只在代码块用 mono。本设计把页码、状态枚举、置信度、run id 全交给 IBM Plex Mono，让 mono 成为“这是一台仪器”的结构信号。代价：长串枚举文字 mono 略慢读（本场景为短 token，可接受）。
3. **彻底去玻璃、改实面 + 1px 发丝边框**。品类默认是 frosted glass。改成不透明实面 + 发丝边框，更像仪器表盘。代价：失去“高级发光感”，部分用户初看觉得“不够现代”——这是去模板感的代价，且符合记忆点。

## References

- 审计底稿：`docs/2026-06-21-web-ui-redesign-audit.md`
- 信息架构：`docs/2026-06-21-web-ui-ia-v1.md`
- 产品 spec：`docs/2026-06-10-web-ui-design-spec.md`
- 预览页（字体+色板+审查台 mockup，含中英切换）：`/tmp/deck-master-design-preview.html`（临时，实现后可删）
- 当前实现：`scripts/preview/static/{index.html,style.css,app.js}`
