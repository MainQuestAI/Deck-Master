# 设计评审与证据索引

2026-09-26：已完成一轮 GStack AutoPlan，再执行四轮追加 Review。设计与开发包可以交付评审；正式功能、真实 Host 与安装发布未实施。不是将 AutoPlan 的四阶段重新计作四轮。

| 流程 | 实际输入与方法 | 结果与修订 |
|---|---|---|
| [AutoPlan](00-autoplan-summary.md) | 完整 CEO → Design → DX → ENG；原生与 Claude Code 独立声音，记录各自输入与模型回包 | 四阶段设计决定汇入 PLAN / UI / DX / ENGINEERING 和12包；19组实施要求均有归属 |
| [R1 产品流程](05-round1-product.md) | 独立产品走查及浏览器复现 | 6项修复：候选层级、失败/取消、保留/再试、固定参考、版本文案、重复请求；[R1冻结证据](r1-frozen-evidence/) |
| [R2 设计与操作](06-round2-design.md) | GStack design-review；独立原生浏览器+Claude Code源码审阅，双方结果分开保留 | 9组修复；双视口专项与旧回归通过。材料输入、焦点/矩阵、首次生成、比较尺寸、层级/字号/状态等已闭环 |
| [R3 规格与分包](07-round3-contracts.md) | 独立检查旧能力继承、契约、工程边界与owner | 5项修订并独立复核：旧要求细化、统一压力、trial/auto关系、create复用、安装与发布拆开 |
| [R4 最终回归](08-round4-final.md) | 新独立浏览器context；1280×800与1440×900，主线及恢复/结构/历史 | 每视口40项通过，14张新截图、亲自阅图6张；无新增实质缺陷，源码前后hash一致 |
| [OpenDesign同步](09-opendesign-sync.json) | MCP写入6文件、get_artifact逐字回读、独立预览核验 | 具体状态与资源hash按记录；不冒充由生成run制作 |

## 证据限制

AutoPlan CEO外部CLI曾返回文本，但缺必需Recommendation结束标记，按流程记为unavailable；没有用其他阶段补算。Design / DX / ENG外部结果完成，原始modelUsage保留。R2自动detector未安装/未运行，mode=none，不能写成自动扫描零问题。主观设计评分不等同陌生用户测试、可访问性认证或性能结果。

R1输入源文件未完整冻结，仅有输入hash、定位和修订前截图；修订后源文件可从ba4aefe恢复，31个当时证据文件已独立归档。后来重复测试生成的同名文件只是当前回归证据，不覆盖其历史含义。R2/R3/R4另有各自输入清单。

浏览器证据全部来自合成数据，批量状态样板中的候选比较为明确标注的文字说明；执行按钮是模拟。本轮没有真实模型/Host、网络故障注入、真实导出、安装候选、300页压力或用户盲测。正式87条AC仍全为未实施/未验证；D04与D06明确部分原型覆盖，见[验收矩阵](../ACCEPTANCE.md)。

## 复核与来源

- [R2原生](06-round2-design-native.md) / [外部](06-round2-outside.md) / [原始CLI结果](06-round2-outside-result.json) / [输入](06-round2-input.json)
- [R3输入](07-round3-input.json) / [R4输入与结果](round4-evidence/)
- [主原型与状态专项](../prototype/validation/) / [离线启动与走查](../WALKTHROUGH.md)
- [87条一致性检查](delivery-check.json) / [交付文件SHA-256](final-manifest.json)

运行 `python3 reviews/validate_delivery.py`（在本方案目录中）重新核对条目、owner、正文和链接并生成manifest。该检查只证明设计文档一致性，不运行生产行为验收。
