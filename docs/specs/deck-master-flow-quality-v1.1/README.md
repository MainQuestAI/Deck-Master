# Deck Master Flow Quality Spec v1.1（精简版）

交给 Codex 时按以下顺序阅读：

1. `SPEC.md`：范围、契约和砍掉的清单（§1.2 列出了从 v1.0 删减的内容）
2. `TASKS.md`：9 项任务、依赖关系和验证点
3. `ACCEPTANCE.md`：18 条验收和 7 步真实场景
4. `MIGRATION.md`：旧 Skill 的退役方式和本机旧安装的迁移
5. `methods/`：方法正文草案，合并进 `skills/deck-master/`
6. `examples/`：合成的往返样例，digest 已按 v1.1 算法重新计算

本包只是开发输入，不代表已实现，也不授权安装或合并。

2026-09-26：按用户确认的 PR #39 修复范围，迁移规则扩展至本安装旧目录下的 deck-* 与 ppt-* 链接，本机预期 19 条；SPEC、MIGRATION、ACCEPTANCE、TASKS 及 FILES.sha256 已同步。原始规格和校验值可从此前 Git 提交追溯。此修订不表示真实 HOME 已迁移或 AC-17 已验收。
