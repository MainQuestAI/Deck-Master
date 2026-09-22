# Compatibility, Migration & Release

## 1. Legacy Run Bootstrap

### 1.1 原则

- 不重写原 Artifact。
- 不伪造历史 Approval。
- 根据现有 Artifact 推断最高可证明 Stage。
- 推断状态标记 `legacy_inferred=true`。
- 在下一个高影响 Transition 或 client export 前要求确认。

### 1.2 输出

```text
workflow/bootstrap_report.json
workflow/workflow_state.json
```

Report 记录：

- discovered artifacts；
- inferred completed stages；
- missing contracts；
- approvals not provable；
- stale risks；
- required next action。

## 2. `ppt-*` Compatibility

| 旧入口 | 新公开 Stage | 规则 |
|---|---|---|
| `ppt-library` | `deck-sourcing` | selection 必须进入 Sourcing Plan / Handoff |
| `ppt-deck-pro-max` | `deck-producer` | result 必须引用 Page Package 或可归一化 |
| `ppt-master` | `deck-builder` | build result 必须进入 Builder Handoff |
| `ppt-quality-gate` | `deck-quality` | findings 必须进入 Quality Bundle |

旧入口在 v1.x 不删除。兼容 Skill 文档必须说明 public Stage 和 handback 规则。

## 3. 外部完整 Skill Package / Ability-style Compatibility

不得只按目录名称判断是否采用外部完整 Skill。定义通用 external package manifest：

```text
skill name
package version
contract versions
operations
entry command
smoke command
handoff contracts
source repository / SHA
production_capable
```

规则：

- 已安装的完整 real directory 不被覆盖。
- Symlink 到外部完整包同样允许。
- 只有 manifest + smoke + contract compatibility 通过，才可标记 production capable。
- Adapter-only 包不得冒充完整能力。
- 外部包的输出仍必须回写 Deck Master Run。

## 4. Manifest Migration

`skills/manifest.json` 升级到 1.1.0：

- 每个 public production skill 增加 `stage_id`；
- 引用 `stage_contract_version`；
- 增加 `transition_role`；
- compat skill 增加 `public_stage`；
- Installer / Router 从 Manifest 加载。

`skills/stage-contracts.json` 随 Release Tree 发布并写入 capability lock。

## 5. Version Governance

A0 必须统一：

- suite version；
- runtime version；
- skill conformance version；
- contract version；
- release notes version。

不得继续出现 Skill Suite 1.0.0、runtime 0.9.x、release docs 另一版本但无映射说明的情况。

## 6. Release Tree

必须新增：

```text
skills/stage-contracts.json
contracts/workflow/
workflow-migrations/
```

Release verification 检查：

- Manifest / Stage Contract 引用完整；
- Skill docs frontmatter 与 Manifest 一致；
- Schema hash lock；
- external package compatibility metadata；
- Workflow CLI smoke；
- legacy bootstrap smoke。

## 7. Deprecation

- 本轮不删除命令。
- 旧顶层命令只增加 machine-readable `canonical_command`。
- v1.2 前不把 deprecation warning 放进用户主文案。
- 删除任何别名前必须有使用证据和迁移说明。
