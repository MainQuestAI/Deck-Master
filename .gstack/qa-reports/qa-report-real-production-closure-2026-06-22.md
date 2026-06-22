# Deck Master Real Production Closure QA Report

日期：2026-06-22 16:41 CST  
分支：`codex/real-production-closure`  
QA 样本：`qa-real-production-closure-20260622`  
本地预览：`http://127.0.0.1:5063/?run=qa-real-production-closure-20260622`

## 结论

本轮 QA 结论：通过，包含 3 个已修复问题；上一轮记录的 suite 降级风险已关闭。

核心链路已验证：fixture autoplan、build prepare/run/status、render 兼容模式、final readiness、workspace API、delivery preview、export queue、浏览器桌面/移动端、release smoke、benchmark aggregate、RC gate。

## 已修复问题

1. `QA-20260622-001`：`autoplan` 生成的 preview manifest 进入 `build prepare` 时失败。原因是构建器优先读取 `source_preview_asset`，该字段可能指向运行目录外的原始来源。修复后构建器优先使用运行目录内的 `preview_path`，安全边界保持不变。
2. `QA-20260622-002`：工作台暴露 `needs_context`、`Run state is needs_context.`、`completed`、`blocked` 等机器状态。修复后，主工作台、交付预览、最终放行和生产状态区统一显示中文业务状态。
3. `QA-20260622-003`：Codex 本机 suite readiness 为 `degraded_ready`。已执行安全迁移，把 required skill 入口统一挂到当前 Deck Master release tree，`suite-status` 已恢复 `ready`。

## 浏览器验收

- 桌面首屏：可加载，页面队列、阶段卡、交付预览、处理记录可见。
- 页面切换：点击第 6 页后 URL 和焦点页同步更新。
- 移动端：390x844 视口可完整纵向浏览；首次溢出 3px，最终桌面复验溢出 0px。
- 控制台：无错误。
- 最终截图：`.gstack/qa-reports/screenshots/real-production-closure-final-browser-i18n-20260622.png`

## 自动化验证

- `git diff --check`：通过
- JSON contract 解析：通过
- `python3 -m compileall scripts tests`：通过
- `python3 -m unittest discover -s tests`：798 tests passed
- `python3 scripts/deck_master.py validate-product-capability-manifest`：通过
- `python3 scripts/deck_master.py setup-status --include-suite --output json`：`ready`，suite `ready`
- `python3 scripts/deck_master.py suite-status --output json`：`ready`
- `python3 scripts/deck_master.py release-build --output <tmp> --force`：`built`
- `python3 scripts/deck_master.py release-smoke --release-root <tmp>`：`passed`
- `python3 scripts/deck_master.py benchmark-aggregate-report --benchmark-dir benchmarks --min-real-cases 3 --force`：`metadata_ready`
- `python3 scripts/deck_master.py rc-gate --output-dir <tmp> --benchmark-dir benchmarks --min-real-cases 3 --skip-browser-smoke --force`：`pass`

## Suite 风险关闭记录

- 迁移命令：`deck-master suite-migrate-legacy-skills --apply --plan-file /tmp/deck-master-suite-migration-plan.json`
- rollback id：`2026-06-22T092726.961744Z0000`
- rollback record：`/Users/dingcheng/.deck-master/current/migration/rollback/2026-06-22T092726.961744Z0000.json`
- 当前 Codex suite：7 个 required skill 全部 `ready`
- 当前 setup：`ready`，`next_command` 为空

## 说明

- RC gate 使用 `--skip-browser-smoke`，浏览器验收由本轮手动浏览器 QA 覆盖。
- benchmark 只使用脱敏 metadata，没有提交客户原文或私有资料。
