# P1 细化实现稿 — PPT Master Backend Certification

日期：2026-07-03
状态：Implemented locally (2026-07-03)
对应任务包：[`../tasks/P1-ppt-master-backend-certification.md`](../tasks/P1-ppt-master-backend-certification.md)

## 1. 目标

把 `hugohe3/ppt-master` 收成 Deck Master 可以正式识别的 production backend package，并完成本轮最小闭环：

1. `ppt-master` skill 根目录存在 Deck Master 可读 manifest
2. manifest 明确声明 `render / smoke / writeback`
3. `ppt-master` 自带一个最小 smoke 命令
4. Deck Master 当前 verifier 能把它识别为 `production_capable=true`

## 2. 当前事实

### 2.1 外部 git 真源

本机当前可用、且 remote 指向 `https://github.com/hugohe3/ppt-master.git` 的 git 仓是：

```text
<ppt-master-backend-repo>
```

当前 HEAD：

```text
668131f0ac05289c169a05a66c03182066fdccaf
```

说明：

1. `~/Downloads/ppt-master` 只有文件拷贝，不是 git 仓
2. `~/.codex/skills/ppt-master` 是安装态目录，不适合作为版本追溯真源

因此本轮实现先以这份本机 git 仓作为 P1 开发落点。

### 2.2 Deck Master 当前识别规则

当前 `scripts/runtime/builder_backend.py` 已经具备基础识别能力，要求：

1. `SKILL.md` frontmatter 合法
2. `references/`、`scripts/`、`templates/` 非空
3. 存在 `deck-master-backend.json` 或 `capability.json`
4. `operations` 至少包含：
   - `render`
   - `smoke`
   - `writeback`

当前阻断根因非常明确：本机安装态缺少 backend manifest，因此 verifier 会输出：

1. `backend capability manifest is missing or invalid`
2. `backend capability manifest lacks operations: render, smoke, writeback`

### 2.3 当前测试覆盖缺口

`tests/test_skill_installation.py` 目前只覆盖了“完整 real dir，但没有 backend manifest”的路径，预期仍是：

- `production_capable=false`

它还没有覆盖：

1. 完整 real dir + 合法 backend manifest
2. manifest 声明 required operations 后应变成 `production_capable=true`
3. malformed manifest / operation 缺失的负向路径

## 3. 本轮实现范围

## 3.1 外部 `ppt-master` 仓

新增三个文件：

1. `skills/ppt-master/deck-master-backend.json`
2. `skills/ppt-master/scripts/deck_master_backend_smoke.py`
3. `skills/ppt-master/references/deck-master-backend-integration.md`

## 3.2 Deck Master 主仓

本轮只做最小适配：

1. 如有必要，给 `builder_backend.py` 增加 manifest 附加信息输出
2. 补 `tests/test_skill_installation.py` 的生产后端正向与负向覆盖

本轮不做：

1. `backend bind`
2. capability lock `external_dependencies[]`
3. RC gate 新检查
4. Review Desk 状态扩展

补充约束：

5. 本轮不能把 `manifest ready` 直接写成 `client delivery ready`
6. 如当前 Deck Master 生产 build 仍走内部 `contract_smoke`，P1 交付报告必须显式保留这条未闭环事实

## 4. 设计方案

## 4.0 预审结论吸收

本轮实现先吸收以下约束：

1. 认证不能停留在“JSON 声明存在”
2. smoke 必须留下真实可执行证据
3. P1 可以建立认证基础，但不能借此提前宣告客户交付已闭环
4. 多 target 场景下的全局 ready 口径问题，记录为后续主仓任务风险，不在本轮顺手扩展

## 4.1 backend manifest 设计

文件：

```text
skills/ppt-master/deck-master-backend.json
```

建议结构：

```json
{
  "schema_version": "deck_master_backend_manifest.v1",
  "name": "ppt-master",
  "operations": ["render", "smoke", "writeback"],
  "runtime": {
    "operations": ["render", "smoke", "writeback"],
    "smoke_command": "python3 scripts/deck_master_backend_smoke.py",
    "default_command": "python3 scripts/project_manager.py",
    "skill_root": "skills/ppt-master"
  },
  "contracts": {
    "outputs": ["deck_render_result.v1", "deck_render_result.v2"],
    "canonical_artifact": "render_results/render_result.json"
  },
  "writeback": {
    "render_result_path": "render_results/render_result.json"
  }
}
```

设计理由：

1. 顶层 `operations` 和 `runtime.operations` 同时保留，兼容 Deck Master 当前解析逻辑
2. `smoke_command` 为 P2 的 `backend verify` 预留
3. `contracts.outputs` 与 Deck Master 现有 `ppt-master` capability copy 对齐
4. `canonical_artifact` 与当前 Deck Master 的 render handback 路径对齐
5. 固定 schema 名称，避免任意 JSON 冒充认证 manifest

## 4.2 smoke 脚本设计

文件：

```text
skills/ppt-master/scripts/deck_master_backend_smoke.py
```

### 命令形态

默认命令：

```bash
python3 scripts/deck_master_backend_smoke.py
```

可选保留输出目录：

```bash
python3 scripts/deck_master_backend_smoke.py --output-dir /tmp/ppt-master-backend-smoke
```

### smoke 行为

脚本使用 Python 标准库完成以下检查：

1. skill root 可定位
2. `SKILL.md` 存在
3. `references/`、`scripts/`、`templates/` 非空
4. `deck-master-backend.json` 可解析
5. manifest 中 required operations 完整
6. 关键脚本存在：
   - `project_manager.py`
   - `finalize_svg.py`
   - `svg_to_pptx.py`

### contract smoke 行为

脚本额外生成一个最小临时输出：

1. 在临时目录或 `--output-dir` 下创建：
   - `exports/ppt-master-contract-smoke.pptx`
   - `render_results/render_result.json`
2. `render_result.json` 使用 `deck_render_result.v2`
3. payload 至少包含：
   - `schema_version`
   - `run_id`
   - `tool`
   - `status`
   - `artifact_path`
   - `page_count`
   - `source_fingerprint`
   - `artifacts`
4. smoke 结果记录执行命令、退出码、输出目录，供后续 `backend verify` 或人工审计复用

### smoke 输出

脚本 stdout 输出一个 JSON 结果，至少包含：

```json
{
  "status": "pass",
  "skill_root": "...",
  "manifest": "...",
  "smoke_output_dir": "...",
  "checks": {
    "skill_md": true,
    "required_dirs": true,
    "manifest": true,
    "operations": true,
    "entry_scripts": true,
    "contract_smoke_output": true
  }
}
```

失败时 exit code 非 0，并输出失败原因。

## 4.3 Deck Master verifier 最小适配

当前 `builder_backend.py` 的 operation 解析已经可用，所以本轮原则上不改 verifier 主逻辑。

只有在以下两种情况之一出现时才补最小适配：

1. 需要把 manifest 路径或 smoke command 暴露到 status payload，便于测试断言
2. 需要修正 operation token 解析，确保 `render / smoke / writeback` 被稳定识别

如无必要，本轮保持 `builder_backend.py` 逻辑不扩展。

## 4.4 测试设计

主仓测试文件：

```text
tests/test_skill_installation.py
```

### 测试辅助调整

将 `_write_full_ppt_master_skill()` 扩展成可选写入 backend manifest，例如：

```python
_write_full_ppt_master_skill(with_backend_manifest: bool = False)
```

### 新增测试

1. `full package + manifest + required operations -> production_capable=true`
2. `full package + malformed manifest -> production_capable=false`
3. `full package + manifest but missing operation -> production_capable=false`
4. `full package + manifest but missing key script -> production_capable=false`，或保留为已知缺口并在报告中明确声明

### 保留现有测试

现有“完整目录但无 manifest 仍为 `production_capable=false`”测试保持不变，作为基线负向样本。

## 5. 实施步骤

1. 在外部 `ppt-master` 仓新增 manifest
2. 在外部 `ppt-master` 仓新增 smoke 脚本
3. 在外部 `ppt-master` 仓新增 Deck Master backend integration 文档
4. 在 Deck Master 主仓补测试辅助与正负向测试
5. 运行 focused verification

## 6. 验证计划

外部仓：

```bash
python3 skills/ppt-master/scripts/deck_master_backend_smoke.py
python3 skills/ppt-master/scripts/deck_master_backend_smoke.py --output-dir /tmp/ppt-master-backend-smoke
```

主仓：

```bash
python3 -m unittest tests.test_skill_installation
python3 - <<'PY'
from scripts.runtime.builder_backend import builder_backend_status
import json
print(json.dumps(builder_backend_status(), ensure_ascii=False, indent=2))
PY
```

## 7. 风险

### 风险 1：外部仓当前 worktree 非干净

当前 git 真源已有无关改动：

- `skills/ppt-master/scripts/source_to_md/ppt_to_md.py`
- `skills/ppt-master/.venv`

处理方式：

1. 本轮只新增文件
2. 不接触已有修改文件
3. 最终报告明确区分“本轮新增”与“原有未清工作区”

### 风险 2：contract smoke 容易过重

如果 smoke 直接依赖真实导出链路，会把 P1 做成另一个 A4/P5。

处理方式：

1. smoke 仅验证 package 健康和最小 render result 输出
2. 不接入真实 Playwright / PPTX 渲染依赖
3. 真正 production 行为在后续 `backend verify`、benchmark、RC 中继续验证

### 风险 3：主仓当前 build 路径仍是 internal contract smoke

影响：

1. 即使 P1 成功，Deck Master 也可能仍未真实调用外部 backend
2. 如果状态口径处理不严，会提前误导为“生产可交付”

处理方式：

1. 在 P1 报告中单列“仍未闭环事实”
2. P2 开始承接 backend bind / verify 和状态真相治理
3. P5 才承担最终客户交付闭环的放行判断

## 8. 实现前必须确认的事实

1. P1 的目标口径是“建立可认证基础”，还是“认证后即允许 production build 真实外调”
2. 外部 `ppt-master` 的唯一 git 真源是否固定为 `<ppt-master-backend-repo>`
3. `writeback` 与主仓现有 `handback` 命名是否视为同一 contract 概念
4. smoke 的最小交付标准是否只要求 `render_result` 写回样本，还是还要求最小 PPTX 产物
5. 是否要求 smoke 顺带校验关键 Python 依赖可用

## 9. 完成定义

满足以下条件，可认为 P1 完成：

1. 外部 `ppt-master` 仓存在 `deck-master-backend.json`
2. 外部 `ppt-master` 仓存在可运行的 `deck_master_backend_smoke.py`
3. 外部 `ppt-master` 仓存在 Deck Master backend integration 文档
4. Deck Master 当前 verifier 可识别 `production_capable=true`
5. `tests/test_skill_installation.py` 对正负向路径都有覆盖
6. P1 交付报告已明确列出当前仍未闭环的 production/client-delivery 事实

## 10. 本轮实装结果

已完成：

1. `ppt-master` 外部真源仓已补：
   - `deck-master-backend.json`
   - `scripts/deck_master_backend_smoke.py`
   - `references/deck-master-backend-integration.md`
2. Deck Master 主仓已补：
   - `builder_backend.py` 认证收紧
   - `installer.py` 状态真相修正
   - `build.py` / `run_state_resolver.py` runtime 未接通时继续阻断 production render
   - `tests/test_skill_installation.py`
   - `tests/test_build_runtime.py`
3. 本机 live backend `~/.codex/skills/ppt-master` 已同步认证文件，默认运行态已能识别：
   - `production_backend_ready=true`
   - `render=blocked`
   - `client_delivery_ready=false`

真实验证：

1. `python3 -m unittest tests.test_skill_installation` 通过
2. `PYTHONPATH=scripts python3 -m unittest tests.test_skill_installation tests.test_build_runtime tests.test_run_state_resolver` 通过
3. 外部 smoke 两次执行通过
4. smoke 产出的 `render_result.json` 已通过 `validators.companion_tools.validate_render_result`
5. `python3 scripts/deck_master.py suite-status --target codex --output json` 已确认：
   - backend 已认证
   - render runtime 仍阻断
   - client delivery 仍阻断

当前仍未闭环：

1. Deck Master 真实 render runtime 还未接到外部 `ppt-master`
2. `client_delivery_ready` 仍应保持 `false`
3. 后续由 `P2/P3/P5` 继续承接 bind、bridge、benchmark、RC gate 闭环
