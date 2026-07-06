# Deck Master 开源成熟度迭代计划

日期：2026-07-06
分支：`codex/oss-release-readiness-review`
输入评审：`docs/qa/2026-07-06-open-source-release-readiness-review.md`
补充评审：CEO / founder strategy review findings
目标：基于开源就绪评审，把 Deck Master 从当前 No-Go 状态推进到可控技术预览，再推进到正式开源候选。

## 1. 结论

Deck Master 当前不适合直接正式开源。合理路径是先发布 M1 受控技术预览，验证外部用户能在干净环境跑通公开 fixture demo，并清楚理解“当前可用能力”和“生产后端边界”。M2 再进入正式开源候选，要求真实后端、Review Desk 设计系统、安全边界、release tree 与版本证据全部收口。

| 里程碑 | 发布形态 | 行为闸门 |
|---|---|---|
| M1 技术预览 | public Technical Preview；允许 preview / pre-release 语义 tag，不承诺正式版、不发布 stable release | Legal、First-run demo、Capability truth、Repo hygiene、Design minimum、Preview gate 全部严格通过 |
| M2 正式候选 | 正式开源 RC | M1 全部通过，当前 RC gate、真实后端、Review Desk 设计收口、安全加固、release tree 发布标准全部通过 |

分数只做内部追踪，Go / No-Go 只看行为闸门。

## 2. 边界

- 本计划只制定迭代路线和验收标准，不直接实施代码改动。
- 本计划承诺当前 Deck Master 仓库全仓 Apache-2.0 开源；PPT Master、PPT Library、PPT Deck Pro Max 若属于外部独立仓，按 M2 production 外部依赖处理。
- 本计划不处理长期架构重构，除非该重构直接阻断开源发布。
- 本计划保留内部 agent 指引，但会增加外部贡献者可读入口。
- 本计划只清理正式开源入口会暴露的内部噪音；历史归档类资料放到 Phase 3。

## 3. 已拍板的关键决策

| 决策 | 已定口径 | 理由 | 阻断范围 |
|---|---|---|---|
| D0 发布可见性 | M1 直接 public，状态标记为 Technical Preview；允许 preview / pre-release tag，不承诺正式版 | M1 会被外部看到，必须用命名、tag、README 共同压住正式版预期 | README、CHANGELOG、GitHub 设置、release checklist |
| D1 License | `Apache-2.0` | 企业采用更看重专利授权和清晰治理，适合售前与方案交付场景 | LICENSE、pyproject、manifest、release tree |
| D2 开源范围 | 当前 Deck Master 仓库全仓开源；如 production 仍依赖外部独立仓，M2 前必须同步开源、替换为本仓能力或明确移出正式候选范围 | “全仓开源”能提升可信度，但 production 依赖不能继续靠本机路径或口头说明兜底 | README、Quick Start、builder backend、rc gate |
| D2.1 产品独立性 | M1 以 Review Desk + 公开 fixture demo 证明独立可体验；production 价值到 M2 用真实后端或公开替代链路证明 | 公开后用户首先验证首跑体验，demo 不能含假路径、placeholder 或闭源暗依赖 | README 首屏、demo、Known Limitations |
| D3 Web UI 门槛 | 严格口径：M1 做 DESIGN.md 最小合规；M2 做全量收口 | AGENTS / DESIGN.md 已把视觉方向设为项目约束，公开入口不能继续严重偏离 | Review Desk 静态资源、截图/GIF |
| D4 文档语言 | 外部入口英文优先，内部 agent 指引保留中文 | GitHub 外部采用需要英文首屏，内部协作资料无需重写 | README、Quick Start、CONTRIBUTING、SECURITY |
| D5 版本真相源 | 优先用 `pyproject.toml` 作为包版本真相源；`skills/manifest.json` 记录 suite/version，并在 release checklist 写清关系 | 当前 v0.9.14、1.1.0、v1.3.0 口径分裂，会削弱发布可信度 | pyproject、manifest、CHANGELOG、tag |
| D6 维护承诺 | M1 写明 Best-effort technical preview；M2 再定义安全响应与 issue SLA | 个人开发者需要控制承诺边界 | README、SECURITY、issue templates |
| D7 贡献授权 | M1 采用 DCO 口径；暂不引入复杂 CLA | 低摩擦、成本低，足够支撑早期开源贡献 | CONTRIBUTING、PR template |

已拍板组合：

| License | 开源范围 | M1 口径 | M2 追加要求 |
|---|---|---|---|
| Apache-2.0 | 当前 Deck Master 仓库全仓开源 | public Technical Preview，不承诺正式版；preview / pre-release tag 可用 | production 所需外部独立仓必须同步开源、替换为本仓能力或明确移出正式候选范围 |

## 4. 阶段路线

### Phase 0：发布口径冻结

目标：停止版本、授权、能力边界继续漂移。

任务：

1. 固化 D0-D7，形成 `docs/releases/2026-07-06-release-checklist.md` 的决策记录。
2. 将 `Apache-2.0` 写入根目录和 package metadata。
3. 将当前仓库全仓开源策略写入 README 的 Capability Boundaries。
4. 确定 preview tag 与候选版本关系，建立单一版本真相源。
5. 定义 M1 与 M2 的发布名称、支持范围、已知限制、维护承诺。
6. 明确 M1 public 的额外约束：Status 标记 Technical Preview；tag 只能使用 preview / pre-release 语义；不发布 stable release，不承诺正式版。

验收：

- README 能用 30 秒说明“当前支持什么、暂不支持什么、怎么验证”。
- `pyproject.toml`、`skills/manifest.json`、README、release notes、tag 口径有唯一候选版本关系。
- release checklist 明确 M1/M2 的命令集和阻断条件。
- M1 public 技术预览策略、preview tag 语义和“非正式版承诺”已经写入 README 和 release checklist。

### Phase 1：M1 技术预览解阻断

目标：从 No-Go 推到受控技术预览可发。

任务：

1. 开源授权与治理：
   - 新增 `LICENSE`。
   - 新增 `CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`。
   - 新增 `THIRD_PARTY_NOTICES.md` 或 license inventory。
   - 在 `CONTRIBUTING.md` 中明确 DCO / 贡献授权口径。
   - README 首屏加入 License、Status、Known Limitations、维护承诺。
   - `pyproject.toml`、`skills/manifest.json`、`product-capability-manifest.json` 补齐 license/version 口径。
2. 标准安装与开发依赖：
   - 新增 `pyproject.toml`，提供 `deck-master` console script。
   - 增加 `dev` extra，声明 `pytest`、`jsonschema`、`playwright`、`coverage`。
   - CI 改为 `python -m pip install -e ".[dev]"`。
3. 后端依赖透明化：
   - T3a：移除 `scripts/runtime/builder_backend.py` 中的本机桥接路径默认值。
   - T3b：`_generation_bridge_status()` 未配置时返回 `unbound` 或 `not_configured`，禁止硬报 `bound_verified`。
   - T3c：`setup-status` / `suite-status` 给出修复命令和能力边界。
   - T3d：production 命令在后端未配置时阻断，并给 fixture/demo 路径。
   - T3e：记录已配置后端的 path/remote/SHA/dirty 状态，方便 release checklist 追溯。
4. README、Quick Start 与 production 文档一致性：
   - README 改为外部用户结构：What / Who / Install / Run Demo / Review Desk / Status / License。
   - `docs/quick-start.md` 增加 10 分钟 demo：clone、venv、install、fixture autoplan、启动 Review Desk、审批一页、查看 readiness/export。
   - 新增或补齐 `scripts/demo.sh`，把 demo 命令串成一条可复制路径。
   - `skills/deck-master/SKILL.md`、`skills/ppt-master/SKILL.md` 等 production 入口不得把 fixture-only 命令包装成生产路径。
5. M1 预览闸门：
   - 新增或明确 `preview-gate`：只验证安装、fixture demo、README 路径、Review Desk 可启动、未配置后端不误报。
   - 当前 `rc-gate` 不作为 M1 Go 条件，保留给 M2 正式候选。
   - Review Desk 异常路径测试分歧纳入 M1：能复现就修，不能复现就记录环境差异和剩余风险。
6. 仓库卫生：
   - 清除已被 Git 跟踪的 `.gstack/qa-reports` 产物。
   - 扫描并处理 `.claude`、`.gbrain-source`、`.impeccable`、本机路径、agent 注释、内部工作流痕迹。
   - 必要 QA 证据迁入 `docs/qa/` 或 release artifact。
   - 对顶层和外部入口文档做公开性扫描，优先处理个人命名、内部底稿、客户/售前敏感迹象。
   - M1 计划、README、release manifest 不保留作者本机路径。
7. 公开 demo：
   - 准备一个 10-12 页可公开 fixture demo run。
   - `examples/preview-run/preview_manifest.json` 使用 repo 内相对路径或 fixture 标识。
   - 示例中不出现 placeholder、客户敏感信息或作者本机绝对路径。
8. Review Desk M1 最小设计合规：
   - 加载或明确自托管 Satoshi / Geist / IBM Plex Mono 的可执行方案。
   - 移除 `.glass-panel` 与 `backdrop-filter`。
   - `.btn-cta` 改为琥珀铜主动作。
   - 文案统一为 Deck Master Review Desk / 审查台 / 审稿桌。
   - M1 严格执行最小设计合规，公开入口不保留已知核心偏离。
9. release tree 基础包装：
   - release tree 带 README、LICENSE、Known Limitations。
   - 默认 release manifest 不写入作者本机绝对路径；需要保留时放入 debug-only 本地报告。
10. 版本与发布证据：
    - 新增 `CHANGELOG.md`。
    - 清理 v0.9.14、1.1.0、v1.3.0 等口径冲突。
    - 在干净 venv 跑完整验证并写入 release checklist。

验收：

- 新机器执行 `python -m pip install -e ".[dev]"` 后能跑测试。
- `python -m unittest discover -s tests` 通过；如 Review Desk 异常路径有环境分歧，release checklist 写明复现条件和剩余风险。
- pytest 合约子集通过。
- fixture autoplan smoke 生成 10+ 页可审查预览。
- `preview-gate` 通过。
- Review Desk 能启动并打开公开 demo run。
- 未配置外部后端时不再报告 ready，production 命令按边界阻断。
- fixture demo 无 placeholder、客户敏感信息、作者本机绝对路径。
- release tree 含 README、LICENSE、Known Limitations。
- Git 不再跟踪 `.gstack/qa-reports`。
- M1 public Technical Preview、preview tag 语义和非正式版承诺写入 README 和 release checklist。

### Phase 2：M2 正式开源候选收口

目标：把产品第一印象、发布树、社区入口、安全边界和验证证据拉到正式开源候选标准。

任务：

1. Review Desk 设计系统全量收口：
   - 自托管或可复现加载 Satoshi / Geist / IBM Plex Mono。
   - 全面移除玻璃质感、过大圆角和多余强调色。
   - 主动作、状态色、发丝边框、命名体系全部接入 DESIGN.md token。
   - Skill OS 状态色接入 DESIGN.md token。
   - 预估 human 1.5-2 人日 / CC 45-60min，按字体、实面化、主动作、圆角命名四个小步验收。
2. Demo 与产品证明：
   - README 加 Review Desk 截图或 GIF。
   - 新增 `docs/user-guide.md`。
   - 用真实 benchmark 或公开样例证明 production 链路，减少对 fixture 的依赖。
3. release tree 与 manifest：
   - release tree 补正式安装说明、版本信息和回滚说明。
   - release manifest 清理本机路径或放入 debug-only 字段。
   - 发布包可独立安装、验证、回滚。
4. GitHub 社区入口：
   - 新增 issue template、PR template、CODEOWNERS。
   - 新增 `ROADMAP.md` 或把 `docs/TODOS.md` 提炼为公开路线图。
   - 增加 dependabot 配置。
5. CI 与质量门禁：
   - 增加 ruff。
   - 增加 coverage 报告或最低阈值计划。
   - 增加 Python 版本矩阵的最小集。
   - 当前 `rc-gate --skip-browser-smoke` 和 `rc-gate --require-browser-smoke` 作为 M2 Go 条件。
6. 安全加固：
   - 本地 POST 写操作增加轻量 token 或 origin 校验。
   - 增加静默异常日志，避免 preview server 吞掉关键错误。
   - `SECURITY.md` 说明 localhost 威胁边界、报告方式和响应承诺。

验收：

- 外部贡献者在 5 分钟内理解项目价值和运行 demo。
- README 首屏能表达“专业 Solution Deck 审查台”的价值。
- Review Desk 第一屏符合 DESIGN.md 的严肃工具感。
- 发布树不暴露作者本机路径。
- release checklist 全绿。

### Phase 3：开源后维护

目标：降低长期维护成本，避免开源后被内部历史包袱拖住。

任务：

1. 拆分大文件：`scripts/deck_master.py`、`scripts/preview/static/app.js`、`scripts/skills/installer.py`。
2. 梳理 `docs/archive` 和内部评审底稿。
3. 建立 Makefile、Dockerfile、devcontainer。
4. 建立 good first issue 和社区沟通渠道。
5. 收集真实项目指标，验证从 12 小时到 2 小时的效率主张。

## 5. 现有资产复用

| 子问题 | 已有资产 | 复用方式 |
|---|---|---|
| 运行时命令面 | `scripts/deck_master.py` | README 和 Quick Start 直接复用现有命令，不发明新入口 |
| 技能与能力清单 | `skills/manifest.json`、`product-capability-manifest.json` | 作为版本和能力边界的输入，但需要补 license/version 字段 |
| RC 验证 | `scripts/runtime/rc_gate.py`、CI workflow | release checklist 复用现有 gate，补干净环境安装路径 |
| Review Desk | `scripts/preview/server.py`、`scripts/preview/static/` | M1 做最小设计合规，M2 做全量设计收口 |
| 设计源真相 | `DESIGN.md`、IA v1、web UI audit | UI 改动必须对齐这些文档 |
| 发布与迁移资料 | `docs/releases/`、`docs/migration/` | 汇总为 `CHANGELOG.md` 与对外迁移说明 |

## 6. 不在本轮范围

- 不同步改造 PPT Library、PPT Master、PPT Deck Pro Max 的完整开源策略。
- 不把 Review Desk 扩展成完整编辑器。
- 不引入云端服务、账号系统、SaaS 托管或远程协作。
- 不重写核心编排架构。
- 不清理所有历史文档，只清理正式开源入口会看到的噪音。

## 7. 错误与救援注册表

| 路径 | 可能失败 | 当前风险 | 计划救援 | 用户看到 |
|---|---|---|---|---|
| 发布可见性 | M1 被误判为正式 release | License、安装、demo 同时出现时，外部会自然形成正式发布预期 | M1 public Technical Preview；tag 只用 preview / pre-release 语义；不发布 stable release | “这是技术预览，能力边界明确” |
| 外部后端探测 | 未配置 PPT Deck Pro Max / PPT Master | 当前可能误报 `bound_verified` | 返回 `unbound`，给修复命令，production 命令阻断 | “生产后端未配置，当前只支持 fixture/demo” |
| 安装依赖 | 干净 venv 缺 pytest/jsonschema/playwright | CI 与本地声明不一致 | `pyproject.toml[dev]` 统一声明 | 安装命令一次成功或给缺依赖提示 |
| demo 首跑 | 外部用户没有真实后端 | production 链路断裂 | Quick Start 默认 fixture demo，README 标清边界 | demo 可审查，production 边界清楚 |
| fixture 可信度 | 示例含 placeholder 或绝对路径 | 外部用户认为 demo 数据虚假或不可复现 | 10-12 页公开 fixture，全部用 repo 相对路径或 fixture 标识 | demo 像真实产品体验，可复现 |
| Web UI 首屏 | 设计系统偏离 | 第一印象不专业 | M1 做最小合规，M2 做全量收口 | Review Desk 呈现严肃工具感 |
| 仓库卫生 | `.gstack/qa-reports` 和内部目录被 Git 跟踪 | 外部用户看到内部 QA 噪音和大图 | M1 清理跟踪产物，保留必要证据到公开位置 | 仓库根目录干净、可信 |
| release tree | 缺 README/LICENSE/限制说明 | 用户拿到发布包后不知道用途和边界 | M1 包含基础包装，M2 补正式安装/回滚 | 发布包可独立理解和验证 |
| release 版本 | README、manifest、tag 不一致 | 用户不知道稳定版本 | 单一版本真相源 + checklist | 版本号一致，发布说明可追溯 |
| 测试复验 | 历史报告与当前结果冲突 | 发布可信度不足 | 干净环境复验并记录命令输出 | release checklist 有可复验证据 |
| 安全边界 | localhost 写操作被跨站触发 | 公开后被安全审查扣分 | M2 加 token/origin 校验和 SECURITY 威胁边界 | 本地工具风险可解释、可控制 |

## 8. 测试与验收计划

```text
CODE PATHS / RELEASE PATHS
├── Release visibility
│   ├── [GAP] M1 public Technical Preview policy recorded
│   ├── [GAP] Technical Preview status visible
│   └── [GAP] preview / pre-release tag semantics documented
├── Packaging
│   ├── [GAP] pyproject editable install
│   ├── [GAP] console script deck-master
│   └── [GAP] dev extra drives CI
├── Backend truth
│   ├── [GAP] unconfigured bridge reports unbound
│   ├── [GAP] generation bridge does not report bound_verified by default
│   ├── [GAP] configured bridge reports path/remote/SHA/dirty
│   └── [GAP] production commands block when bridge is missing
├── Docs first run
│   ├── [GAP] README 5-minute path
│   ├── [GAP] Quick Start fixture demo
│   ├── [GAP] production skill docs do not point users to fixture-only paths
│   └── [GAP] Known limitations
├── Preview gate
│   ├── [GAP] M1 gate excludes real backend and benchmark requirements
│   ├── [GAP] Review Desk opens public demo run
│   ├── [GAP] unconfigured backend is visible but non-blocking for fixture demo
│   └── [GAP] Review Desk exception-path test divergence resolved or documented
├── Repo hygiene
│   ├── [GAP] tracked .gstack/qa-reports removed
│   ├── [GAP] .claude/.gbrain-source/.impeccable/internal traces scanned
│   ├── [GAP] required QA evidence moved to public docs or release artifact
│   └── [GAP] no author-local path in public docs/manifests
├── Fixture demo
│   ├── [GAP] 10-12 page demo run
│   ├── [GAP] no placeholder content
│   └── [GAP] repo-relative paths or fixture identifiers only
├── Review Desk design
│   ├── [GAP] no backdrop-filter
│   ├── [GAP] amber primary action
│   ├── [GAP] font loading
│   └── [GAP] Review Desk naming
└── Release evidence
    ├── [GAP] unittest full run in clean env
    ├── [GAP] pytest contract subset
    ├── [GAP] fixture autoplan smoke
    └── [GAP] rc-gate with browser smoke
```

M1 验证命令：

```bash
python -m pip install -e ".[dev]"
python -m unittest discover -s tests
python -m pytest tests/test_skill_manifest.py tests/test_stage_contract_registry.py tests/test_workflow_state.py tests/test_stage_validation.py tests/test_skill_handoff.py tests/test_workflow_approval.py tests/test_workflow_questions.py tests/test_sourcing_plan_v2.py tests/test_page_package.py tests/test_build_manifest_v2.py tests/test_workflow_autopilot_v2.py tests/test_workflow_cli.py tests/test_skill_doc_contract.py tests/test_skill_os_migration.py tests/test_skill_os_release_contract.py -q
python scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --run-mode fixture --dev-allow-unsetup --runs-dir /tmp/deck-master-demo --run-id oss-demo
python scripts/deck_master.py preview-gate --run-dir /tmp/deck-master-demo/oss-demo --expect-unconfigured-backend-ok
```

M2 正式候选追加：

```bash
python scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc --benchmark-dir benchmarks --skip-browser-smoke --force
python scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc-browser --benchmark-dir benchmarks --require-browser-smoke --force
```

## 9. 并行实施建议

| Lane | 工作流 | 目录 | 依赖 |
|---|---|---|---|
| A | D0-D7 固化 + License + 治理文件 + README 首屏 | 根目录、`.github/`、`docs/releases/` | 已拍板 |
| B | pyproject + dev 依赖 + CI | 根目录、`.github/workflows/` | A 可并行 |
| C | 后端依赖真相与状态输出 | `scripts/runtime/`、`scripts/skills/`、tests | D2 / D2.1 |
| D | preview-gate + Quick Start + demo + Known Limitations | `docs/`、`examples/`、`scripts/` | B、C 后验收 |
| E | Review Desk M1 最小设计合规 | `scripts/preview/static/` | D3 |
| F | repo hygiene + release tree 基础包装 | `.gstack/`、`.claude/`、`.gbrain-source`、`.impeccable`、`docs/qa/`、`scripts/skills/` | A、B、C |
| G | release checklist + CHANGELOG + 版本对齐 | `docs/releases/`、manifest | D5 |
| H | M2 安全加固 + 社区模板 | `scripts/preview/server.py`、`.github/`、`SECURITY.md` | M1 后 |

执行顺序：

1. 先做 A、B、C。
2. 再做 D、E、F、G。
3. M1 验收后做 H 和 Review Desk 全量收口。
4. H 与全量设计收口完成后冲 M2。

## 10. 实施任务清单

- [ ] **T1 (P1, human: ~1.5h / CC: ~15min) — governance + release policy** — 新增开源授权、治理文件和 M1 可见性策略
  - 文件：`LICENSE`、`CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`、`THIRD_PARTY_NOTICES.md`、`docs/releases/2026-07-06-release-checklist.md`
  - 验证：README 可链接到治理文件，GitHub 页面可识别 license，贡献授权口径明确，M1 public Technical Preview 和 preview tag 策略明确。

- [ ] **T2 (P1, human: ~2h / CC: ~20min) — packaging** — 新增 `pyproject.toml` 与 dev extra
  - 文件：`pyproject.toml`、`.github/workflows/ci.yml`
  - 验证：`python -m pip install -e ".[dev]"` 成功，CI 不再散写测试依赖。

- [ ] **T3 (P1, human: ~2.5h / CC: ~30min) — backend truth** — 移除硬编码桥接路径和误报 ready
  - 文件：`scripts/runtime/builder_backend.py`、`scripts/runtime/rc_gate.py`、`tests/`
  - 子任务：T3a 移除默认本机路径；T3b 修 `_generation_bridge_status()`；T3c 修 `setup-status` / `suite-status`；T3d production 未配置阻断；T3e 配置后记录 remote/SHA/dirty。
  - 验证：未配置时返回 `unbound`，配置时记录 remote/SHA/dirty，production 命令按真实状态阻断。

- [ ] **T4 (P1, human: ~2h / CC: ~20min) — docs** — 重写 README、Quick Start 与 production 文档
  - 文件：`README.md`、`docs/quick-start.md`、`docs/known-limitations.md`、`skills/deck-master/SKILL.md`、`skills/ppt-master/SKILL.md`
  - 验证：外部用户按文档 10 分钟内跑通 fixture demo 和 Review Desk；production 文档不会把 fixture-only 路径当作正式路径。

- [ ] **T5 (P1, human: ~2h / CC: ~20min) — preview gate** — 新增 M1 技术预览闸门
  - 文件：`scripts/deck_master.py`、`scripts/runtime/`、`tests/`
  - 验证：`preview-gate` 验证安装、fixture demo、Review Desk 可启动、未配置后端不误报，不要求真实 benchmark 和生产后端。

- [ ] **T6 (P1, human: ~1.5h / CC: ~20min) — repo hygiene** — 清理已跟踪内部产物和公开入口噪音
  - 文件：`.gstack/qa-reports`、`.claude`、`.gbrain-source`、`.impeccable`、`docs/qa/`、顶层公开文档
  - 验证：`git ls-files .gstack` 为空；公开入口无作者本机路径、内部注释、客户敏感迹象；必要 QA 证据迁到公开位置或 release artifact。

- [ ] **T7 (P1, human: ~1.5h / CC: ~20min) — public demo** — 准备 10-12 页公开 fixture demo
  - 文件：`examples/preview-run/`、`examples/briefs/`、`docs/quick-start.md`
  - 验证：demo run 无 placeholder、无作者本机绝对路径、无客户敏感信息；Review Desk 可打开并完成一次审批。

- [ ] **T8 (P1, human: ~1h / CC: ~15min) — release package** — 给 release tree 增加基础开源包装
  - 文件：`scripts/skills/installer.py`、`README.md`、`LICENSE`、`docs/known-limitations.md`
  - 验证：release tree 含 README、LICENSE、Known Limitations，默认 manifest 不暴露作者本机路径。

- [ ] **T9 (P1, human: ~1h / CC: ~15min) — versioning** — 建立版本真相源和 CHANGELOG
  - 文件：`pyproject.toml`、`skills/manifest.json`、`README.md`、`CHANGELOG.md`
  - 验证：版本一致性检查通过，release notes 指向当前候选版本。

- [ ] **T10 (P1, human: ~1.5h / CC: ~20min) — design minimum** — 修复 M1 公开入口的 DESIGN.md 核心偏离
  - 文件：`scripts/preview/static/index.html`、`scripts/preview/static/style.css`、`scripts/preview/static/app.js`
  - 验证：无 `.glass-panel`、无 `backdrop-filter`，主动作琥珀铜，字体加载方案明确，命名为 Review Desk / 审查台。

- [ ] **T11 (P2, human: ~1.5-2d / CC: ~45-60min) — review desk full close** — 完成 Review Desk 全量设计系统收口
  - 文件：`scripts/preview/static/index.html`、`scripts/preview/static/style.css`、`scripts/preview/static/app.js`
  - 验证：字体、实面化、主动作、圆角、命名、状态色全部符合 DESIGN.md；README 截图/GIF 更新。

- [ ] **T12 (P2, human: ~2h / CC: ~25min) — security** — 补 localhost 写操作安全边界
  - 文件：`scripts/preview/server.py`、`SECURITY.md`、`tests/`
  - 验证：POST 写操作有轻量 token 或 origin 校验，静默异常有日志，SECURITY 说明 localhost 威胁边界。

- [ ] **T13 (P2, human: ~2h / CC: ~25min) — release evidence** — 干净环境 release checklist
  - 文件：`docs/releases/`、`docs/qa/`
  - 验证：记录 unittest、pytest 合约、fixture demo、RC gate、browser smoke 的日期和输出摘要。

- [ ] **T14 (P2, human: ~2h / CC: ~20min) — community** — 新增 GitHub 模板与公开路线图
  - 文件：`.github/ISSUE_TEMPLATE/`、`.github/PULL_REQUEST_TEMPLATE.md`、`CODEOWNERS`、`ROADMAP.md`
  - 验证：新 issue/PR 默认带复现和验证字段。

## 11. 发布判定

### M1 技术预览 Go 条件

- D0-D7 决策已记录，尤其是 M1 public Technical Preview、当前仓库全仓开源、版本真相源、维护承诺。
- License、安装、README、Quick Start、Known Limitations 齐备。
- 外部后端未配置时不误报 ready，production 命令按边界阻断。
- 干净环境基础验证通过。
- README 明确技术预览边界和维护承诺。
- `preview-gate` 通过，且不要求真实后端或 benchmark。
- 公开 fixture demo run 可启动 Review Desk，且无 placeholder、客户敏感信息、作者本机绝对路径。
- Review Desk 完成 M1 最小设计合规，公开入口无核心设计偏离。
- Review Desk 异常路径测试分歧已修复或被 release checklist 记录。
- Git 不再跟踪 `.gstack/qa-reports`，公开入口无内部噪音。
- release tree 含 README、LICENSE、Known Limitations。

### M2 正式候选 Go 条件

- M1 全部通过。
- Review Desk 与 DESIGN.md 核心方向一致。
- README 截图/GIF 齐备。
- release tree 含正式安装/版本/回滚说明且无本机路径泄露。
- `rc-gate --skip-browser-smoke` 与 `rc-gate --require-browser-smoke` 通过。
- 本地写操作安全边界进入 SECURITY 与测试。
- 版本、tag、manifest、CHANGELOG 全部对齐。
- GitHub 社区入口、路线图和维护承诺齐备。

## 12. 参考依据

- [Python Packaging User Guide: Writing your pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [PEP 621: Storing project metadata in pyproject.toml](https://peps.python.org/pep-0621/)
- [GitHub Docs: Community health files](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file)
- [OpenSSF Scorecard](https://scorecard.dev/)
