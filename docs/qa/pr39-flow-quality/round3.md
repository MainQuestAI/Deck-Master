# PR #39 第三轮修复验证

日期：2026-09-26。审查起点 `75c2eba`。仅 A 线 Flow Quality，保留前两轮修复。最终提交 SHA、CI 和干净提交候选安装的命令结果见 PR 验证记录。

## 审查项与行为证据

| 问题 | 修复与验证 |
|---|---|
| P1：晚到修订覆盖后来的页序 | `compose/input_revision` 从既有派发快照比较有序 `(page_id, page.sha256)`。重排、增页、删页、正文修改均过期，不再走逐页 fallback。真实 CLI create → inputs update → import-draft 重排 → 旧 task accept 返回 exit 5 / stale_input_context，Document（包括 pages、basis、outputs）不变。 |
| 结算与提交竞态 | 调用事实结算并重新加载 Document 后再检查正文依赖；最终提交保留 base_revision 校验。两个故障注入测试分别在结算后和最终提交前重排，均拒绝覆盖；已结算 unknown 调用事实保留。 |
| continue 恢复 | 待对齐时退役过期修订并重派当前输入；导入已对齐正文后同样退役旧修订，再进入制作。task start、调用分配及显示名变化的既有测试保持；逐页任务规则未修改。 |
| P2：Host 父路径漏检 | skills、CODEX_HOME、上级组件分别覆盖断链、循环链接和非目录，共 9 个预检场景；返回 HostSkillConflict，CLI exit 5，current 未切换。有效目录符号链接正常注册。 |
| 安装失败补偿 | 锁内生成一次迁移计划；进程内反向操作覆盖目录迁移、旧链接清理、current/previous、Host 注册/摘链、新启动器与目录。全新、升级、旧布局、延后清理、rollback 注入故障后恢复原状态，保留候选与第三方条目。既有 install.lock 保留以维持并发锁语义。 |
| 补偿失败与 opt-out | 补偿验证条目及父目录身份，拒绝覆盖外部替换。失败报告包含原错误、未恢复路径和备份位置，CLI exit 4，保留现场。禁用注册不进入 Host 预检或 Host 写入/补偿；断链 Host 仍可完成 CLI 激活。 |
| 安装指引 | 整篇报告将 dc2636e 候选及其 511 项结果标为历史证据，移除旧发布激活命令。当前命令要求 CI 通过、工作树干净、HEAD 对应 PR；构建后检查 source_sha/source_dirty，从 manifest 读取 release_id，默认使用隔离前缀。首次 companion 迁移没有可执行 previous 的说明保留。 |
| 新增 PR 评审：compose doctor 漏检方法 | 使用实际 compose/initial 与 input_revision 的方法清单并集检查全部文件，避免另外维护一份列表。缺 source-reading、content-examples、input-update 任一文件均 needs_tool，不能报告 ready。 |

测试入口：`tests/rebuild/test_review_round3.py`，33 个场景；既有 flow-quality、task、budget、install 与 Host 注册测试全部保留。

## 先复现再修复

- 最初 15 个行为场景：11 failed、4 passed，确认重排漏检、Host 父路径断链/循环漏检与注册失败残留切换。
- 新增 doctor 评审先以三种缺文件运行：3 failed；修复后全部通过。
- 修复后的第三轮专项：33 passed。

## 全量回归

```text
Python 3.12: python -m pytest tests/rebuild -q
586 passed in 127.19s

Python 3.11: python -m pytest tests/rebuild -m 'not render' -q
557 passed, 29 deselected in 38.32s

ruff check src tools tests
All checks passed!

git diff --check
exit 0
```

Python 3.12 全量包含 29 项真实渲染，以及完整安装、Host 注册、真实候选安装、连续构建与 sdist 重建。两版测试串行执行，未跳过此前要求补齐的安装测试。安装指引的 shell 块已通过语法检查；最终 CI 全绿后的干净提交构建、manifest 校验与隔离激活结果追加在 PR 验证评论，以免更新证据后改变被验证的 source_sha。

## 再次复核与边界

检查了完整正文依赖与实际写回范围的一致性、结算后重读路径、最终并发校验、两类 continue 恢复，以及 activate/rollback 共用补偿、Host opt-out、外部占用保护和安装文档的发布标识来源。补偿仅覆盖当前进程内异常，不新增持久事务协议。

本轮未修改 B 线或 UI，未操作真实 HOME，未执行 AC-17 真人会话或合并。自动测试、合成项目、真实渲染及隔离安装不替代这些用户验收。
