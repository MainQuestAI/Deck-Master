# RC3-04 最终工程可移交报告

当前代码 `a53a265321ca6bb15f347bbe23b5143fe8b7378c` 已完成固定 unit 2362/2362、render 71/71 和 Ruff 检查。独立代码、实际安装行为和实际安装 UI delta 三路有限审查均已 PASS，无剩余must-fix。实际四 Skill 代表性组合16条由 R3 新 Master-natural 1条与 R2 未变15条构成。工程交接供 RC3-05 继续验效；最终文档 HEAD 的7项 CI、PR与merge仍为 **PENDING_FINAL_HEAD**，不把 a53 的本地检查写成最终 CI。

## 版本、合同、方法与实际安装

| 身份 | 精确值及边界 |
|---|---|
| 03实际合并基线 | `634d75e4cc48368e53b088e47fa09c675cd2b998` / tree `4acb0e07536bd71882cea128d9247f772c049fcd` |
| R1 | `7a8578baa210a92b92ae98922ff3236edf4d5975` / tree `4b7c5a931998ced2de624ee0ec29ff4a9e023139`；原缺陷/回归失败保留 |
| R2 | `573a46a85bf93d71a13652756bc3a6cdb1fab6ae` / tree `135769e0b16d6397baa51b5c098425b9a80eb9ff`；F1–F8关闭证据、F9新失败分开 |
| 当前运行代码R3 | `a53a265321ca6bb15f347bbe23b5143fe8b7378c` / tree `31cca075ac76877908e04f030f0c4e815d3a6268`，parent为R2 |
| 版本与写协议 | `1.0.0rc3`；当前 `rc3-entry.v1` rank13；旧 `rc3.v1` rank12无协作区域仍需迁移。技术 floor 不代替授权，旧不可变对象/closed receipts不重写 |
| 实际wheel | SHA256 `01177541b9a1bc38aefb50fd6c8e8499b6bae4a6afe59b7b467693fc1bd740fb` |
| 实际sdist | SHA256 `37ab2d030bc207689534e3d039629600f56a0250c0da4d07d02decbdc035f01b` |
| 实际release | `a53a265321ca-01177541b9a1`；manifest SHA256 `a338a72fb577890e77fbf6f5b0f25663f551b85d77eb04f85706a9c59c59368e` |
| 严格安装字节 | 270 canonical + 唯一generated method-inventory；四Role均核。报告SHA256 `9209595b80d313436dd9bbd98443466f8e0da5668e55517271db907afc3bcb4c`；仅PASS_BYTES_ONLY，不代替方法实际应用 |

隔离安装的实际 Python 位于该 release 的 `venv/bin/python`，module来自该 release 的 site-packages；不是源码环境或旧安装。路径/版本与manifest原件见 [identity.json](identity.json) 及 raw/candidate-04-a53a265。安装/Host/registry均使用临时隔离位置，没有真实 HOME/第三方配置切换。

四入口的 wheel 路径为 `deck_master/resources/skill/SKILL.md`（Master）和 `deck_master/resources/skills/{deck-content,deck-design,deck-review}/SKILL.md`。前者映射 `skills/deck-master/**`，后三者逐Role映射同名 canonical。四Role各有 `agents/openai.yaml`；共享可编辑方法只在 `skills/deck-master/references/`。原23资源路径映射仍见 [B resource mapping](../RC3-04-B-RESOURCE-MAPPING.json)，其中旧mutable包身份只解释当时诊断，不是当前安装。当前完整方法/合同字节通过候选 method-bytes、release manifest和严格审计重新绑定。

## 三入口与真实职责路径

CLI、HTTP/Studio和Host消费同一 Runtime/协作事实。默认create登记真实指令来源、framing和无隐式制作授权；所有正式writer同卡切换，legacy读取、精确terminal replay、cancel/settle仍按原协议可用。§12新collaboration统一错误映射与旧export/handoff脚本兼容分别保留：strict needs_reviewer为409/4且完整报告可取得，旧工程/审查未就绪路径仍按其原3语义。不存在public legacy writer开关或前端私存批准。

R1安装UI真实暴露确认稿入口缺失F5；R2独立安装UI已通过launcher确认稿新建、空项目future页明确scope、纯preview→CAS→明确替换request→独立确认import、stale/窄scope拒绝、非200完整报告下载、三视口/键盘与源树不变。CLI确认稿实际链及§12适配器证据和其L1界限保留在各轮报告。R3 UI-O1/O2/C6只改变当前内容出口、已知安全错误文案和已知模板摘要；raw Task、用户原话、unknown fallback与业务gate均保留。

Host 16组合逐项定位在 [role-entry-paths.json](role-entry-paths.json)。Content独立完成 plan_only/write_only/speech_only/content_full并正常停止；Design返回有界零图建议；Review提供只读文本关系意见和真实 needs_reviewer缺口；Master返回协调/范围/下一责任。R3原F9指令逐字重放，完整当前方法实际读入，两阶段真实claim/adopt后completed/closed，两次continue不新增制作。其余15条依完整方法/包/业务依赖核对复用R2，未倒签为a53执行。全部由同一个实际Host完成，Review仍host_self；没有新独立专业模型、人类、真实provider或图像调用。已知合成材料/既有scaffold不构成E1盲评或公平效果证明。

真实旧03安装→迁移→旧版本rollback拒绝Entry13写→新rollforward→speech_only链在R2完成。旧Page/visual原件、实际旧Task unknown调用事实与四managed links逐相核对；原R1末端F8阻断仍保留。R3只依据精确未变依赖复用该生命周期，没有声称重跑或实际用户日常安装激活。

## 原失败、修复与固定复验

| 固定候选 | 原始结果 | 后续边界 |
|---|---|---|
| R1 unit/render | unit538FAIL/1674PASS/74ERROR；render47FAIL/24PASS | 原日志/result保留；不能一律称fixture。F1–F8和迁移暴露的真实core问题分别修复 |
| R2 unit/render | unit255FAIL/2099PASS/0ERROR；render19FAIL/52PASS | 255/19逐文件分工映射、真实产品delta和原业务断言保留；R3固定退出0，不覆盖原失败 |
| R3 unit | 2362PASS/506deselect/460.23s，0FAIL/ERROR/SKIP | raw SHA256 `0353df1f913ec9f881b14a4c85154a502881280c4803307e5d41f823bc03f14a` |
| R3 render | 71PASS/2797deselect/22warn/140.04s，0FAIL/SKIP | raw SHA256 `f378031faaa0affe9eee1e2e55f1b9100f45af092652688cda666a95e42a2a76`；warnings不隐去 |

Root使用固定clean snapshot、专属absolute Python、offline wheelhouse和短TMPDIR。3622 tracked文件/HEAD/tree/status/模块origin/version前后一致，source manifest SHA256 `46399074a0a4541144ece9efc8135ffaa3b51b682ef061b0b78e92786d21e20c`。raw Root summary、unit/render原log和result随包保留。这是固定本地回归，不是最终HEAD CI或真实专业验收。

R3独立code报告 SHA256 `8b332bd82b009c05b399c8c29ca97160d1a7645b0a5b56d38ecf98a5e3b3c191`：有限delta PASS，实际9路由+6摘要控制、4focused通过，完整审阅46测试/helper路径；R2原F1/F2/F3/F4/F6及40相关checks按14产品模块/合同未变精确复用。R3独立installed behavior报告 SHA256 `cd12d8ff76b506b55a0ce80cc6442f83e27e8e39372511f7f0c7759cbaecf4d6`：5/5真实公开delta轨迹，12项纯投影unknown fallback辅助控制；17实际安装模块未变支撑R2有限复用。R3独立installed UI报告 SHA256 `19693ba1fc6e0294741bbb1987a9420e55689f42fdde4635432dec6c969fb250`：UI-O1/O2/C6的16有限断言通过，source3622/installed381完整树及两个外置原始来源前后不变，3服务已停。它们不冒称已重跑旧全矩阵或另一reviewer的工作。UI中04c是实际展开raw instruction的截图，06b是明确查看当前版本；其它collapsed/旧revision/错误在fold下的截图不作为相应可见证明。原locator/空error选择探针错误和修正均保留于原报告。

九个SVG机械回归明确分为“正式production拒绝且无发布”与“项目外调用相同真实compiler/render/readback工程链”；原像素、隐藏文本、渐变、几何和回读断言保留，不伪造PageVisual PASS。真实notes生产正例仍经过bounded blueprint→SVG→preview→PageVisual→produce/export并实际PPT notes回读。边界、原失败、每worker最终文件hash与所有mutable focused分次记录保留于R3 handoff及安全副本；不得把其数字累计为第二个正式suite。

## 当前出口与未运行

这份docs-only交接不改变runtime/tests/合同/方法/安装字节。最终Git提交身份由包含这些文件的commit及Root记录确定；a53 snapshot和所有R1/R2/R3原件均不修改。最终当前HEAD的7项CI、PR、merge及必要文档审查尚待Root，统一 **PENDING_FINAL_HEAD**。

唯一37AC/13CQ台账仅补本卡精确证据，原status、失败和签署者不批量覆写。实际人类Owner/至少三位目标类似听众/完整计时/目标PowerPoint桌面/人类professional policy仍 **NOT_RUN（按既有授权延期）**；没有把host_self或JSON身份冒充真实人类，也没有向用户重复要材料。完整E1/E2/E3、公平效果、剩余风险和RC3候选最终结论由RC3-05继续。model/token/价格未知仍未知，不记为费用0。RC3-03单p04 native工程结论保留其旧精确文件和版本，不沿称全稿或本卡新native执行。
