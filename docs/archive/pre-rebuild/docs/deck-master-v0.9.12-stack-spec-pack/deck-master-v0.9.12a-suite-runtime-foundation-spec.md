# Deck Master v0.9.12a Spec - Suite Runtime Foundation

## 1. 目标

建立 Deck Master Skill Suite 的 runtime foundation：安装模型、companion manifest、capability readiness、first-run setup ceremony、routing guard 和 non-mutating status。

本 Stack 不实现 companion skill 的深业务调用，只保证 Deck Master 能安全地知道 suite 是否可用、哪里缺失、下一步 Agent 应该做什么。

## 2. 非目标

- 不实现 PPT Library 搜索逻辑。
- 不实现 PPT Deck Pro Max 生成逻辑。
- 不实现 PPT Quality Gate 深度审查。
- 不做真实 feedback writeback。
- 不新增内置 LLM provider。
- 不覆盖用户已有真实 skill directory。

## 3. 修改边界

允许修改：

```text
skills/deck-master/SKILL.md
skills/deck-master/references/agent-instructions.md
scripts/deck_master.py
scripts/skills/*
scripts/runtime/*
docs/contracts/*
docs/specs/*
tests/*suite* / tests/*setup* / tests/*install*
```

当前代码基线已确认存在 `scripts/skills/*`、`scripts/runtime/*`、`scripts/deck_master.py`。安装链路必须复用这些入口；不得为了安装链路新建平行 `scripts/install/*` 目录，除非先在本 spec 中补充迁移理由和兼容测试。

## 4. 数据契约

### 4.1 Companion Skill Source Matrix

Stack A 必须先冻结 companion 来源矩阵，后续 suite install/status/repair 只能按该矩阵执行。不得在实现阶段临时创建半套 `skills/ppt-*` 目录。

| Skill | Required | Install source | Agent link name | CLI / tool key | Required capabilities | Default blocking behavior |
|---|---:|---|---|---|---|---|
| `deck-master` | yes | bundled: `skills/deck-master` | `deck-master` | `deck-master` | `deck_master.run.v1`, `deck_master.setup.v1` | missing blocks all Deck Master runs |
| `ppt-library` | yes for library sourcing, optional for direct generation | external adopted skill or release bundle | `ppt-library` | `ppt-lib` | `ppt_library.doctor.v1`, `ppt_library.search.v1`, `ppt_library.selection.v1` | missing blocks `library_sourcing`, but does not block Deck Master setup/run when the task can proceed without library sourcing |
| `ppt-deck-pro-max` | yes for new/adapt generation | external adopted skill or release bundle | `ppt-deck-pro-max` | `ppt-deck-pro-max` | `ppt_deck_pro_max.generate.v1`, `ppt_deck_pro_max.handback.v1` | missing blocks `new_generation` |
| `ppt-quality-gate` | yes for standalone audit and imported quality findings | external adopted skill or release bundle | `ppt-quality-gate` | `ppt-quality-gate` | `ppt_quality_gate.audit.v1`, `ppt_quality_gate.findings.v1` | missing blocks `standalone_audit`; Deck Master built-in quality gates remain available |
| `ppt-master` | optional | external adopted skill or release bundle | `ppt-master` | `ppt-master` | `ppt_master.render.v1`, `ppt_master.handback.v1` | missing reports `optional_missing`; render/export falls back to existing Deck Master paths |

Source policy:

- `bundled` means the repo/release owns the skill package and can install it by symlink.
- `external adopted skill` means Deck Master only adopts a valid existing skill/package; it must not overwrite a real user directory.
- `release bundle` means future installer may ship the package under `~/.deck-master/current/skills/<name>`.
- If an external skill has missing YAML frontmatter, wrong `name`, missing `description`, unsupported schema, or broken script references, suite status must report `schema_incompatible` or `capability_missing` and include `next_agent_action`.

### 4.2 Companion Manifest v2

新增：

```text
docs/contracts/companion-manifest.v2.schema.json
~/.deck-master/current/companion-manifest.json
```

建议 shape：

```json
{
  "schema_version": "deck_master_companion_manifest.v2",
  "suite_name": "deck-master",
  "suite_version": "0.9.12",
  "skills": [
    {
      "name": "deck-master",
      "required_for": ["full_deck_workflow", "setup", "run_orchestration"],
      "install_source": "bundled",
      "source_path": "~/.deck-master/current/skills/deck-master",
      "min_cli_version": "0.9.12",
      "cli": "deck-master",
      "required_capabilities": [
        "deck_master.run.v1",
        "deck_master.setup.v1"
      ],
      "optional_capabilities": [],
      "schema_versions": {
        "setup_status": "deck_master_setup_status.v2"
      },
      "agent_targets": {
        "codex": "~/.codex/skills/deck-master",
        "claude-code": "~/.claude/skills/deck-master"
      },
      "adoption_policy": "bundled_symlink_only",
      "conflict_policy": "never_overwrite_real_directory"
    },
    {
      "name": "ppt-library",
      "required_for": ["library_sourcing", "asset_feedback"],
      "install_source": "external_adopted_or_release_bundle",
      "min_cli_version": "0.1.0",
      "cli": "ppt-lib",
      "required_capabilities": [
        "ppt_library.doctor.v1",
        "ppt_library.search.v1",
        "ppt_library.selection.v1"
      ],
      "optional_capabilities": ["ppt_library.feedback.v1"],
      "schema_versions": {
        "selection_output": "deck_master_ppt_library_selection.v1",
        "feedback_input": "deck_master_ppt_library_feedback.v1"
      },
      "agent_targets": {
        "codex": "~/.codex/skills/ppt-library",
        "claude-code": "~/.claude/skills/ppt-library"
      },
      "adoption_policy": "adopt_valid_external_symlink_only",
      "conflict_policy": "never_overwrite_real_directory"
    },
    {
      "name": "ppt-deck-pro-max",
      "required_for": ["new_generation", "adapt_generation"],
      "install_source": "external_adopted_or_release_bundle",
      "min_cli_version": "0.1.0",
      "cli": "ppt-deck-pro-max",
      "required_capabilities": [
        "ppt_deck_pro_max.generate.v1",
        "ppt_deck_pro_max.handback.v1"
      ],
      "optional_capabilities": [],
      "schema_versions": {
        "generation_result_input": "ppt_deck_pro_max_generation_result.v1",
        "generation_result_canonical": "deck_generation_result.v1"
      },
      "agent_targets": {
        "codex": "~/.codex/skills/ppt-deck-pro-max",
        "claude-code": "~/.claude/skills/ppt-deck-pro-max"
      },
      "adoption_policy": "adopt_valid_external_symlink_only",
      "conflict_policy": "never_overwrite_real_directory"
    },
    {
      "name": "ppt-quality-gate",
      "required_for": ["standalone_audit", "quality_findings_import"],
      "install_source": "external_adopted_or_release_bundle",
      "min_cli_version": "0.1.0",
      "cli": "ppt-quality-gate",
      "required_capabilities": [
        "ppt_quality_gate.audit.v1",
        "ppt_quality_gate.findings.v1"
      ],
      "optional_capabilities": [],
      "schema_versions": {
        "quality_findings_input": "deck_master_quality_findings.v1",
        "quality_report_canonical": "deck_quality_report.v1"
      },
      "agent_targets": {
        "codex": "~/.codex/skills/ppt-quality-gate",
        "claude-code": "~/.claude/skills/ppt-quality-gate"
      },
      "adoption_policy": "adopt_valid_external_symlink_only",
      "conflict_policy": "never_overwrite_real_directory"
    },
    {
      "name": "ppt-master",
      "required_for": ["render_export_optional"],
      "install_source": "optional_external_adopted_or_release_bundle",
      "min_cli_version": "0.1.0",
      "cli": "ppt-master",
      "required_capabilities": [
        "ppt_master.render.v1",
        "ppt_master.handback.v1"
      ],
      "optional_capabilities": [],
      "schema_versions": {
        "render_result": "deck_master_render_result.v1"
      },
      "agent_targets": {
        "codex": "~/.codex/skills/ppt-master",
        "claude-code": "~/.claude/skills/ppt-master"
      },
      "adoption_policy": "adopt_valid_external_symlink_only",
      "conflict_policy": "never_overwrite_real_directory"
    }
  ]
}
```

### 4.3 Setup Status v2

新增或扩展：

```text
docs/contracts/setup-status.v2.schema.json
```

建议输出：

```json
{
  "schema_version": "deck_master_setup_status.v2",
  "status": "degraded_ready",
  "install_ready": true,
  "workspace_ready": true,
  "production_ready": true,
  "full_suite_ready": false,
  "capabilities": {
    "deck_master.run.v1": "ready",
    "ppt_library.search.v1": "blocked_cli_missing",
    "ppt_deck_pro_max.generation.v1": "ready",
    "ppt_quality_gate.audit.v1": "missing",
    "ppt_master.render.v1": "optional_missing"
  },
  "task_readiness": {
    "full_deck_workflow": "degraded_ready",
    "library_sourcing": "blocked",
    "new_generation": "ready",
    "standalone_audit": "blocked",
    "render_export": "optional_missing"
  },
  "next_command": "deck-master suite-repair --target codex",
  "next_agent_action": "Proceed with Deck Master run if no library/audit/render capability is required; otherwise guide suite repair."
}
```

Rules:

- `next_command` 给 Agent 执行。
- `next_agent_action` 给 Agent/用户理解。
- `setup-status --include-suite` 默认 JSON 输出，`--output json` 是兼容参数。
- `full_suite_ready=false` 不必阻断所有 run；应由 `task_readiness` 决定当前任务能否继续。

### 4.4 Status 枚举

必须支持：

```text
ready
missing
optional_missing
wrong_symlink
real_dir_conflict
external_adoptable
external_version_mismatch
cli_missing
doctor_failed
schema_incompatible
capability_missing
permission_denied
unsafe_source_config
blocked_cli_missing
```

### 4.5 Pure-Read Inspection Contract

新增或拆分纯读能力：

```text
scripts/runtime/setup_status.py
scripts/skills/*
```

要求：

- 提供纯读 setup inspection，例如 `inspect_setup_status(...)`，供 `setup-status` 和 Review Cockpit readiness API 调用。
- 提供纯读 skill link inspection，例如 `inspect_skill_link(...)`，供 `suite-status` 调用。
- inspection 不得写 `~/.deck-master/setup_events.jsonl`、`~/.deck-master/install_log.jsonl`、run `events.jsonl`、workspace 文件或任何 production artifact。
- 现有会写事件或日志的 `setup_status(..., write_event=True)`、`validate_skill()` 不能直接作为 status/readiness 默认路径。
- mutating 命令可在执行完成后写事件或日志，但命令名必须明确，例如 `setup`、`suite-install`、`suite-repair`。

## 5. CLI

新增或扩展：

```bash
deck-master suite-status [--target codex] [--target claude-code] [--output json]
deck-master suite-install [--target codex] [--target claude-code] [--include-optional]
deck-master suite-repair [--target codex] [--target claude-code]
deck-master setup-status --include-suite [--output json]
deck-master install-skill --suite --target codex --target claude-code
```

要求：

- `suite-status` non-mutating。
- `setup-status --include-suite` non-mutating。
- `deck-master` wrapper 是 public command，测试必须覆盖；开发测试可继续使用 `python3 scripts/deck_master.py`，但 docs 和 skill first checks 必须使用 public command。
- `suite-install` idempotent。
- `suite-repair` 不得覆盖真实目录。
- 所有命令支持 JSON 输出，供 Agent 判断下一步；默认输出保持当前 CLI 的 JSON 行为。
- 若实现需要改现有 `install-skill`，必须保持单 skill 安装能力兼容，suite install 只能扩展现有行为。

## 6. Routing Guard

Deck Master skill docs 必须改成：

```text
If user explicitly names Deck Master:
1. Run non-mutating setup-status --include-suite --output json first.
2. If setup is not production_ready, enter first-run setup ceremony; do not create or modify production run.
3. If user says continue, resolve active/last run first; do not create a new run unless user explicitly asks.
4. If setup is production_ready and no active run applies, then call deck-master start/create-run.
5. If companion skill is used inside an active Deck Master run, import result through Deck Master before reporting completion.
```

## 7. First-Run Setup Ceremony

Skill docs 必须包含：

1. Agent loads Deck Master skill。
2. Agent runs `setup-status --include-suite --output json`。
3. 如果缺 workspace，询问用户 active workspace。
4. 用户确认后运行 setup。
5. 验证 suite status。
6. 验证 Review Cockpit health。
7. 输出短 readiness summary 和 next action。

禁止在可执行时只给用户裸 CLI 命令。

## 8. 测试

必须覆盖：

- temporary HOME 下 suite install 创建 required links。
- 重复 suite install idempotent。
- valid symlink 可被识别。
- wrong symlink 可被报告。
- real directory conflict 不被覆盖。
- required companion missing 被报告。
- optional companion missing 不阻断 setup/status。
- missing CLI 被报告为 capability blocked。
- version mismatch 被报告。
- permission denied 被报告。
- `setup-status --include-suite` 不创建 run、不改 workspace。
- `setup-status --include-suite` 和 `suite-status` 在 temporary HOME 下不新增文件、不改变已有文件 mtime。
- malformed external skill，例如缺 YAML frontmatter、缺 `name`、缺 `description`、脚本引用不存在，会被报告为 `schema_incompatible` 或 `capability_missing`。
- `deck-master --help`、`deck-master setup-status --include-suite --output json`、`deck-master suite-status --output json` 可执行。
- `install-skill --suite` 不破坏单 skill 安装与 validate/uninstall 流程。
- setup 未 production_ready 时，Deck Master 不执行 start/create-run。

## 9. 验收标准

- Agent 点名 Deck Master 时，第一步是 non-mutating readiness check。
- `setup-status --include-suite` 返回 install/workspace/production/suite/capability/task_readiness。
- Suite install/reinstall 不破坏现有用户目录。
- Codex / Claude Code skill dirs 只使用 soft links。
- Suite install 复用现有 skill installer 或在其附近扩展，不创建第二套安装系统。
- Companion missing 时有明确 next_agent_action。
- v0.9.11 production guards 保持有效。

## 10. 给 Codex 的执行提示

```text
你正在开发 MainQuestAI/Deck-Master v0.9.12a：Suite Runtime Foundation。

目标：实现 suite install/status/repair、companion manifest v2、setup-status v2、first-run routing guard。

禁止：
- 不实现 companion 深业务逻辑。
- 不覆盖真实 skill directory。
- 不新增内置 LLM provider。
- setup/status/suite-status 命令不得写 HOME 日志、run artifact 或 workspace 文件。
- 不临时创建未在 source matrix 中定义来源的 companion skill 目录。

完成后输出：
- 修改文件清单。
- 新增/修改 CLI。
- JSON schema。
- 测试命令和结果。
- 已知限制。
```
