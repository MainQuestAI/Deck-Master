# Page content handoff

Production native `autoplan` prepares `production/page_content_task.json` before any image or SVG task. `page-content prepare|status|submit` are the public continuation commands. Status is read-only; submit accepts `--input <host-content.json>` and dispatches native production only after all content is validated.

A `deck_page_content_task.v1` includes `run_id`, `task_id`, `status`, `based_on` (actual input file SHA-256 refs and fingerprint), ordered `page_ids`, narrative `pages`, `output_contract`, and `submit_command`. A pending task is `awaiting_agent_content`; successful submission makes it `content_ready`. Changed inputs require preparing a fresh task.

The host returns `deck_page_content_result.v1` with matching `run_id`, `task_id`, `source_fingerprint`, and the exact complete ordered `pages`. Each page contains `page_id`, finished `page_title`, `conclusion`, `business_implication`, nonempty Context `source_refs`, source-qualified `evidence_bindings`, and `fact_kind` (`customer_fact`, `design_suggestion`, `analysis_judgment`, or `working_assumption`). Source references are stored in `provenance.source_refs`, separately from evidence. Suggestion pages carry `evidence_state: design_basis`; a customer-fact page requires an existing verified quote binding. Legacy `evidence_refs` is accepted only as an alias for source provenance, never proof of fact support. The host must review that relationship. Unsupported numerical claims are blocked by the semantic evidence check.

`content_review` must contain `status: approved_for_build`, actual `reviewer`, and a nonempty review `basis`. This authorizes draft construction only. Existing final quality and delivery approval requirements remain applicable.

Submit validates all pages before publishing PagePackages, enriched Narrative, and the receipt in one revision. Missing/reordered pages, stale fingerprints, unknown sources, missing review, unsupported numbers, or production instructions are rejected. Identical replay is idempotent. No legacy generation artifact is fabricated by this path.

The result may include `evidence_quotes`: each item has `source_id`, local `evidence_id`, original `quote`, its `quote_sha256`, and exact `source_position` (`unit_type`, `start`, `end`). Submit verifies the immutable source file hash and exact quoted span, rejects conflicting evidence identities, and atomically appends valid evidence to Context with PagePackages. Page bindings use `source_id::evidence_id`; no generated page text can establish source evidence.
