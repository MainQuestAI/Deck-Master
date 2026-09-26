# PR #39 第二轮修复验证

日期：2026-09-26。审查起点 `fc6a949`，修复代码提交：`12816f8`、`a96366d`、`b79e6a5`。仅 A 线 Flow Quality。

## 六项结论与修复证据

| 审查项 | 最终行为与验证 |
|---|---|
| 迁移前启动器预检 | 安装锁内先检查候选、current/previous、启动器与父目录；普通文件、目录、有效/悬空符号链接、父路径占用均在迁移前拒绝。测试核对旧 manifest、15 条链接、无新增备份。 |
| 材料 needs_tool | 缺 pdftotext 或 python-pptx 保留 needs_tool / exit 3 与原始材料路径。显式/目录 create 中止且无项目残留；inputs update 的 add/replace 失败保持 Document、revision、来源和任务不变。损坏文本、JSON、DOCX、PPTX、PDF 仍为 source_unreadable。 |
| 禁用 Host 注册 | opt-out 不清理旧链接，也不摘除受管链接；CLI 仍可激活。随后正常激活依据保留且重新校验的 manifest 完成清理与注册，重复调用幂等；manifest 被改坏时拒绝清理。 |
| 循环符号链接 | 目录中的自环、双节点环、祖先目录环、断链均有跳过记录，CLI 成功导入其余材料；显式点名循环路径返回 exit 2。 |
| 自定义安装前缀 | 实际候选安装到含空格的前缀，默认 HOME 放置失败启动器；执行已安装 SKILL.md 中的绑定代码，从 Codex 入口解析到同一 release，运行真实 doctor，检查 module_path 归属与 Skill 字节一致。非受管路径被拒绝。 |
| 连续构建残留 | 构建钩子清理 build 输出中的退役 resources/skills-references。测试执行 c93 基线钩子后保留 build/ 再执行当前钩子；另用完整 c93f5a2 源码连续构建复核：旧资源 6 → 0，9 个 canonical 方法文件逐字节一致。 |

完整基线连续构建的文件清单：[round2-warm-build.json](round2-warm-build.json)。常规 wheel、sdist 重建和真实候选安装测试全部执行。构建回归使用保存的基线钩子，避免 CI 浅克隆依赖历史 Git 对象。

## 先复现，再修复

- 安装和材料新增回归在原实现上：12 failed / 16 passed，覆盖迁移破坏、opt-out 清理/摘链、缺工具分类及循环链接。
- 连续构建测试在原钩子上确实生成旧资源，并在第二次构建后的无残留断言失败；Skill 的旧 HOME 绑定不满足新版绑定检查。
- 修正一条旧的构建代码文本断言：不能因为清理代码提到退役目录而失败。保留包配置检查，并以实际 wheel 内容和连续构建验证代替代码字样推断。

## 最终回归

```text
Python 3.12:
python -m pytest -q tests/rebuild
553 passed in 106.84s

Python 3.11:
python -m pytest -q tests/rebuild -m 'not render'
524 passed, 29 deselected

python -m ruff check src/deck_master tests/rebuild tools/build_hook.py
All checks passed!

git diff --check
exit 0
```

Python 3.12 全量包含全部 29 项真实渲染测试、此前未重跑的 14 项安装测试，以及本轮新增安装/打包测试。Python 3.11 使用单独虚拟环境；两版打包阶段串行执行，避免共享 build 目录竞争。GitHub 最终提交的 Python 3.11/3.12 unit、真实渲染与汇总结果在 PR Checks 记录。

## 修复后复核与边界

复核重点：所有占用检查发生在迁移写入前；opt-out 没有 Host 写入路径；延后清理要求有效保留清单；缺工具不进入材料错误吞掉分支；循环路径不破坏正常材料导入；CLI 与 Skill 来自同一 release；旧构建资源不进入新 wheel。未发现本轮六项范围内的新阻断项。

本次只使用隔离 prefix、HOME/CODEX_HOME 与合成材料；未执行真实 HOME 迁移、AC-17 真人会话、B 线改动或自动合并。首轮浏览器与状态流证据仍见 [README](README.md)；这些证据不代表专业内容或生产验收。
