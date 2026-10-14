# RC3-01 / T00 合成锚点校准证据

本目录按批准清单原字节复制 **38 文件、912285 bytes**，另加本 README 与路径映射 manifest。原初判/复评/报告原字节及记录路径均保留；[路径映射与全部 hash](path-mapping-manifest.json) 将原工作路径映射到本目录的相对路径。

- [校准报告](report/rc3-01-anchor-calibration.md) · [机器摘要与实际替换全文/来源引文](report/rc3-01-anchor-calibration.json)
- 初判：[A 匿名完整输入](evidence/judge-a/packet.json) · [A 冻结初判](evidence/judge-a/output/initial-judgments.json) · [A 读取日志](evidence/judge-a/output/read-log.json)；[B 匿名完整输入](evidence/judge-b/packet.json) · [B 冻结初判](evidence/judge-b/output/initial-judgments.json) · [B 读取日志](evidence/judge-b/output/read-log.json)
- [初判冻结/实际 native 观察](evidence/controller/initial-freeze-observation.json) · [匿名映射（初判冻结后解盲）](evidence/controller/mapping-and-seeds.json) · [原来源读取范围](evidence/controller/read-ranges.json)
- [Root 来源限定裁决](evidence/repair/controller/adjudication.json) · [历史 Q3-2 原判原字节](evidence/repair/controller/historical-q3-2.raw.md) · [修复冻结](evidence/repair/controller/frozen-repairs.json)
- 复评：[A 当前完整修复候选](evidence/repair/judge-a/packet.json) · [A 独立复评](evidence/repair/judge-a/output/repair-judgments.json) · [A 读取日志](evidence/repair/judge-a/output/read-log.json)；[B 当前完整修复候选](evidence/repair/judge-b/packet.json) · [B 独立复评](evidence/repair/judge-b/output/repair-judgments.json) · [B 读取日志](evidence/repair/judge-b/output/read-log.json)
- [复评冻结及实际完成观察限制](evidence/repair/controller/root-repair-freeze-observation.json)

16 个原匿名候选每人独立初判：12 个受控负例和 4 个正对照。等级一致 15/16，用途状态一致 16/16；唯一等级分歧 AN-Q3-2 原 A 为 F0/fail、原 B 为 F2/fail，root 本次来源限定裁决 F2/fail，原初判和历史 F1 均不改写。Q2-5 原两人 F2/needs_review，经条件未来文本修复。12 项实际修复后，两位原评价者各自完整复评，24 项 none/pass；4 正对照的 pass 只来自原初判，没有伪称再次复评。

A 复评实际收到 canonical FINAL，但 roster 淘汰前未观察到 list completed；B 实际收到 canonical FINAL 并观察到 list completed。平台事件/签名与未暴露配置保持 unknown。复评允许记得自己的初判，未读取他评/root裁决，不能与 fresh 初判混为同阶段。

| 具体实质修订 | 相对 diff |
|---|---|
| AN-Q1-1 | [AN-Q1-1.diff](diffs/AN-Q1-1.diff) |
| AN-Q1-2 | [AN-Q1-2.diff](diffs/AN-Q1-2.diff) |
| AN-Q1-3 | [AN-Q1-3.diff](diffs/AN-Q1-3.diff) |
| AN-Q1-4 | [AN-Q1-4.diff](diffs/AN-Q1-4.diff) |
| AN-Q2-1 | [AN-Q2-1.diff](diffs/AN-Q2-1.diff) |
| AN-Q2-2 | [AN-Q2-2.diff](diffs/AN-Q2-2.diff) |
| AN-Q2-3 | [AN-Q2-3.diff](diffs/AN-Q2-3.diff) |
| AN-Q2-4 | [AN-Q2-4.diff](diffs/AN-Q2-4.diff) |
| AN-Q2-5 | [AN-Q2-5.diff](diffs/AN-Q2-5.diff) |
| AN-Q3-1 | [AN-Q3-1.diff](diffs/AN-Q3-1.diff) |
| AN-Q3-2 | [AN-Q3-2.diff](diffs/AN-Q3-2.diff) |
| AN-Q3-3 | [AN-Q3-3.diff](diffs/AN-Q3-3.diff) |

Diff 比较冻结原错误原文/变体描述与具体 replacement 全文/对象，不是产品 Git diff、真实 Writer 首稿或已渲染 PPTX。完整最终候选在各复评 packet 内，完整实际替换/来源行/原错误 raw 在机器摘要内，不需要访问记录中的外部工作路径。

该合成校准链路 PASS 不推导 RC3-01 整卡 ready、RC3 总体 ready、真实 Native Writer 生成效果、E1、Owner/听众/人类/专业验收或实际渲染/文件/计时。目录没有创建 run、.decks、.deckmaster 或客户项目对象。冻结历史文件内的绝对路径是来源记录，不能把它们当作可执行命令或项目状态。

原字节校验全部通过。对新增文件逐项执行 git no-index whitespace 检查时，历史原段 `historical-q3-2.raw.md` 的原末尾空行产生唯一 `new blank line at EOF` 提示；依原字节保留要求不裁剪该历史证据。其余新增文件没有 whitespace 提示，tracked/staged 文件未改。
