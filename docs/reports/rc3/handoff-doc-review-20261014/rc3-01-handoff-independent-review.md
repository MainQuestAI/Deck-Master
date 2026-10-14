# RC3-01 最终文档与证据独立审查：第一轮

结论：**REQUEST_CHANGES**。唯一阻塞项是六条 ledger 输入记录将 Git commit SHA-1 误标为 SHA-256；当前内容工程交接、原件完整性和限定披露没有发现其他阻塞项。修正后需对文档 delta 复审，本轮报告保留不改。

审查者：`/root/rc3_01_handoff_review`，未参与方法、S01 产品、实验、导入或受审文档实现。固定产品 HEAD `cc6150da513ce38060b0a8ad045ea5159a56cae6`；审查 dirty `RC3-01-METHODS.md` / `evidence-ledger.json`，new `RC3-01-HANDOFF.md` 和两个证据目录。产品及153份原件只读，未运行 broad tests、未 commit/merge、未写真实运行项目。

## F-DOC-01：ledger 的 commit 哈希算法标签错误

位置：`docs/reports/rc3/evidence-ledger.json` 的 AC-B02、AC-M01、AC-M02、AC-M03、AC-M04、AC-M05，`input_hashes` 中 `ref="B supplemental source"`、`sha256="cc6150da513ce38060b0a8ad045ea5159a56cae6"`；第一处当前第60行，其余第300、358、416、474、532行。

实际 Git commit identity 是40位；`sha256` 表示64位字节摘要。原 ledger template 仅有空 input/output hash 数组，没有允许算法名称误标的约定。原 RC3 ACCEPTANCE §2 分别要求准确候选 SHA/tree 和输入输出 hash。读者或后续验证器按字段直接检查 SHA-256 会得到错误身份，不能依靠 HANDOFF 表格弥补机器台账错误。

最小修复：将六个输入项改为可实际核验的 B installation manifest 路径及其64位 SHA-256 `475e9c6355cde08f157446061b78782dff4135718f53da710a30f55707a12d63`；40位源码 commit 身份继续以 HANDOFF 的正确对象标签保存。也可使用明确 `git_commit_sha` 字段，不能保留错误 `sha256`。不改其余 AC/CQ、global 身份、原件或 Runtime schema。

## 已实际核验通过的范围

- 公开 native manifest 的115原件总计6,479,571 bytes；anchor manifest 的38原件总计912,285 bytes。逐个读取实际 source 和公开 destination：bytes、长度及 SHA-256 全一致，无缺件、额外非导航文件。Native manifest SHA `dd3c276256a8eed0059f1f572643805043f3689c5b4eb7df6ff767432c89a0aa`；anchor mapping SHA `f0be87351a3c8a38823b9a25820e5deea0105a3b2424a0c3e5d23b865dcdecec`。两个目录共157文件（153原件+4导航）；无运行对象库、虚拟环境、wheel、缓存、私钥/显式凭证模式命中。历史末尾空行警告已准确披露，不规范化原字节。
- METHODS/HANDOFF及两README合计50个本地导航链接全部可解析。完整读取受审叙述、原RC3-01开发卡/工程出口、RC3验收编排和原M01–M05要求；工程出口与后续专业AC关闭分开的解释符合原规划。
- 四份fresh SDK finish均实际 accepted，raw及Root completed observer hashes匹配；每份都保留真实 canonical FINAL/list_agents completed，host_attested身份及未知模型配置。全部实际作者排除、JSON context、改结果和foreign Task负控均拒绝。没有模型变人类/平台签名声明。
- Q1-B / Q2-A / Q2-B 当前四unit及gate pass，三个owner快照hash与HANDOFF一致；实际中央旧blocker closure检查保存。Q1-A当前page_copy fail，新增 exercise-boundary F2开放、gate missing page_copy、无owner快照、writer_feedback=false / extra_repair_round=false。B合格工程稿没有抵消A失败，F3 advisory没有被改称已修。
- 原Q1正确cue、旧SDK拒收、controller机械改kind、正式接纳稿F2、额外turns及作者跨臂暴露分别保留。Frozen driver `f70a5d63…`、protocol `4fa26f30…` 与新adapter `33db0444…`原件hash一致；所有补充finish明确不是原冻结E1。未把恢复cue类别当原native写作提升，未声称盲效果/陌生迁移/完整十二会话已完成。
- A/B两个实际source HEAD/tree及wheel hash、manifest hash、transition hash与HANDOFF一致，源码工作树干净。实际逐文件比较231个src package文件加13/14个Skill文件，分别244/245个 source/wheel/install字节全部一致；四个共通core文件A/B相同，新旧各臂Skill原字节相同，activation=none、actual_home_modified=false。
- S01三轮原独立报告保留两轮REQUEST_CHANGES、最终cc6150d PASS；独立162 targeted的真实日志陈述与最终报告一致。root broad日志实际1742 pass / 455 deselected / 2 failed / 3 errors；失败均安装DNS，离线复跑实际5 pass /17.41s。文档只陈述合计1747覆盖，不冒称单次1747全绿。Adapter第三轮PASS绑定实际33db0444…、9 helper范围明确。
- 十二anchor独立初判、原分歧和source-bound裁决、12实质修复/24复评、4原正对照及A未观察历史roster completed的限制如实登记。B03/CQ-11仅合成校准PASS，未冒充SDK/human/E1 PASS。
- ledger与固定HEAD机器逐项比较：37AC长度不变、仅本卡7条变化；13CQ长度不变、仅本卡3条变化。其余30AC/10CQ及所有global字段完全相同；release_conclusion=NOT_RUN，AC signed_by全部原null保持。缺六组逐组效果、Q3/混用版本/五分钟取舍、E1 C/公平复跑、人类Owner/受众/完整计时/桌面等仍明确BLOCKED/NOT_RUN。当前cc/final-doc CI保持pending，未借旧1fb3七项CI。

## 复审边界

修复F-DOC-01后仅重验六条输入、完整ledger变更边界、受影响文档/hash/link及153原件不变即可；不需重跑已合格的162/1747检查。最终文档commit的七项CI仍由root推送后核验；本审查PASS不替代该CI或RC3完整交付结论。
