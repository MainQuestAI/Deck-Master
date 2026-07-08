# Deck Master 正式开源发布成熟度评审报告

日期：2026-07-06
分支：`codex/oss-release-readiness-review`
报告版本：v0.2，多评审整合版
目标：判断当前 Deck Master 是否已经具备正式开源发布条件，并形成可执行 gap 清单。

## 1. 整合输入

本报告整合三类输入：

1. `.claude/worktrees/hopeful-jang-5c7cd6/docs/qa/2026-07-06-oss-release-readiness/`
   - `00-summary.md`
   - `01-code-maturity.md`
   - `02-project-maturity.md`
   - `03-product-maturity.md`
2. `docs/qa/2026-07-06-open-source-readiness-audit.md`
3. 主线程上一轮复核结论与验证记录。

说明：第一份评审目录当前位于 `.claude/worktrees/hopeful-jang-5c7cd6/` worktree 内，未出现在当前分支的 `docs/qa/` 根目录。已按用户给定路径检索并纳入整合。

## 2. 总结论

Deck Master 当前 **No-Go，不建议直接作为正式开源版本发布**。

可接受的发布形态：**技术预览版 / 受控邀请试用版**。
不建议的发布形态：**面向外部开发者和真实用户的正式开源 v1.0**。

综合成熟度判断：**约 60 / 100**。

判断依据：

- 代码底座明显强于普通早期项目：模块边界、CLI、契约、质量门禁、RC gate、Skill OS 都已有基础。
- 最大短板集中在开源发布工程、产品首体验、设计系统落地和外部依赖透明度。
- 当前 ready 很大程度依赖本机安装、外部仓库绑定、内部文档和本地路径。外部用户从零 clone 后，还不能稳定完成“安装、理解、演示、贡献、发布验证”。
- 评审材料对测试状态存在分歧：有报告记录 893 tests OK，也有主线程临时补依赖后复验剩余 1 个 Review Desk 异常路径失败。正式发布前必须以干净环境复验结果为准。

一句话判断：**Deck Master 的核心产品方向和代码底座值得推进开源，但当前还欠一层正式开源交付包装和产品表层收口。**

## 3. 三维度成熟度

| 维度 | 综合判断 | 当前水位 | 关键结论 |
|---|---:|---:|---|
| 代码成熟度 | 接近可开源 | 约 70 / 100 | 架构、契约、安全姿态和测试基础较好；硬编码路径、依赖声明、静默异常、CSRF、安装方式仍需收口 |
| 项目成熟度 | 不可正式开源 | 约 40 / 100 | 缺 LICENSE、CONTRIBUTING、SECURITY、pyproject、CHANGELOG、版本/tag 真相源、贡献路径 |
| 产品成熟度 | 不可正式开源 | 约 55 / 100 | CLI 工作流较完整；Web UI 与 DESIGN.md 偏离明显，README 未讲清 Web UI 和审查台价值，demo 说服力不足 |
| 发布可信度 | 不可正式开源 | 约 45 / 100 | RC gate 能跑，但发布基线、外部依赖、发布树内容、干净机器复现仍未闭环 |

两个外部评审的共同点：

- 都判定当前不 ready 做正式开源。
- 都认为代码底座本身有价值，主要 gap 不在核心架构。
- 都把 LICENSE、安装/打包、贡献治理、外部依赖、Web UI 首体验列为发布前重点。

主要分歧：

- 第一份评审把硬编码路径、pip 安装、社区基础设施、后端依赖列为最重 P0。
- 第二份 audit 把设计系统偏离提升为 Blocker，尤其是字体、去玻璃、主动作琥珀铜、审查台命名、README 产品故事。
- 主线程复核更关注“陌生用户可复现”和“文档与真实代码行为一致”，并补充了测试证据冲突与 production flow 文档漂移。

总控采纳：**采用更谨慎口径。正式开源需要同时满足法务/工程/产品三条线，不能只凭代码测试通过发布。**

## 4. 关键事实与验证状态

### 已确认强项

- CLI 能提供从 setup、suite-status、workflow、generation、build、render、quality、review 到 rc-gate 的完整命令面。
- `product-capability-manifest` 可验证通过。
- RC gate 在 `--skip-browser-smoke` 和 `--require-browser-smoke` 两种模式下均有通过记录。
- Skill OS 契约测试有通过记录，外部评审记录 172 passed。
- 项目已有大量 schema、release notes、QA、migration、troubleshooting、agent guide 资料。
- Web UI 已具备三栏结构、底部抽屉、页面队列、审批动作、状态条等主体功能。

### 待复验或存在分歧

- 测试状态：
  - 外部 audit 记录 `893 tests, OK`。
  - 主线程此前在临时补齐 `pytest/jsonschema` 后复验为 `893 tests, 1 error`，错误集中在 Review Desk 安装/工作区不完整时的安全提示路径。
  - 发布前应以干净环境重新执行 `python -m unittest discover -s tests`、pytest 合约子集、RC gate 和浏览器 smoke。
- 文档状态：
  - 多份文档记录的版本口径不一致：README 指向 v0.9.14，manifest 为 1.1.0，planning 已出现 v1.3.0。
  - `skills/deck-master/SKILL.md` 的 production flow 仍出现 `render --fixture-safe`，而代码阻断 production/benchmark 使用该参数。
- 外部依赖状态：
  - 本机报告显示 backend ready。
  - 代码中存在硬编码 bridge 路径和 `bound_verified` 返回，外部机器无法自然复现。

## 5. P0 发布阻断

P0 是正式开源前必须关闭的事项。未关闭时，不建议打正式开源 tag。

### P0-1 缺少 LICENSE 与开源授权声明

影响：

- 无 LICENSE 时，外部用户无法合法使用、修改、分发和贡献。
- README、manifest、release tree 都缺少许可证信号。

证据：

- 根目录未发现 `LICENSE`、`COPYING`、`NOTICE`。
- README Start Here 没有 License 或贡献入口。

补齐标准：

- 新增根目录 `LICENSE`。
- README 首屏增加 License badge 和 License 段落。
- `skills/manifest.json` 或发布 manifest 增加 license 字段。
- 许可证类型需老板拍板：MIT 更宽松，Apache-2.0 带专利保护。

### P0-2 缺少标准安装与开发依赖入口

影响：

- 外部用户无法通过常见 Python 开源方式安装。
- CI 临时安装 `pytest/jsonschema`，但仓库依赖声明未包含测试依赖。
- 当前大量测试依赖 `sys.path.insert`，说明包安装路径尚未标准化。

证据：

- 根目录无 `pyproject.toml`、`setup.py`。
- `requirements.txt` 只声明 `python-pptx`。
- `.github/workflows/ci.yml` 中直接 `pip install pytest jsonschema`。

补齐标准：

- 新增 `pyproject.toml`，提供 `deck-master` console script。
- 增加 `dev` extra 或 `requirements-dev.txt`，声明 `pytest`、`jsonschema`、`playwright`、`coverage` 等开发/测试依赖。
- README 提供从零安装路径。
- CI 改为按仓库声明安装依赖，避免在 workflow 内散写依赖。

### P0-3 外部后端依赖无法被外部用户复现

影响：

- `deck-builder` 依赖 PPT Master。
- `deck-producer` 依赖 PPT Deck Pro Max。
- 当前开源用户拿到 Deck Master 后，production 链路会在生成或渲染阶段断裂，除非外部依赖也可获取、绑定和验证。

证据：

- README 写明 `ppt-master` 是 `deck-builder` 的完整后端依赖。
- `product-capability-manifest.json` 声明多个 backend dependency。
- `scripts/runtime/builder_backend.py` 中存在硬编码 `PPT-Deck-Pro-Max-deck-master-bridge` 本机路径。
- `_generation_bridge_status()` 返回 `bound_verified` 与 `verified=True`。

补齐标准：

- 外部依赖状态必须由真实探测生成：路径、git remote、SHA、dirty 状态、能力 smoke。
- 未配置时返回 `unbound` 或 `not_configured`，并给修复命令。
- README 写清三种策略之一：
  - 同步开源最小可用后端。
  - 标注 production backend 暂未公开，仅支持 fixture/demo。
  - 明确 open-core 策略和闭源边界。

### P0-4 README 与 Quick Start 不能支撑外部用户首体验

影响：

- 外部用户读 README 后难以理解产品真实价值。
- README 几乎不讲 Web UI 审查台，容易被误解为 CLI 编排框架。
- Quick Start 从 setup/status 命令切入，缺少 5-10 分钟可展示 demo。

证据：

- README 首屏直接进入 Current Production Closure。
- README 几乎没有 Web UI、审查台、localhost Review Desk、截图、GIF。
- `docs/quick-start.md` 缺少从安装到启动 Web UI 的完整 demo 路径。

补齐标准：

- README 顶部改为外部用户结构：What、Who、Why、Install、Run Demo、Screenshot、Status、License。
- Quick Start 提供一条可复制路径：clone、venv、install、fixture autoplan、启动 Web UI、审批一页、查看 readiness/export。
- 提供 `scripts/demo.sh` 或等价命令组。

### P0-5 Web UI 与 DESIGN.md 锁定方向偏离

影响：

- AGENTS.md 明确要求 UI 以 `DESIGN.md` 为源真相。
- 当前前端实现与“严肃工具感、去玻璃、发丝实面、小圆角、琥珀铜单点、审查台身份”存在多处偏离。
- 正式开源会把未收口的视觉方向暴露为产品第一印象。

证据：

- 字体变量定义了 Satoshi、Geist、IBM Plex Mono，但 HTML/CSS 未加载字体。
- `.glass-panel` 与 `.bottom-drawer` 仍使用 `backdrop-filter`。
- `.btn-cta` 是白底黑字，未使用琥珀铜主动作。
- 大圆角仍广泛存在。
- 前端标题和文案仍使用“方案项目工作台”，与 IA v1 锁定“审稿桌/审查台”冲突。
- Skill OS 阶段进度使用 Tailwind 默认色，绕过 DESIGN.md 色板。

补齐标准：

- 加载或自托管锁定字体。
- 移除玻璃和装饰光球，使用实面 + 1px hairline。
- 主动作改为琥珀铜 token。
- 圆角收敛到 2-4px，pill 例外。
- 文案统一为 Deck Master Review Desk / 审查台 / 审稿桌。
- Skill OS 状态色统一使用设计系统 token。

### P0-6 版本、tag、release notes 无单一真相

影响：

- 外部用户无法判断当前稳定版本。
- 发布说明、manifest、README、git tag 不一致，会削弱可信度。

证据：

- `skills/manifest.json` 为 1.1.0。
- README Release Notes 指向 v0.9.14。
- git tag 评审记录仅发现 `V0.9.8`。
- planning 中已出现 v1.3.0。

补齐标准：

- 明确版本单一真相源，建议以 `skills/manifest.json` 或 `pyproject.toml` 为准。
- 补 `CHANGELOG.md`。
- README 指向当前候选 release notes。
- 打正式 tag 前完成版本一致性检查。

### P0-7 发布证据必须可复验

影响：

- 不同评审对测试是否全绿存在分歧。
- 正式开源需要可复现验证，而不能依赖本机已有依赖或历史报告。

证据：

- 有报告记录 `893 tests OK`。
- 主线程此前复验记录：临时补齐依赖后仍剩 1 个 Review Desk 浏览器异常路径 error。

补齐标准：

- 在全新 venv 中执行：
  - `python -m pip install -e ".[dev]"`
  - `python -m unittest discover -s tests`
  - pytest 合约子集
  - fixture autoplan smoke
  - `rc-gate --require-browser-smoke`
- 将命令和结果写入 release checklist。

## 6. P1 发布前强烈建议

P1 是正式开源前强烈建议关闭的事项。若确需先发技术预览，可明确写入 Known Limitations。

### P1-1 社区治理三件套与 GitHub 模板

内容：

- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `.github/ISSUE_TEMPLATE/`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `CODEOWNERS`
- dependabot 配置

采纳判断：正式开源建议全部补齐。个人项目也需要最低限度贡献入口，避免 issue/PR 失控。

### P1-2 仓库卫生与内部产物清理

问题：

- `.gstack/` 已被 `.gitignore` 忽略，但评审记录显示仍有内部 QA 报告和截图被 track。
- `.claude/`、`.gbrain-source`、`.impeccable/`、大量日期型内部文档会增加外部用户认知噪音。
- QA PNG 截图体积偏大，有报告估计约 30MB。

采纳判断：

- `.gstack/qa-reports` 应从 Git 跟踪中清理。
- 必须保留的 QA 证据迁入 `docs/qa/`，并减少图片体积或改用 release artifact。
- 内部 agent 文档保留但加外部说明，避免普通贡献者误读。

### P1-3 CI 工程化门禁增强

问题：

- 当前 CI 有 compile、unit、contract、fixture smoke、RC gate，但缺 lint、format、type、coverage、多 Python 版本、依赖审计。

采纳判断：

- 正式开源前至少补 ruff 和 dev dependency 安装验证。
- mypy、coverage、Python matrix 可分阶段补，但应纳入 release hardening 计划。

### P1-4 Web UI 信息架构与动作层级收敛

问题：

- 右栏仍有多个同权按钮。
- 中栏 action bar 与右栏动作重复。
- 顶部“新建项目”“提交审批”与当前 run 审查争抢注意力。
- status bar 信息仍偏满。

采纳判断：

- 按 IA v1 收敛为一个主动作 + 次动作。
- `确认交付` 仅在 export_ready 阶段成为顶部高权重动作。
- `新建项目` 降为次入口。

### P1-5 Demo 与用户文档

问题：

- 示例 `examples/preview-run` 只有 3 页，含绝对路径和 placeholder。
- 无 Web UI 截图/GIF。
- 无面向售前解决方案架构师的 user guide、FAQ、已知限制。

采纳判断：

- 准备 8-12 页公开 demo run。
- README 放一张 Review Desk 截图。
- 增加 `docs/user-guide.md`、`docs/known-limitations.md`。

### P1-6 安全与健壮性增强

问题：

- preview server 本地 POST 端点无 CSRF token。
- 存在 broad exception 和静默 fallback。
- `tool_registry.py` 之类配置驱动命令需要更清晰的安全边界。

采纳判断：

- 由于服务默认绑定 127.0.0.1，CSRF 不必阻断技术预览，但正式发布前建议补轻量 token。
- 静默异常按关键路径优先加日志和事件记录，不建议为了风格一次性大改。

### P1-7 release tree 面向外部使用者的信息不足

问题：

- release tree planned 列表缺 README/LICENSE。
- release manifest 记录构建机路径。

采纳判断：

- release tree 应带 README、LICENSE、安装说明。
- 构建机路径要脱敏或移动到 debug-only 字段。

## 7. P2 可后补技术债

这些事项不应阻断有限技术预览，但应进入后续维护计划：

- 拆分 `scripts/deck_master.py`、`scripts/preview/static/app.js`、`scripts/skills/installer.py` 等大文件。
- 明确 `orchestrate/` 与 `runtime/` 职责边界。
- 统一 subprocess 错误处理。
- 统一 `from __future__ import annotations`。
- 增加 Makefile、Dockerfile、devcontainer。
- 完善 i18n，启用或移除 disabled 语言切换。
- 将 loading 文本升级为 skeleton。
- 将手写浅色替换为 design token。
- 整理 docs，将内部评审底稿移入 archive，保留用户向文档入口。
- 建立 MAINTAINERS、GOVERNANCE、ROADMAP、Discussions 或社区沟通渠道。

## 8. 决策点

以下决策需要老板拍板，决定后才能进入实施：

### D1 License 选择

选项：

- MIT：更宽松，利于传播和二次集成。
- Apache-2.0：更正式，包含专利授权条款，对企业场景更稳。

建议：如果 Deck Master 未来希望被企业和生态项目集成，优先 Apache-2.0；如果目标是快速传播和社区采用，MIT 更轻。

### D2 外部后端开源策略

选项：

- 同步开源最小可用 PPT Master / PPT Deck Pro Max 后端。
- Deck Master 先开源，生产后端标注为 coming soon，当前只承诺 fixture/demo。
- open-core：Deck Master 开源，生产后端保持闭源或商业版。

建议：正式开源 v1.0 不建议带着未说明的闭源依赖发布。至少要在 README 和 Quick Start 明确能力边界。

### D3 Web UI 发布门槛

选项：

- 先按技术预览发布，README 明确 UI 正在设计系统收口。
- 正式开源前完成 DESIGN.md 核心偏离修复。

建议：正式开源应先修 DESIGN.md 核心偏离。技术预览可以先发，但文档必须写清边界。

### D4 文档语言策略

选项：

- 中文优先，服务当前老板和中文售前场景。
- 英文优先，面向国际开源社区。
- 双语骨架，README/Quick Start/CONTRIBUTING 英文，DESIGN/AGENTS 保留中文。

建议：正式开源至少需要英文 README 和 Quick Start；内部 agent 指引可保留中文。

## 9. 建议执行路线

### Phase 0：发布口径冻结

目标：统一判断标准和版本基线。

任务：

1. 确认开源许可证。
2. 确认后端依赖策略。
3. 确认正式开源版本号。
4. 确认技术预览与正式开源的边界。

完成标准：

- README 可明确写出“当前支持什么，不支持什么”。
- release checklist 有唯一版本号和唯一验证命令集。

### Phase 1：解除正式开源阻断

目标：从 No-Go 升级到有限技术预览可发。

任务：

1. 补 `LICENSE`、`CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`。
2. 补 `pyproject.toml` 或 `requirements-dev.txt`。
3. README 重写首屏，加入 Web UI 审查台定位。
4. Quick Start 增加 10 分钟 demo。
5. 清理硬编码 bridge 路径和错误的 `bound_verified`。
6. 对齐版本号、release notes、tag 口径。
7. 在干净环境跑完整验证。

完成标准：

- 外部用户能从零安装并运行 demo。
- CI 和本地干净环境验证命令一致。
- LICENSE 与贡献路径齐备。

### Phase 2：正式开源发布收口

目标：从有限技术预览升级到正式开源候选。

任务：

1. Web UI 完成 DESIGN.md 核心偏离修复：字体、去玻璃、主动作、圆角、色板、命名。
2. 准备 8-12 页公开 demo run 和截图/GIF。
3. release tree 带 README/LICENSE，manifest 清理本机路径。
4. 增加 GitHub issue/PR 模板、CHANGELOG、ROADMAP。
5. CI 增加 ruff、coverage、依赖审计或对应分阶段计划。
6. 修复或解释 Review Desk 异常路径测试分歧。

完成标准：

- README、Quick Start、Web UI 第一屏能传达“Deck Master 是专业 Solution Deck 审查台”。
- demo 能展示来源、风险、审批、质量门禁、导出队列。
- release checklist 全绿。

### Phase 3：开源后维护

目标：降低长期维护成本。

任务：

1. 拆分大文件。
2. 建立 Makefile/devcontainer/Dockerfile。
3. 梳理 docs/archive。
4. 建立 good first issue 与社区沟通渠道。
5. 收集真实项目指标，验证 12h 到 2h 这类效率主张。

## 10. 最小发布前验收清单

正式开源前至少满足：

- [ ] 根目录存在 `LICENSE`，README 明确 license。
- [ ] README 有 What / Who / Install / Run Demo / Web UI 截图 / Known Limitations。
- [ ] `pyproject.toml` 或 dev requirements 可让干净 venv 安装并跑测试。
- [ ] `python -m unittest discover -s tests` 在干净环境通过。
- [ ] pytest 合约子集通过。
- [ ] `rc-gate --require-browser-smoke` 通过。
- [ ] 外部 backend 未配置时不报告 ready。
- [ ] production 文档不再引导用户执行 fixture-only 命令。
- [ ] DESIGN.md 核心偏离项已修复或在技术预览说明中明确标注。
- [ ] `.gstack/` 等内部生成物不再被 Git 跟踪。
- [ ] README 版本、manifest 版本、release notes、git tag 对齐。

## 11. 总控采纳结论

本轮两份交叉评审都给出了同一方向：**Deck Master 值得推进开源，但不能以当前形态正式发布**。

总控采纳后形成三条推进主线：

1. **开源发布工程线**：LICENSE、pyproject、CONTRIBUTING、SECURITY、CHANGELOG、tag、CI、仓库卫生。
2. **产品首体验线**：README、Quick Start、Web UI 启动、demo run、截图/GIF、用户文档。
3. **能力可信线**：外部 backend 策略、真实依赖探测、production 文档一致性、release checklist。

优先顺序：

1. 先做 Phase 0 决策冻结。
2. 再做 Phase 1，达到可控技术预览。
3. 最后做 Phase 2，冲正式开源候选。

当前最小下一步：

- 老板确认 License 和后端开源策略。
- 开一个实施任务分支，先补 Phase 1 阻断项。
- Phase 1 完成后重新跑干净环境验证，再判断是否进入技术预览发布。

## 12. 后续交叉评审合并位

后续其他 agent 的交叉评审建议追加到本节。

模板：

```md
### YYYY-MM-DD Agent 名称 / 线程 ID

- 总体判断：
- 新增 P0：
- 新增 P1：
- 与本报告冲突点：
- 总控采纳结论：
```

当前已合并：

- `.claude/worktrees/hopeful-jang-5c7cd6/docs/qa/2026-07-06-oss-release-readiness/`
- `docs/qa/2026-07-06-open-source-readiness-audit.md`

待合并：

- 其他 agent 交叉评审：待老板提供。
