# C1 — Self-contained Release Tree

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `C1` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | Stack B complete |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

把 release 从源码仓软链接升级为真正自包含版本目录。

## 3. In Scope

- runtime copy/package。
- relative launcher。
- capability lock。
- release manifest。
- versioned releases。
- checksums。

## 4. Out of Scope

不发布到 PyPI；不实现在线 updater。

## 5. 必须实现

1. Release 包含完整 runtime。
2. launcher 不引用 repo root。
3. vendor/pin required capability runtime。
4. 生成 capability lock。
5. 生成 release manifest 和 SHA256SUMS。
6. current/previous symlink。
7. runtime doctor 检查 missing files。

## 6. 允许 / 预期修改路径

- `scripts/skills/installer.py`
- `scripts/release/`（新增）
- `product-capability-manifest.json`
- packaging scripts
- `tests/test_release_tree.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- build release outside repo。
- move/delete repo 后 CLI 仍可运行。
- checksum。
- missing file doctor。
- target skill links。

## 8. 成功标准

- Release 在临时目录独立运行。
- 无 repo-root dependency。
- 所有 required capability 有 lock。

## 9. 风险

Vendored 跨仓代码需处理 license 和同步流程。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
