# 固定版本源码证据索引

所有链接绑定 Git SHA。旧代码用于职责对照，不代表该历史版本已通过真实业务验收。

## E35 · 人类专业复核 policy 的原定义

版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [spec 03.3 L44](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-rebuild-v1/specs/03-data-and-state-contracts.md#L44)：professional_review_required_for_delivery 只有用户明确要求人类专业复核作为交付条件时为 true。

## E01 · `skills/stage-contracts.json`
版本：`4d44c7ee92632622a13d3770025ccac5ea49b982`

- [L98](https://github.com/MainQuestAI/Deck-Master/blob/4d44c7ee92632622a13d3770025ccac5ea49b982/skills/stage-contracts.json#L98)：`"stage_id": "deck-brief",`
- [L200](https://github.com/MainQuestAI/Deck-Master/blob/4d44c7ee92632622a13d3770025ccac5ea49b982/skills/stage-contracts.json#L200)：`"stage_id": "deck-planner",`
- [L629](https://github.com/MainQuestAI/Deck-Master/blob/4d44c7ee92632622a13d3770025ccac5ea49b982/skills/stage-contracts.json#L629)：`"stage_id": "deck-review",`

## E02 · `scripts/workflow/questions.py`
版本：`d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf`

- [L42](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/questions.py#L42)：`class QuestionResolver:`
- [L103](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/questions.py#L103)：`def exit_validation(`
- [L137](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/questions.py#L137)：`def _answer_status(`

## E03 · `scripts/workflow/decisions.py`
版本：`d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf`

- [L23](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/decisions.py#L23)：`SOURCE_USER = "user"`
- [L48](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/decisions.py#L48)：`def record(`
- [L60](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/decisions.py#L60)：`source_type: str = SOURCE_USER,`
- [L118](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/decisions.py#L118)：`def is_stale(decision: dict[str, Any], current_input_fingerprint: str) -> bool:`
- [L128](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/decisions.py#L128)：`"SOURCE_USER",`

## E04 · `scripts/workflow/autopilot.py`
版本：`d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf`

- [L78](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/autopilot.py#L78)：`class AutopilotV2:`
- [L127](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/autopilot.py#L127)：`# 1. final export always stops (never auto-export)`
- [L146](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/autopilot.py#L146)：`exit_val = self.questions.exit_validation(root, current)`

## E05 · `scripts/workflow/validator.py`
版本：`d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf`

- [L63](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/validator.py#L63)：`def validate_entry(`
- [L83](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/validator.py#L83)：`# entry.required_decisions and transition approvals are facts produced by`

## E06 · `scripts/conversation/session_builder.py`
版本：`d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf`

- [L6](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/conversation/session_builder.py#L6)：`GUIDED_QUESTIONS = [`
- [L54](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/conversation/session_builder.py#L54)：`"questions": GUIDED_QUESTIONS,`
- [L57](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/conversation/session_builder.py#L57)：`"首版记录 AI 引导问题和已锁定判断；实际多轮交互可后续接入。",`

## E07 · `scripts/conversation/brief_compiler.py`
版本：`d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf`

- [L12](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/conversation/brief_compiler.py#L12)：`def infer_core_points(request: dict[str, Any], context_manifest: dict[str, Any], conversation: dict[str, Any]) -> list[str]:`
- [L24](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/conversation/brief_compiler.py#L24)：`def compile_deck_brief(request: dict[str, Any], context_manifest: dict[str, Any], conversation: dict[str, Any]) -> dict[str, Any]:`

## E08 · `scripts/high_density/style.py`
版本：`d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf`

- [L115](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/high_density/style.py#L115)：`def load_style_lock(root: Path, *, require_approved: bool = True, expected_run_id: str | None = None) -> dict[str, Any]:`
- [L137](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/high_density/style.py#L137)：`def ensure_style_lock(root: Path, run_id: str, *, mode: str, style_id: str | None = None, approver: str = "") -> dict[str, Any]:`

## E09 · `scripts/runtime/final_approval.py`
版本：`d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf`

- [L84](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/runtime/final_approval.py#L84)：`approver = payload.get("approver") if isinstance(payload.get("approver"), dict) else {}`
- [L100](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/runtime/final_approval.py#L100)：`return {"ready": False, "reason": "Final artifact approval is stale because the artifact changed.", "path": str(APPROVAL_PATH)}`

## E10 · `scripts/quality/external_review.py`
版本：`d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf`

- [L186](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/quality/external_review.py#L186)：`def prepare_quality_review(`
- [L422](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/quality/external_review.py#L422)：`def import_external_review(`

## E11 · `scripts/runtime/orchestration.py`
版本：`d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf`

- [L46](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/runtime/orchestration.py#L46)：`REQUIRED_SEQUENCE = [`
- [L69](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/runtime/orchestration.py#L69)：`def orchestration_check(`
- [L105](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/runtime/orchestration.py#L105)：`for name in REQUIRED_SEQUENCE`
- [L109](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/runtime/orchestration.py#L109)：`for name in REQUIRED_SEQUENCE:`

## E12 · `src/deck_master/service.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L89](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/service.py#L89)：`def create(`
- [L280](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/service.py#L280)：`def open_compose_task(store: Store, document: dict, *, operation_id: str,`
- [L563](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/service.py#L563)：`def open_blueprint_task(store: Store, document: dict, page_entry: dict) -> dict:`
- [L715](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/service.py#L715)：`def _continue_project(project_dir: Path | str) -> dict:`
- [L765](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/service.py#L765)：`if entry.get("page") and not entry.get("blueprint"):`

## E13 · `src/deck_master/models.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L397](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/models.py#L397)：`def default_design_context() -> dict[str, Any]:`
- [L481](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/models.py#L481)：`"external_call_limit": None,`
- [L510](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/models.py#L510)：`CONTENT_KEYS = ("project_id", "task", "sources", "pages", "design_context", "policy", "outputs")`
- [L520](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/models.py#L520)：`projection = {key: document.get(key) for key in CONTENT_KEYS}`
- [L567](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/models.py#L567)：`def new_document(`
- [L601](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/models.py#L601)：`"external_call_limit": None,`

## E14 · `src/deck_master/content_plan.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L39](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/content_plan.py#L39)：`def bind_result(store, document, task, value, pages):`
- [L69](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/content_plan.py#L69)：`def validate_input(store, document, value, pages):`

## E15 · `src/deck_master/tasks.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L593](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/tasks.py#L593)：`def _check_scope(kind: str, envelope: dict, task: dict) -> None:`
- [L915](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/tasks.py#L915)：`def accept_result(store: Store, **kwargs) -> dict:`
- [L1313](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/tasks.py#L1313)：`"next_action": "auto_view_then_production"`
- [L1335](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/tasks.py#L1335)：`def reserve_allowances(store, document, task, count):`
- [L1439](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/tasks.py#L1439)：`def call_begin(store: Store, *, task_id: str, allowance_id: str, execution_ref: str | None,`

## E16 · `src/deck_master/review.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L38](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/review.py#L38)：`def validate_independence(reviewer: dict) -> bool:`
- [L63](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/review.py#L63)：`def finding_closed(reviews: list[dict], review: dict, finding: dict, artifacts: dict) -> bool:`
- [L197](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/review.py#L197)：`def _substance_gate(kind: str, review: dict) -> str | None:`
- [L331](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/review.py#L331)：`def evaluate_current(document: dict, reviews: list[dict], artifacts: dict) -> dict:`

## E17 · `src/deck_master/exports.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L106](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/exports.py#L106)：`def _gate(store, doc, facts, purpose):`
- [L129](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/exports.py#L129)：`if (doc.get("policy") or {}).get("professional_review_required_for_delivery"):`
- [L145](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/exports.py#L145)：`and review["status"] != "fail"`

## E18 · `src/deck_master/handoff.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L13](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/handoff.py#L13)：`def check_handoff(project_dir, *, file_path, purpose="review"):`
- [L67](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/handoff.py#L67)：`if purpose == "delivery" and review_status != "pass":`

## E19 · `src/deck_master/cli.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L814](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/cli.py#L814)：`def _legacy_final_readiness(argv) -> int:`

## E20 · `src/deck_master/method_resources.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L34](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/method_resources.py#L34)：`_INITIAL_METHODS = ("source-reading", "content-methods", "content-examples")`
- [L66](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/method_resources.py#L66)：`def method_ids_for(kind: str, *, intent: str | None = None) -> tuple[str, ...]:`
- [L70](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/method_resources.py#L70)：`return _INPUT_REVISION_METHODS if intent == "input_revision" else _INITIAL_METHODS`

## E21 · `skills/deck-master/SKILL.md`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L33](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/skills/deck-master/SKILL.md#L33)：`## 正常循环`
- [L57](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/skills/deck-master/SKILL.md#L57)：`## 用户改变要求时`
- [L67](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/skills/deck-master/SKILL.md#L67)：`## 连续制作与返修`

## E22 · `skills/deck-master/references/style-calibration.md`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L7](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/skills/deck-master/references/style-calibration.md#L7)：`'styles confirm --proposal-id … --base-revision … --operation-id <UUIDv4>' 确认不可变配方。更新以 parent_recipe_id 创建新建议/新版本；旧配方不改。响应丢失查询原 operations，不创建新确认。'styles list/show' 支持 '--revision'。`
- [L9](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/skills/deck-master/references/style-calibration.md#L9)：`'styles plan --input plan-input.json' 的输入为 recipe_id、page_ids、max_calls。首轮只能一个目标；返回既有 change_plan 后用 'changes commit' 派发，当前采用不变。沿用 'changes handoff' 的原任务 ID、generation_input 和调用额度。`
- [L13](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/skills/deck-master/references/style-calibration.md#L13)：`用户比较并采用首张候选后，再传 adopted_candidate_id 和明确其它 page_ids 计划扩展。必须是本配方当前采用且依据有效的原图候选；未选择页及参考页不变。目标基准变化报告逐页 style_conflict，不能更新配方锚点以隐藏冲突。改变目标范围/基准先创建新配方版本，再试一页。取消/unknown/晚到遵循原恢复协议。`

## E23 · `src/deck_master/stages.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L9](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/stages.py#L9)：`def require_assembly_ready(store, document):`

## E24 · `src/deck_master/production.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L32](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/production.py#L32)：`def resolve_design(page, design, permitted_assets):`
- [L42](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/production.py#L42)：`if aid not in asset_map or asset_map[aid].get("external_use") != "allowed":`
- [L81](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/production.py#L81)：`def project_prompt(`

## E25 · `docs/specs/deck-master-flow-quality-v1.1/SPEC.md`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L38](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-flow-quality-v1.1/SPEC.md#L38)：`| 'task request-input'、'input_request' | 推迟。缺少关键决定时 Host 在对话中询问，答复后用 'inputs update' 写入 |`
- [L51](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-flow-quality-v1.1/SPEC.md#L51)：`- 不新增审批、评分、Planner 或多 Agent 接力。`
- [L69](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-flow-quality-v1.1/SPEC.md#L69)：`'title, brief, audience, scenario, presentation_mode(live|read_alone|mixed), page_limit(int|null), existing_decisions(string[])'`
- [L72](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-flow-quality-v1.1/SPEC.md#L72)：`- 'existing_decisions' 只收用户明确确认的决定，并且始终是**完整有效集合**。Host 自己的推断不写进来。`
- [L84](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-flow-quality-v1.1/SPEC.md#L84)：`- '--decision' 与 task-file 里的 'existing_decisions' 同时出现时直接拒绝（'task_field_conflict'，exit 2），不做拼接。`
- [L96](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-flow-quality-v1.1/SPEC.md#L96)：`"page_limit": 8, "existing_decisions": ["…"]},`
- [L167](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-flow-quality-v1.1/SPEC.md#L167)：`"task_patch": {"audience": "…", "existing_decisions": ["…完整集合…"]},`

## E26 · `docs/specs/deck-master-flow-quality-v1.1/ACCEPTANCE.md`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L30](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-flow-quality-v1.1/ACCEPTANCE.md#L30)：`## AC-17：7 步场景（从仓库外、新开的 Codex 会话启动）`
- [L32](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-flow-quality-v1.1/ACCEPTANCE.md#L32)：`1. 老板给出一个普通材料目录和一句业务任务，其中写明受众和一条已确认的决定。Host 不重复询问已给出的信息。`

## E27 · `docs/specs/deck-master-rebuild-v1/inventory/old-files.csv`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L33](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-rebuild-v1/inventory/old-files.csv#L33)：`OLD-035,2a866cf138f6359f853db35e0a926ad79391b691,scripts/conversation/session_builder.py,RETIRE_THEN_DELETE,—,WP05,WP04默认入口切换（先在新包内禁入）,WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史,默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移,AC-L05,T24 已退役:2026-09-22 引用扫描 living 面零残留(inventory/reference-scan.md);行为替代见 tests/rebuild;Git 历史保留`
- [L122](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-rebuild-v1/inventory/old-files.csv#L122)：`OLD-121,2a866cf138f6359f853db35e0a926ad79391b691,scripts/runtime/final_approval.py,RETIRE_THEN_DELETE,—,WP05,WP04默认入口切换（先在新包内禁入）,WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史,默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移,AC-L05,T24 已退役:2026-09-22 引用扫描 living 面零残留(inventory/reference-scan.md);行为替代见 tests/rebuild;Git 历史保留`
- [L172](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-rebuild-v1/inventory/old-files.csv#L172)：`OLD-171,2a866cf138f6359f853db35e0a926ad79391b691,scripts/workflow/questions.py,RETIRE_THEN_DELETE,—,WP05,WP04默认入口切换（先在新包内禁入）,WP05：替代行为/安装/legacy导入通过，静态与运行引用均为零；保留Git历史,默认主线与发行包不继承；必要历史行为在固定旧Git引用中保留，相关有效测试先按矩阵迁移,AC-L05,T24 已退役:2026-09-22 引用扫描 living 面零残留(inventory/reference-scan.md);行为替代见 tests/rebuild;Git 历史保留`

## E28 · `docs/specs/deck-master-rebuild-v1/specs/12-legacy-and-document-retirement.md`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L39](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-rebuild-v1/specs/12-legacy-and-document-retirement.md#L39)：`## 12.5 活动文档清单`
- [L45](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-rebuild-v1/specs/12-legacy-and-document-retirement.md#L45)：`## 12.6 何时可以删，何时不能删`

## E29 · `docs/specs/deck-master-flow-quality-v1.1/MIGRATION.md`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L3](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-flow-quality-v1.1/MIGRATION.md#L3)：`## 1. 旧 Skill → 新用法`
- [L17](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/docs/specs/deck-master-flow-quality-v1.1/MIGRATION.md#L17)：`| deck-learn | 记录反馈 | 不再提供。局部意见用 edit/feedback |`

## E30 · `src/deck_master/doctor.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L13](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/doctor.py#L13)：`def diagnose(step, *, fonts=(), host_imagegen=False):`

## E31 · `src/deck_master/changes.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L138](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/changes.py#L138)：`def plan(project, *, input):`
- [L156](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/changes.py#L156)：`def commit(project, *, plan_id, base_revision, operation_id):`

## E32 · `src/deck_master/editing.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L200](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/editing.py#L200)：`def check_summary(store, doc):`
- [L383](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/editing.py#L383)：`def restore_document(store, current, past, operation_id):`

## E33 · `src/deck_master/install.py`
版本：`af9fd7a6b4d08f753d2f16536a03f386384f49d2`

- [L377](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/install.py#L377)：`def activate(prefix,release_id,*,register_host=True):`
- [L397](https://github.com/MainQuestAI/Deck-Master/blob/af9fd7a6b4d08f753d2f16536a03f386384f49d2/src/deck_master/install.py#L397)：`def rollback(prefix,*,register_host=True):`

## E34 · `scripts/workflow/policy.py`
版本：`d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf`

- [L29](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/policy.py#L29)：`FINAL_EXPORT_TRANSITION = "deck-review->client-export"`
- [L51](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/policy.py#L51)：`class Preauthorization:`
- [L96](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/policy.py#L96)：`class PreauthorizationRuntime:`
- [L132](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/policy.py#L132)：`if FINAL_EXPORT_TRANSITION in allowed_transitions:`
- [L151](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/policy.py#L151)：`"protected_transitions": [FINAL_EXPORT_TRANSITION],`
- [L235](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/policy.py#L235)：`out.add(FINAL_EXPORT_TRANSITION)`
- [L243](https://github.com/MainQuestAI/Deck-Master/blob/d573b3c5dbfbaa742bfed32ec84e9dd79ac62faf/scripts/workflow/policy.py#L243)：`"FINAL_EXPORT_TRANSITION",`
