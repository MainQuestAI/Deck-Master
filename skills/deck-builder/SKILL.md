---
name: deck-builder
description: Deck Master build entry for producing delivery-oriented HTML, PDF, PNG, PPTX, artifact manifest, render result, and editability metadata through the PPT Master backend.
triggers:
  - build deck
  - render deck
  - export pptx artifact
  - deck builder
---

# Deck Builder

Use this skill after preview review and quality gate pass. Deck Builder is the
public Deck Master build entry. PPT Master is the backend dependency.

## First Checks

```bash
~/.deck-master/bin/deck-master suite-status --target codex --output json
~/.deck-master/bin/deck-master run-state --run-dir <run_dir>
```

## Allowed Commands

```bash
~/.deck-master/bin/deck-master build prepare --run-dir <run_dir>
~/.deck-master/bin/deck-master build run --run-dir <run_dir>
~/.deck-master/bin/deck-master build status --run-dir <run_dir>
~/.deck-master/bin/deck-master render-status --run-dir <run_dir>
~/.deck-master/bin/deck-master import-render-result --run-dir <run_dir> --input <render_result.json>
```

## Backend Rule

Production/client export requires the full PPT Master backend package. Internal
repair may continue with degraded status, but it cannot be marked deliverable.


<!-- skill-os-contract:v1 -->

## Use When
Public build entry for HTML, PDF, PNG, PPTX, artifact manifest, render result, and editability metadata.

## Do Not Use
Do not use outside its lane in the Skill OS workflow. Do not treat a successful command return code as stage completion.

## First Checks
- producer handoff accepted
- page packages valid
- certified build backend ready

## Forcing Questions
- builder.output_mode: 输出格式与模式是什么（HTML/PDF/PPTX/PNG）？
- builder.font_policy: 字体策略是否已确认？

## Runtime Ownership
Skill OS workflow runtime; stage `deck-builder`. Stage completion is validated by the contract entry/exit validator and handoff/approval runtime, not by command return code.

## Allowed Commands
```bash
deck-master build prepare --run-dir <run_dir>
deck-master build run --run-dir <run_dir>
deck-master build status --run-dir <run_dir>
deck-master render-status --run-dir <run_dir>
deck-master import-render-result --run-dir <run_dir> --input <render_result.json>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
build_manifest, artifact_manifest, render_result.v2, final_artifacts

## Next Skill
deck-quality

## Stop Conditions
- build_backend_unavailable
- render_failed
- preview_manifest_used_without_adapter

## Safety Rules
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
