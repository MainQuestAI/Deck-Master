# T7 — Review Desk Design Minimum

## 1. 目标

完成 M1 公开入口的 Review Desk 最小设计合规。

## 2. In Scope

1. `scripts/preview/static/index.html`
2. `scripts/preview/static/style.css`
3. `scripts/preview/static/app.js`
4. README 截图引用

## 3. 必须实现

1. 字体方案：Satoshi / Geist / IBM Plex Mono。
2. 移除 `.glass-panel`。
3. 移除 `backdrop-filter`。
4. 主动作使用琥珀铜。
5. 命名统一为 Review Desk / 审查台 / 审稿桌。
6. 发丝实面、小圆角、冷墨底。

## 4. 验证

```bash
rg -n "glass-panel|backdrop-filter|方案项目工作台|#fff;\\s*color:\\s*#000|border-radius:\\s*(1[2-9]|[2-9][0-9])px" scripts/preview/static
```

## 5. 截图

必须提供：

1. Desktop 1440x900 首屏。
2. Desktop 1280x720 主工作区。
3. Mobile 390x844 首屏。
