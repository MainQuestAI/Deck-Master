# PR #39 合并前两项补缺验证

起点：`cad56e0`。用户授权补齐两项明确缺口后合并 PR #39；真实 HOME 迁移、AC-17 和 B 线仍不在本轮范围。

## 修复与证据

- 旧链接清理匹配 `deck-*` 或 `ppt-*`，其余条件保持：有效旧 companion manifest、符号链接、目标位于本安装前缀旧 `current/skills/`。19 是本机预期数量，不是删除条件。隔离测试包含 15+4 条目标链接、其他前缀链接、用户真实目录；覆盖正常迁移、opt-out 后延后清理、幂等与注册失败补偿。
- 页数约束比较最终正文总页数：首次 compose、完整稿导入、增量 content_update，以及写入 Page 的其他 Host 结果均受约束。超过上限拒绝采用并报告上限、实际页数与恢复动作；无变化结果不能绕过。将三页降为两页后，三页旧结果拒绝、两页结果正常采纳；未设置上限、等于或低于上限保持兼容。
- 历史已采纳超限稿件即使 basis 已标记 current，统一 CheckSummary 仍 fail，delivery export 与 delivery handoff 无法放行。审阅记录不能覆盖页数硬约束。沿用既有状态与错误协议，无新增 CLI 或 JSON 字段。
- SPEC §8.3、MIGRATION、AC-18、T9、当前安装指引同步更新；FILES.sha256 已重新计算，原规格与校验值保留在 Git 历史。

专项入口：`tests/rebuild/test_review_round4.py`，11 个测试。先在原代码运行初始 5 个场景，5 failed；修复后 11 passed。旧 Skill 名扫描仍执行，新迁移夹具按前缀与后缀构造退役名称，避免把测试数据误判为活动依赖。

## 最终验证

```text
Python 3.12: pytest tests/rebuild -q
597 passed in 111.14s

Python 3.11: pytest tests/rebuild -m 'not render' -q
568 passed, 29 deselected in 39.82s

ruff check src tools tests: All checks passed!
git diff --check: exit 0
FILES.sha256: 36 entries verified
```

两版测试串行运行；全量包含全部安装/Host 注册、真实候选安装、连续构建、sdist 重建和 29 项真实渲染测试。首次全量仅新夹具的旧名扫描冲突失败，修正后重新全量运行通过。

## 范围与后续

空 brief 互斥、方法派发粒度及其他已知小项不在用户本次指定的两个缺口中，未混入修复。A/R 工程证据不代表 AC-17 H 类验收。最终 SHA、CI 和合并结果记录在 PR；未执行真实安装迁移。
