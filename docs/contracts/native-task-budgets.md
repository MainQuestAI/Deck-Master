# Native 页任务额度授权

当某页某类动作预算已耗尽，使用精确任务上限追加已获授权的尝试次数。入口保留原运行、已消耗次数、失败明细、已派发 action 和提交收据，不修改其他页或动作类别。上限是目标整数，不是每次调用都累加的增量。

```bash
deck-master build budget status --run-dir <run> \
  --task-id native_reconstruct_P006 --task-id native_reconstruct_P008

deck-master build budget set --run-dir <run> \
  --limit native_reconstruct_P006=4 --limit native_reconstruct_P008=4 \
  --expected-revision <status-returned-revision> \
  --reason '<existing user authorization and reason>' \
  --actor-id '<local caller declaration>' --actor-role user
```

上述是命令形式，任务名和额度仅为示例，不授予任何运行额度。`actor` 是本地调用者声明，`actor_authenticated=false`；接口不伪造远程认证，也不授予内容或最终文件批准。执行者必须已有对应用户授权，不能把 Agent 推断写成用户决定。

Python 接口：

```python
read_native_task_budgets(run_dir, *, task_ids: list[str]) -> dict
set_native_task_budgets(
    run_dir, *, limits: dict[str, int], expected_revision: str,
    reason: str, actor: dict[str, str],
) -> dict
```

`limits` 非空，每个键必须对应本运行实际 Runtime 派发过、仍归属当前批准 Page Package 的精确 task。允许类别为 `imagegen / reconstruct / svg`。上限严格为 1 至 20 的整数，不接受布尔、浮点、字符串、降低现有额度或路径逃逸。原生路由必须已持久化。状态同时给出累计 `used`、当前配置上限 `max_actions`、以及旧已派发动作仍受约束的 `issued_max_actions`，避免混淆下一次派发额度与在途动作额度。

权威 `request.json` 快照保存：

```json
{
  "native_task_budget_limits": {
    "native_reconstruct_P006": 4,
    "native_reconstruct_P008": 4
  },
  "native_task_budget_authorizations": []
}
```

示例省略了实际授权记录；正式 setter 必须追加经过 [native-task-budget-authorization.v1.schema.json](native-task-budget-authorization.v1.schema.json) 校验的记录，其中有授权 ID、源修订、原默认额度、原任务额度、目标上限、当时累计消耗、原因、actor 声明及对应提交 action。不得手工把此示例写进运行以绕过授权记录。

修改通过既有 request 修订事务完成。提交写锁内复核源修订、request、当前派发 action 和累计消耗；并发修改或新的失败记录会拒绝旧请求，调用方重新读取再决定重试。两页可在同一 `limits` 请求里一次提交，避免逐页提交造成部分授权。成功后的同源修订、同目标、同 actor、同原因重放返回原授权及收据；不会再次增加上限或追加记录。同一当前修订上的相同上限返回 `unchanged`。旧修订上的不同授权返回 stale，不覆盖并发结果。

预算写入不重派任务，也不改写 issued 文件。在途 action 仍使用派发时的预算和输入指纹；普通续跑保留它的 action ID 与上限。已失败、已完成、已取消的动作，或正常内容变更后发生的新派发，才使用配置覆盖。比如已耗尽的 3/3 提高至 4 后只有 1 次新尝试，旧 action 仍受 3 次上限约束。失败、取消与预算上限继续按现有 ledger 规则计算。

先完成已授权的内容变更，再读取当前预算与源修订，提交目标上限，最后按正式 retry/next-step 继续。固定路径 request 仅作兼容投影；派发读取权威修订快照。提交点后的进程中断可以通过原授权重放恢复结果，投影恢复不丢额度或审计记录。更新 request 会产生新修订，旧成品及最终批准不会因此自动更新。
