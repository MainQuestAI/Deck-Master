# Agent Execution Protocol

## 1. 开工前

1. 读取 `00-master-spec.md`。
2. 读取当前 Task Spec。
3. 读取依赖 Task 的 implementation evidence。
4. 核验 main SHA 和工作区干净状态。
5. 创建独立分支。

## 2. 开发约束

- 只修改允许路径；超出先写 deviation。
- 不以文档声明替代 Runtime 行为。
- 新 JSON 必须带 schema_version。
- Mutation 使用原子写、锁和 typed event。
- 不删除旧命令和 `ppt-*` wrapper。
- 不把 fixture / legacy inference 宣称为 production completion。
- 不提交客户原文、绝对路径、token 或本机私密配置。

## 3. 每个 Task 的提交要求

- 单 Task 至少一个独立 commit。
- Commit message 包含 Task ID。
- 测试失败必须如实记录。
- Schema 变化必须附兼容说明。

## 4. 完成报告

```text
Task:
Branch / SHA:
Modified files:
Contract changes:
Migration impact:
Tests executed:
Tests passed / failed:
Known limitations:
Spec deviations:
Review focus:
```

## 5. 禁止

- 未完成依赖就并行实现下游。
- 手工编辑 workflow_state 伪造完成。
- 在测试里跳过 Approval 以获得绿色结果。
- 用只检查文件存在的测试替代语义验证。
- 把 final export Approval 设为 optional。
