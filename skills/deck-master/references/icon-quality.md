# Icon refinement (icon_quality.v1)

Existing content acceptance is not permission to silently adopt a visual alternative.
Read the fixed selected annotations and `deck-master icons inspect --project … --page-id …`.
Inspect original pixels and SVG separately; never infer equal regions after layout changes.
Use `icons catalog` for the bundled standard set. Default to faithful redraw; semantic
standard replacements and page expansion require an explicit user selection.

Submit `icons propose --input icon-input.json`. Each target freezes page_ref, svg_ref,
blueprint_ref; each icon names semantic_key, label, original_region and svg_region (normalized
coordinates), non-nested objects (path + subtree sha256 returned by inspect), method
redraw|standard|reuse, style {color:#RRGGBB,stroke_width:positive}. Standard names asset_id;
reuse names sample_candidate_id and sample_icon_index of a still-current adopted icon candidate.
The input also carries schema_version=icon_input.v1, project_id, base_revision, instruction,
and annotation_refs. Never manufacture object hashes, original-region recognition or approval.

The user reviews highlights and confirms the proposal in UI or through icons confirm with
base_revision and a UUIDv4. Confirmation dispatches nothing. Explicit page selection via
icons plan then normal changes commit creates zero-call repair trials. Declare icon_repair,
change_plan and candidate_result when claiming the task. Read the immutable icon_recipe_ref
from task inputs; modify only selected geometry, keep one replacement subtree per locator.
Preserve every other element, attribute, text, ordering and original image binding.

For standard/reuse, icons draft --recipe-id … --page-id … returns verified deterministic SVG
geometry for inspection; it does not submit or adopt. For redraw build explicit native geometry.
Submit complete SVG through normal task accept. No raster replacement or external assets.
Run candidate-preview request --candidate-id … to compile/render/read back the candidate
without changing the current deck; status shows real tool failures and check state.
Only the user's actual choice authorizes candidate plan/adopt. A passed engineering check
is not semantic or aesthetic approval. Reuse across pages requires a confirmed adopted sample
and explicit target objects/pages; one page can contain several icons but produces one candidate.
After adoption use normal page visual review and stages assemble/final readiness.
