# 接口与资源

运行时合同唯一源为 `src/deck_master/resources/contracts/`；本目录 contracts 是可验证镜像。

| 入口 | 行为 |
|---|---|
| `deck-master styles references import/list/show` | 导入、列出、读取独立截图参考 |
| `deck-master styles analyze` | 创建零生图分析任务 |
| `/api/styles/references`、`/api/styles/references/import`、`/api/styles/references/{id}` | 同源读取和受限二进制导入 |
| `/api/styles/analyze` | 创建固定输入分析任务 |
| `/api/tasks/{id}`、既有 task start/accept/cancel | 复用任务状态、执行和结果机制 |
| 既有 styles propose/confirm/plan | v1/v2 按版本校验；确认和试作不自动采用 |
| 既有 changes commit、candidates plan/adopt | 分发、候选与原子采用 |
| 既有 history | 固定 revision、page/layer、limit/cursor、related 过滤 |

新增合同：`style-reference.v1`、`visual-style-spec.v1`、`style-input.v2`、`style-proposal.v2`、`style-recipe.v2`。Task 增加 `style_analyze`、`analysis_request_ref`；v2 图像试作增加 `stage_request.target_reference_ref`。Document 增加 `style_references`、独立 `committed_at`，写入边界为 `workbench-quality.v1`。

公共 Skill 的 `references/visual-reference.md` 与核心一并打包，任务方法按实际动作派发。参考路径是工作单输入，不能要求用户操作 XML 或手工维护对象摘要。
