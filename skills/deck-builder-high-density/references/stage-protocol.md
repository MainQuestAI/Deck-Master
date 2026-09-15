# High-Density Stage Protocol

### A. PagePackage and Content Lock

For a new task, import the complete Agent-authored draft with `import-plan
--source agent`. Narrative beats define the page set and order; every beat has
one `ready_for_build` PagePackage with customer-visible copy, visual intent,
notes, and citations. Production projects the complete business content into
`content_lock.v2` with `enrichment.framework=page_package`. It must not ask for
an MBB candidate, a second storyline decision, SCR fields, per-page management
conclusions, or synthetic evidence.

`enrichment.framework=mbb` remains readable for existing runs. Do not convert a
new draft to MBB or fill legacy fields with placeholder values. A changed page
invalidates that page's downstream assets; a pure reorder only reassembles the
deck and refreshes file-level checks.

Facts and numbers retain locatable citations. Reasoned recommendations are
reviewed for mechanism, assumptions, and conditions; they do not require
historical outcome evidence merely because they are recommendations. Page
numbers, source labels, business frameworks, and ordinary business terms are
valid customer-visible copy when the author intended them.

### B. Style and Blueprint

Production uses an approved style lock. Each blueprint prompt receives the full
customer-visible projection and the page's visual specification. ImageGen or an
explicitly imported external blueprint supplies visual direction only; it never
supplies business facts. The Agent reviews the actual blueprint before
reconstructing it.

Provider receipts bind prompt and image hashes for traceability. A copied run
can verify its imported image from run-local hashes without the original host
cache. A failed content review returns a page-scoped repair action; retry until
the defect is fixed or the user-supplied budget or stop instruction is reached.

Before reconstruction, inventory the blueprint's visible regions, nested cards,
status badges, directed connections, icons, labels, and footer. Compare that
inventory with the Scene and SVG preview. A sparse Scene cannot count as a
faithful redraw merely because it contains every locked text field.

### C. Blueprint to editable Scene, SVG, and PPTX

The Agent reads the blueprint and Content Lock and writes canonical
`high_density_build/scenes/<page_id>.page_scene.json`. The Scene preserves
business text, ownership, connections, direction, values, units, labels, and
footnotes. Structural and layout metadata stays internal. Native SVG and the
DrawingML compiler preserve editable text and shapes; a single background image
cannot stand in for editable delivery.
Blueprint copy that is useful but absent from the Content Lock must first be
edited into customer-visible PagePackage content; the image alone is not a
source of business facts.

The runtime checks actual overflow, clipping, illegal overlap, unsupported SVG,
unregistered assets, content coverage, and readback. It does not impose a
universal block count, character count, numeric count, or image-area quota.

### D. Visual and semantic review

Metrics compare the current blueprint, SVG, and PPTX render. They are evidence
about geometry and rendering, not a substitute for semantic review. Producer
self-review and optional independent review record concrete observations,
issues found, and an explicit revision decision bound to current hashes. A
reviewer ID alone cannot create a passing review.
Review the blueprint and actual SVG side by side, including icon and dense-card
crops. Record missing regions or details as revision work. Do not explain away
a failed full-page comparison as an editable-style difference when structure,
icons, or information density have visibly changed.

```bash
PYTHONPATH=scripts python3 -m high_density.self_review --run-dir <run_dir> --page-id P001 --reviewer-id <id> --observation "<what was checked>" --no-revision-required
PYTHONPATH=scripts python3 -m high_density.main_review --run-dir <run_dir> --page-id P001 --reviewer-id <id> --observation "<what was checked>" --no-revision-required
```

Any visible copy added during blueprint or Scene work re-enters semantic review.
Final PPTX readback checks text, editable objects, relations, ordering, and
current artifact hashes.

### E. Agent continuation

When Agent work is required, the runtime returns `awaiting_agent_build` with
`input_refs`, `output_refs`, schema, acceptance command, and resume command. If
the current Agent has the required tool and authorization, it writes the exact
output and resumes immediately. Stop only for an unavailable capability,
missing source material, or a decision the user must make.

Canonical outputs include Content Locks, prompts, blueprint manifests, Scenes,
native SVG, review evidence, PPTX traces and readback, the high-density manifest,
artifact manifest, and render result. Legacy MBB artifacts are exit artifacts
only for legacy runs that already use that framework.

### F. Completion

A run is complete only when the current artifact passes applicable contract,
render, semantic, editability, and readback checks. Fixture runs support
deterministic regression but never prove production readiness. Keep customer
materials, generated runs, provider payloads, credentials, and private evidence
outside the repository.
