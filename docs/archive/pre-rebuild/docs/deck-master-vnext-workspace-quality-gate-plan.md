# Deck Master vNext: Workspace + Quality Gate Implementation Plan

Date: 2026-06-10
Status: PROPOSED
Scope: Deck Workspace, demand-to-deck runtime, tool orchestration, quality gate, approval and export loop

## 1. Product Positioning

Deck Master vNext should evolve into a trusted deck production runtime.

Its job is to turn a user brief into a reviewable, source-aware, quality-gated deck production process. It should coordinate historical slide reuse, new page generation, workspace standards, preview approval, quality checks, and final export.

Current implemented baseline:

- `scripts/deck_master.py autoplan` can create a run from a brief.
- Runtime files are written under `runs/<run_id>/`.
- The planner creates a narrative plan.
- PPT Library integration has a fake/fixture fallback.
- Sourcing decisions support `reuse`, `adapt`, `generate`, and `manual_placeholder`.
- Generation task packages can be created.
- Preview UI can show runs, page previews, source decisions, risks, candidates, and generation tasks.
- Approval state and notes can be written back to the preview manifest.
- Approved queue export and slide win-rate feedback MVP exist.

The next product layer should solve three larger problems:

- A user needs a durable deck workspace, not a one-off run folder.
- A deck needs reusable page archetypes and visual standards, not only hardcoded planner defaults.
- A generated deck needs quality gates for narrative, evidence, screenshots, density, visual readiness, and delivery consistency.

## 2. Target User Flow

The target workflow:

1. User creates or registers a Deck Workspace.
2. User provides a brief, document, or short demand statement.
3. Deck Master creates a run and normalizes the request.
4. Deck Master reads workspace standards and generates a narrative/page plan.
5. Deck Master searches PPT Library for historical slide candidates.
6. Deck Master decides each page source: reuse, adapt, generate, or manual placeholder.
7. Deck Master creates generation task packages for pages that need new work.
8. Deck Master builds a preview manifest.
9. User reviews the deck in Web Studio.
10. Deck Master runs Draft Gate once `narrative_plan.json` and `page_tasks.json` exist.
11. User reviews pages in Web Studio and approves or rejects pages.
12. Render Gate runs only when HTML/SVG/PPTX preview assets exist.
13. Delivery Gate runs only when an export queue or deliverable package exists.
14. Feedback from approval and rejection updates future sourcing decisions.

Expected artifacts:

```text
deck-workspace/
  workspace_manifest.json
  AGENTS.md
  visual-system/
  structure-assets/
  quality/
  sources/
  projects/
  runs/
  exports/
```

Per-run artifacts:

```text
runs/<run_id>/
  request.json
  events.jsonl
  narrative_plan.json
  page_tasks.json
  library_results/
  sourcing_plan.json
  generation_tasks/
  preview_manifest.json
  quality_reports/
  approved_queue.json
```

## 3. Runtime Model

Deck Master should remain runtime-first. The runtime owns state, recovery, tool records, approval points, and quality reports.

Runtime requirements:

- `request.json` stores normalized user demand, constraints, audience, target pages, style preference, and source constraints.
- `events.jsonl` records typed events for runtime recovery and audit.
- `narrative_plan.json` stores deck-level strategy and page-level beats.
- `page_tasks.json` stores layered implementation tasks derived from narrative beats.
- `library_results/` stores full PPT Library candidate results and per-beat results.
- `sourcing_plan.json` stores final source decisions and explanations.
- `generation_tasks/` stores handoff packages for generation tools.
- `preview_manifest.json` stores the reviewable deck state shown in Web Studio.
- `quality_reports/` stores Draft Gate, Render Gate, and Delivery Gate results.
- `approved_queue.json` stores only pages approved for downstream assembly/export.

Recovery rules:

- If `request.json` exists and `narrative_plan.json` is missing, resume from planning.
- If `narrative_plan.json` exists and `library_results/selection.json` is missing, resume from library search.
- If library results exist and `sourcing_plan.json` is missing, resume from sourcing decision.
- If sourcing exists and generation tasks are missing, resume from generation task creation.
- If preview manifest is missing, resume from preview build.
- If preview exists, open Web Studio and preserve user approval state.
- Any corrupt JSON should create an error event and stop before overwriting data.

Event types:

- `run_created`: a run folder and initial request were created.
- `step_started`: a pipeline step started.
- `step_completed`: a pipeline step finished successfully.
- `tool_call`: an external tool command was prepared or executed.
- `tool_result`: an external tool returned usable output.
- `decision`: Deck Master made a planning, sourcing, or export decision.
- `manual_action`: a user approval, rejection, or note was written back.
- `warning`: a recoverable issue was detected.
- `error`: a blocking issue was detected.

Minimum event fields:

- `timestamp`
- `event_type`
- `run_id`
- `step`
- `message`
- `refs`
- `severity`

## 4. Deck Workspace

Deck Workspace is the durable production environment for a brand, customer, business line, or repeatable solution system.

### 4.1 Workspace Initialization

Add a command:

```bash
python3 scripts/deck_master.py init-workspace \
  --workspace /path/to/deck-workspace \
  --name "MarketingForce PPT Workshop" \
  --reference-ppt /path/to/reference.pptx
```

Initial behavior:

- Create the standard workspace folder structure.
- Write `workspace_manifest.json`.
- Create starter files under `visual-system/`, `structure-assets/`, and `quality/`.
- Optionally register a reference PPT path and basic metadata only.
- Support registering an existing folder as a workspace.

First version boundary:

- `--reference-ppt` only records path, filename, file size, modified time, and optional user note.
- It does not extract colors, fonts, layouts, screenshots, or master templates.
- Visual extraction from reference PPT is a later package because it requires Office parsing, heuristic cleanup, and human review.

`workspace_manifest.json` minimum fields:

```json
{
  "workspace_id": "marketingforce-ppt-workshop",
  "name": "MarketingForce PPT Workshop",
  "version": 1,
  "created_at": "2026-06-10T00:00:00Z",
  "visual_system": {
    "design_spec": "visual-system/design_spec.md",
    "spec_lock": "visual-system/spec_lock.md",
    "layout_blueprint": "visual-system/layout_blueprint.md"
  },
  "structure_assets": {
    "page_archetypes": "structure-assets/page_archetypes.md"
  },
  "quality": {
    "policy": "quality/quality_policy.md",
    "failure_modes": "quality/failure_modes.md",
    "scoring_rubric": "quality/scoring_rubric.md",
    "repair_playbooks": "quality/repair_playbooks.md"
  },
  "sources": [],
  "default_output": "exports/"
}
```

### 4.2 Visual System

The visual system should provide stable production standards:

- Canvas size and safe areas.
- Logo area.
- Font policy.
- Color palette.
- Background policy.
- Component style.
- Density standard.
- Layout rhythm.
- Template constraints.

Deck Master does not need to render every page itself. It needs to make these standards available to the planner, preview layer, quality gate, and downstream generators.

First version source:

- New workspaces receive human-editable starter templates.
- Existing workspaces can reuse committed files such as `design_spec.md`, `spec_lock.md`, and `layout_blueprint.md`.
- If a field is unknown, the template should mark it as `pending_manual_review`.
- No automatic visual spec extraction is required in Package 1.

### 4.3 Structure Assets

Structure assets define how common page types organize information.

Recommended page archetype fields:

- `archetype_id`
- `name`
- `best_for`
- `page_role`
- `required_modules`
- `evidence_pattern`
- `visual_pattern`
- `density_target`
- `avoid`
- `example_refs`

Initial archetypes:

- cover
- agenda
- executive_summary
- problem
- business_context
- solution_overview
- architecture
- capability_matrix
- process_flow
- case_study
- roadmap
- roi
- risk_control
- closing

Planner behavior:

- Prefer workspace archetypes when available.
- Fall back to Deck Master defaults when a workspace is missing.
- Record selected archetype references into `page_tasks.json`.

## 5. Demand-to-Deck Planning

The existing autoplan flow should be extended to use workspace standards.

Command:

```bash
python3 scripts/deck_master.py autoplan \
  --workspace /path/to/deck-workspace \
  --brief "零售客户数字化转型方案，关注全渠道、库存可视化、最后一公里配送" \
  --auto-through preview
```

Planner inputs:

- Normalized request.
- Workspace visual standards.
- Workspace page archetypes.
- Existing Deck Master planner defaults.
- Target page count.
- Audience.
- Industry.
- Source constraints.

Planner outputs:

- `narrative_plan.json`
- `page_tasks.json`

`page_tasks.json` should avoid a flat structure. Use stage-specific sections so each pipeline step writes to its own area.

Recommended task shape:

```json
{
  "beat_id": "beat_004",
  "order": 4,
  "planning": {
    "page_title": "库存可视化目标架构",
    "role": "architecture",
    "core_claim": "库存可视化需要打通门店、仓、渠道和配送履约状态。",
    "content_goal": "说明目标架构和关键数据流。",
    "evidence_need": ["系统截图", "库存状态样例", "履约指标"],
    "visual_need": "分层架构图",
    "density": "high",
    "preferred_archetype": "architecture",
    "workspace_refs": ["structure-assets/page_archetypes.md#architecture"],
    "quality_requirements": ["必须有主观点", "必须说明数据如何服务决策"],
    "gaps": []
  },
  "retrieval": {
    "reuse_query": "retail inventory visibility architecture omnichannel fulfillment",
    "constraints": ["avoid generic platform overview"]
  },
  "sourcing": {
    "decision": null,
    "selected_candidate": null,
    "alternatives": [],
    "risk_flags": [],
    "confidence": null
  },
  "generation": {
    "generation_brief": "生成一页库存可视化目标架构页，强调全渠道库存、履约状态和最后一公里配送。",
    "reference_slide": null,
    "task_path": null,
    "status": "pending"
  }
}
```

Planner writes:

- `beat_id`
- `order`
- `planning.*`
- `retrieval.reuse_query`
- `generation.generation_brief`

Sourcing writes:

- `sourcing.decision`
- `sourcing.selected_candidate`
- `sourcing.alternatives`
- `sourcing.risk_flags`
- `sourcing.confidence`

Generation writes:

- `generation.reference_slide`
- `generation.task_path`
- `generation.status`

Default planning rules:

- `auto` target pages: 12-18 pages.
- `15` pages: executive-level compact solution.
- `30` pages: complete solution proposal.
- `60` pages and above: chaptered long deck with stronger section handoff.
- Missing customer facts should create explicit `manual_placeholder` gaps.
- Evidence-heavy pages should ask for screenshots, case evidence, metrics, or before/after signals.

## 6. PPT Library Integration

Deck Master should remain the caller and decision owner. PPT Library should stay focused on indexing, searching, selecting, and returning slide candidates.

Primary command shape:

```bash
ppt-lib select-slides \
  --plan <run>/narrative_plan.json \
  --brief <run>/request.json \
  --ranking business \
  --max-per-role 5 \
  --output <run>/library_results/selection.json
```

Fallback command shape:

```bash
ppt-lib search "<reuse_query>" \
  --top-k 8 \
  --ranking business \
  --output json
```

Deck Master should parse:

- `slide_id`
- `canonical_slide_id`
- `title`
- `text_summary`
- `source_file`
- `page_number`
- `screenshot_path`
- `confidence`
- `win_rate`
- `reuse_count`

Failure behavior:

- No results: record empty result and continue.
- CLI missing: record tool unavailable and use fixture or generate/manual fallback.
- Bad JSON: record parse error and continue.
- Screenshot missing: keep candidate but add risk flag.
- Embedding service unavailable: record dependency failure and continue.

## 7. Sourcing Decision Engine

The sourcing decision engine chooses one primary source strategy for every page.

Decision types:

- `reuse`: use a historical slide directly.
- `adapt`: use a historical slide as structure/reference and generate an adjusted page.
- `generate`: create a new page.
- `manual_placeholder`: user must provide missing facts, screenshots, data, or customer-specific evidence.

Scoring dimensions:

- Semantic match.
- Narrative role match.
- Archetype match.
- Screenshot availability.
- Source credibility.
- Win rate.
- Reuse count.
- Customer-context conflict.
- Visual continuity with workspace.
- Evidence sufficiency.

Initial scoring weights:

| Dimension | Weight |
|---|---:|
| Semantic match | 0.30 |
| Narrative role match | 0.18 |
| Archetype match | 0.10 |
| Screenshot availability | 0.10 |
| Source credibility | 0.08 |
| Win rate | 0.10 |
| Reuse count | 0.04 |
| Customer-context conflict | -0.12 |
| Visual continuity with workspace | 0.06 |
| Evidence sufficiency | 0.06 |

Initial thresholds:

- `reuse`: score >= 0.78, screenshot available, no high customer-context conflict.
- `adapt`: score >= 0.58 and either archetype match >= 0.70 or narrative role match >= 0.70.
- `generate`: score < 0.58 and no required evidence gap.
- `manual_placeholder`: required evidence or customer fact is missing.

Tie-breaking:

- Prefer higher narrative role match over higher raw semantic match.
- Prefer higher win rate when scores differ by less than 0.05.
- Prefer candidates with screenshots when scores differ by less than 0.08.
- If the best candidate has a context conflict, downgrade from `reuse` to `adapt`.

Decision defaults:

- High match plus usable screenshot: `reuse`.
- Strong structure plus context mismatch: `adapt`.
- Weak or missing candidates: `generate`.
- Missing required facts or evidence: `manual_placeholder`.
- Missing screenshot should lower confidence and add a risk flag.
- High win-rate candidates should be preferred when match quality is close.

Each decision should include:

- `beat_id`
- `decision`
- `decision_reason`
- `selected_candidate`
- `alternatives`
- `risk_flags`
- `confidence`
- `tool_refs`

## 8. Generation Handoff

Deck Master should create generation task packages for `adapt` and `generate` pages.

Task file:

```text
generation_tasks/<beat_id>.json
```

Task fields:

- `beat_id`
- `page_title`
- `role`
- `core_claim`
- `generation_brief`
- `reference_slide`
- `preferred_archetype`
- `visual_need`
- `evidence_need`
- `style_constraints`
- `workspace_refs`
- `quality_requirements`

Supported downstream tools:

- PPT Deck Pro Max for content and page generation.
- PPT Master for SVG/PPTX page execution.
- Guizang for HTML deck execution.
- Future renderers through the same task package shape.

First implementation boundary:

- Create task packages and project skeletons.
- Track generated assets when they appear.
- Merge generated previews into `preview_manifest.json`.
- Defer expensive rendering or image generation to explicit downstream commands.

Minimum orchestration strategy:

- `autoplan --auto-through preview` runs request intake, planning, library search, sourcing, generation task creation, and preview build in sequence.
- It creates generation tasks but does not automatically run expensive renderers.
- `create-generation-tasks` can be run independently after sourcing.
- `run-generation --beat-id <id>` should be added later for manual targeted execution.
- Parallel execution is allowed only inside an external renderer after task files are created.
- If task creation fails for one page, record an error for that beat and continue building preview for other pages.
- If a downstream renderer fails later, keep the task in `failed` state and keep the page visible in preview with a risk flag.

## 9. Preview UI Upgrade

The current preview UI should become the review surface for source decisions and quality risks.

Additional UI sections:

- Deck strategy summary.
- Page budget and section plan.
- Per-page source decision.
- Candidate slides and alternatives.
- Risk flags.
- Generation task status.
- Quality gate summary.

User actions:

- Approve page.
- Reject page.
- Add review note.

Deferred actions:

- Request replacement.
- Lock historical slide.
- Convert to generated page.
- Mark manual evidence required.

Manifest extensions:

- `beat_id`
- `source_decision`
- `decision_reason`
- `alternatives`
- `risk_flags`
- `tool_refs`
- `generation_task`
- `quality_status`
- `review_note`

Export rule:

- Only approved pages should enter `approved_queue.json`.
- Pages with P0 quality issues should not export unless explicitly overridden.
- Manual placeholders should export only as task reminders, not as final pages.

## 10. Quality Gate

Quality Gate should become a first-class Deck Master submodule.

It should run at three points:

- Draft Gate: after narrative plan and page tasks.
- Render Gate: after HTML/SVG/PPTX preview assets exist.
- Delivery Gate: after an export queue or deliverable package exists.

Implementation order:

- Draft Gate belongs in the first vNext implementation wave because it only needs `narrative_plan.json` and `page_tasks.json`.
- Render Gate should wait until the pipeline has real rendered assets or fixture assets.
- Delivery Gate should wait until export queue and package validation are in place.

### 10.1 Draft Gate

Checks:

- Deck has a clear audience and business goal.
- Each page has a clear job.
- Each page has a main claim.
- Page sequence has narrative progression.
- Evidence needs are explicit.
- Missing facts are marked as gaps.
- Long decks have section handoff.
- Page density target matches page role.

Output:

```text
quality_reports/draft_gate.json
quality_reports/draft_gate.md
```

### 10.2 Render Gate

Checks:

- Rendered output keeps the original page intent.
- High-density pages did not collapse into sparse bullet pages.
- Screenshots are large enough, cropped well, and tied to the claim.
- Product screenshots prove capability or outcome.
- Architecture and method pages include evidence or examples when needed.
- Layout patterns are not over-repeated.
- Text does not overflow.
- Font size is readable.
- Pages are not flattened into whole-page screenshots unless intended.
- Vector-heavy PPT Master pages are not misread as empty image-less pages.

Output:

```text
quality_reports/render_gate.json
quality_reports/render_gate.md
```

### 10.3 Delivery Gate

Checks:

- Expected page count matches exported page count.
- Preview package and PPTX package point to the same version.
- No stale pages remain in export.
- All image/assets links are valid.
- Deliverable path is correct.
- Internal wording and context-sensitive terms are reviewed.
- File package can be opened independently.
- Approved queue and exported deck are aligned.

Output:

```text
quality_reports/delivery_gate.json
quality_reports/delivery_gate.md
```

### 10.4 Scoring

Quality dimensions:

- Narrative Integrity.
- Page Job Clarity.
- Information Density.
- Evidence And Specificity.
- Screenshot And Asset Integration.
- Layout Variety.
- Consulting-Style Expression.
- Visual Readiness.
- Delivery Readiness.

Decision levels:

- `pass`: ready for next step.
- `conditional_pass`: usable with known issues.
- `rework_required`: must repair before next step.

Severity levels:

- `P0`: blocks delivery.
- `P1`: blocks client-facing use unless repaired.
- `P2`: should repair when time allows.
- `P3`: improvement suggestion.

## 11. Feedback Loop

Deck Master should record which decisions worked.

First version signal:

- Page approved.
- Page rejected.

Later signals:

- Page converted from reuse to generate.
- Candidate replaced.
- User note.
- Final exported.
- Deal won or lost.
- Slide win rate.

Feedback targets:

- PPT Library ranking.
- Sourcing decision weights.
- Workspace page archetypes.
- Quality failure modes.
- Future planner defaults.

Feedback artifacts:

```text
feedback/
  sourcing_outcomes.jsonl
  slide_outcomes.jsonl
  quality_outcomes.jsonl
```

First version only writes `sourcing_outcomes.jsonl`:

```json
{
  "timestamp": "2026-06-10T00:00:00Z",
  "run_id": "run_001",
  "beat_id": "beat_004",
  "decision": "reuse",
  "candidate_id": "slide_123",
  "outcome": "approved"
}
```

## 12. Implementation Sequence

### Package 1: Workspace foundation

Deliver:

- `init-workspace` CLI command.
- `workspace_manifest.json` schema.
- Workspace folder templates.
- Existing workspace registration.

Verify:

- Create a new workspace.
- Register the MarketingForce workshop folder.
- Detect missing workspace files and show pending status.

### Package 2: Planner reads workspace standards and writes layered tasks

Deliver:

- Planner loads page archetypes.
- Page tasks use `planning`, `retrieval`, `sourcing`, and `generation` sections.
- Planner writes only planning/retrieval/generation brief fields.
- Default planner still works without workspace.

Verify:

- Same brief produces workspace-aware page tasks.
- Missing archetype falls back to default.
- `page_tasks.json` has no flat mixed-stage decision fields.

### Package 3: Sourcing thresholds and generation handoff

Deliver:

- Initial sourcing weights and thresholds.
- Deterministic sourcing decision output.
- Generation task creation for `adapt` and `generate`.
- Minimum orchestration strategy for `autoplan --auto-through preview`.

Verify:

- Same input produces the same sourcing decision.
- High screenshot + high score candidate becomes `reuse`.
- Context mismatch downgrades `reuse` to `adapt`.
- Missing evidence becomes `manual_placeholder`.
- Generation task creation failure records an event and does not block other preview pages.

### Package 4: Preview UI minimal approval upgrade

Deliver:

- Source decision display.
- Candidate and risk display.
- Approval actions limited to approve, reject, and note.
- Export queue filters approved pages.

Verify:

- User can approve, reject, and note pages.
- Export includes only approved pages.

### Package 5: Draft Gate

Deliver:

- Draft Gate.
- `quality_reports/draft_gate.json`.
- `quality_reports/draft_gate.md`.
- Draft findings visible in preview.

Verify:

- Retail brief Draft Gate catches missing evidence.
- Draft Gate does not require rendered assets.
- Draft Gate findings map to page task ids.

### Package 6: Render and Delivery Gate

Deliver:

- Render Gate for HTML/SVG/PPTX assets.
- Delivery Gate for export queue and package validation.
- Quality summary display in Preview UI.

Verify:

- Danone HTML deck Render Gate.
- Enterprise AIGC PPTX Delivery Gate.
- ECCO long deck regression.
- PPT Master vector-heavy output is not misread as empty.

### Package 7: Feedback and asset learning

Deliver:

- `approved` and `rejected` outcomes in `sourcing_outcomes.jsonl`.
- Later hooks for PPT Library win-rate handoff.

Verify:

- Approved pages update sourcing outcome logs.
- Rejected candidates are traceable for later ranking changes.

## 13. Acceptance Scenarios

### Retail digital transformation

Input:

```text
零售客户数字化转型方案，关注全渠道、库存可视化、最后一公里配送
```

Expected:

- Creates a run.
- Generates a complete deck structure.
- Includes omnichannel, inventory visibility, last-mile delivery, architecture, case, and value pages.
- Produces preview manifest.

### Strong historical match

Expected:

- High-confidence candidate with screenshot and win-rate becomes `reuse`.
- Decision reason explains why.

### Partial historical match

Expected:

- Useful historical structure with context mismatch becomes `adapt`.
- Generation task references the historical slide.

### No historical match

Expected:

- New architecture or customer-specific page becomes `generate`.

### Missing evidence

Expected:

- Missing customer data, screenshots, case proof, or metrics becomes `manual_placeholder`.
- Preview shows required manual input.

### Tool failure

Expected:

- PPT Library failure is recorded in `events.jsonl`.
- Deck Master continues with a reviewable draft.

### Quality failure

Expected:

- Screenshot wall, weak evidence chain, page-count mismatch, or stale export creates P0/P1 findings.
- Export blocks or requires explicit override.

### Approval export

Expected:

- Only approved pages appear in `approved_queue.json`.

## 14. Testing Plan

Required tests:

| Test | Input | Expected output |
|---|---|---|
| Runtime creates run | `brief="零售数字化"` | `request.json` and `events.jsonl` exist |
| Runtime rejects duplicate run | same `run_id` created twice | second create raises a clear error |
| Runtime resumes from planning | `request.json` exists, `narrative_plan.json` missing | next step is planning |
| Runtime handles corrupt JSON | invalid `request.json` | error event is written and no overwrite happens |
| Brief intake short text | one-sentence Chinese brief | normalized request with business goal and topics |
| Brief intake file | `examples/briefs/retail_digital_transformation.txt` | same normalized fields as text input |
| Workspace initialization | `init-workspace --workspace tmp/ws --name Test` | standard folders and manifest exist |
| Workspace reference registration | `--reference-ppt sample.pptx` | manifest stores path and metadata only |
| Planner with workspace | retail brief + workspace archetypes | page tasks reference workspace archetypes |
| Planner without workspace | retail brief only | page tasks use default archetypes |
| Page task layering | generated `page_tasks.json` | fields are grouped under planning/retrieval/sourcing/generation |
| PPT Library normal result | fixture with screenshot | candidate parsed with source metadata |
| PPT Library empty result | empty fixture | beat has empty result, no silent skip |
| PPT Library bad JSON | malformed fixture | error event and fallback decision |
| Sourcing reuse | score >= 0.78, screenshot available | decision is `reuse` |
| Sourcing adapt | strong archetype match, context mismatch | decision is `adapt` |
| Sourcing generate | low score, no evidence gap | decision is `generate` |
| Sourcing manual placeholder | required evidence missing | decision is `manual_placeholder` |
| Generation task | one `adapt` and one `generate` page | two task files with beat ids |
| Preview manifest compatibility | old manifest without new fields | server still loads it |
| Preview approval | approve one page, reject one page | manifest stores both outcomes |
| Export filtering | one approved, one rejected page | approved queue contains only approved page |
| Draft Gate | page task missing evidence | Draft Gate emits page-level finding |
| Render Gate fixture | HTML deck with sparse screenshot page | Render Gate emits screenshot/evidence finding |
| Delivery Gate fixture | expected 17 pages, PPTX reports 30 | Delivery Gate emits P0 page-count finding |
| End-to-end fixture | retail brief with fake library | run reaches preview manifest deterministically |

Suggested regression samples:

- Danone AI consumer HTML deck.
- Enterprise AIGC solution PPTX.
- ECCO KOS case pages.
- ECCO long proposal deck.
- PPT Master vector-heavy output.

## 15. Product Boundary

Deck Master owns:

- Run state.
- Workspace state.
- Planning.
- Tool orchestration.
- Source decisions.
- Preview approval.
- Quality gate.
- Export queue.
- Feedback loop.

PPT Library owns:

- Historical deck indexing.
- Slide search.
- Candidate ranking.
- Slide metadata.
- Screenshot and source references.

PPT Deck Pro Max owns:

- Rich content generation.
- Page-level generation workflow.
- Project skeletons and generated assets.

PPT Master and Guizang own:

- Visual execution.
- SVG/HTML/PPTX rendering.
- Renderer-specific QA.

## 16. First Release Definition

The first vNext release is complete when:

- A user can create or register a Deck Workspace.
- A user can start from one business brief.
- Deck Master creates a run with recoverable state.
- Page planning reads workspace standards.
- Page tasks are layered by planning, retrieval, sourcing, and generation sections.
- PPT Library or fake client produces candidates.
- Every page has a source decision.
- Sourcing decisions use documented initial weights and thresholds.
- Generate/adapt pages have task packages.
- `autoplan --auto-through preview` runs the minimum sequence through preview without running expensive renderers.
- Preview UI shows decisions, candidates, risks, and approve/reject/note state.
- Draft Gate produces JSON and Markdown reports.
- Render Gate and Delivery Gate specs exist and can run against fixtures when rendered/exported assets are available.
- Export queue contains approved pages only.
- First feedback loop writes approved/rejected outcomes to `sourcing_outcomes.jsonl`.
- Tests cover the full fixture flow.
- Documentation explains current capability and known boundaries.
