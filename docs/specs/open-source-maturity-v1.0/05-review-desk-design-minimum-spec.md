# 05 — Review Desk Design Minimum Spec

## 1. 目标

让 M1 public Technical Preview 的第一屏符合 `DESIGN.md` 最小要求，避免公开入口继续保留核心视觉偏离。

## 2. 必须先读

实施前必须阅读：

1. `DESIGN.md`
2. `docs/2026-06-21-web-ui-redesign-audit.md`
3. `docs/2026-06-21-web-ui-ia-v1.md`

## 3. M1 最小修复

必须完成：

1. 加载或明确自托管 Satoshi / Geist / IBM Plex Mono。
2. 移除 `.glass-panel`。
3. 移除 `backdrop-filter`。
4. `.btn-cta` 改为琥珀铜主动作。
5. 文案统一为 Deck Master Review Desk / 审查台 / 审稿桌。
6. 核心面板改为发丝实面、小圆角、冷墨底。

## 4. 允许修改路径

1. `scripts/preview/static/index.html`
2. `scripts/preview/static/style.css`
3. `scripts/preview/static/app.js`
4. `README.md` 中的截图引用

## 5. 不做内容

1. 不重写 Review Desk 信息架构。
2. 不新增完整编辑器能力。
3. 不引入新的前端框架。
4. 不做大范围动效改造。

## 6. 验收方式

静态扫描：

```bash
rg -n "glass-panel|backdrop-filter|方案项目工作台|#fff;\\s*color:\\s*#000|border-radius:\\s*(1[2-9]|[2-9][0-9])px" scripts/preview/static
```

人工截图：

1. Desktop 1440x900：首屏。
2. Desktop 1280x720：Review Desk 主工作区。
3. Mobile 390x844：首屏可读性。

## 7. 成功标准

1. 第一屏符合严肃工具感。
2. 主动作层级明确。
3. 文案不再出现旧命名。
4. 公开截图可用于 README。
