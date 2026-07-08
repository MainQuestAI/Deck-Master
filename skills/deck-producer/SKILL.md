---
name: deck-producer
description: Deck Master production entry for generation sessions, Agent dispatch packages, page production, and deck_generation_result.v2 import.
triggers:
  - produce deck pages
  - start generation session
  - import generation result
  - deck producer
---

# Deck Producer

Use this skill when sourcing decides pages need new production or adaptation.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master generation-session create --run-dir <run_dir>
~/.deck-master/bin/deck-master run-generation --run-dir <run_dir>
~/.deck-master/bin/deck-master generation-session dispatch --run-dir <run_dir>
~/.deck-master/bin/deck-master generation-session import-results --run-dir <run_dir> --input <result.json>
~/.deck-master/bin/deck-master refresh-preview-from-generation --run-dir <run_dir>
```

## Output Rule

Production results must return as canonical `deck_generation_result.v2` with
run/session binding, safe paths, checksums, and real artifacts.


<!-- skill-os-contract:v1 -->

## Use When
Generation sessions, dispatch packages, and canonical generation result import.

## Do Not Use
Do not use outside its lane in the Skill OS workflow. Do not treat a successful command return code as stage completion.

## First Checks
- sourcing handoff accepted
- sourcing plan fresh
- required page set known

## Forcing Questions
- producer.page_claim: 每页要表达的核心主张是什么？
- producer.public_evidence: 证据是否可对客户公开？
- producer.visual_lead: 每页的视觉主角是什么？
- producer.internal_client_boundary: 内部制作说明与客户可见内容的边界如何界定？

## Runtime Ownership
Skill OS workflow runtime; stage `deck-producer`. Stage completion is validated by the contract entry/exit validator and handoff/approval runtime, not by command return code.

## Allowed Commands
```bash
deck-master generation-session create --run-dir <run_dir>
deck-master generation-session status --run-dir <run_dir>
deck-master run-generation --run-dir <run_dir>
deck-master generation-session dispatch --run-dir <run_dir>
deck-master generation-session import-results --run-dir <run_dir> --input <result.json>
deck-master refresh-preview-from-generation --run-dir <run_dir>
deck-master build-preview --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
deck_generation_result.v2, preview_refresh

## Next Skill
deck-builder

## Stop Conditions
- blocking_question
- internal_field_leak
- missing_required_page_package

## Safety Rules
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
