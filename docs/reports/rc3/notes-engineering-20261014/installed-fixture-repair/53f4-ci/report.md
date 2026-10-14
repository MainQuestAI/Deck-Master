# RC3-02 修复后最终 Head CI 守门

结论：FAIL_ENGINEERING_CI。本源Head不能合并；失败报告与原日志从此冻结，后续修复另建新Head目录。

- PR：#117，当前源Head `53f4ab335d4bacb0862d810cf8acf55eeba7e744`，Tree `a3b2116f1e11a30ca3f8d892241ec25d5d00e4a9`。
- Base：`8e274576e7a93de7d10c054558991878501fff0c`。
- 实际被测PR merge SHA：`3ee8a46c1c90a098dc99b52481c5e37293567733`，6个源码Job checkout一致并与PR metadata一致。
- 精确Run：[38642260224（#490，Rebuilt Core Gate）](https://github.com/MainQuestAI/Deck-Master/actions/runs/38642260224)，completed / failure。
- 最终观察：2026-10-14 22:08:28 UTC。

| Job | ID | 状态 / 结论 | 当前日志实测 |
|---|---|---|---|
| Required browser and installed UI (Python 3.12, Node 22) | 116120840984 | completed / failure | 403 passed, 1904 deselected in 1410.49s (0:23:30) |
| Real rendering chain (Python 3.12) | 116120841343 | completed / success | 56 passed, 1 skipped, 2250 deselected, 22 warnings in 96.35s (0:01:36) |
| Unit (Python 3.11, Node 24) | 116120841344 | completed / success | 1845 passed, 2 skipped, 460 deselected in 236.75s (0:03:56) |
| Unit (Python 3.11, Node 22) | 116120841397 | completed / success | 1845 passed, 2 skipped, 460 deselected in 249.56s (0:04:09) |
| Unit (Python 3.12, Node 22) | 116120841633 | completed / success | 1845 passed, 2 skipped, 460 deselected in 259.33s (0:04:19) |
| Unit (Python 3.12, Node 24) | 116120841672 | completed / success | 1845 passed, 2 skipped, 460 deselected in 275.96s (0:04:35) |
| Group report | 116131016976 | completed / failure | unit/render success，browser failure |

Browser第9步production regressions通过：`403 passed / 1904 deselected`；第10步wheel构建与安装也通过。第11步 `Offline installed UI and fixed-version downloads` 失败：`w12_offline_browser.py` → `w11_browser.py:92` fixture断言readback为pass，实际 `speaker_notes_mismatch`，P1原生备注为合成 `PRIVATE-CANARY`。根因仍待Owner区分runtime与fixture；此失败不能归为已解决的旧0d渲染器依赖问题。

第12步installed recovery因前序失败而skipped，状态NOT_RUN，当前run没有安装恢复测试计数，不能借旧239通过。Group report依据browser failure而失败。

当前Unit各2skip，render1skip；`-q`没有提供测试ID或原因，保持未知，不写成通过或本地1847/57。必要完整trace分别存 `raw/job-116120840984-failure-trace.txt` 与 `raw/job-116131016976-failure-trace.txt`；原API状态存raw/final JSON。先前IN_PROGRESS报告原字节保留于 `raw/report.pre-failure.*`，旧0d报告及失败raw完全未改。

已通知Root与Owner；未修改源码、重跑、评论、推送或合并。仅覆盖工程CI，文档终审、专业、桌面与人类验收另行记录。
