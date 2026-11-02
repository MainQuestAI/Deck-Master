# Deck Master

[English](README.md) | [简体中文](README.zh-CN.md)

Deck Master 是面向商业方案创作与表达的 AI 原生工作台，帮助解决方案架构师、提案者和演讲者，将复杂材料组织成清晰、连贯、有真实业务依据的 deck。

## 核心理念

一份好的 deck，始于对业务的理解与判断：这次要讲清什么，为什么值得讲，各部分如何构成一个整体。我们希望帮助作者理清问题、提炼能够统领方案的主线，并将它展开为完整的说明，把复杂的事情讲简单，把抽象的事情讲具体。

产品围绕三个原则发展：

- **以任务决定表达。** 作者的商业任务决定主张、重点和内容取舍；受众的知识与经验决定如何讲清楚。
- **以理解组织内容。** 有解释力的业务框架连接需求、能力与场景，并贯穿整套方案和讲述过程。
- **让视觉承担说明。** 文字、图形与实例共同呈现关系、过程和取舍，文件形式与制作工具服务于表达目的。

这些原则指导产品发展。当前工作台通过 CLI 和本机 Web UI 连接内容策划、可编辑 SVG/PPT 制作、审查与修改。现阶段的实现范围见[能力边界](#能力边界)。

**版本：** Python 包 `1.0.0`，处于发布准备阶段。已发布资产与发布状态见 [GitHub Releases](https://github.com/MainQuestAI/Deck-Master/releases)。使用前请阅读[安装与首次运行指南](docs/getting-started.md)。

[RC4 增量](docs/specs/deck-master-next-iteration-20261019/README.md)及其[唯一台账](tests/rebuild/fixtures/history/rc4/iteration-20261019/execution-ledger.json)保留原候选版本的证据。源码版本、构建出的 wheel、当前安装和公开 Release 分别记录。源码已包含 RC5 内容方法目录及有范围限制的 Host 选用机制、PR130 的内容/方法/证据阅读与可恢复交接，以及支持和文档治理。验证范围与待发布事项见[发布准备记录](docs/releases/1.0.0-preparation.md)。

**许可证：** Apache-2.0。

核心继承了 RC4 对 RC3 和 Flow Quality 合同的扩展，包括可恢复的输入与安装操作、冻结的任务方法、有范围限制的内容校验，以及可协商的读取上下文。工程检查、实际 Host 应用和专业/用户认可分别记录。

重建后的核心从普通材料目录即可开始，无须绑定 PPT Master 后端、安装页面库或首次配置工作区。旧版 v0.9.x 材料和运行记录按[迁移说明](docs/migration-to-rebuilt-core.md)处理；旧命令到新 CLI 的映射见[规格 09.6](docs/specs/deck-master-rebuild-v1/specs/09-cli-and-host-protocol.md)，也可运行 `deck-master legacy-map` 查看。

## 适用人群

Deck Master 服务于需要讲清商业方案的人：解决方案架构师、顾问、提案者、竞标者和演讲者。工作流程覆盖材料理解、主线组织、制作、审查与改稿。

## 安装

CI 测试覆盖 Python 3.11 和 3.12。包元数据允许 Python 3.13，但尚未纳入测试矩阵；不支持 Python 3.14。

安装发行版本时，请一起下载 wheel 与 `release.json`，按[托管安装说明](docs/getting-started.md#install-a-release)操作。以下命令用于源码开发：

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

如果本地 Python 无法在虚拟环境中初始化 pip，可使用等价的 uv 流程：

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

旧工作台的命令是 `deck-master ...`；源码环境中也可用 `python -m deck_master ...`。`scripts/install.sh` 安装的 Rust 命令是 `deck`。激活发行版本时会注册 Master、Content、Design、Review 四个 Codex Skill，详见[安装说明](skills/deck-master/references/installation.md)。

## 新装

从源码同时安装 Rust 命令、生产工具和 Codex Skill：

需要 Rust 1.88 或更新版本，最低版本由 Cargo 检查。

```bash
./scripts/install.sh
```

脚本会构建 Web UI，把 `deck` 装到 `~/.local/bin`，用 Python 3.12 在
`~/.local/share/deck/venv` 建立独立的 deck-tools 环境，并把 `deck-skill/`
链接到 `~/.codex/skills/deck`。不执行托管安装的激活或回滚。

可选参数：`--prefix DIR`、`--skill-dir PATH`、`--dry-run`。若
`~/.local/bin` 不在 PATH 中，请加入，或用该目录下 `deck` 的完整路径。
Skill 路径必须是新的，或已经是指向本仓库 `deck-skill/` 的同一链接；已有
其他文件或链接时脚本报错，不会覆盖。

安装后用 `deck new ./my-deck --title '方案标题'` 新建作品目录。链接的
Skill 说明首跑命令。

新装用户不用设置 `DECK_TOOLS_PYTHON`：`deck` 使用安装前缀里的 venv。
`cargo install --force` 会换掉 `PREFIX/bin` 里已有的 `deck`。deck-tools 是对当前
checkout 的可编辑安装，移动或删除这份 checkout 后，该 venv 会无法导入 deck-tools。

把旧项目迁到新目录，旧目录保持原样：

```bash
deck-master legacy-export <project> <out>
deck import <out> <new>
```

`<out>` 必须在 `<project>` 之外。导入后的原图和 SVG 以 `basis` `imported` 写入，总览里这些页显示为已过期。`deck export pptx` 会报告 `input_changed`。

最近 PPTX 清洗成功后才可下载，保留其自身的页序和讲稿。清洗失败或缺工具时，
正文仍可导入、编辑；报告中的 `last_export:false` 与 `unmapped` 会说明最近 PPTX
未迁入的原因及下一步。未清洗文件仍留在旧项目和迁移档案中。

## 快速开始

使用自己的完整材料与任务说明。以下命令分阶段执行；请用实际返回 Task 中的 ID 和 hash 替换占位符，不能直接将尖括号内容作为参数。

示例假定 `deck-master` 已在 PATH 中，例如已激活上面的源码虚拟环境。托管安装可使用所选安装前缀下 `.deck-master/bin/deck-master` 的绝对路径，或先把该目录加入 PATH。

```bash
# 1. 新项目默认使用 workbench.v3，保留指令证据；初始仅生成提案，
#    create 不授予制作权限。
deck-master capabilities
deck-master create --brief-file ./brief.txt --source ./materials \
  --out ./my-deck --no-open
deck-master continue --project ./my-deck --no-open

# 2. 读取 Task 冻结的准确方法及完整材料/上下文。
#    仅在 capabilities.read_protocols 声明支持时使用 v2；
#    否则省略读取选项使用 v1。v2 默认返回完整正文。
deck-master methods --project ./my-deck --task-id <task_id> --read \
  --read-protocol work_context.v2 --body-mode full

# 3. 执行前认领实际 Task。对 required_capabilities 中每个值重复传入
#    --capability，仅声明 Host 实际支持的能力。
deck-master task start --project ./my-deck --task-id <task_id> \
  --execution-ref <actual_Host_execution> --supported-protocol <protocol_version> \
  --capability <required_capability>

# 4. 执行返回的作用域，再提交实际结果信封。
deck-master task accept --project ./my-deck --task-id <task_id> \
  --operation-id <operation_id> --produced-against <produced_against> \
  --result ./result.json
deck-master continue --project ./my-deck --no-open

# 5. 打开可读结果，按所选用途导出。
deck-master view --open --project ./my-deck
deck-master export --project ./my-deck --out ./out --purpose review
```

逐次遵循 `continue` 的返回结果：framing 和 argument 产出提案，之后按当前请求推进 page_copy、适用的 speech 和审查。`compose.v2` 结果使用 `schema_version=compose_result.v2`、实际 Task 的 variant/IDs/produced_against/eligibility_digest，以及该 variant 对应的 payload；每个阶段分别提交。详见[结果合同](src/deck_master/resources/contracts/)与[协作方法](skills/deck-master/references/collaboration-routing.md)。

当 `continue` 要求方向决定时，用 `collaboration decision --input decision.json` 记录真实决定，再用 `collaboration adopt-proposal --input adoption.json` 结合当前 CAS 和准确提案进行采用。存在覆盖本次工作的真实授权时，才使用 `collaboration grant`。复制交接或认领任务不代表批准；缺少授权或可信独立审查渠道时，保留具体缺口。

仅需内容时，可用 `create --request-input request.json` 指定 `intent=content_only`、所需 `content_intent`（`plan_only|write_only|speech_only|content_full`）、实际作用域和指令证据。按 `completion.state/outputs/checks/missing` 查看结果；内容完成后返回所请求的产物，不自动启动设计或 PPT 制作。已确认的完整稿可通过 `create --draft draft.json` 或 `import-draft` 导入，提供真实导入指令和 `imported_mapping`，无需另造 Narrative。教学内容也不必附加销售 CTA。

`full_deck` 按实际制作范围继续。生成须经过冻结请求、分配调用额度、begin → 真实工具调用 → settle → accept 的完整链路。检查实际原图、PPT 预览、逐页与终稿审查后，运行 `final-readiness`、以 `--purpose delivery` 导出，并用 `handoff-check --purpose delivery` 检查实际导出的 PPTX。`review` 可返回带真实未解决项的未完成可读稿；`needs_tool` 和 `needs_reviewer` 保留实际原因。

显式本地 `--file` 校验只接受稳定的普通文件，包括项目外的副本；符号链接、设备、FIFO 和目录会被拒绝。HTTP 交付检查器不接受本地路径。文件读取受已知输出长度限制，并复查文件替换或增长。

审阅用途的 `handoff-check` 可将准确匹配的已提交历史原件识别为 `historical_output`，列出所有匹配的 revision 和输出引用；该结果仍不能用于当前正式交付。识别过程不会重建历史脱敏副本。历史索引不完整时会报告缺口；索引完整也不表示重读了全部历史 PPTX，只有匹配原件会进行字节核验。

个人状态清理会在提交前保留操作与请求。若响应丢失，重新打开“个人状态与恢复”，使用“核实并重试原清理”，重放同一请求并保留后续草稿。不含输入 digest 的历史清理回执仍可读取，其备份仍可使用，但不能证明准确请求重放，也不被当作新的清理指令。

内容前审报告保留每条阻塞记录，分别展示 `blocking_record_count` 与 `logical_finding_count`。后者按显式的同 owner 替换链统计，不会因为本地 ID 相同就合并无关 finding。已有 eligibility 字段 `open_findings` 继续作为记录数的兼容别名；UI 分别标注两种计数，均不放宽制作门禁。

需求或材料变化后，先持久化更新，再继续同一项目：

```bash
deck-master inputs show --project ./my-deck
deck-master inputs update --project ./my-deck --patch update.json \
  --base-revision <original_revision_id> --operation-id <saved_unique_id>
deck-master operations show --project ./my-deck --operation-id <saved_unique_id>
```

响应丢失时保留原始 payload、base、ID 和相对路径上下文。准确重放会返回原结果及当前 revision；再用新的 `continue` 获取当前待办。`unknown` 状态不能换新 ID 重试。新的无变化输入更新可能只推进回执 revision，同时保持 Page/输入依据及任务。普通 `inputs update` 和 `content inputs` 使用不同的 ID/digest 合同，重试前阅读[输入恢复说明](skills/deck-master/references/input-update.md)。

[N6 常规任务证据](https://github.com/MainQuestAI/Deck-Master/blob/62dfcfc5637f0bee2358074c4458047689dd5299/docs/reports/rc4/iteration-20261019/N6-evidence.md)保留原分阶段观察。后续在 PR125 的 `d7ec4530` 上进行实际安装版 Host 验证，完成原生独立审查、两页原生图像观察、SVG/PPT、真实渲染和正式交付，得到 `ready` 与 `handoff-check verified`。这是一次完整任务的观察；字体处理及尚未验证的 WPS 编辑范围见[验证范围与已知限制](docs/getting-started.md#known-limitations)。

## 工作台

当前使用方式见[安装与首次运行指南](docs/getting-started.md)。[RC3 试用说明](docs/rc3-tryout.md)是历史兼容入口。

工作台提供项目入口、制作总览、内容与材料、整稿画廊、风格校准、任务与交付。每页保留来源、正文、提示词、原图、SVG 和 PPT 视图。`deck-master view --open --project <dir>` 为每个项目启动或复用一个本机服务。

工作台是唯一 UI。旧 `/legacy/` 界面与 `--ui legacy` 选项已移除，现有项目数据和 CLI 流程继续支持。

工作台写入需要每个服务独立的会话 token 和同源 Origin 检查；读取在本机回环地址开放。服务仅绑定 `127.0.0.1`。

## 能力边界

重建核心提供以下能力与约束：

1. 生成 PPTX 包含可编辑的真实形状和文本（`editability=editable_shapes_and_text`）；表格和图表由形状与文本组合，尚非 Office 原生数据对象。
2. 各阶段显示真实状态：等待 Host 的任务为 `awaiting_host`；`review` 导出可包含未完成稿及真实缺口清单；`delivery` 要求当前检查通过。
3. 渲染器与字体缺口通过 `needs_tool` 报告实际原因。
4. 审阅工作台从项目相对路径对象提供 content / blueprint / SVG / PPT 四种真实视图。

专业人工审查与桌面编辑验证，在实际执行前保持 `not_evaluated`。

## 诊断

```bash
deck-master doctor --step compose   # 内容输入
deck-master doctor --step render    # 渲染工具链（soffice/pdftoppm/rsvg-convert）
deck-master doctor --step export    # 交付前检查
```

渲染器或字体缺口逐步报告为 `needs_tool`，保留实际原因，不静默回退到测试 fixture。

## 项目文档

从[文档导航](docs/README.md)查找使用指南、继承工程规格与带日期的证据。历史报告不能证明当前候选已通过，详见[归档索引](docs/archive/README.md)。

- [安装、首次运行、Host 要求与升级](docs/getting-started.md)
- [核心理念：从业务判断到商业表达](docs/product-philosophy.md)
- [下一轮商业表达能力：总方案与开发卡](docs/specs/deck-master-business-expression-20261029/README.md)
- [Agent 入口](AGENTS.md)
- [Agent 任务索引](docs/agent-task-index.md)
- [Agent 恢复手册](docs/agent-recovery-playbook.md)
- [继承的 RC4 增量](docs/specs/deck-master-next-iteration-20261019/README.md)
- [迁移到重建核心](docs/migration-to-rebuilt-core.md)
- [支持与反馈](SUPPORT.md)
- [Issue 维护](docs/issue-maintenance.md)
- [贡献指南](CONTRIBUTING.md)
- [安全政策](SECURITY.md)
