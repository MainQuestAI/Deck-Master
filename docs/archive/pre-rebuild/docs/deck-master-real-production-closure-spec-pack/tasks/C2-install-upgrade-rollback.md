# C2 — Transactional Install / Upgrade / Rollback

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `C2` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | C1 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

提供安全安装、升级和回滚。

## 3. In Scope

- stage/verify/activate。
- migration plan。
- backup。
- rollback。
- failure recovery。
- temp HOME smoke。

## 4. Out of Scope

不做自动联网更新。

## 5. 必须实现

1. 安装先 stage。
2. Verify 后原子切 current。
3. 保留 previous。
4. legacy real dir 不静默覆盖。
5. upgrade from 0.9.13。
6. rollback command。
7. 失败自动恢复。
8. install log。

## 6. 允许 / 预期修改路径

- `scripts/release/install.py`
- `scripts/skills/installer.py`
- CLI commands
- `tests/test_release_install.py`
- `tests/test_skill_installation.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- clean install。
- reinstall。
- upgrade。
- broken release。
- real dir conflict。
- rollback。
- symlink repair。
- multi-target。

## 8. 成功标准

- Temporary HOME 全部通过。
- 安装失败不破坏当前可用版本。

## 9. 风险

macOS symlink、权限和路径空格需要单独测试。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
