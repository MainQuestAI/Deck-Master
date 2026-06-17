# Deck Master v0.9.13 Agent-facing Product Capability Packaging & Migration Spec v0.2

日期：2026-06-17  
状态：v0.2 修订版，已吸收 P0/P1 评审意见  
适用范围：Deck Master v0.9.13 的开发主控 Spec、任务拆分和验收口径

## 1. 核心结论

v0.9.13 保持 Deck Master 的既定运行形态：Agent-facing、local-first、provider-free，运行在 Codex、Claude Code、Coworker、Workbody 等 Agent 环境之上。本轮不扩展为独立桌面应用、SaaS 或自带 LLM 的 Agent Runtime。

v0.9.13 改变产品能力交付边界：PPT Master、PPT Library、PPT Deck Pro Max、PPT Quality Gate 从用户侧额外安装、额外理解、额外配置的依赖，收敛为 Deck Master release tree 随包分发的 required Product Capabilities。

一句话定义：

> Deck Master v0.9.13 要把“多仓库能力依赖”收敛为“一次安装即可获得的 Agent-facing Solution Deck Product Capability Suite”。

## 2. 设计原则

### 2.1 运行形态不变

Deck Master 不做：

- LLM provider。
- 自研 Agent Runtime。
- 独立桌面应用。
- SaaS 登录、租户、计费和多团队后台。
- 通用 PPT 编辑器。
- 通用 Presentation 生成器。

Deck Master 做：

- CLI / Runtime。
- Workspace / Run State。
- Skill Suite。
- Product Capability Suite。
- Review Cockpit。
- Quality / Export / Benchmark。
- Capability readiness / migration / setup。
- 所有产物回写 Deck Master run 的强约束。

### 2.2 用户侧单安装

开发侧可以多仓库，用户侧不承担多仓库安装。

允许：

- PPT Library、PPT Deck Pro Max、PPT Master、PPT Quality Gate 保留独立仓库和独立使用方式。
- Deck Master release 构建时引用、vendor、subtree、wheel bundle、wrapper 或重建这些能力。

不允许：

- 用户安装 Deck Master 后，还必须额外 clone / install / configure required capabilities 才能跑主链路。
- `suite-status` 在 required capabilities 缺失时仍作为最终验收通过。

### 2.3 Product Capability 不再称为外部 companion dependency

v0.9.13 起，文档和代码层建议统一使用：

- Product Capability。
- bundled capability。
- internalized capability。
- required capability。

仅在说明历史迁移或 legacy compatibility 时使用 legacy companion / former companion 表达。

### 2.4 required suite 必须 ready

v0.9.13 最终验收必须满足：

```text
required suite ready
full_suite_ready=true
required task_readiness 全部 ready
```

`degraded_ready` 只能用于中间状态、可选能力或真实用户环境诊断，不能作为 v0.9.13 release acceptance 的通过条件。

### 2.5 PPT Master 是硬验收，禁止 placeholder

PPT Master 是 Deck Master 默认 build / render 引擎。v0.9.13 不允许只创建 `ppt-master` metadata / placeholder 后宣称 suite 完整。

v0.9.13 至少必须提供 PPT Master 的最小可执行能力：

- `status` / `doctor`。
- fixture-safe render smoke。
- render session 或 render result contract。
- active run writeback。
- run-state 阻断：需要 render 时，PPT Master 不 ready 不得进入 delivery-ready / benchmark-rc-ready。

## 3. Required Capability Scope

| Capability | v0.9.13 角色 | required | 最小可执行能力 |
|---|---|---:|---|
| `ppt-master` | default build / render engine | 是 | status / doctor / render fixture smoke / import-render-result / render state gate |
| `ppt-library` | asset intelligence | 是 | status / doctor / selection fixture smoke / canonical selection import / feedback queue |
| `ppt-deck-pro-max` | production intelligence | 是 | status / doctor / generation fixture smoke / generation-session result binding |
| `ppt-quality-gate` | quality governance | 是 | status / doctor / findings fixture smoke / import-quality-findings |
| `deck-master` | top-level router and runtime owner | 是 | start / doctor / run-state / setup-status / suite-status |
| `deck-planner` | planning task entry | 是 | context / brief / claim / narrative playbook entry |
| `deck-review` | review and delivery task entry | 是 | quality / export / cockpit / repair playbook entry |
| `deck-learning` | feedback and benchmark entry | 可选，后置 | may be degraded in v0.9.13 unless explicitly promoted |

## 4. Release Tree

v0.9.13 release tree:

```text
~/.deck-master/current/
  product-capability-manifest.json
  bin/
    deck-master
  skills/
    deck-master/
    deck-planner/
    deck-review/
    ppt-master/
    ppt-library/
    ppt-deck-pro-max/
    ppt-quality-gate/
  capabilities/
    ppt-master/
    ppt-library/
    ppt-deck-pro-max/
    ppt-quality-gate/
  contracts/
    generation-result.v1.schema.json
    render-result.v1.schema.json
    library-selection.v1.schema.json
    quality-findings.v1.schema.json
  reference-packs/
    ppt-structure-assets/
    visual-system-default/
    quality-rubrics-default/
```

Codex and Claude Code target directories keep symlinks only:

```text
~/.codex/skills/deck-master -> ~/.deck-master/current/skills/deck-master
~/.codex/skills/deck-planner -> ~/.deck-master/current/skills/deck-planner
~/.codex/skills/deck-review -> ~/.deck-master/current/skills/deck-review
~/.codex/skills/ppt-master -> ~/.deck-master/current/skills/ppt-master
~/.codex/skills/ppt-library -> ~/.deck-master/current/skills/ppt-library
~/.codex/skills/ppt-deck-pro-max -> ~/.deck-master/current/skills/ppt-deck-pro-max
~/.codex/skills/ppt-quality-gate -> ~/.deck-master/current/skills/ppt-quality-gate
```

Claude Code follows the same managed symlink rule.

## 5. Capability Discovery Policy

### 5.1 Default discovery

Default runtime discovery priority:

```text
1. bundled capability in ~/.deck-master/current/capabilities/<name>/
2. workspace capability override
3. global tool registry
```

This makes bundled capability the default user experience.

### 5.2 Explicit CLI override

Explicit CLI override is not part of default discovery. When supplied, it wins intentionally:

```text
0. explicit CLI --tool-command or --capability-command
1. bundled capability
2. workspace override
3. global registry
```

Rules:

- CLI override must record `source=cli_override`.
- CLI override must write a warning event or diagnostic warning.
- CLI override must still satisfy output schema and run/session binding.
- CLI override cannot bypass import contracts, quality gates, or run-state blocking.

## 6. Full Suite Readiness Definition

`full_suite_ready=true` only when all required capabilities are ready:

```json
{
  "schema_version": "deck_master_suite_status.v2",
  "status": "ready",
  "full_suite_ready": true,
  "required_capabilities": {
    "deck-master": "ready",
    "deck-planner": "ready",
    "deck-review": "ready",
    "ppt-master": "ready",
    "ppt-library": "ready",
    "ppt-deck-pro-max": "ready",
    "ppt-quality-gate": "ready"
  },
  "task_readiness": {
    "planning": "ready",
    "asset_sourcing": "ready",
    "generation": "ready",
    "render": "ready",
    "quality": "ready",
    "delivery": "ready"
  }
}
```

Acceptance must fail if any required capability is missing, placeholder-only, broken symlink, invalid manifest, or lacks a passing fixture-safe smoke.

`setup-status --include-suite --output json` and `suite-status --output json` must remain pure-read inspection commands:

- no HOME file creation;
- no install log writes;
- no setup event writes;
- no workspace artifact writes;
- no run artifact writes;
- no mtime changes for existing config / manifest / run files.

## 7. Minimal Executable Capability Contract

Every required Product Capability must ship with:

```text
capability.yaml
SKILL.md
contracts/
smoke/
adapters/
```

Every required capability must expose the following logical operations, either as a Python entrypoint, CLI wrapper, or Deck Master-managed runner:

| Operation | Required | Meaning |
|---|---:|---|
| `status` | 是 | Pure-read capability status, no write |
| `doctor` | 是 | Dependency and schema validation |
| `smoke --fixture` | 是 | Safe fixture smoke, no private data |
| `schema` | 是 | Prints supported input/output schema versions |
| `writeback` | 是 | Writes result through Deck Master import/state path |

Metadata-only packages cannot be marked ready.

## 8. PPT Master P0 Render Contract

v0.9.13 must include a minimal PPT Master render path.

### Required CLI surface

```bash
deck-master render-status --run-dir <run_dir>
deck-master render --run-dir <run_dir> --format html --fixture-safe
deck-master import-render-result --run-dir <run_dir> --input <render_result.json>
```

If `deck-master render` is implemented as a wrapper over bundled `ppt-master`, the wrapper must still produce canonical Deck Master render state.

### Required artifacts

```text
render_session.json
render_results/render_result.json     # canonical v0.9.13+ render result
rendered/index.html
quality_reports/render_gate.json   # generated after explicit render quality gate
```

Legacy compatibility:

- `external_results/render_result.json` may be read as a legacy render result source.
- root-level `render_result.json` may be read only for old benchmark fixtures.
- v0.9.13 write paths must write canonical render result to `render_results/render_result.json`.
- Importing a legacy render result must normalize it into `render_results/render_result.json` and record an event / import log entry.
- run-state resolver, benchmark runner, Review Cockpit readiness, and export / delivery gates must read canonical first, then legacy fallback.

### Minimum render result schema

```json
{
  "schema_version": "deck_render_result.v1",
  "run_id": "example-run",
  "session_id": "render-001",
  "tool": "ppt-master",
  "status": "completed",
  "format": "html",
  "artifact_path": "rendered/index.html",
  "preview_refs": ["preview_manifest.json"],
  "created_at": "..."
}
```

### Run-state blocking rule

If a run has approved pages and no render result, the run may be ready for page export queue, but it must not be `ready_for_delivery` or `benchmark_rc_ready`.

If PPT Master capability is not ready, `suite-status` cannot be full ready.

## 9. Agent-driven Setup Ceremony

Deck Master setup is an Agent-driven ceremony, not a user-facing command dump.

When a user invokes Deck Master or any required Deck Master capability, the relevant Skill must:

1. Run `deck-master setup-status --include-suite --output json`.
2. Explain missing setup / workspace / suite readiness in natural language.
3. Confirm or infer the intended workspace.
4. Run setup / suite repair / migration commands on behalf of the user when safe.
5. Re-run setup and suite status.
6. Continue only after production readiness and required suite readiness are clear.

Required Skill documentation updates:

- `skills/deck-master/SKILL.md` First checks must start from setup-status with suite included.
- `skills/deck-planner/SKILL.md` must defer production planning to Deck Master run state when setup is blocked.
- `skills/deck-review/SKILL.md` must read Deck Master run-state before judging delivery readiness.
- Product Capability Skills must state that active-run output must return through Deck Master import / state update.

Final acceptance must include text tests that prevent these Skill docs from telling users to manually run a raw setup command without Agent guidance.

## 10. Installation and Migration Targets

v0.9.13 must test both:

```text
--target codex
--target claude-code
```

Required smoke matrix:

| Target | Fresh install | Symlink check | Migration plan | Migration apply | Rollback | Suite status |
|---|---:|---:|---:|---:|---:|---:|
| codex | required | required | required | required | required | required |
| claude-code | required | required | required | required | required | required |

Hermes / custom may remain best-effort unless explicitly promoted.

## 11. P0 / P1 / P2 Corrections Integrated

This v0.2 integrates the following review corrections:

| Finding | v0.2 decision |
|---|---|
| PPT Master placeholder unacceptable | PPT Master minimal render contract is P0 hard gate |
| degraded suite acceptance too weak | final acceptance requires `full_suite_ready=true` |
| Claude Code under-tested | Codex and Claude Code both required in install/migration smoke |
| discovery priority conflict | default bundled-first and explicit override-wins are separated |
| metadata-only capability too weak | required capabilities need real status/doctor/smoke/writeback |
| companion wording misleading | docs use Product Capability / bundled capability except legacy notes |
| `.DS_Store` present | release pack and docs must exclude `.DS_Store` |
| disallowed phrase in master spec | wording rewritten in v0.2 |
| render result path split | canonical path is `render_results/render_result.json`; legacy paths are read-only fallback |
| Agent setup not hard-gated | setup ceremony and Skill doc tests are required |
| pure-read status regression risk | setup-status and suite-status must not write files or mtimes |
| real HOME smoke risk | CI / QA uses temporary HOME; real install is a separate deployment step |

## 12. Task Breakdown

Recommended PR order:

```text
A. Manifest, Release Tree, Full Suite Readiness
B. Required Capability Package Shape and PPT Master P0 Render Path
C. Core Skill Split and Target Routing
D. Suite Install, Legacy Migration, Setup for Codex and Claude Code
E. Runtime Discovery and Capability Integration
F. Acceptance, Regression, Release Readiness
```

## 13. Non-goals

v0.9.13 does not:

- Fully rewrite PPT Library.
- Fully rewrite PPT Deck Pro Max.
- Fully rewrite PPT Quality Gate.
- Create a standalone UI product.
- Create a hosted product or SaaS.
- Introduce LLM providers.
- Add team/commercial workspace features.
- Implement high-fidelity PowerPoint rendering beyond minimum PPT Master P0 render contract.

## 14. Definition of Done

v0.9.13 is done only if:

1. Temporary HOME install can build release tree without touching the user's real install.
2. `suite-install --target codex --target claude-code` creates managed symlinks.
3. Existing real directories are never overwritten without migration plan.
4. Migration apply and rollback are both tested for Codex and Claude Code.
5. `suite-status --output json` returns `full_suite_ready=true` for required suite in fixture test environment.
6. PPT Master minimal render smoke passes and writes canonical `render_results/render_result.json`.
7. PPT Library fixture selection smoke passes and writes canonical library selection.
8. PPT Deck Pro Max fixture generation smoke passes and generation session binding remains enforced.
9. PPT Quality Gate fixture findings smoke passes and writes quality report.
10. Runtime discovery defaults to bundled capabilities.
11. CLI override wins only when explicit and records warning.
12. No `.DS_Store`, `__MACOSX`, `.env`, local screenshots, font files, or private artifacts are included in release tree.
13. `setup-status --include-suite` and `suite-status` are proven pure-read under temporary HOME.
14. Skill docs enforce Agent-driven setup ceremony and active-run writeback.
15. Full test suite passes.

## 15. Commands to Validate

```bash
python3 -m unittest discover -s tests
git diff --check HEAD
find . -name .DS_Store -o -name __MACOSX

export HOME=<tmp_home>
deck-master suite-build-release-tree --output "$HOME/.deck-master/current"
deck-master suite-install --target codex --target claude-code
deck-master suite-status --output json
deck-master setup --workspace <workspace> --target codex --target claude-code --repair-workspace --install-suite

deck-master render --run-dir <fixture_run> --format html --fixture-safe
deck-master render-status --run-dir <fixture_run>
deck-master import-render-result --run-dir <fixture_run> --input <render_result.json>
```
