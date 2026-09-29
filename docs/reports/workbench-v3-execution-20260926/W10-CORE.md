# W10 运行与恢复共享核心

实现提交 `b505d34f384edda5f50e94f1e8d2a3d0060fb737`。状态：本地实现与回归完成，[PR #56](https://github.com/MainQuestAI/Deck-Master/pull/56) 已提交，等待 CI；前端、20 分钟压力、实际当前 Host 验证与用户验收未完成。

运行列表复用正式 Task/ChangeSet/Candidate/Request/Attempt 对象，分页最多 100 条，可按修改组、任务状态和人的待办过滤。当前运行不会被列为人的待办；复制、读取、轮询均无执行动作。固定 revision 的后续分页保留该版本，历史任务不会因墙上时间流逝获得当前超时状态。旧 `/api/tasks` 与旧 CLI status 响应保留；新 CLI list/status --details 与 HTTP 分页/详情共用投影和错误。

首次真实 `task_start` 将 execution_started_at 与 execution_ref/status 一起写入 Task。冻结请求、调用结算、同执行重复接手与取消保留该时间；旧任务不补造时间。仅 workbench.v3 的新接手进入 run-desk.v1 写入边界；更高边界在内容计划、变更、候选采用、组装等写入中保留。真实前版核心 d42dda6 的取消命令在写入前拒绝新边界（退出 4），指针未变化。

修改交接增加作用页、接手时间、结果/候选、Attempt ID 和调用状态。读取不可损坏全部页面；坏对象作为局部错误，错误带原因、动作和离线 docs_ref。unknown 始终不是 not_sent；30 分钟仅提示核实，没有新增调度或外部调用重试。

验证：848 项完整 rebuild 测试通过；随后补历史超时隔离并通过 13 项 run_desk/changes 针对性测试。Ruff 和合同镜像一致检查通过。恢复脚本 8 项检查通过，原始请求/响应留在本地 local-only，公开 checks 保留可核对 ID 和完整错误 JSON。合成时钟、晚到结果和 unknown 注入均标明，不作为真实模型或真实 Host 证明。

- 实现：run_desk.py、Task 接手事实、共享 writer 边界、CLI/HTTP 与 handoff 投影。
- 复现：`PYTHONPATH=src python examples/workbench/w10_recovery.py --out <new-directory>`。
- 恢复说明：[Run Desk Recovery](../../agent-recovery-playbook.md#run-desk-recovery)。

本卡未关闭。下一步仅在共享核心合入 main 后接前端、补浏览器恢复矩阵和固定 300×5×3 的 20 分钟内存测量。

证据：[恢复检查及完整错误 JSON](w10/core/recovery-checks.json) / [真实前版核心拒写](w10/core/old-core-checks.json)。

W04 压力首屏补证使用 W01 的同一 300×5×3 manifest，并使用提交中的 w04_pressure.py 复现。两个视口各 3 次，最慢 0.899 秒；只预热首 30 页窗口的实际缩略图，页面导航包括真实 JSON 读取与页面选择动作。[原始样本](w04/pressure/checks.json)、[1280 视口](w04/pressure/gallery-1280.png)、[1440 视口](w04/pressure/gallery-1440.png)。原型画面没有替代这些真实浏览器读取。该补证不覆盖 20 分钟压力缓存/内存，W04-AC06 仍待 W10 持续浏览证据补全。
