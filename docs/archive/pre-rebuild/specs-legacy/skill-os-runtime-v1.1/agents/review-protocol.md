# Review Protocol

## 1. 评审顺序

1. Spec / deviation。
2. Contract 真源。
3. Runtime 行为。
4. Migration / compatibility。
5. Test quality。
6. UI / docs。
7. 成熟度提升。

## 2. P0 判定

- Stage 可无 Handoff 进入下游。
- 必需 Approval 可绕过。
- Final export 可预授权或自动执行。
- Builder 读取 internal-only。
- Workflow State 可被直接编辑而成为事实。
- Legacy migration 伪造 Approval。
- external full package 被覆盖。
- CI / RC 用 metadata 或文件存在代替行为证据。

## 3. 评审输出

```text
结论：Approve / Request Changes
P0：
P1：
P2：
Spec coverage：
Compatibility：
Tests：
Maturity impact：
Required fixes before merge：
```

## 4. 完成度口径

不得把以下内容算作已完成：

- 只有 SKILL.md 文案。
- 只有 CLI skeleton。
- 只有 schema 文件，无 Runtime validation。
- 只有 UI mock，没有 API truth。
- 只有 happy-path test。
- 只有 fixture，没有 production policy negative test。
