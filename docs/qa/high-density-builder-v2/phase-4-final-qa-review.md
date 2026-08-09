# High-Density Builder v2 Final QA Review

Date: 2026-08-09
Branch under review: `codex/fix-hd2-final-trust-audit`
Integration target: `main`

## Review Scope

本轮针对 v3 修复计划核验以下真实链路：

```text
Page Package -> MBB selection/seal -> Content Lock -> ImageGen blueprint
-> native SVG -> DrawingML PPTX -> batch render/readback -> handback
```

重点检查 MBB 用户选择与 Runtime seal、claim binding、provider challenge lineage、SVG authority、Scene/Content Lock 覆盖、文字 mask、PPTX 批量渲染、readback，以及 7 页差异化验收。

## Executed Evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Full pytest | pass | `1,399 passed`, `105 subtests passed` |
| Coverage | pending | Must be regenerated on the current MBB head before release acceptance |
| Focused high-density tests | pass | `120 passed` in the builder, distinct-acceptance, and icon-stability suites |
| Ruff | pass | high-density scripts and acceptance tests |
| Compileall | pass | high-density scripts and acceptance tests |
| Diff check | pass | `git diff --check` |
| Seven-page E2E | pass | `phase-4-seven-page-e2e.json` |
| Fresh provider smoke | blocked | The committed provider record is retired after the MBB migration; fresh evidence is required |
| Provider `deck-quality` render gate | pending | Cannot be claimed until the fresh MBB provider run is complete |
| Standard profile regression | pass | `phase-4-standard-profile-evidence.json` |
| GitHub Actions CI | pending | No new remote CI result was generated in this close-out |
| Six-page external icon acceptance | blocked | `phase-4-six-page-icon-external-acceptance.json` reports `blocked_missing_local_benchmark_artifacts`; raw page artifacts are excluded |
| 73-page external MVP evidence | historical | Sanitized index only; no new 73-page run is part of this close-out |

## Findings

1. MBB selection records the user decision without regenerating Agent-authored content. Selected-storyline enrichment is required before the Runtime can seal the plan.
2. Content Lock projection preserves plan, page-plan, storyline, evidence, and claim-binding lineage. Unsupported facts, unbound additions, stale hashes, and forged receipts are blocked by tests.
3. Blueprint generation requires the locked content and style lock, explicit approval, and a provider challenge. The previously committed provider record is retained for audit only and cannot serve as current MBB evidence.
4. Native SVG validation and DrawingML compilation share the controlled SVG paint and content rules. Scene visual metadata cannot override SVG geometry or styles.
5. Visual metrics are calculated from rendered artifacts. Text masks are glyph-based, bounded, and fail closed when coverage or usable comparison pixels are invalid.
6. The seven-page fixture has independent blueprint, Scene, SVG, and PPTX render lineage. The current test suite includes the mutation probes required by AF-01 through AF-20.
7. The current local test run validates the MBB implementation. Provider smoke, coverage, and six-page external evidence still require a fresh run on the current head.

## Release Decision

**Local implementation acceptance: pass. Release acceptance: blocked pending current MBB provider evidence, coverage evidence, and the six-page external icon artifact refresh.**

The implementation tests are green, while the release evidence is deliberately fail-closed where private artifacts are unavailable. Production release proceeds only after the documented blockers are either regenerated or explicitly carried into the next release gate.
