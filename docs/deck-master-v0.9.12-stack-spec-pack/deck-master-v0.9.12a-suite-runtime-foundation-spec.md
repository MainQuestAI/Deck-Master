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

### 4.1 Companion Manifest v2

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
      "name": "ppt-library",
      "required_for": ["library_sourcing", "asset_feedback"],
      "install_source": "external_cli_with_bundled_skill_docs",
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
    }
  ]
}
```

### 4.2 Setup Status v2

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
  "next_agent_action": "Proceed with Deck Master run if no library/audit/render capability is required; otherwise guide suite repair."
}
```

### 4.3 Status 枚举

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
- `suite-install` idempotent。
- `suite-repair` 不得覆盖真实目录。
- 所有命令支持 JSON 输出，供 Agent 判断下一步。
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
- setup/status 命令不得产生 production run 副作用。

完成后输出：
- 修改文件清单。
- 新增/修改 CLI。
- JSON schema。
- 测试命令和结果。
- 已知限制。
```
