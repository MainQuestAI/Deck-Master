# RC3-04 R4/R5 最终交接补充

当前软件冻结于 `740af2bddbc1199762c750be2f98474feaadb5a6` / tree `0ef706cca75acefaba218f714ffbc5c29f5d8aae`。本次只提交文档和安全证据副本；产品、测试、四Role方法、合同及唯一37AC/13CQ台账均保持该版本字节。

- [当前报告](report.md)：R4/R5修复、真实固定结果、有限审查与准确复用边界。
- [状态与身份](status-and-identity.json)：R5软件/实际包/安装身份，已完成与仍运行的gate，ledger不变证明。
- [逐字节安全副本清单](manifest.json)：42份冻结原件、10份仅索引原件；不复制正在变化的R5 browser/recovery日志。
- [R4原94事件映射](../r4-focused-evidence-20261015/original94-r4-mapping.json)、[R4修复交接](../RC3-04-R4-HANDOFF.md)、[R5资产回归修复交接](../RC3-04-R5-HANDOFF.md)。原FAIL/ERROR、后续focused及固定验证分别保留。
- [R1–R3原证据导航](../entry-integration-handoff-20261015/README.md)、[原卡/AC映射](../entry-integration-handoff-20261015/acceptance-map.md)、[16组合路径](../entry-integration-handoff-20261015/role-entry-paths.json)：仍为R3新执行1条+R2精确复用15条，同一个实际Host，未在R5重跑16条。

冻结本补充时，Root R5 source browser与installed full recovery仍为 **PENDING_RUNNING**；最终文档HEAD的独立docs复核、新建包/严格字节比较和实际7项CI为 **PENDING_FINAL_DOCS_HEAD**。Root后续将用外置冻结汇总与PR119真实GitHub checks记录完成情况，05总台账再回引实际结果。此处不预填尚未发生的计数或PASS；PR119仍未merge，RC3-05执行不开始。

`raw/`仅为manifest明确allowlist的逐字节原件，SHA/size/来源逐项可查。报告内绝对路径属于历史执行身份，不代表clone内包含那些目录。SDK脚本是当时固定环境的原探针源码，含历史绝对路径；不是新执行、便携安装器或客户数据。只索引的全量清单/identity/XML不表示整目录已交付。未复制Store、registry、runtimeauth/key/HMAC、venv、客户原料、原始wheel或会话；没有脱敏文件冒充原件，原诊断未删除。

原人类Owner/受众/计时/目标桌面/professional签署继续延期 **NOT_RUN**；37AC/13CQ状态、Owner与signers不变。RC3-03单p04 native仍只代表其原有限范围。05 E1/E2/E3效果与controller执行均 **NOT_RUN**，未知token/费用不抹为0。
