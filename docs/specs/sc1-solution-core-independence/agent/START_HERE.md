> **历史规格适用范围更新（SC-1.1 superseded）**：下文保留 SC-1 历史正文。默认外部 PPT Master 后端及标准／高密度双引擎要求，已由 [SC-1.1 正式替换裁决](../../sc1.1-native-deck-core/specs/00-decisions-and-supersession.md#02-正式替换旧裁决)替换为默认内置 `deck_native`，旧运行按明确兼容／迁移规则处理；并非废弃整份 SC-1。研究、公共内容、真实编译／渲染／回读、质量、数据保护与当前批准等未冲突要求继续有效。逐项工程范围见 [SC-1 验收替换映射](../../sc1.1-native-deck-core/acceptance/SC1_SUPERSESSION_MAP.json)；映射不代表验收通过。

# 给 Codex 的开工说明

你正在执行 MainQuestAI/Deck-Master 的 SC-1 迭代。阅读本包 README、00/01/02 规格与任务计划，遵守实际仓库 AGENTS。发生产品目标冲突时登记并按本包已批准方向提出最小修正，不能静默换 scope。

## 第一项工作

只先执行 Q0：核对源码 HEAD、origin/main 与 `4199a6a8cc17ac522e074fee95bc114d4e274849` 差异；保护未提交修改；定位本包涉及实现与契约；确认标准后端、Library、宿主、测试和真实样本的实际条件。

本包内所有新命令、Schema 和目录都是开发目标，不要在当前版本当作已存在接口执行。既有状态查询可以使用仓库当前 `--help` 确认的命令。

Q0 输出固定到本地/仓库适当文档位置：baseline-audit、reuse-map、schema-migration-map、capability-migration-matrix、deviation-log 与 acceptance tracking。路径由仓库惯例决定并写回本包实现映射。

## 随后的执行方式

按建议八个 PR 顺序推进，每轮只实现明确任务；验证后交付 PR 供评审。实现过程中发现内部文件名/参数不匹配可做适配并更新 Spec，不能自行取消真实标准 build、公共内容内核、无历史库生产、语义审查或真实 UAT。

不新增 Provider、不另起 Agent Runtime、不新增公开 Skill、不重做全套 UI。复用既有状态/契约/批准，提取高密度内容逻辑而非复制。

不要向用户重复索取材料中已有答案。真实缺工具、未授权范围、关键业务取舍或最终版本批准才需要用户决定。普通实现难点先分析并给出可行方案，不把整个任务退回用户。

## 每次交付模板

```text
任务：
源码基线/分支/HEAD：
实际执行 Spec 与偏差：
新增/修改文件：
实现和复用点：
执行的测试命令、结果与日志：
真实工具验证与 Fixture 验证的区别：
已通过 acceptance IDs：
未执行/失败 IDs 与影响：
数据/安装迁移和回滚：
需要用户裁决的事项（没有则写无）：
下一项可执行任务：
```

不得把计划测试写成已通过，不得把生成的示例数据写成真实客户 UAT。
