# RC3-04 当前8223最终 CI 失败记录

结论：FAIL_ENGINEERING_CI。当前Head不能合并；报告与证据从此冻结，后续修复另建Head目录。

- PR119源Head：`8223df80be654c9a89a44cd97cf770fa01bf4383`
- 源Tree：`7b96dbcc1784160a5e045e3198e51f93c0542504`
- Base：`634d75e4cc48368e53b088e47fa09c675cd2b998`
- 实际被测merge：`749b022e016a058f80fd516117c8d324227fab4f`，6源码Job checkout一致。
- 精确Run：38696634552（#495），completed/failure。
- 最终观察：2026-10-15 07:51:15 UTC（UTC）。

| Job | ID | 状态/结论 | 当前日志结果 |
|---|---|---|---|
| Real rendering chain (Python 3.12) | 116294607001 | completed/success | 70 passed, 1 skipped, 2797 deselected, 22 warnings in 169.85s (0:02:49) |
| Unit (Python 3.12, Node 22) | 116294607189 | completed/success | 2360 passed, 2 skipped, 506 deselected in 369.22s (0:06:09) |
| Required browser and installed UI (Python 3.12, Node 22) | 116294607252 | completed/failure | 90 failed, 342 passed, 2433 deselected, 4 errors in 2408.20s (0:40:08) |
| Unit (Python 3.11, Node 24) | 116294607255 | completed/success | 2360 passed, 2 skipped, 506 deselected, 1 warning in 540.03s (0:09:00) |
| Unit (Python 3.12, Node 24) | 116294607391 | completed/success | 2360 passed, 2 skipped, 506 deselected in 526.76s (0:08:46) |
| Unit (Python 3.11, Node 22) | 116294607444 | completed/success | 2360 passed, 2 skipped, 506 deselected, 1 warning in 531.55s (0:08:51) |
| Group report | 116309755416 | completed/failure | unit/render success，browser failure |

Browser第9步真实90 failed /342 passed /4 errors /2433 deselected，2408.20秒。四ERROR为3个studio_range_edit fixture direction缺失及1个batch teardown 409!=200；全部90个FAILED与4个ERROR原始ID见raw/failure-index.json。失败摘要可归为授权动作25、direction缺失4、预算链0为1、Host compose.v2能力2、UI断言36、UI等待超时20、其他2；这只是症状分组，不能据此先认定全是fixture。必要完整四类trace与全部原日志已留存。

后续wheel构建安装、Offline installed UI、完整installed recovery均skipped/NOT_RUN，本轮没有UI9或恢复239计数。Group依据browser failure失败。5成功Job实际4Unit各2360 passed/2skip，render70 passed/1skip；skip原因未输出，保持unknown。

Browser日志完整解码文本由apply_patch存储时规范末尾换行，不称byte-verbatim：本地快照SHA `9705083903f932e1da74310b9c5bc066781d290de443dc15e18e2a251c632f89`；与Root独立exact API文件比较为“exact match”。Root exact API原件SHA `9705083903f932e1da74310b9c5bc066781d290de443dc15e18e2a251c632f89`，路径与字节数见JSON。未为匹配修改本地原快照。

已通知Root，停止此Head轮询；未修改源码、重跑、评论、推送或合并。Root的独立docs限定PASS不抵消此次CI失败，card总体验收未通过。
