# RC3-04 完整入口、方法与安装工程交接

本目录把 RC3-04 的固定软件结果、实际 Host 职责产物、原失败与后续关闭放到可 clone 的仓库中。当前运行代码为 `a53a265321ca6bb15f347bbe23b5143fe8b7378c` / tree `31cca075ac76877908e04f030f0c4e815d3a6268`。最终文档提交与其后的 CI/merge 是另外的事件，CI 仍为 **PENDING_FINAL_HEAD**。本交接不签完整 RC3、真实人类、听众、专业政策或目标桌面验收。

- [当前报告](report.md)：版本/包/安装、固定回归、独立审查与三入口边界。
- [原卡与 AC/CQ 证据映射](acceptance-map.md)：原九项工作、17 条本卡 AC 和 CQ-07/CQ-13；最终状态仍以[唯一37 AC/13 CQ台账](../evidence-ledger.json)为准。
- [问题关闭与精确复用](finding-closure-map.json)：F1–F9、R2-C1–C5、Plan/recovery/style/CLI 及 R3-C6；原失败保留原版本。
- [16 组合路径](role-entry-paths.json)：**R3 新执行1条 + R2 精确复用15条**，同一个实际 Host，非16个独立模型或一次全新16路重跑。
- [版本与安装身份](identity.json)、[保留失败索引](preserved-failure-index.json)、[逐字节副本清单](manifest.json)。

`raw/` 只包含明确白名单中的安全原件副本，SHA256 与外置原件逐一相同。原件中的绝对路径是历史执行定位；离开原工作区后通过 manifest 的 `copied_path` 查仓库内副本。导航 JSON/Markdown 是派生索引，不是新的 Runtime 决定或批准。没有脱敏后冒充原件的文件；没有复制实际项目 Store、registry、runtimeauth/HMAC、venv、客户原料、原始安装包或缓存。未入白名单的外置诊断原件仍保留，不代表本目录穷尽所有运行材料。

原 R1/R2/R3 交接分别保留于 [R1](../RC3-04-HANDOFF.md)、[R2](../RC3-04-R2-HANDOFF.md)、[R3](../RC3-04-R3-HANDOFF.md)。其中当时的 pending/失败措辞属于当时版本，不覆盖为后来的 PASS。RC3-03 的单 p04 native 工程交接与660原件也保持原范围，不升级为本卡或全 RC3 专业验收。
