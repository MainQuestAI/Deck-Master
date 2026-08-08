# High-Density Builder v2 Final QA Review

Date: 2026-08-08
Branch: `codex/fix-hd2-final-trust-audit`
PR: #26, Draft

## Review Scope

本轮针对 v3 修复计划核验以下真实链路：

```text
Page Package -> NBB selection/seal -> Content Lock -> ImageGen blueprint
-> native SVG -> DrawingML PPTX -> batch render/readback -> handback
```

重点检查 NBB 用户选择与 Runtime seal、claim binding、provider challenge lineage、SVG authority、Scene/Content Lock 覆盖、文字 mask、PPTX 批量渲染、readback，以及 7 页差异化验收。

## Executed Evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Full pytest | pass | `1,365 passed`, `105 subtests passed` |
| Coverage | pass | 82%, `--fail-under=80` |
| Focused high-density tests | pass | `86 passed` in the builder and distinct-acceptance suites |
| Ruff | pass | high-density scripts and acceptance tests |
| Compileall | pass | high-density scripts and acceptance tests |
| Diff check | pass | `git diff --check` |
| Seven-page E2E | pass | `phase-4-seven-page-e2e.json` |
| Fresh provider smoke | pass | `phase-4-provider-smoke-evidence.json` |
| Provider `deck-quality` render gate | pass | local fresh provider smoke run; raw report excluded |
| Standard profile regression | pass | `phase-4-standard-profile-evidence.json` |
| GitHub Actions CI | pass | Python 3.11/3.12 main tests, autoplan smoke, and CI-tier RC gate on final head `a6c4fda` |
| 73-page external MVP evidence | pass as external evidence | sanitized index only; raw material is excluded |

## Findings

1. NBB selection records the user decision without regenerating Agent-authored content. Selected-storyline enrichment is required before the Runtime can seal the plan.
2. Content Lock projection preserves plan, page-plan, storyline, evidence, and claim-binding lineage. Unsupported facts, unbound additions, stale hashes, and forged receipts are blocked by tests.
3. Blueprint generation requires the locked content and style lock, explicit approval, and a provider challenge. The committed smoke evidence contains nonzero prompt, image, Scene, SVG, PPTX, readback, Runtime receipt, Host receipt, and review hashes.
4. Native SVG validation and DrawingML compilation share the controlled SVG paint and content rules. Scene visual metadata cannot override SVG geometry or styles.
5. Visual metrics are calculated from rendered artifacts. Text masks are glyph-based, bounded, and fail closed when coverage or usable comparison pixels are invalid.
6. The seven-page fixture has independent blueprint, Scene, SVG, and PPTX render lineage. The current test suite includes the mutation probes required by AF-01 through AF-20.
7. Provider smoke, seven-page E2E, standard-profile evidence, and the acceptance matrix are bound to source commit `4af2928b3a98ddeafba2abe49a890f3051458afc`.

## Release Decision

**Local acceptance: pass. CI/review/QA: pass.**

The implementation and evidence satisfy the current v3 repair scope. PR #26 remains Draft by delivery instruction; this review does not change Ready-for-review or merge state.
