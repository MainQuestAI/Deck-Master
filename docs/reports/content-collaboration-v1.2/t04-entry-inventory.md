# T04 入口清单与资格覆盖（AC-R04）

本文件与 `src/deck_master/eligibility_entries.py` 的清单一致；
`tests/rebuild/test_eligibility_entry_coverage.py` 枚举真实入口集合，
未分类的新入口直接使测试失败，因此不存在“先放行、以后再补”的旁路窗口。
清单本身（含每个旧命令名）保存在模块里；本报告把只做拒绝/映射的旧命令
合并成组，避免活动文档重复列出已退役命令名。

## 1. 统计

- 入口总数：**330**（已接 gate：112；登记豁免：218）
- service.py 公开用例：15
- operations.public 操作：45
- 协作控制面写路径：16
- CLI 子命令（含旧命令映射）：158
- HTTP / Studio 路由：96

其中旧命令拒绝/映射面 79 项，逐名清单见 `eligibility_entries.legacy_refusal_entries()`。

已消费的 action 集合：

- `allowance.allocate`
- `annotation.save`
- `asset.import`
- `authorization.grant`
- `authorization.revoke`
- `call.begin`
- `call.settle`
- `candidate.adopt`
- `candidate.select`
- `change.commit`
- `change.plan`
- `compile.ppt`
- `content.inputs_update`
- `content.operation`
- `continue_project`
- `create`
- `decision.record`
- `design.update`
- `dispatch.blueprint`
- `dispatch.compose`
- `dispatch.host_task`
- `export.delivery`
- `generation.dispatch`
- `handoff.delivery`
- `import_draft`
- `migration.apply`
- `migration.describe`
- `page.edit`
- `readiness.final`
- `render.preview`
- `request.pause`
- `request.resume`
- `request.start`
- `restore`
- `stage.assemble`
- `style.propose`
- `task.accept`
- `task.cancel`
- `task.start`

## 2. 豁免词表（只读/无害入口的显式理由）

- `read_model`：read-only projection/read model; no project control change
- `read_download`：reads an already-fixed immutable export object
- `read_plan`：immutable derived plan/preview; writes no Document, Task, allowance or call
- `read_analysis`：read-only analysis/plan output
- `ui_state`：personal UI journal / gallery / overview state; never writes project control or business objects
- `legacy_refusal`：legacy mapping/refusal surface: maps to a rebuilt command or refuses with guidance; writes nothing
- `internal`：internal write mechanics/helper used by classified entries; not an independently reachable business entry
- `staging`：stages a material upload for later confirmation; writes no Document/Task/allowance
- `install`：installation/registry/diagnostic surface; not project business state

## 3. 入口明细

### 3.1 service.py 公开用例

| 入口 | 必检 action | gate 落点 | 豁免理由 |
| --- | --- | --- | --- |
| `accept_result` | `task.accept` | service.accept_result → tasks.accept_result: call facts settle first (unchanged protocol, CONTRACTS §6.1 accept_result exception), then adoption consumes the gate | — |
| `continue_project` | `continue_project` | service.continue_project: consumes the decision and returns the card/gaps; every dispatch it makes goes through a gated helper | — |
| `create` | `create` | service.create: routing only; the compose task it opens passes the dispatch.compose gate inside open_compose_task | — |
| `import_asset` | `asset.import` | service.import_asset: guard before the design commit | — |
| `import_draft` | `import_draft` | service.import_draft: guard before _adopt_draft | — |
| `inputs_show` | — | - | read-only projection/read model; no project control change |
| `inputs_update` | `content.inputs_update` | service.inputs_update: guard inside the locked transaction before staging/commit; the reconciliation task is dispatched through open_compose_task's gate | — |
| `open_blueprint_task` | `dispatch.blueprint` | service.open_blueprint_task: guard before reserve_allowances and the dispatch commit | — |
| `open_compose_task` | `dispatch.compose` | service.open_compose_task: guard before new_task/commit | — |
| `open_host_task` | `dispatch.host_task` | service.open_host_task: guard before the dispatch commit | — |
| `task_cancel` | `task.cancel` | service.task_cancel: consumes the decision; cancellation stays available while paused (CONTRACTS §7.1) | — |
| `task_start` | `task.start` | service.task_start: guard before the claim commit | — |
| `task_status` | — | - | read-only projection/read model; no project control change |
| `task_summary` | — | - | read-only projection/read model; no project control change |
| `update_design` | `design.update` | service.update_design: guard before the design commit | — |

### 3.2 operations.public 操作

| 入口 | 必检 action | gate 落点 | 豁免理由 |
| --- | --- | --- | --- |
| `annotation_service.list_annotations` | — | - | read-only projection/read model; no project control change |
| `annotation_service.save` | `annotation.save` | annotation_service.save: guard before the annotation commit | — |
| `candidate_preview.file_bytes` | — | - | reads an already-fixed immutable export object |
| `candidate_preview.request` | `render.preview` | candidate_preview.request: local candidate rendering request | — |
| `candidate_preview.status` | — | - | read-only projection/read model; no project control change |
| `candidates.adopt` | `candidate.adopt` | candidates.adopt: guard before the adoption commit (adoption never consumes image-call credit) | — |
| `candidates.decide` | `candidate.select` | candidates.decide: guard before recording the decision | — |
| `candidates.listing` | — | - | read-only projection/read model; no project control change |
| `candidates.plan` | `change.plan` | candidates.plan: read-only candidate plan (immutable object); consumes the plan decision and reports it | — |
| `candidates.show` | — | - | read-only projection/read model; no project control change |
| `changes.commit` | `change.commit` | changes.commit: guard before dispatch/commit | — |
| `changes.handoff` | — | - | read-only projection/read model; no project control change |
| `changes.list_changes` | — | - | read-only projection/read model; no project control change |
| `changes.plan` | `change.plan` | changes.plan: read-only derived plan (immutable object) | — |
| `content_ops.commit` | `content.operation` | content_ops.commit: guard before the outline/content commit | — |
| `content_ops.inputs` | `content.inputs_update` | content_ops.inputs: recoverable inputs update; same gate as service.inputs_update | — |
| `content_ops.lineage` | — | - | read-only projection/read model; no project control change |
| `content_ops.plan` | `change.plan` | content_ops.plan: read-only plan (immutable object) | — |
| `content_ops.source` | — | - | read-only projection/read model; no project control change |
| `exports.create` | `export.delivery` | exports.create: purpose=delivery consumes the delivery gate; review/engineering stay report-only | — |
| `exports.describe` | — | - | read-only projection/read model; no project control change |
| `exports.download` | — | - | reads an already-fixed immutable export object |
| `exports.show` | — | - | reads an already-fixed immutable export object |
| `icons.catalog` | — | - | read-only projection/read model; no project control change |
| `icons.confirm` | `candidate.select` | icons.confirm: guard before recording the accepted design dimension | — |
| `icons.draft` | `style.propose` | icons.draft: guard before the recipe draft commit | — |
| `icons.inspect` | — | - | read-only analysis/plan output |
| `icons.listing` | — | - | read-only projection/read model; no project control change |
| `icons.plan` | `change.plan` | icons.plan: read-only design plan (immutable object) | — |
| `icons.preview` | `render.preview` | icons.preview: local rendering only; request scope applies | — |
| `icons.propose` | `style.propose` | icons.propose: guard before the design proposal commit | — |
| `operations.show` | — | - | read-only projection/read model; no project control change |
| `restoration.commit` | `restore` | restoration.commit: guard before the restore commit | — |
| `restoration.plan` | — | - | immutable derived plan/preview; writes no Document, Task, allowance or call |
| `source_uploads.receive` | — | - | stages a material upload for later confirmation; writes no Document/Task/allowance |
| `source_uploads.show` | — | - | read-only projection/read model; no project control change |
| `stages.assemble` | `stage.assemble` | stages.assemble: guard before the assembly commit | — |
| `styles.confirm` | `design.update` | styles.confirm: guard before the design commit | — |
| `styles.listing` | — | - | read-only projection/read model; no project control change |
| `styles.plan` | `change.plan` | styles.plan: read-only design plan (immutable object) | — |
| `styles.propose` | `style.propose` | styles.propose: guard before the proposal/recipe commit | — |
| `styles.show` | — | - | read-only projection/read model; no project control change |
| `visual_styles.analyze` | `dispatch.host_task` | visual_styles.analyze: dispatches a Host analysis task | — |
| `visual_styles.import_reference` | `asset.import` | visual_styles.import_reference: guard before the reference/asset commit | — |
| `visual_styles.listing` | — | - | read-only projection/read model; no project control change |

### 3.3 协作控制面写路径

| 入口 | 必检 action | gate 落点 | 豁免理由 |
| --- | --- | --- | --- |
| `collaboration.commit_collaboration_change` | — | - | internal write mechanics/helper used by classified entries; not an independently reachable business entry |
| `collaboration.describe` | — | - | read-only projection/read model; no project control change |
| `collaboration.grant` | `authorization.grant` | collaboration.grant: T02 write path owns scope/parent-chain correctness | — |
| `collaboration.pause_request` | `request.pause` | collaboration.pause_request: stop fact, always recordable | — |
| `collaboration.payload_digest` | — | - | internal write mechanics/helper used by classified entries; not an independently reachable business entry |
| `collaboration.record_decision` | `decision.record` | collaboration.record_decision: T02 write path owns evidence/delegation correctness | — |
| `collaboration.replay_or_conflict` | — | - | internal write mechanics/helper used by classified entries; not an independently reachable business entry |
| `collaboration.resolve_evidence` | — | - | internal write mechanics/helper used by classified entries; not an independently reachable business entry |
| `collaboration.resume_request` | `request.resume` | collaboration.resume_request: explicit resume; never widens scope (T02 re-derives from the same request) | — |
| `collaboration.revoke_authorization` | `authorization.revoke` | collaboration.revoke_authorization: withdrawal is a fact, never refused | — |
| `collaboration.start_request` | `request.start` | collaboration.start_request: T02 write path owns record correctness; T04 consumes the decision | — |
| `collaboration.write_digest` | — | - | internal write mechanics/helper used by classified entries; not an independently reachable business entry |
| `collaboration_migration.apply` | `migration.apply` | collaboration_migration.apply: single-transaction migration with plan digest + CAS | — |
| `collaboration_migration.describe` | `migration.describe` | collaboration_migration.describe: read-only migration plan | — |
| `collaboration_migration.migration_plan` | — | - | internal write mechanics/helper used by classified entries; not an independently reachable business entry |
| `collaboration_migration.migration_response` | — | - | internal write mechanics/helper used by classified entries; not an independently reachable business entry |

### 3.4 CLI 子命令（含旧命令映射）

| 入口 | 必检 action | gate 落点 | 豁免理由 |
| --- | --- | --- | --- |
| `annotations list` | — | - | read-only projection/read model; no project control change |
| `annotations save` | `annotation.save` | cli.annotations save → annotation_service.save | — |
| `attempts show` | — | - | read-only projection/read model; no project control change |
| `build` | `compile.ppt` | cli.build → pipeline.produce (local production) | — |
| `candidate-preview request` | `render.preview` | cli.candidate-preview request → candidate_preview.request | — |
| `candidate-preview status` | — | - | read-only projection/read model; no project control change |
| `candidates adopt` | `candidate.adopt` | cli.candidates adopt → candidates.adopt | — |
| `candidates decision` | `candidate.select` | cli.candidates decision → candidates.decide | — |
| `candidates list` | — | - | read-only projection/read model; no project control change |
| `candidates plan` | `change.plan` | cli.candidates plan → candidates.plan (immutable plan object) | — |
| `candidates show` | — | - | read-only projection/read model; no project control change |
| `changes commit` | `change.commit` | cli.changes commit → changes.commit | — |
| `changes handoff` | — | - | read-only projection/read model; no project control change |
| `changes list` | — | - | read-only projection/read model; no project control change |
| `changes plan` | `change.plan` | cli.changes plan → changes.plan (immutable plan object) | — |
| `content commit` | `content.operation` | cli.content commit → content_ops.commit | — |
| `content inputs` | `content.inputs_update` | cli.content inputs → content_ops.inputs | — |
| `content lineage` | — | - | read-only projection/read model; no project control change |
| `content plan` | `change.plan` | cli.content plan → content_ops.plan (immutable plan object) | — |
| `content source` | — | - | read-only projection/read model; no project control change |
| `continue` | `continue_project` | cli.continue → service.continue_project (decision card) | — |
| `create` | `create` | cli.create → service.create (routing gate) | — |
| `doctor` | — | - | installation/registry/diagnostic surface; not project business state |
| `edit` | `page.edit` | cli.edit → editing.edit_page | — |
| `export` | `export.delivery` | cli.export → exports.create (purpose gate) | — |
| `handoff-check` | `handoff.delivery` | cli.handoff-check → handoff.check_handoff | — |
| `history commit-restore` | `restore` | cli.history commit-restore → restoration.commit | — |
| `history list` | — | - | read-only projection/read model; no project control change |
| `history plan-restore` | — | - | immutable derived plan/preview; writes no Document, Task, allowance or call |
| `history restore` | `restore` | cli.history restore → editing.restore | — |
| `icons catalog` | — | - | read-only projection/read model; no project control change |
| `icons confirm` | `candidate.select` | cli.icons confirm → icons.confirm | — |
| `icons draft` | `style.propose` | cli.icons draft → icons.draft | — |
| `icons inspect` | — | - | read-only analysis/plan output |
| `icons list` | — | - | read-only projection/read model; no project control change |
| `icons plan` | `change.plan` | cli.icons plan → icons.plan (immutable plan object) | — |
| `icons propose` | `style.propose` | cli.icons propose → icons.propose | — |
| `import` | `asset.import` | cli.import → service.import_asset | — |
| `import-draft` | `import_draft` | cli.import-draft → service.import_draft | — |
| `inputs show` | — | - | read-only projection/read model; no project control change |
| `inputs update` | `content.inputs_update` | cli.inputs update → service.inputs_update | — |
| `install activate` | — | - | installation/registry/diagnostic surface; not project business state |
| `install candidate` | — | - | installation/registry/diagnostic surface; not project business state |
| `install rollback` | — | - | installation/registry/diagnostic surface; not project business state |
| `legacy-map` | — | - | read-only projection/read model; no project control change |
| `legacy:agent-doctor` | — | - | installation/registry/diagnostic surface; not project business state |
| `legacy:build prepare` | — | - | read-only projection/read model; no project control change |
| `legacy:build status` | — | - | read-only projection/read model; no project control change |
| `legacy:final-readiness` | `readiness.final` | cli._legacy_final_readiness: consumes the delivery report policy | — |
| `legacy:import-plan` | `import_draft` | cli._legacy_import_plan: full deck_page_package.v2 plans import as a draft | — |
| `legacy:next-step` | — | - | read-only projection/read model; no project control change |
| `legacy:product-capability-manifest` | — | - | read-only projection/read model; no project control change |
| `legacy:run-state` | — | - | read-only projection/read model; no project control change |
| `legacy:validate-product-capability-manifest` | — | - | read-only projection/read model; no project control change |
| `operations show` | — | - | read-only projection/read model; no project control change |
| `requests freeze` | `generation.dispatch` | cli.requests freeze → generation.freeze (bounded call input) | — |
| `requests show` | — | - | read-only projection/read model; no project control change |
| `stages assemble` | `stage.assemble` | cli.stages assemble → stages.assemble | — |
| `styles analyze` | `dispatch.host_task` | cli.styles analyze → visual_styles.analyze | — |
| `styles confirm` | `design.update` | cli.styles confirm → styles.confirm | — |
| `styles list` | — | - | read-only projection/read model; no project control change |
| `styles plan` | `change.plan` | cli.styles plan → styles.plan (immutable plan object) | — |
| `styles propose` | `style.propose` | cli.styles propose → styles.propose | — |
| `styles references import` | `asset.import` | cli.styles references import → visual_styles.import_reference | — |
| `styles references list` | — | - | read-only projection/read model; no project control change |
| `styles references show` | — | - | read-only projection/read model; no project control change |
| `styles show` | — | - | read-only projection/read model; no project control change |
| `task accept` | `task.accept` | cli.task accept → service.accept_result | — |
| `task call allocate` | `allowance.allocate` | cli.task call allocate → tasks.allocate_call_allowances | — |
| `task call begin` | `call.begin` | cli.task call begin → tasks.call_begin | — |
| `task call settle` | `call.settle` | cli.task call settle → tasks.call_settle (settles facts; never a new production channel) | — |
| `task cancel` | `task.cancel` | cli.task cancel → service.task_cancel (available while paused) | — |
| `task list` | — | - | read-only projection/read model; no project control change |
| `task start` | `task.start` | cli.task start → service.task_start | — |
| `task status` | — | - | read-only projection/read model; no project control change |
| `ui commit-clear` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `ui plan-clear` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `view` | — | - | read-only projection/read model; no project control change |
| `workbench` | — | - | installation/registry/diagnostic surface; not project business state |
| 旧命令拒绝/映射面（79 项，逐名见模块） | — | — | legacy mapping/refusal surface: maps to a rebuilt command or refuses with guidance; writes nothing |

### 3.5 HTTP / Studio 路由

| 入口 | 必检 action | gate 落点 | 豁免理由 |
| --- | --- | --- | --- |
| `/api/actions/` | — | - | read-only projection/read model; no project control change |
| `/api/annotations` | — | - | read-only projection/read model; no project control change |
| `/api/annotations/` | — | - | read-only projection/read model; no project control change |
| `/api/annotations/batch` | `annotation.save` | web.do_POST → annotation_service.save | — |
| `/api/attempts/` | — | - | read-only projection/read model; no project control change |
| `/api/cancel` | `task.cancel` | web.do_POST → service.task_cancel (available while paused) | — |
| `/api/candidate-preview/` | — | - | read-only projection/read model; no project control change |
| `/api/candidate-preview/file` | — | - | read-only projection/read model; no project control change |
| `/api/candidate-preview/request` | `render.preview` | web.do_POST → candidate_preview.request | — |
| `/api/candidate-preview/status` | — | - | read-only projection/read model; no project control change |
| `/api/candidates` | — | - | read-only projection/read model; no project control change |
| `/api/candidates/` | — | - | read-only projection/read model; no project control change |
| `/api/candidates/adopt` | `candidate.adopt` | web.do_POST → candidates.adopt | — |
| `/api/candidates/decision` | `candidate.select` | web.do_POST → candidates.decide | — |
| `/api/candidates/plan` | `change.plan` | web.do_POST → candidates.plan (immutable plan object) | — |
| `/api/changes` | — | - | read-only projection/read model; no project control change |
| `/api/changes/` | — | - | read-only projection/read model; no project control change |
| `/api/changes/commit` | `change.commit` | web.do_POST → changes.commit | — |
| `/api/changes/plan` | `change.plan` | web.do_POST → changes.plan (immutable plan object) | — |
| `/api/check` | — | - | read-only projection/read model; no project control change |
| `/api/compose/handoff` | — | - | read-only projection/read model; no project control change |
| `/api/content-plan` | — | - | read-only projection/read model; no project control change |
| `/api/content/` | — | - | read-only projection/read model; no project control change |
| `/api/content/commit` | `content.operation` | web.do_POST → content_ops.commit | — |
| `/api/content/inputs` | `content.inputs_update` | web.do_POST → content_ops.inputs | — |
| `/api/content/lineage/` | — | - | read-only projection/read model; no project control change |
| `/api/content/plan` | `change.plan` | web.do_POST → content_ops.plan (immutable plan object) | — |
| `/api/content/sources/` | — | - | read-only projection/read model; no project control change |
| `/api/content/uploads` | — | - | stages a material upload for later confirmation; writes no Document/Task/allowance |
| `/api/content/uploads/` | — | - | read-only projection/read model; no project control change |
| `/api/drafts` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/drafts/` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/drafts/import` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/drafts/recovery` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/drafts/save` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/edit` | `page.edit` | web.do_POST → editing.edit_page | — |
| `/api/export` | `export.delivery` | web.do_POST → editing.export_project (working/review copies stay report-only) | — |
| `/api/export-facts` | — | - | read-only projection/read model; no project control change |
| `/api/exports` | `export.delivery` | web.do_POST → exports.create (purpose=delivery consumes the gate) | — |
| `/api/exports/` | — | - | reads an already-fixed immutable export object |
| `/api/feedback` | `dispatch.host_task` | web.do_POST → service.open_host_task (feedback dispatch) | — |
| `/api/file` | — | - | reads an already-fixed immutable export object |
| `/api/gallery` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/health` | — | - | read-only projection/read model; no project control change |
| `/api/history` | — | - | read-only projection/read model; no project control change |
| `/api/history/` | — | - | read-only projection/read model; no project control change |
| `/api/history/commit-restore` | `restore` | web.do_POST → restoration.commit | — |
| `/api/history/plan-restore` | — | - | read-only projection/read model; no project control change |
| `/api/icons/` | — | - | read-only projection/read model; no project control change |
| `/api/icons/catalog` | — | - | read-only projection/read model; no project control change |
| `/api/icons/catalog/file` | — | - | read-only projection/read model; no project control change |
| `/api/icons/confirm` | `candidate.select` | web.do_POST → icons.confirm | — |
| `/api/icons/inspect` | — | - | read-only projection/read model; no project control change |
| `/api/icons/list` | — | - | read-only projection/read model; no project control change |
| `/api/icons/plan` | `change.plan` | web.do_POST → icons.plan (immutable plan object) | — |
| `/api/icons/preview` | `render.preview` | web.do_POST → icons.preview (local rendering) | — |
| `/api/icons/propose` | `style.propose` | web.do_POST → icons.propose | — |
| `/api/inputs` | — | - | read-only projection/read model; no project control change |
| `/api/inputs/update` | `content.inputs_update` | web.do_POST → service.inputs_update | — |
| `/api/operations/` | — | - | read-only projection/read model; no project control change |
| `/api/overview` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/pages/` | — | - | read-only projection/read model; no project control change |
| `/api/project` | — | - | read-only projection/read model; no project control change |
| `/api/requests/` | — | - | read-only projection/read model; no project control change |
| `/api/requests/freeze` | `generation.dispatch` | web.do_POST → generation.freeze | — |
| `/api/restore` | `restore` | web.do_POST → editing.restore | — |
| `/api/result-reading` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/result-reading/import-legacy` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/reviews` | — | - | read-only projection/read model; no project control change |
| `/api/session` | — | - | read-only projection/read model; no project control change |
| `/api/stages/` | — | - | read-only projection/read model; no project control change |
| `/api/stages/assemble` | `stage.assemble` | web.do_POST → stages.assemble | — |
| `/api/styles` | — | - | read-only projection/read model; no project control change |
| `/api/styles/` | — | - | read-only projection/read model; no project control change |
| `/api/styles/analyze` | `dispatch.host_task` | web.do_POST → visual_styles.analyze | — |
| `/api/styles/confirm` | `design.update` | web.do_POST → styles.confirm | — |
| `/api/styles/plan` | `change.plan` | web.do_POST → styles.plan (immutable plan object) | — |
| `/api/styles/propose` | `style.propose` | web.do_POST → styles.propose | — |
| `/api/styles/references` | — | - | read-only projection/read model; no project control change |
| `/api/styles/references/` | — | - | read-only projection/read model; no project control change |
| `/api/styles/references/import` | `asset.import` | web.do_POST → visual_styles.import_reference | — |
| `/api/tasks` | — | - | read-only projection/read model; no project control change |
| `/api/tasks/` | — | - | read-only projection/read model; no project control change |
| `/api/text-ranges/` | — | - | read-only projection/read model; no project control change |
| `/api/text-ranges/validate` | — | - | read-only projection/read model; no project control change |
| `/api/thumbnail-file` | — | - | reads an already-fixed immutable export object |
| `/api/thumbnails` | — | - | read-only projection/read model; no project control change |
| `/api/ui-state` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/ui-state/backups` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/ui-state/commit-clear` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/ui-state/plan-clear` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/ui-state/plan-restore` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/ui-state/restore` | — | - | personal UI journal / gallery / overview state; never writes project control or business objects |
| `/api/view` | — | - | read-only projection/read model; no project control change |
| `/api/view/summary` | — | - | read-only projection/read model; no project control change |
| `/api/workbench` | — | - | read-only projection/read model; no project control change |

## 4. 本增量内的启用边界（如实说明）

- gate 只在 `minimum_writer=collaboration.v1`（或存在 collaboration 区域）的项目上生效；
  低于该 writer 的历史项目保持现行行为，resolver 仍计算 `migration_required`，
  由 `tests/rebuild/test_eligibility_resolver.py` 单独锁定，发布集成时一并启用。
- 清单里的 action 是 resolver 的判定入口；具体 enforcement 接线与真实测试证据见
  `docs/reports/content-collaboration-v1.2/t04-eligibility-scope.md`。

