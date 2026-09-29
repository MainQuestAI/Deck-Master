# W06 共享核心：意见、明确范围的变更计划与可恢复提交

实现提交：`f3d5c3ebcd8dac12541e62b49e280cbaa34ab60f`。基线：`2d7e1a6dffc6755c20e8ca51175450b0fcbf829b`（W05 前端 PR #50 合并）。共享核心切片；前端与真实 Host 接手尚未完成，不关闭整卡验收。

## 行为

- `annotations save/list` 与同源 `annotations/batch` / GET annotations 共用 Service。四种 scope 和 whole/point/rect/text 绑定固定版本；文本复用 W05 码点校验，几何绑定实际位图尺寸或 SVG viewBox。完整批次预检后一次提交；保存不建任务、不改生产 content_identity 或产物。
- `changes plan/commit/list/handoff` 共用 CLI/HTTP。plan 只存不可变预览对象，不移动业务指针。commit 对完整 payload、当前版本、页和目标槽重新核验，原子建立 ChangeSet 与明确范围的任务。每个计划每页一个动作，依赖层分步计划；PPT 意见明确先修该页 SVG，再沿正常编译链产生整稿 PPT。
- Task 的 change_binding 约束结果的页、写入层及调用上限；蓝图仍用原有 generation.v1 和调用账。旧任务正在目标页工作时，须先核实或确认取消。任务的完成与实际质量评价分别记录。
- 新操作 UUIDv4 由客户端发送前保存。OperationCommit 及 result_ref 随 Document 同次指针提交；索引损坏、缺失或后续写入后仍从已提交 parent 链恢复原结果。未提交对象不算成功，异 payload 拒绝。旧 task accept 的查重、结算与采用现在在同一个项目锁内。
- `operations show` 与 GET operations 使用一致 typed error / CLI 退出码 / HTTP 状态。旧无摘要历史操作保留 unknown，不猜测重放。核心交接块包含实际计划、任务、请求和协议；CLI 入口经 shell 引用，复制不会领取任务。30 分钟只提示核实，unknown 不自动重试。
- `changes.v1` writer boundary 防止旧核心覆盖新记录；ContentPlan 和历史恢复保留边界。默认入口、实际 HOME 和其他工作树未修改。

## 验证

- 全部 rebuild 回归：**808 passed，146.81 秒**，见 [原始摘要](w06/core/pytest.txt)。包含既有安全、安装隔离、渲染链和全部新增核心测试；不等于 W12 用户安装验收。
- 可运行脚本 `examples/workbench/w06_change_handoff.py`：**9 项通过**，见 [checks](w06/core/checks.json)。CLI 从真实回包获得版本/引用，再保存、plan、commit、查询与读取交接；真实 Chromium 同源 fetch 完成另一条意见保存。
- 新操作与旧 task accept 各覆盖 pointer 前/后、index 前/后四个位置的真实子进程 `os._exit(73)`；重启后同 ID/同 payload 只产生一次提交，插入后续写入仍恢复原结果。另测线程并发同/异 payload、取消后晚到、索引损坏/删除、索引 symlink 和 UUID 负例。
- CLI/HTTP 回归验证跨 Origin、缺 token/错误 token、错误字段、operation_not_found、返回字段和状态一致；原 Web 安全回归通过。Ruff 与 diff 检查通过。
- 先前回归暴露并修复 CLI 主解析器变量覆盖；更新了两份旧 schema 镜像。旧竞态测试改为检查结算/采用持锁，并保留真实并发测试。一次源码变化导致 BUILD_ID 不同的测试运行被明确作废，稳定源码下重新完成 808 项。

## 证据边界与后续

所有数据为合成项目；测试中的 execution_ref 是明确的合成标识。脚本任务停在 awaiting_host，没有模型调用或真实 Host 接手。原始输入/回包及完整交接仅存本机 `/tmp/deck-master-w06-core-example-first/local-only-requests/`，不提交运行目录或 session/token。

W06-Web 仍需完成阅读/标注模式、坐标交互、个人草稿 pending 冻结、保存未知恢复、持久交接面板、复制与真实 Codex CLI start；W06-AC08 和整卡 accepted 保持未验证。用户验收另记。
