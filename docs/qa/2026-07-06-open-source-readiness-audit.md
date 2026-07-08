# Deck Master 开源发布就绪评审

- 日期：2026-07-06
- 评审范围：代码成熟度 / 项目基建成熟度 / 产品成熟度 三维度
- 评审方式：三个 sub-agent 分头评审，各自取证后汇总
- 评审目标：判定 Deck Master 距离正式开源版本是否 ready，列出 gap 并给出执行路径
- 总体判定：🔴 **当前 Not Ready**，但核心代码无需返工，gap 集中在「开源发布工程 + 设计系统落地 + 产品故事对齐」三类非核心代码工作

---

## 一、三维度就绪判定

| 维度 | 就绪度 | 一句话结论 |
|---|---|---|
| **代码成熟度** | 🟡 Almost | 架构、质量、测试、安全均达标（893 测试全过、0 CVE、0 注入面、错误分类成熟），但缺 LICENSE 是法律硬阻塞，外加无 lint/type 强制、硬编码作者路径、~30MB QA 截图入库。**核心代码本身已 ready，无需重构。** |
| **项目基建成熟度** | 🔴 Not Ready | 缺 LICENSE、缺贡献者文档、开发依赖未声明、版本/tag 不一致、`.gstack` 内部 QA 产物入库、README 首屏内部化——任一项都构成对外发布硬阻断。 |
| **产品成熟度** | 🔴 Not Ready | CLI 契约层 ready，但 Web UI 在 DESIGN.md 五条核心锁定（字体/去玻璃/大圆角/主动作暖铜/色板）上**全面偏离**，产品故事在 README↔DESIGN.md↔前端命名三处不自洽，且 Web UI 无用户文档、无截图、无 demo 引导。 |

**总体结论：底子很扎实（代码与测试层面几乎不用动），gap 全部集中在「开源发布工程 + 设计系统落地 + 产品故事对齐」三类非核心代码工作上。** 闭合 Phase 1 的 7 个 Blocker 即可升到 🟡 Almost；再做完 Phase 2 的 Major 即可达 ⬜ Ready。

---

## 二、Blocker 级 Gap（开源前必须闭合，共 7 项）

| # | 维度 | 问题 | 证据 | 修复 |
|---|---|---|---|---|
| **B1** | 代码+项目 | **无 LICENSE 文件**，仓库默认"全保留权利"，外部无法合法使用/贡献 | `git ls-files` 无 LICENSE | 新增 `LICENSE`（建议 MIT 或 Apache-2.0，与 python-pptx 兼容）；README + manifest 补 license 声明 |
| **B2** | 产品 | **字体未加载**：Satoshi/Geist/IBM Plex Mono 全 fallback 到 system-ui/monospace，设计身份未实现 | `index.html:7-8`（无字体 link）；`style.css:23-26`（无 @font-face） | index.html `<head>` 加 Google Fonts(Geist+IBM Plex Mono)+Fontshare(Satoshi) link，或自托管 |
| **B3** | 产品 | **主动作按钮白底黑字**（`.btn-cta{background:#fff;color:#000}`），非琥珀铜 #E09043，破坏"冷底暖点"核心张力 | `style.css:518-519`；`app.js:1898` | `.btn-cta` 改 `background:var(--accent-action); color:var(--ink-base)`，仅主动作用 |
| **B4** | 产品 | **玻璃面板仍存在**（`.glass-panel`/`.bottom-drawer` 用 `backdrop-filter: blur`），违反"去玻璃改实面+发丝边" | `style.css:141-148,841-842`；`index.html:73,121,155,247` | 移除 backdrop-filter，改 `background:var(--surface-1)` 实面 + 1px hairline |
| **B5** | 产品+项目 | **README 完全没提 Web UI/审查台**，产品故事与 DESIGN.md(localhost Web UI 审查面板)脱节，新用户不知有 Web UI | `README.md`（grep web ui/preview/审查 仅命中 browser smoke） | README 重写首屏：产品定位→受众→一行启动审查台→截图→badge；把"Production Closure"细节下沉 docs |
| **B6** | 产品 | **前端命名全用"工作台"**，偏离 IA v1 锁定身份"审查台/审稿桌" | `index.html:6,15`；app.js ~25 处 | 统一改"审查台"文案 + `<title>` |
| **B7** | 项目 | **版本号无单一真相且 tag 严重落后**：git tag 仅 `V0.9.8`，manifest=1.1.0，README 链 v0.9.14，planning 已到 v1.3.0 | `git tag -l`；`skills/manifest.json:3`；`README.md:35` | 定 semver 单一来源（manifest），补打 tag，README 链接更新到 v1.1.0 |

> 说明：B2–B6 直接决定 AGENTS.md 锁定的"严肃工具感"记忆点是否在交付物上成立——不解决就开源，等于对外发布了一个偏离自家设计源真相的版本。

---

## 三、Major 级 Gap（开源前强烈建议闭合，共 14 项）

### 项目/发布工程类

| # | 问题 | 证据 | 修复 |
|---|---|---|---|
| M1 | 无 CONTRIBUTING / CODE_OF_CONDUCT / SECURITY policy | 根目录与 docs/ 全量搜索无 | 新增三件套（Contributor Covenant + 漏洞上报流程） |
| M2 | 开发/测试依赖未声明，干净机器无法跑测试（CI 硬编码 `pip install pytest jsonschema`） | `requirements.txt:5`；`ci.yml:37` | 新增 `requirements-dev.txt` 或 `pyproject.toml`，CI 改读它 |
| M3 | 无 `pyproject.toml`/`setup.py`，不可 pip 安装、无标准化入口 | 根目录无 packaging 文件 | 加最小 pyproject + `deck-master` console script 入口 |
| M4 | 无 lint/format/type/precommit 配置（代码已写满 type hint 却不强制） | 根目录无 ruff/mypy/precommit | 加 `pyproject.toml` 配 ruff+black+mypy + `.pre-commit-config.yaml`；前端加 prettier/eslint |
| M5 | `.gstack/` 已 `.gitignore` 但 36 个内部 QA 报告/截图仍 tracked | `git ls-files .gstack/`=36 | `git rm -r --cached .gstack/`；同步清 `.impeccable/`/`.gbrain-source`/`.claude/` |
| M6 | ~30MB QA PNG 截图入库致仓库膨胀 | `docs/qa/*.png`(5.5MB)、`.gstack/screenshots/*`(20+) | 截图移出主仓（release artifact / git-LFS / 外部图床） |
| M7 | AGENTS.md/CLAUDE.md 是内部 agent 指引（中文、"老板"、gstack/gbrain 机器 pin），对人类贡献者不友好且部分重复 | `AGENTS.md:3,10,11`；`CLAUDE.md` | 拆分：人类向 CONTRIBUTING；CLAUDE.md 机器配置移出仓库或入 .gitignore |

### 产品/设计系统类

| # | 问题 | 证据 | 修复 |
|---|---|---|---|
| M8 | Skill OS 阶段进度用 Tailwind 默认色（#3b82f6 蓝/#10b981/#f59e0b/#ef4444），绕过 DESIGN.md 色板，蓝色是额外强调色 | `style.css:1523-1577` | 全部替换为 --status-success/warning/error/info + P0–P3 token |
| M9 | 大圆角遍地（status-bar 28px / glass-panel 20px / 子卡 22px / page-card 16px / decision 18px / preview 20px），违反"sm 2 / md 4" | `style.css:157,147,209,609,988,763,93` | 统一降到 2–4px，pill 状态保留 999px |
| M10 | 装饰光球 `.ambient-light-container`/`.light-orb` CSS 仍保留，违反"删除一切装饰光球" | `style.css:110-139` | 删除该段 CSS |
| M11 | IA v1 动作收敛未完成：右栏 `.action-grid` 仍 4 同权按钮，且与中栏 action-bar 主动作重复 | `index.html:164-169`；`app.js:2504-2507` | 按 IA v1 §6/§7 拆为"主动作(审批)+次动作"，移除重复项 |
| M12 | 顶部 `.header-actions` 仍常驻"新建项目"+"提交审批"，与当前 run 审查争抢注意力，违反 IA v1 §6 降权 | `index.html:58-59` | "新建项目"降为次入口/菜单，"提交审批"按阶段条件显示 |
| M13 | box-shadow 用于非浮层（status-bar / preview img / logo 发光），违反"阴影仅用于浮层/抽屉" | `style.css:162,776,311` | 移除非浮层阴影，预览图改 hairline 边框 |
| M14 | 无 Web UI 启动文档、无截图/GIF、无一键 demo，新用户无法 5 分钟看到价值 | quick-start.md/README 无 server.py 指引 | quick-start 加"启动审查台"段 + 提交 1–2 张截图 + `scripts/demo.sh` |

---

## 四、Minor 级 Gap（开源后可补，共 11 项）

| # | 问题 | 修复 |
|---|---|---|
| m1 | 硬编码作者路径 `GENERATION_BRIDGE_REPO_PATH` 并报告 `bound_verified`（`builder_backend.py:39,418,425`） | 改环境变量/配置读取，未配置报 `unbound` |
| m2 | `.github` 仅 `ci.yml`：无 issue/PR 模板、无 CODEOWNERS、无 dependabot | 加模板 + CODEOWNERS + dependabot |
| m3 | 无 Makefile/Dockerfile/devcontainer | 加 `make setup/test/smoke` 一键开发环境 |
| m4 | 无统一 CHANGELOG.md；文档中英混杂 | 汇总 Keep a Changelog；统一语言策略 |
| m5 | 无 MAINTAINERS/GOVERNANCE/沟通渠道/公开 ROADMAP | 新增 + README 加 Discussions 链接 |
| m6 | 语言切换 `#lang-toggle` 是 disabled 死控件，无 handler（DESIGN.md 承诺"中英切换"） | 实现切换，或暂从 UI 移除 |
| m7 | skeleton loading 未实现，加载态仅文字"载入中" | 关键区域加 skeleton |
| m8 | 多处手写浅色（#ffd4d0/#ffb7b1/#f1ca95…）未走 token | 统一到 text-primary/--status-* |
| m9 | `.btn:active` 用 `scale(.99)` 微弹跳 | 改纯 background/border 过渡，去 transform |
| m10 | jsonschema 运行时可选依赖却未声明 | 进 `requirements-dev.txt` |
| m11 | 无面向终端用户的 user-guide；docs/ 多为带日期内部评审底稿 | 新增 `docs/user-guide.md`；内部底稿移 `docs/archive/` |

---

## 五、推荐执行路径

**Phase 1 — 解除阻断（目标：🟡 Almost）**
闭合 7 个 Blocker：LICENSE → 字体加载 → 主动作暖铜 → 去玻璃 → README 重写（含 Web UI 定位）→ 命名改"审查台"→ 版本/tag 对齐。
> 这一批决定"能不能合法开源 + 严肃工具感记忆点是否成立"，建议一个 PR 收口。

**Phase 2 — 工程化与设计落地（目标：⬜ Ready）**
闭合 14 个 Major：贡献者三件套 + dev 依赖 + pyproject + lint/type + `.gstack` 清理 + 截图瘦身 + AGENTS/CLAUDE 拆分；设计侧色板/圆角/光球/动作收敛/阴影/IA 降权/截图 demo。
> 可拆成「发布工程」与「设计系统落地」两个并行 PR。

**Phase 3 — 打磨（开源后持续）**
11 个 Minor：模板/Makefile/CHANGELOG/治理/skeleton/死控件/token/弹跳/bridge 路径/终端用户文档。

---

## 六、总体结论

**Deck Master 不需要返工核心代码**——架构分层、契约测试、安全姿态都已达开源水准。真正卡住发布的是三类"交付物未对齐锁定真相"的工作：

1. **法务与发布工程缺位**（LICENSE、贡献者文档、依赖声明、版本/tag、仓库卫生）——纯流程，工作量小但不可绕。
2. **设计系统未落地**（字体/玻璃/圆角/主动作配色/色板五条核心偏离）——AGENTS.md 已把 DESIGN.md 钉为源真相，但前端实现没跟上，这是最该优先闭合的产品 gap。
3. **产品故事不自洽**（README 不提 Web UI、前端叫"工作台"、版本号过时）——对外身份模糊，开源访客会误以为是 CLI 构建工具。

闭合 Phase 1 的 7 个 Blocker 是最小可发布前置项；做完即可进入有限开源（🟡 Almost）。要达到正式开源（⬜ Ready），Phase 2 的设计系统落地与发布工程必须一并完成。

---
---

# 附录 A：代码成熟度评审报告（sub-agent 全文）

## 1. 评审范围与方法

**覆盖范围**：仓库根目录、`scripts/`（143 个 .py 文件，30 个子包）、`tests/`（102 个测试文件）、`scripts/preview/static/`（Web UI）、`skills/`、`.github/workflows/`、`docs/`、所有 manifest（`requirements.txt`、`.gitignore`）。实际打开了 `deck_master.py`、`builder_backend.py`、`rc_gate.py`、`server.py`、`manifest.py`、`DESIGN.md`/`AGENTS.md`/`README.md` 等核心文件读取上下文。

**实际执行的检查**：
- `python3 -m unittest discover -s tests` → **893 tests, OK (skipped=3)**（33.5s）
- CI 的 15 个 pytest 合约测试 → **172 passed**
- `pip-audit` → 仅 1 个漏洞，且是 pip 工具自身（PYSEC-2026-196），项目依赖 0 CVE
- grep 全量扫描：`TODO/FIXME/HACK`、`secret/token/password`、`eval/exec/shell=True`、`/Users/` 硬编码路径、`console.log`、`innerHTML`、`# type: ignore`、broad `except`、CORS、第三方版权声明
- `git ls-files` 核查：LICENSE、committed artifacts、tracked-ignored 文件、大文件

**跳过及原因**：未跑 `npm audit`（项目无 package.json，Web UI 为纯 vanilla HTML/CSS/JS，无 JS 依赖）；未跑 mypy（项目无 mypy 配置，无强制类型检查可跑）；浏览器 smoke 跳过（需浏览器环境，CI 中亦为可选）。

## 2. 架构与结构

**结论：架构成熟，分层清晰，无循环依赖。** 这是本项目最突出的优点。

- **模块化良好**：`scripts/` 是正规 Python 包（27 个 `__init__.py`），30 个子包按职责切分（`runtime/`、`quality/`、`workflow/`、`benchmark/`、`generation/`、`preview/`、`planning/`、`delivery/` 等），单一职责明确。`runtime/` 子系统 21 个文件，命名聚焦（`build.py`、`render.py`、`rc_gate.py`、`run_state.py`、`schema.py`、`artifact_validator.py`）。
- **god file 是良性分发器**：`scripts/deck_master.py` 3049 行、132 个子命令，看似巨大，但经核查子模块**从不反向 import 它**（`grep import deck_master` 在 scripts/ 下 0 命中），它是纯顶层 CLI dispatcher，命令函数多为 1–2 行委托（如 `command_approval_submit` `scripts/deck_master.py:896-899` 直接调 `submit_approval(...)`）。无循环依赖。
- **边界清晰**：前端（`preview/static/` vanilla JS）↔ 本地 HTTP server（`preview/server.py` + `workspace_api.py`）↔ CLI/runtime 模块，三层边界干净。Web UI 无构建步骤、无 node 依赖，符合"local-first 审查台"定位。
- **唯一结构瑕疵**：`preview/static/app.js` 2537 行单文件、`skills/installer.py` 2191 行、`preview/server.py` 1567 行偏大，但均有明确用途，非上帝文件。

## 3. 代码质量

**结论：质量高于多数开源项目。错误处理、类型标注、命名均规范，技术债极低。**

- **错误分类成熟**：34 个自定义异常类，均继承 `ValueError`/`RuntimeError`，域语义清晰（`ManifestError`、`RunStateError`、`BenchmarkRunError`、`BrowserSmokeUnavailable` 等，见 `scripts/runtime/rc_gate.py:28-33`、`scripts/runtime/run_state.py:23`）。
- **TODO/FIXME 几乎为零**：全 `scripts/` 仅 1 处，且是 `customer_visible_safety.py:35` 的字面字符串 `"TODO"`（数据值，非标记）。无 FIXME/HACK/XXX 堆积。
- **类型标注现代化**：全面使用 PEP 604（`str | None`、`dict[str, Any]`）；全仓仅 **5 处** `# type: ignore`，且都带精确错误码（`[import-untyped]`、`[method-assign]`、`[attr-defined]`），见 `workspace/foundation.py:53`、`rc_gate.py:286`。
- **无危险调用**：`eval(`/`exec(`/`subprocess shell=True`/`os.system(` 在 scripts/ 下 **0 命中**——无命令注入面。
- **broad except 可接受**：62 处 `except Exception`，但多有 `# noqa: BLE001` 注释说明（如 `benchmark/runner.py:215` "benchmark report should capture partial local runs"）；仅 7 处静默 `pass/continue`，均在防御性 fallback 路径。
- **print 使用合理**：CLI 工具以 `print_json()`（`deck_master.py:212`）为统一输出通道，错误走 `sys.stderr`（`deck_master.py:3044`），非滥用。
- **app.js 质量**：0 个 `console.log`；`innerHTML` 共 57 处，但动态插值**一致使用 `escapeHtml()`**（`app.js:1026,1534,1570,1592`），XSS 风险低。

## 4. 测试

**结论：测试覆盖扎实，CI 真跑且真 gate。这是强项，非 blocker。**

- **规模**：102 个测试文件，`unittest discover` 跑出 **893 tests, 全过 (skipped=3)**；pytest 合约套件 **172 passed**。
- **覆盖广度**：approval flow、artifact validator、benchmark（5 文件）、brand gate、brief intake、build manifest v2、claim evidence graph、confidentiality gate、delivery validation、draft gate v2、end-to-end autoplan、evidence gate、export quality blocking、external quality review、final readiness、generation handback、page package、sourcing plan v2、skill handoff/manifest/migration、stage contract/validation、workflow autopilot v2/cli/state 等均有专门测试。
- **CI 真跑**（`.github/workflows/ci.yml`）：① `compileall` 语法检查；② `unittest discover -s tests`；③ 15 个 pytest 合约/schema 测试；④ fixture autoplan smoke（生成 ≥10 页并校验产物存在）；⑤ RC gate smoke。PR 与 push 均触发，concurrency 取消冗余运行。
- **测试即文档**：合约测试（`test_skill_manifest.py`、`test_stage_contract_registry.py`、`test_build_manifest_v2.py` 等）即 schema 一致性的活文档。

## 5. 安全

**结论：安全姿态良好，无凭证泄露、无注入面、localhost 绑定、路径穿越已防。仅 1 处硬编码作者路径需处理。**

- **无凭证泄露**：`secret/token/password/api_key` 模式扫描 0 命中；`.env`/`.env.*` 已在 `.gitignore`，`git ls-files` 确认无 `.env`/密钥文件入库。
- **无注入面**：无 `eval`/`exec`/`shell=True`。
- **服务器安全**：默认绑定 `127.0.0.1`（`server.py:1544` `--host default="127.0.0.1"`），仅本地；无 CORS 头（本地工具不需要）。
- **路径穿越已防**：`server.py:379-383` 对 URL `run_id` 做 `.resolve()` + `startswith(root + "/")` 包含检查，不合法即抛 `ManifestError("Invalid run_id.")`。✅
- **依赖 CVE**：`pip-audit` 仅报 pip 自身 1 个（PYSEC-2026-196，工具链问题，非项目依赖）。项目唯一依赖 `python-pptx` 无 CVE。
- **唯一问题**：`scripts/runtime/builder_backend.py:39` 硬编码 `GENERATION_BRIDGE_REPO_PATH = "<ppt-deck-pro-max-bridge-repo>"`，并在 `_generation_bridge_status()`（`:411-433`）中作为 `"repo_path"` 输出、`"binding_status": "bound_verified"`、`"verified": True`。开源后他人运行会报告一个指向不存在路径的"已验证"绑定，既泄露作者家目录、又误导状态。**Major**。

## 6. 依赖与构建

**结论：依赖极简、可复现性好，但缺 lock 文件与 dev 依赖声明；有大量 QA 截图入库致仓库膨胀。**

- **依赖面极小**：`requirements.txt` 仅 `python-pptx>=0.6.21`（且为可选，缺失时优雅降级，注释已说明）。无重依赖、无 node 依赖。
- **无 lock 文件**：无 `pip-locks`/`poetry.lock`。但因仅 1 个可选依赖，可复现性风险低；CI pin Python 3.11。
- **jsonschema 未声明**：`scripts/skills/manifest.py:318` 运行时 lazy import（try/except 守卫，注释为 "dev dependency"），CI 显式 `pip install pytest jsonschema`。属可选 dev 依赖，但未进任何 `requirements-dev.txt`。**Minor**。
- **无 build 产物入库**：`dist/`、`*.pyc`、`node_modules/` 均 0 命中（`.gitignore` 正确）。
- **仓库膨胀（Major）**：22 个 >100KB 文件**全部是 QA PNG 截图**，分布在 `docs/qa/` 与 `.gstack/qa-reports/screenshots/`（最大 5.5MB，合计约 30MB+）。`runs/`、`benchmarks/results/` 产物正确地**未入库**（0 文件），但 QA 截图入库不适合开源主仓。
- **无 pyproject.toml/setup.py**：项目以 `python3 scripts/deck_master.py` 方式运行，不可 `pip install`。对开源贡献者而言是摩擦点。

## 7. 可维护性信号

**结论：代码本身可维护性好，但缺少工程化强制配置（lint/format/type/precommit）。**

- **无 lint/format/type 配置**：无 `.flake8`、`.pylintrc`、`pyproject.toml`（ruff/black/mypy）、`.pre-commit-config.yaml`、`.eslintrc`、`.prettierrc`、`tsconfig`。类型标注写得很好却不强制检查。**Major**。
- **无硬编码"仅作者本机"路径**（除 §5 的 bridge 路径外）：其余 `/Users/` 命中均为测试 fixture（`/Users/example/...`）或路径脱敏标记（`rc_gate.py:240`、`setup_status.py:154` 把 `/Users/`、`/private/` 列为待脱敏标记，实为安全实践）。
- **本地 agent 状态入库**：`.gstack/`（36 个文件，含截图与 baseline JSON）虽在 `.gitignore` 列入，却已被 track。`.impeccable/`、`.claude/`、`.gbrain-source` 为本地工具状态，对开源用户是噪音。

## 8. 开源代码门槛

**结论：缺 LICENSE 是硬门槛（Blocker）；其余开源元文件全缺；无第三方版权冲突。**

- **无 LICENSE/COPYING/NOTICE**：`git ls-files` 确认 0 命中。这是开源发布的**法律硬阻塞**——无 LICENSE 默认 "all rights reserved"，他人无权使用/修改/分发。
- **无 CONTRIBUTING/SECURITY/CODE_OF_CONDUCT/CHANGELOG**，无 issue/PR 模板。
- **无第三方版权代码**：`skills/` 为作者原创 SKILL.md 数据文件（18 个，0 个 .py，无 "copyright/adapted from" 命中）；`scripts/` 无 vendored 代码。
- **依赖 license 无冲突**：`python-pptx` 为 MIT/BSD，jsonschema 为 MIT，均兼容任意主流开源 license。

## 9. 就绪判定

- 代码层面开源就绪度：🟡 **Almost**
- 一句话结论：**代码架构、质量、测试、安全均达到开源水准（893 测试全过、无 CVE、无注入面、错误处理成熟），但缺 LICENSE 是法律硬阻塞，加上无 lint/type 强制配置、硬编码作者路径、~30MB QA 截图入库三项 Major，需闭合后方可正式开源。**

## 10. Gap 清单（按严重度排序）

| 序号 | 严重度 | 问题 | 证据(文件:行) | 建议修复 |
|------|--------|------|--------------|----------|
| C1 | Blocker | 无 LICENSE 文件，代码法律上不可被他人使用 | `git ls-files` 无 LICENSE/COPYING/NOTICE | 新增 `LICENSE`（建议 MIT/Apache-2.0，与 python-pptx 兼容），并在 README 补 license 声明 |
| C2 | Major | 无 lint/format/type 强制配置与 pre-commit | 根目录无 `.flake8`/`pyproject.toml`/`.pre-commit-config.yaml`/eslint | 加 `pyproject.toml` 配 ruff+black+mypy（type hint 已就绪，门槛低），加 `.pre-commit-config.yaml`；前端加 prettier/eslint |
| C3 | Major | 硬编码作者本机路径并报告为 "bound_verified" | `scripts/runtime/builder_backend.py:39,418,425` | 将 `GENERATION_BRIDGE_REPO_PATH` 改为环境变量/`backend_bindings.json` 读取，未配置时报告 `unbound` 而非 `bound_verified` |
| C4 | Major | ~30MB QA PNG 截图入库致仓库膨胀 | `docs/qa/b25-gate/*.png`(5.5MB)、`.gstack/qa-reports/screenshots/*`(20+ 张) | 截图移出主仓（release artifact / git-LFS / 外部图床）；`.gstack/` 已在 `.gitignore`，用 `git rm --cached` 清理已 track 的 36 个文件 |
| C5 | Major | 无 `pyproject.toml`/`setup.py`，不可 pip 安装、无标准化入口 | 根目录无 packaging 文件，仅 `python3 scripts/deck_master.py` | 加最小 `pyproject.toml`，定义 `deck-master` console script 入口，便于开源用户安装 |
| C6 | Minor | jsonschema 为运行时可选依赖却未声明 | `scripts/skills/manifest.py:318`(lazy import) + CI `pip install ... jsonschema` | 加 `requirements-dev.txt` 或 pyproject `[project.optional-dependencies]` 声明 |
| C7 | Minor | 缺开源元文件（CONTRIBUTING/SECURITY/CODE_OF_CONDUCT/CHANGELOG） | 根目录与 `.github/` 均无 | 补齐模板文件，降低社区贡献摩擦 |
| C8 | Minor | 本地 agent/工具状态入库（`.gstack/`、`.impeccable/`、`.gbrain-source`、`.claude/`） | `.gstack/` 36 个 tracked 文件；`.gitignore:5-6,25` 已列但未清 | `git rm --cached -r` 清理已 track 的本地状态，确保 `.gitignore` 实际生效 |
| C9 | Minor | 前端 `app.js` 单文件 2537 行偏大，部分 `innerHTML` 模板拼接未走 escapeHtml | `scripts/preview/static/app.js:1560,2261` | 中期可拆分模块；短期对 `${stage.label}` 等结构化数据插值也走 `escapeHtml()` 统一风格 |

**总评**：清单短且全部为工程化/打包类工作，**无一项触及核心代码重构**。闭合 Blocker #1 + Major #3/#4 后即可安全开源；#2/#5 建议在同一 PR 内完成以提升维护门槛。代码本身已就绪。

---
---

# 附录 B：项目基建成熟度评审报告（sub-agent 全文）

## 1. 评审范围与方法

**覆盖文件/目录**：根目录全量 `ls`、`README.md`、`AGENTS.md`、`DESIGN.md`、`CLAUDE.md`、`.gitignore`、`requirements.txt`、`product-capability-manifest.json`、`skills/manifest.json`、`.github/`（仅 `workflows/ci.yml`）、`docs/`（55 项，含 `quick-start.md` / `agent-guide.md` / `releases/` / `contracts/` / `schemas/`）、`scripts/`（33 子包 + `deck_master.py` 入口）、`skills/`（18 skill + manifest）、`examples/`、`tests/`（103 测试文件）、`benchmarks/`。

**实际试跑的命令**：
- `python3 scripts/deck_master.py setup-status --include-suite --output json` —— 成功输出合法 JSON（`README.md:40`）。
- `python3 scripts/deck_master.py --help` —— 成功，100+ 子命令可用，纯 Python 无强依赖。
- `/usr/bin/python3 -m pytest tests/test_skill_manifest.py -q` —— 17 passed（但仅因本机已装 pytest/jsonschema，见 §5 gap）。
- `gh run list --limit 5` —— CI 近 5 次全部 success，~30s，PR #9 走过 PR 流程。
- 全仓库 `find -iname 'license*'`、`git ls-files` 噪声扫描、`git tag -l`、README 视觉资产 grep。

**跳过**：完整 `npm install`/`pip install`（项目无 node 侧、无 setup.py；唯一 pip 依赖 python-pptx 可选）；浏览器 smoke（README 已声明可选）；未跑全量 103 测试（已抽样验证契约测试可跑）。

## 2. README 与首屏印象

README 存在但首屏体验偏内部化，对外部开发者不友好：

- **定位**：`README.md:3` 用一句话讲了"是什么"，但没有独立的「Who is this for / Installation / Quick run」人类向章节——直接跳到 `## Current Production Closure`（`README.md:5`），满屏"Real Production Closure / generation handoff v2 / final readiness gate"等内部迭代黑话，外部读者第一眼难懂。
- **badges / 截图 / demo gif**：全无（grep `badge|shield|svg|png|gif|screenshot|demo` 仅命中一处 `PPTX package` 误匹配）。无 CI badge、无 License badge、无 demo 动图。
- **安装/运行**：README 的「Start Here」直接链到 `docs/quick-start.md`，而 quick-start 第 1 步是 `setup-status`——在一台干净机器上会返回 not-ready，但 quick-start 未先讲"先装依赖/先 setup"，onboarding 略突兀。
- **贡献入口**：README 完全没有「Contributing / License」段落。

## 3. 文档体系

文档**量大且成体系**（docs/ 55 项，含 `contracts/`、`schemas/`、`releases/`、`migration/`、`planning/`、`qa/`），但存在开源关键缺口：

- ✅ `DESIGN.md` 作为设计源真相完整、有 Decisions Log 与 Risks（`DESIGN.md:80-96`），与 `AGENTS.md:7-13` 引用一致。
- ✅ `docs/quick-start.md`、`agent-guide.md`、`troubleshooting.md`、`releases/` 均存在且 README 链接全部可解析。
- ❌ **无 CONTRIBUTING.md、CODE_OF_CONDUCT.md、SECURITY.md、CHANGELOG.md**（根目录与 docs/ 全量搜索均无；docs 中"governance"命中均为产品质量治理，非社区治理）。
- ⚠️ **文档语言混杂**：README/quick-start/agent-guide 为英文，`AGENTS.md`、`DESIGN.md`、`docs/TODOS.md`、release notes 为中文——对国际贡献者是摩擦。
- ⚠️ `AGENTS.md:3` 自述"Web UI 重构线程的 AI agent 指引"，引用"老板"（`AGENTS.md:10`）——是内部 worktree 指引，非人类贡献者文档。`CLAUDE.md` 同样是机器配置（gbrain/.gbrain-source pin），与 AGENTS.md 部分重叠。

## 4. 仓库结构与卫生

`.gitignore` 基本合理，但存在已入库的噪声与本地状态：

- ✅ `__pycache__/`、`.venv/`、`.env*`、`dist/`、`node_modules/`、`rc_reports/` 均已忽略（`.gitignore:7-27`）；`.DS_Store` 未被跟踪。
- 🔴 **`.gstack/` 被 `.gitignore:25` 忽略，却有 36 个文件已被 track**（`git ls-files .gstack/` = 36），含 `qa-reports/*.md` 与 `screenshots/*.png`（如 `.gstack/qa-reports/baseline.json`、`screenshots/final-initial-preview-ui.png`）。这是"先提交后加 ignore"留下的内部 QA 产物泄漏。
- ⚠️ `runs/local-mac-v098-smoke` 残留本地 run 产物（已忽略未跟踪，但属工作树杂物）。
- ⚠️ 根目录有 `CLAUDE.md` + `AGENTS.md` + `.gbrain-source` + `.claude/` + `.gstack/` + `.impeccable/` 等多个 agent/工具本地状态目录，对"外部开发者第一次 clone"是认知噪声。
- ✅ 目录命名一致（`scripts/` 按领域分子包，`skills/` 一 skill 一目录）。

## 5. 构建与可复现性

入口可跑，但依赖声明不完整：

- ✅ `python3 scripts/deck_master.py --help` 在无 venv 下直接可用，100+ 子命令；`setup-status` 输出合法 JSON。运行时几乎零强依赖（python-pptx 可选降级，`requirements.txt:1-4`）。
- 🔴 **开发/测试依赖未在仓库声明**：`requirements.txt` 只有 `python-pptx>=0.6.21`（`requirements.txt:5`），而 CI 在 `ci.yml:37` 硬编码 `pip install --quiet pytest jsonschema`。无 `requirements-dev.txt`、无 `pyproject.toml`、无 `Pipfile`。一台干净机器按仓库声明装依赖后**无法跑测试**（本机能跑只因系统 Python 恰好预装了 pytest 8.4.2 / jsonschema 4.25.1）。
- ⚠️ 无 `Makefile`、无 `Dockerfile`、无 `.devcontainer`——没有一键开发环境脚本，贡献者需自己拼装命令。
- ⚠️ `requirements.txt` 未锁定版本（`>=0.6.21`），无 lockfile，不可复现。

## 6. CI/CD

CI 存在且绿，但覆盖面窄、无 release 自动化：

- ✅ `.github/workflows/ci.yml` 触发于 `pull_request` / `push: main` / `push: codex/**,claude/**` / `workflow_dispatch`（`ci.yml:3-10`），有 concurrency 取消（`ci.yml:15-17`）。
- ✅ CI 跑：Python 语法 compileall、unit tests、Skill OS 契约/schema 校验、fixture autoplan smoke、RC gate smoke（`ci.yml:33-119`）。
- ✅ `gh run list` 近 5 次全 success，PR #9 走过 PR 检查流程。
- ❌ **无 lint/typecheck job**（无 ruff/mypy/flake8）。
- ❌ **无自动化 release 工作流**（无 changesets/semantic-release/tag/release-please；`.github/` 仅 `ci.yml` 一个文件）。
- ❌ `.github` 下无 `ISSUE_TEMPLATE/`、无 `PULL_REQUEST_TEMPLATE.md`、无 `CODEOWNERS`、无 `FUNDING.yml`、无 dependabot 配置。

## 7. License 与法务

🔴 **Blocker 级缺口**：

- ❌ **全仓库无 LICENSE 文件**（`find -iname 'license*'` 仅命中 `.venv/` 内第三方包自带 license，均被 gitignore）。`skills/manifest.json`、`product-capability-manifest.json` 也无 `license` 字段（grep 无命中）。README 无 License 声明段。
- 无 `NOTICE` / 第三方代码标注。`skills/` 下含 `ppt-master`、`ppt-deck-pro-max` 等"legacy 兼容"skill（`README.md:27`），未标注其 license 来源。
- 法务上，没有 LICENSE 的仓库默认"保留所有权利"，外部既不能合法使用也不能贡献——这是开源发布的硬阻断。

## 8. 版本与发布

版本真相碎片化，发布流程文档化但未工程化：

- ⚠️ **版本号无单一来源且互不一致**：`git tag -l` 仅 `V0.9.8`；`skills/manifest.json:3` 是 `1.1.0`；`README.md:35` 链 `v0.9.14` release notes；`docs/planning/2026-07-03-...v1.3.0-execution-plan.md` 已规划 1.3.0。tag/manifest/README/planning 四处版本号不同步。
- ⚠️ `docs/releases/` 有 4 份 per-version release notes（v0.9.12/13/14/v1.1.0），但**无统一 CHANGELOG.md**，也无对应 git tag（v1.1.0 无 tag）。
- ✅ 发布机制本身存在且自包含：`release-build` 生成含 `bin/deck-master`+`scripts/`+`skills/`+`SHA256SUMS` 的 release tree（`quick-start.md:38-55`），支持 staging/verify/activate/rollback。
- ❌ 无打包分发物（无 pypi 包、无 npm、无 docker image），无 GitHub Releases 痕迹。release 仅以本地 release-tree 形式存在。

## 9. 贡献者上手

对外部贡献者几乎无引导：

- ❌ 无 `CONTRIBUTING.md`：分支策略、提交规范（git log 显示用 `feat:/fix:/docs:/merge:` conventional-ish，但未文档化）、PR 流程、代码风格均未写明。
- ❌ 无 issue/PR 模板，无 `good-first-issue` 标签体系，无 CODEOWNERS。
- ⚠️ `AGENTS.md` / `CLAUDE.md` 是面向 AI agent 的内部指引（中文、"老板"、gstack/gbrain 机器上下文），对人类贡献者既不友好也易误导；`AGENTS.md:11` 让改 UI 前先读两份 docs，是内部重构线程约束。
- ✅ `docs/agent-guide.md` 对 agent 路由讲得清楚，可作为人类上手参考，但同样无"如何提 PR"内容。
- ⚠️ 无一键开发环境脚本（无 `make setup` / `scripts/dev-setup.sh`）。

## 10. 治理与社区

基本缺失：

- ❌ 无 `MAINTAINERS.md` / `GOVERNANCE.md`，无维护者名单。
- ❌ 无沟通渠道声明（无 Discord/Discussions/Slack 链接）。
- ⚠️ `docs/TODOS.md` 部分充当 roadmap（列了编排层/Web 预览/反馈闭环/质量门禁状态），但缺少公开 roadmap 形态，且混在 docs 里不显眼。
- ✅ 仓库属 `MainQuestAI` 组织（PR #9 来自 `MainQuestAI/codex-...` 分支），有组织归属，但组织级治理未在本仓声明。

## 11. 就绪判定

- 项目基建层面开源就绪度：🔴 **Not Ready**
- 一句话结论：核心运行时与契约/测试/CI 已相当成熟，但**缺 LICENSE、缺贡献者文档、开发依赖未声明、`.gstack` 内部 QA 产物入库、版本/tag 不一致、README 首屏内部化**——任一项都构成对外发布的硬阻断，必须先补齐法务与发布工程基建再开源。

## 12. Gap 清单（按严重度排序）

| 序号 | 严重度 | 问题 | 证据(文件:行) | 建议修复 |
|---|---|---|---|---|
| P1 | Blocker | 无 LICENSE 文件，仓库默认"全保留权利"，外部无法合法使用/贡献 | `find` 全仓仅 `.venv/` 内有 license；`skills/manifest.json` 无 license 字段 | 新增根 `LICENSE`（建议 MIT/Apache-2.0），在 `skills/manifest.json`、README 加 license 段，规范第三方 skill license 标注 |
| P2 | Major | README 首屏内部化：无人类向 What/Who/Install/Run，无 badges/截图/demo，首段即"Current Production Closure"黑话 | `README.md:5-16`；grep 无 badge/svg/gif 命中 | 重写 README 顶部：项目定位→受众→一行安装→一行跑→demo 截图/gif→CI+License badge；把"Production Closure"细节下沉到 docs |
| P3 | Major | 无 CONTRIBUTING / CODE_OF_CONDUCT / SECURITY policy | 根目录与 docs/ 全量搜索均无 | 新增 `CONTRIBUTING.md`（分支/提交规范/PR 流程/代码风格/测试运行）、`CODE_OF_CONDUCT.md`（Contributor Covenant）、`SECURITY.md`（漏洞上报流程） |
| P4 | Major | 开发/测试依赖未在仓库声明，干净机器无法跑测试 | `requirements.txt:5` 仅 python-pptx；`ci.yml:37` 硬编码 `pip install pytest jsonschema` | 新增 `requirements-dev.txt` 或 `pyproject.toml`（含 pytest/jsonschema 及版本上限），CI 改为 `pip install -r requirements-dev.txt` |
| P5 | Major | 版本号无单一真相且 tag 严重落后；无 release 自动化 | `git tag -l` 仅 `V0.9.8`；`skills/manifest.json:3`=1.1.0；`README.md:35` 链 v0.9.14；`docs/planning/...v1.3.0` | 确定 semver 单一来源（建议 manifest version），为 v0.9.12/13/14/1.1.0 补打 tag，加 release workflow（tag 触发 GitHub Release + 发布产物） |
| P6 | Major | `.gstack/` 已被 `.gitignore:25` 忽略，但 36 个 QA 报告/截图仍被 track | `git ls-files .gstack/` = 36；`.gitignore:25` | `git rm -r --cached .gstack/` 清理已入库的内部 QA 产物，保留 ignore 规则 |
| P7 | Major | AGENTS.md / CLAUDE.md 为内部 agent 指引（中文、"老板"、gstack/gbrain 机器 pin），对人类贡献者不友好且部分重复 | `AGENTS.md:3,10,11`；`CLAUDE.md:1-30`（gbrain/.gbrain-source） | 拆分：保留 AGENTS.md 给 agent 但加英文摘要；新增面向人类的 CONTRIBUTING；CLAUDE.md 的机器配置部分移出仓库或加入 .gitignore |
| P8 | Minor | `.github` 仅 `ci.yml`：无 issue/PR 模板、无 CODEOWNERS、无 FUNDING、无 dependabot | `find .github -type f` = 仅 ci.yml | 加 `.github/ISSUE_TEMPLATE/`、`PULL_REQUEST_TEMPLATE.md`、`CODEOWNERS`、dependabot 配置 |
| P9 | Minor | 无一键开发环境：无 Makefile / Dockerfile / devcontainer | 根目录无此类文件 | 加 `Makefile`（`make setup`/`make test`/`make smoke`）或 `scripts/dev-setup.sh`；可选 devcontainer |
| P10 | Minor | 无统一 CHANGELOG.md；docs 语言中英混杂 | `docs/releases/` 4 份分版 notes；README 英文 vs AGENTS/DESIGN/TODOS 中文 | 汇总 `CHANGELOG.md`（Keep a Changelog 格式）；统一对外文档语言或提供双语策略 |
| P11 | Minor | 无 MAINTAINERS/GOVERNANCE/沟通渠道/公开 roadmap | docs 中"governance"命中均为产品质量治理非社区治理 | 新增 `MAINTAINERS.md`、README 加 Discussions/Discord 链接、把 `docs/TODOS.md` 提炼为公开 `ROADMAP.md` |
| P12 | Minor | `runs/local-mac-v098-smoke` 等本地 run 产物残留工作树 | `ls runs/` | 清理 `runs/` 并确认 `.gitignore` 已覆盖（已覆盖，仅需清工作树） |

**最小可发布前置项（必须先做）**：#1 LICENSE、#2 README 重写、#3 CONTRIBUTING+SECURITY、#4 dev 依赖声明、#5 版本/tag 对齐 + release workflow、#6 清理 `.gstack` 入库产物。完成后可从 🔴 Not Ready 升至 🟡 Almost；再补 #7–#12 即达 ⬜ Ready。

---
---

# 附录 C：产品成熟度评审报告（sub-agent 全文）

## 1. 评审范围与方法

**覆盖文件：**
- 定向文档：`README.md`、`AGENTS.md`、`DESIGN.md`、`CLAUDE.md`、`docs/2026-06-21-web-ui-ia-v1.md`、`docs/2026-06-21-web-ui-redesign-audit.md`、`docs/TODOS.md`、`docs/quick-start.md`、`docs/agent-guide.md`、`docs/troubleshooting.md`、`docs/releases/*`、`product-capability-manifest.json`。
- 前端实现（逐行对照 DESIGN.md）：`scripts/preview/static/index.html`、`scripts/preview/static/style.css`、`scripts/preview/static/app.js`（101KB，grep 关键路径 + 精读 action-bar/状态机/事件绑定）。
- 后端预览服务：`scripts/preview/server.py`（启动方式、静态服务、字体注入检查）、`scripts/preview/workspace_api.py`（占位枚举）。
- 资源：`examples/`、`.gitignore`、git 历史/tag。

**方法：** 对 DESIGN.md 六条核心锁定（字体/配色/去玻璃/圆角/动效/单点暖铜）逐条 grep + 行号取证；对 IA v1 九条验收点逐条对照实际 DOM；对功能链路按 CLI→Web UI 双表面核查死链/占位/半成品。

**跳过：** 未实际运行 Playwright/浏览器（以代码 + QA 截图文件名 + server.py 逻辑推断为准）；未跑完整 1005 测试套件（以 release notes 记录为准）。

## 2. 产品定位与故事

**它是什么 / 给谁用：** DESIGN.md 把产品明确定位为「localhost Web UI——Agent 唤起式 run 审查面板」，给售前解决方案架构师做会后客户 deck 草案审查。这个定位本身清楚、自洽、有差异化（冷底暖点的仪器面板，非 SaaS 营销页）。

**但产品故事在三个地方说不清/自相矛盾：**
1. **README 完全没提 Web UI。** README 把产品讲成「local-first Solution Deck Run OS」，全文是 CLI/skill suite/release tree/RC gate，零次提及 Web UI、审查台、localhost:5050、`scripts/preview/server.py`（`README.md` 全文 grep `web ui|preview|审查|工作台|cockpit` 仅命中 "browser smoke"）。一个开源访客读完 README 会以为这是个 CLI 编排框架，**不知道产品有 Web 界面**。
2. **前端实际身份叫"工作台"，与锁定的"审查台"冲突。** `index.html:6` 标题 `Deck Master 方案项目工作台`、`index.html:15` panel-title 同名，`app.js` 有 ~25 处"工作台"文案。而 audit 明文「把它做成审稿桌，不要做成后台总控台」，IA v1 锁定「Web UI 身份收敛为审稿桌，不退回项目工作台」。命名直接偏离锁定身份。
3. **一句话说不清。** README 第一句「turns a brief, source context, narrative plan, generation handoff, build/render artifacts, review status, and final delivery readiness into one traceable workflow」是把 7 个内部概念塞进一句话，对新用户无意义。没有一句面向用户的"这是什么"。

## 3. 功能完整度

**CLI 侧（闭环）：** init→brief→planner→sourcing→producer→builder→quality→review→export 全链路有 manifest、契约校验、RC gate、1005 tests passed（v1.1.0 release notes）。`deck_generation_result.v2`、final_readiness、release tree、staged install/rollback 均实现。**这一层是 ready 的。**

**Web UI 侧（基本可用但有缺口）：**

| 状态 | 功能 | 证据 |
|---|---|---|
| ✅ 已实现 | 页面预览/导航、审批四动作（approve/reject/request_evidence/submit_approval）、备注、状态带、底部抽屉 6 tab、项目切换、新建项目(fixture)、Skill OS 阶段进度、主动作条状态机 | `app.js:1892 renderActionBar`、`app.js:2504-2507` 事件绑定、`index.html:202-243` 抽屉 |
| ⚠️ 占位 | 预览图真图依赖外部 PPT Deck Pro Max，未生成前显示占位预览 | `docs/TODOS.md:17`、`examples/preview-run/links/*.svg` |
| ⚠️ 占位（数据契约层） | `占位页`/`人工占位` 是 page type 枚举值 | `workspace_api.py:397,412,423` |
| ❌ 死控件 | 语言切换 `#lang-toggle`：HTML `disabled` + title「后续迭代开放」，app.js 仅有元素引用**无任何 addEventListener** | `index.html:49`、`app.js:41`（grep langToggle.addEventListener = 空） |
| ✅ 条件显示 | `#delivery-mode` 仅 delivery shell 显示（非死链） | `app.js:1477` |

**核心链路：** CLI 端到端闭环；Web UI 审查主路径（选页→看预览→审批→备注→下一页）可走通。**但"能点但点不动"的死链存在：语言切换按钮**，且 DESIGN.md References 明写预览页"含中英切换"，属于承诺了没兑现。

## 4. UX 与信息架构

**IA v1 结构层 ≈70% 落地，动作层未收敛：**

| IA v1 验收点 | 状态 | 证据 |
|---|---|---|
| 顶部一条状态带 + 可展开抽屉 | ✅ | `index.html:12 .status-bar`、`index.html:64 .status-drawer` |
| run 级三块（就绪度/论点覆盖/活动流）移入底部抽屉 | ✅ | `index.html:212-232` |
| 中栏预览顶加主动作条 | ✅ | `index.html:122 .action-bar`、`app.js:1892` |
| 预览图成为中栏唯一视觉张力点 | ⚠️ 部分 | 预览外围容器仍大，且 `.preview-stage img` 带巨大阴影抢戏 `style.css:776` |
| **右栏动作收敛为"一个主动作+次动作"** | ❌ | `.action-grid` 仍是 4 个同权按钮（批准/驳回/请求补证据/升级审批，`index.html:164-169`），全部仍 wire（`app.js:2504-2507`），**且与中栏 action-bar 的主动作重复**（两处都有 approve/request-evidence）。IA v1 §6/§7 要求拆分，未完成 |
| **新建项目降权为顶部次入口** | ❌ | `新建项目`+`提交审批` 在 `.header-actions` 常驻（`index.html:58-59`），与当前 run 审查争抢注意力。仅 `确认交付` 做了条件显示（`app.js:1983` ✓） |
| P0/P1 联动三处 | ⚠️ 部分 | block-flag 有联动（`app.js:1848-1872`），但未明确联动右栏风险块 |

**空/错/载态：** 有空态（`index.html:139-142 .empty-state`）、错误态（`app.js:553,624,643` 多个 shellError 分支）、加载态以文字"载入中"为主——audit 与 IA v1 §6 都要求 skeleton loading 替代文字等待，**未实现 skeleton**。

**status-bar 过载：** 实际 status-bar 含 brand+run+run-meta+next-step+block-flag+draft-gate+export+lang+header-actions 九块（`index.html:12-62`），偏离"一条状态带"的克制意图，更像 audit 诊断的"信息过满"问题仍部分存在。

## 5. 视觉与设计系统符合度

逐条对照 DESIGN.md，**偏离严重，视觉层基本未按锁定源真相实现**：

| # | DESIGN.md 锁定 | 实际 | 证据 | 严重度 |
|---|---|---|---|---|
| 1 | 字体 Satoshi/Geist/IBM Plex Mono，CDN 加载 | **字体完全未加载**。CSS 定义了变量但 index.html 无 `<link>` 到 Google Fonts/Fontshare，CSS 无 `@import`/`@font-face`，server.py 不注入。全部 fallback 到 system-ui/monospace | `index.html:7-8`（仅 icon+style.css 两个 link）、`style.css:23-26`（变量定义）、grep `@import/@font-face`=空 | Blocker |
| 2 | 去玻璃、改实面+1px 发丝边框 | **玻璃面板仍存在**。`.glass-panel` 用 `backdrop-filter: blur(24px)`，应用于 left-rail/preview-panel/decision-rail/modal-card；`.bottom-drawer` 用 `blur(20px)` | `style.css:141-148`、`style.css:841-842`、`index.html:73,121,155,247` | Blocker |
| 3 | 删除一切装饰光球 `.ambient-light-container` | CSS 仍保留 `.ambient-light-container`/`.light-orb`/`.orb-1`/`.orb-2`，且 orb 用橙黄 `rgba(255,107,43,.12)`/`rgba(255,184,0,.08)` 非琥珀铜 | `style.css:110-139` | Major |
| 4 | 圆角 sm 2px / md 4px，不做大圆角 | **大圆角遍地**：status-bar 28px、glass-panel 20px、子卡 22px、page-card 16px、decision-block 18px、preview-stage 20px、输入框 10px | `style.css:157,147,209,609,988,763,93` | Major |
| 5 | 强调色单一琥珀铜 `#E09043`，仅用于主动作/阻断/当前态 | **主动作按钮是白底黑字** `.btn-cta{background:#fff;color:#000}`，action-bar 主动作用 `btn btn-cta`。最该暖铜的主动作是最冷的白色，直接破坏"冷底暖点"核心张力 | `style.css:518-519`、`app.js:1898` | Blocker |
| 6 | 语义色 success `#6FAE6F`/warning `#D9A441`/danger `#C75450`/info `#5B8DB8`，P0-P3 | **Skill OS 阶段进度用 Tailwind 默认色**：`#6b7280`/`#10b981`/`#3b82f6`(蓝)/`#f59e0b`/`#fbbf24`/`#ef4444`/`#f87171`，完全绕过 DESIGN.md 色板。`#3b82f6` 蓝是设计系统外的额外强调色 | `style.css:1523-1577` | Major |
| 7 | 阴影仅用于浮层/抽屉 | status-bar 带大阴影 `0 28px 60px`、预览图 `0 30px 80px`、logo 发光 `0 0 10px #fff` | `style.css:162,776,311` | Major |
| 8 | 严肃工具不弹跳，easing ease-out/in | `.btn:active{transform:translateY(1px) scale(.99)}`——虽轻微，但 scale 属应克制类 | `style.css:503` | Minor |
| 9 | 颜色走 token | 多处手写浅色 `#ffd4d0`/`#ffb7b1`/`#f1ca95`/`#f7d4ac`/`#ffc4bc` 未走 text-primary/muted token | `style.css:235,530,668,672,706,755,1024` | Minor |

**结论：** DESIGN.md 是 AGENTS.md 明确的"设计源真相，未经批准不得偏离"，但实际前端在字体、玻璃、圆角、主动作配色、Skill OS 配色五条核心锁定上全面偏离。**视觉层未按 DESIGN.md 实现**，等于锁定的"严肃工具感"记忆点在交付物上未成立。

## 6. 演示与可感知交付

- ✅ `examples/` 有完整示例数据（briefs/context/preview-run 3 页 SVG/feedback/orchestration-plan/adapters，均 git tracked）。
- ✅ `server.py` 默认 `--library-mode fixture`、`run_dir` 可选（Studio 模式），`python3 scripts/preview/server.py` 即可起服务，新建项目选"演示样例"可跑（`server.py:1541-1543`）。
- ❌ **但没有任何用户文档告诉人怎么启动 Web UI。** `quick-start.md`/`README.md`/`agent-guide.md` 全是 CLI 命令，零次提及 `python3 scripts/preview/server.py` 或 localhost:5050。新用户照 README 走不到 Web UI。
- ❌ **仓库零视觉证据。** README 无截图/GIF。`.gstack/qa-reports/screenshots/` 有 ~50 张 QA 截图，但 `.gitignore` 排除 `.gstack/`，未提交。
- ❌ 无一键 demo 脚本（`scripts/*.sh` 不存在，无 `demo`/`quickstart` 脚本）。

**5 分钟看到价值：** 对知道内情的人可行（起 server + fixture），但对一个 clone 仓库的开源访客**不可行**——他不知道有 Web UI，也没有截图能看，文档不引导。

## 7. 终端用户文档

- 现有 `quick-start.md`/`agent-guide.md`/`troubleshooting.md` 全是**面向 agent/开发者**的 CLI 操作手册（setup-status/suite-install/release-build/route-skill/rc-gate）。
- **无面向"售前解决方案架构师"终端用户的文档**：没有"这是什么/为什么用/5 分钟上手/FAQ/已知限制"。
- 已知限制散落在 README「Current Boundaries」与 release notes「Known Boundaries」，无集中终端用户说明。
- 迁移说明有（`docs/migration/real-production-closure.md`，README 链接）。
- `docs/` 下 50+ 篇文档几乎全是设计/spec/评审底稿（带日期前缀的内部工作文档），对终端用户是噪音，且暴露过多内部决策过程。

## 8. 发布就绪的产品信号

| 信号 | 状态 | 证据 |
|---|---|---|
| 版本号传达稳定 | ❌ 混乱 | README "Start Here" 链 `v0.9.14` release notes（`README.md:35`），但实际有更新的 `v1.1.0`（2026-06-24 Skill OS Runtime，`docs/releases/v1.1.0-release-notes.md`），README 未提 v1.1.0。git log 显示 `merge: skill os runtime v1.1` 已合入。**README 过时** |
| 显式版本徽章 | ❌ 无 | README 无版本号/徽章；git tag 仅 `V0.9.8`（远落后） |
| beta/alpha/WIP 字样 | ✅ 无 | 用户面向文件未发现 beta/alpha/WIP/玩具字样 |
| 严肃措辞 | ✅ 是 | "Real Production Closure"/"Current Production Closure" 传达严肃 |
| 内部使用痕迹 | ⚠️ 有 | `.gstack/qa-reports/baseline-*.json` 等内部 QA 产物仍被 git tracked（`git ls-files .gstack` 返回 3 个 baseline JSON，虽 `.gitignore` 排除 `.gstack/` 但历史已提交）；`docs/` 下大量带日期的内部评审底稿 |
| 玩具感信号 | ⚠️ 间接 | 产品形态误判风险：README 把产品讲成 CLI 编排+release+RC gate，访客易误以为是构建工具基础设施，而非审查台产品 |
| `runs/` 本地目录 | ✅ 干净 | `git ls-files runs/` 为空 |

## 9. 就绪判定

- **产品层面开源就绪度：🔴 Not Ready**
- **一句话结论：** 后端 CLI 契约与测试是 ready 的，但产品表层（Web UI）与锁定的 DESIGN.md 设计系统在字体/玻璃/圆角/主动作配色/色板五条核心上全面偏离，产品故事在 README↔DESIGN.md↔前端命名三处不自洽，且 Web UI 既无用户文档引导也无截图/demo 让新用户感知——作为代表"严肃工具感"的开源版本尚不成立。

## 10. Gap 清单（按严重度排序）

| 序号 | 严重度 | 问题 | 证据(文件:行) | 建议修复 |
|---|---|---|---|---|
| R1 | Blocker | 字体 Satoshi/Geist/IBM Plex Mono 完全未加载，全 fallback 到 system-ui/monospace，设计系统字体身份未实现 | `index.html:7-8`；`style.css:23-26`（无 @font-face/@import） | 在 index.html `<head>` 加 Google Fonts(Geist+IBM Plex Mono)+Fontshare(Satoshi) 的 `<link>`，或自托管 |
| R2 | Blocker | 主动作按钮 `.btn-cta` 是白底黑字，非琥珀铜 #E09043，破坏"冷底暖点"核心张力 | `style.css:518-519`；`app.js:1898`(action-bar 用 btn-cta) | `.btn-cta` 改为 `background:var(--accent-action); color:var(--ink-base)`，仅主动作用 |
| R3 | Blocker | 玻璃面板仍存在（.glass-panel/.bottom-drawer 用 backdrop-filter），违反"去玻璃改实面" | `style.css:141-148`、`style.css:841-842`；`index.html:73,121,155,247` | 移除 backdrop-filter，改为 `background:var(--surface-1)` 实面 + 1px hairline |
| R4 | Blocker | README 完全没提 Web UI/审查台，产品故事与 DESIGN.md(localhost Web UI 审查面板)脱节，新用户不知有 Web UI | `README.md`(grep web ui/preview/审查=仅 browser smoke) | README 加产品定位段 + Web UI 启动指引 + 截图 |
| R5 | Major | Skill OS 阶段进度用 Tailwind 默认色(#3b82f6/#10b981/#f59e0b/#ef4444)，绕过 DESIGN.md 语义色板，#3b82f6 蓝是额外强调色 | `style.css:1523-1577` | 全部替换为 --status-success/warning/error/info 与 P0-P3 token |
| R6 | Major | 大圆角遍地(status-bar 28px/glass-panel 20px/子卡 22px/page-card 16px/decision-block 18px/preview-stage 20px)，违反"sm 2px/md 4px 不做大圆角" | `style.css:157,147,209,609,988,763` | 统一降到 2-4px，pill 状态保留 999px |
| R7 | Major | 装饰光球 .ambient-light-container/.light-orb CSS 仍保留，违反"删除一切装饰光球" | `style.css:110-139` | 删除该段 CSS（HTML 已未渲染，清理即可） |
| R8 | Major | IA v1 动作收敛未完成：右栏 .action-grid 仍 4 同权按钮且与中栏 action-bar 主动作重复 | `index.html:164-169`；`app.js:2504-2507` | 按 IA v1 §6/§7 拆为"主动作(审批)+次动作"，移除与 action-bar 重复项 |
| R9 | Major | 前端命名全用"工作台"，偏离锁定身份"审查台/审稿桌" | `index.html:6,15`；`app.js:535,538,553,572,608,612,1222,1350,1852,1858,1977,1978,2361,2415,2529,2530` | 统一改为"审查台"文案 + `<title>` |
| R10 | Major | 无 Web UI 启动文档、无截图/GIF、无一键 demo，新用户无法 5 分钟看到价值 | `quick-start.md`/`README.md`(无 server.py 指引)；`.gitignore` 排除 .gstack 截图 | quick-start 加"启动审查台"段 + 提交 1-2 张截图 + 加 `scripts/demo.sh` |
| R11 | Major | README 版本过时：链 v0.9.14，实际已 v1.1.0(Skill OS)，未提及 | `README.md:35`；`docs/releases/v1.1.0-release-notes.md` | README 链接更新到 v1.1.0，加显式版本号 |
| R12 | Major | 顶部 .header-actions 仍常驻"新建项目"+"提交审批"，与当前 run 审查争抢注意力，违反 IA v1 §6 降权要求 | `index.html:58-59` | "新建项目"降为次入口/菜单，"提交审批"按阶段条件显示 |
| R13 | Major | box-shadow 用于非浮层(status-bar/preview img/logo 发光)，违反"阴影仅用于浮层/抽屉" | `style.css:162,776,311` | 移除非浮层阴影，预览图改用 hairline 边框 |
| R14 | Minor | 语言切换 #lang-toggle 是 disabled 死控件，无 click handler，但 DESIGN.md 写"含中英切换" | `index.html:49`(disabled)；`app.js:41`(无 addEventListener) | 实现中英切换，或暂从 UI 移除以免死链 |
| R15 | Minor | skeleton loading 未实现，加载态以文字"载入中"为主 | `index.html:19`；audit §4.5/IA v1 §6 要求 skeleton | 关键区域加 skeleton 占位 |
| R16 | Minor | 多处手写浅色(#ffd4d0/#ffb7b1/#f1ca95/#f7d4ac/#ffc4bc)未走 token | `style.css:235,530,668,672,706,755,1024` | 统一到 text-primary/--status-* token |
| R17 | Minor | .btn:active 用 scale(0.99) 微弹跳，属应克制动效 | `style.css:503` | 改为纯 background/border 过渡，去 transform |
| R18 | Minor | 内部 QA 产物(.gstack/qa-reports/baseline-*.json)仍 git tracked，开源仓库噪音 | `git ls-files .gstack`(返回 3 baseline JSON) | `git rm --cached` 清理历史 tracked 的 .gstack 内部产物 |
| R19 | Minor | 无面向终端用户(售前架构师)的使用说明/FAQ/已知限制集，docs/ 下多为内部评审底稿 | `docs/`(50+ 带日期内部文档) | 新增 `docs/user-guide.md` 终端用户向；内部底稿移入 `docs/archive/` |

**核心结论：** Blocker 4 项（字体未加载、主动作配色错、玻璃未去、产品故事脱节）必须在开源前解决——它们直接决定"严肃工具感"这一锁定记忆点是否在交付物上成立。Major 级多为 DESIGN.md/IA v1 已锁定但未落地的视觉与动作收敛项，需一并清理才能对外代表锁定方向。

---

*评审由三个独立 sub-agent 取证后汇总，所有结论均带 `文件:行` 证据可复核。*
