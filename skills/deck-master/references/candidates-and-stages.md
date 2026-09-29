# 候选与阶段

适用于已有 `workbench.v3` 项目。没有旧项目原地迁移；本次变更会把最低 writer 提升到 `candidates.v1`。

## 试作

从当前 snapshot 取得 project_id、revision_id、Page/产物引用。按 `change_intent.v1` 构造正常 changes 输入，并加入 `mode: "trial"`，目标 `stage: "blueprint"`（original_image）或 `"reconstruct"/"repair"`（svg/ppt）。每页一次动作；SVG 必须已有原图，Page 内容不支持试作候选。

`references` 可携带 `{page_id, revision_id, artifact_ref, role}`，其中 artifact_ref 必须是该已提交版本的原图。原图之后改变不会替换这一固定文件。generation_input 的 prompt 和 references 由计划冻结，不能在 requests freeze 时更换或遗漏。当前原生附件采集只证明 `role=reference`；其它角色不能被推定为已匹配。

先 `changes plan --input …` 查看写入范围与调用上限，再 `changes commit --plan-id … --base-revision … --operation-id <UUIDv4>`。实际读取 handoff 和 task status 的返回，使用真实 task_id；沿用 start/freeze/begin/settle/accept，声明工作单全部能力，trial 额外要求 candidate_result。已发生调用仍记 consumed，即使候选校验失败。`candidate_ready` 返回实际 candidate_ids，当前 Page/原图/SVG/预览/整稿槽不改变；任务与候选管理 revision 会正常前进。

## 比较与采用

`candidates list --project … [--page-id …] [--revision …]` 与 `candidates show --candidate-id …` 都读已提交对象。show 返回原 request、attempt、result、固定生成依据、原采用目标及当前适用性。原始 prompt 不能用最新任务 prompt 替代。

用户选定后，把真实 ID 写入选择 JSON：

```json
{"schema_version":"candidate_selection.v1","project_id":"实际项目ID","base_revision":"当前版本","candidate_ids":["实际候选ID"]}
```

执行 `candidates plan --input selection.json`，保存回包中的完整 `plan` 为 adoption.json；执行 `candidates adopt --input adoption.json --base-revision … --operation-id <新UUIDv4>`。不要传整个带 plan_ref 的外壳。单页就是长度一集合；批量先全量预检，一次切换指针。一个 Page 一次只选一个候选。

生成依据变化、采用目标变化、全项目 CAS 分开报告。无关页或管理 revision 前进只需新计划与新 operation，不重生图；真正依据变化不允许直接采用。冲突整批零采用；重新选择子集必须明确新计划与新 ID。网络结果未知查询原 operations ID，不偷偷换 ID。原图采用只清除目标页 SVG/预览及整稿输出；SVG 采用保留 Page、原图、实际 prompt，清除目标预览与整稿输出。

## 整稿

候选采用、打开比较或已查看均不是质量 pass。SVG 采用后 `continue` 生成真实单页预览、派发逐页审图，所有页通过后沿用整稿编译与最终审阅。显式 `stages assemble --project … --base-revision … --operation-id …` 使用同一 pipeline 并检查前置；不会生成独立单页 PPT。编译中版本改变时不采用输出；相同操作重放不会重新编译。`build` 在 workbench.v3 中同样不能绕过逐页审图。

HTTP 读取 `/api/candidates`、`/api/candidates/<id>`（可带 revision；list 可带 page_id），写入 `/api/candidates/plan`、`/api/candidates/adopt`、`/api/stages/assemble` 与 CLI 共用服务。浏览器写入仍要求同源 session；Host 使用 CLI。
