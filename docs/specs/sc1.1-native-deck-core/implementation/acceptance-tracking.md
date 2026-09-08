# SC-1.1 验收追踪

当前总状态：`in_progress`。最终候选 SHA 的产品验收尚未集中执行，所有产品 case 起始为 `not_run`。旧文中的“工程通过”仅表示历史局部测试信息，缺少同一候选 SHA、真实命令、环境和证据哈希时，不转录成产品 case 的 passed。

## 数据源与缺口

- SC1.1 `acceptance/cases.json`：64 项，62 项 L1/L2、2 项 L3。
- `acceptance/SC1_SUPERSESSION_MAP.json`：88 项映射。映射状态不等于验收结果，replace/clarify 也不自动通过。
- 原 SC1 当前 `acceptance/cases.json`：91 项，额外 A-13、I-08、Q-13 未列入旧映射。工具保守纳入全部 85 项 L1/L2；6 项 L3 单列。
- [完整待验收清单](engineering-gap-inventory.md)：147 项必需工程记录，以及 8 项效果记录。这里的缺口指缺少当前候选证据，不断言代码未实现。

## 实际记录工具

沿用仓库 `scripts/uat/` 约定，入口为 `scripts/uat/sc1_1_engineering_matrix.py`。工具只记录已执行事实，不代执行传入命令。

```bash
python3 scripts/uat/sc1_1_engineering_matrix.py init --candidate-sha FULL_COMMIT_SHA --output /tmp/sc1-1-candidate-matrix.json
python3 scripts/uat/sc1_1_engineering_matrix.py record --matrix /tmp/sc1-1-candidate-matrix.json --case SC1.1:CMP-01 --status passed --commit FULL_COMMIT_SHA --command '实际命令或工具调用' --result '实际观察结论' --tier L2 --environment-json /tmp/environment.json --evidence /tmp/actual-evidence.json
python3 scripts/uat/sc1_1_engineering_matrix.py summary --matrix /tmp/sc1-1-candidate-matrix.json
```

每条记录必须包含实际源码 SHA、命令/工具、观察结果、环境、证据级别和真实文件哈希。允许 passed/blocked/failed；未执行保留 not_run。证据文件消失或改变使其通过记录失效；不同候选 SHA 必须新建矩阵。工具拒绝将 `validate_spec` 等规格自检结果登记成产品通过。L1 不可冒充 L2。一个新 case 通过不会自动令映射的旧 case 通过。UAT-02/03/04 的用户复核必须有实际用户确认材料，才可使用 `--actor user` 登记；Agent 不可自行代填该身份。缺用户确认时汇总仍为 in_progress。

真实工具记录必须说明实际调用和输出，单元测试中的 stub、合成输入或模拟进程只证明对应机制。环境可用性应现场探测，不继续采用旧记录“当前宿主没有 ImageGen”的结论。

## 本轮准备物

- `tests/test_sc1_1_migration_apply.py`：迁移机制反例与事务测试；其中编译 stub 明确不计真实迁移验收。
- `tests/test_sc1_1_engineering_matrix.py`：矩阵防误报测试；不计任何产品 case 通过。
- `examples/sc1_1_uat/raw_materials.json`：公开合成零售资料、10 页目标、研究缺口和未知客户事实，无逐页稿。真实内容规划、研究、ImageGen、重建和桌面编辑待执行并登记。

只有同一候选的全部必需工程证据通过，且用户完成视觉复核和最终批准，才可标记 `engineering_complete / outcome_pending`。当前不能标记完成或 accepted。
