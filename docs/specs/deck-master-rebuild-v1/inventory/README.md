# 文件级施工台账

B0：`2a866cf138f6359f853db35e0a926ad79391b691`。本清单沿用v1.0固定Git tree，并有用户转交Codex对177项scripts/58项contracts的路径一致性核验；本轮未重新读取远端。路径存在不等于逐行正确性或死代码分析。

- old-files.csv/json：**177** 个现有 scripts 文件逐个给出处置、提取目标、时间与测试。
- new-files.csv/json：**75** 个拟新建目标（其中35个为核心代码/资源文件，其余为构建、方法、测试与文档），列出职责/API/工作包/拟测试。
- old-contracts.csv：**58** 个旧正式合同的归档与读取边界。
- old-tests.csv：**122** 个旧顶层test文件的行为迁移分类。fixture与历史证据由path-rules补充，不能自动删。
- skills.csv：**19** 个Skill主入口处置；附属资源遵循02及12章。
- root-and-config.csv/json：**42** 个配置、活动文档和入口动作。
- path-rules.json：其他Git跟踪文件的穷尽分类规则；未知新路径标REVIEW，不授权删除。

CSV是施工清单，不是待执行的rm列表。`EXTRACT_THEN_DELETE`表示先在新核心实现并验证行为、切换消费者，再删除旧源文件；不是复制后立即删。所有删除只针对仓库跟踪文件；客户资料、run、安装中的用户文件、第三方Skill都不在删除范围。

运行 `tools/materialize_inventory.py` 可在真实本地仓库重新展开所有跟踪文件。它只读取Git并向指定目录写CSV/JSON；不checkout、不reset、不删除。输出需要 Codex 核验。

## v1.1施工字段

task-list新增start_after与early_delivery，仅为施工顺序说明，不新增产品运行对象。depends_on是整项任务的完成依赖。T20显式依赖T13；T25祖先应包含其余24任务。T01建立清单使用AC-L07，T24实际引用归零使用AC-L05。90条验收不等于90份Deck。
