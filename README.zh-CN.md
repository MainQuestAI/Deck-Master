# Deck Master

[English](README.md) | [简体中文](README.zh-CN.md)

Deck Master 是面向商业方案创作与表达的 AI 原生工作台，帮助解决方案架构师、提案者和演讲者，将复杂材料组织成清晰、连贯、有真实业务依据的 deck。

## 核心理念

一份好的 deck，始于对业务的理解与判断：这次要讲清什么，为什么值得讲，各部分如何构成一个整体。我们希望帮助作者理清问题、提炼能够统领方案的主线，并将它展开为完整的说明，把复杂的事情讲简单，把抽象的事情讲具体。

产品围绕三个原则发展：

- **以任务决定表达。** 作者的商业任务决定主张、重点和内容取舍；受众的知识与经验决定如何讲清楚。
- **以理解组织内容。** 有解释力的业务框架连接需求、能力与场景，并贯穿整套方案和讲述过程。
- **让视觉承担说明。** 文字、图形与实例共同呈现关系、过程和取舍，文件形式与制作工具服务于表达目的。

这些原则指导产品发展。当前工作台通过 `deck` 命令和本机 Web UI 连接内容策划、可编辑 SVG/PPT 制作、审查与修改。现阶段的实现范围见[能力边界](#能力边界)。

**版本：** `1.1.0`（Rust 命令 `deck`、Python 包 `deck-master` 与 `deck-tools`、WebUI）。源码版本、构建产物、当前安装和公开 GitHub Release 分别记录。使用前请阅读[安装与首次运行指南](docs/getting-started.md)。迁移、2026-11-04 维护者核对与已知限制见[1.1.0 发版说明](docs/releases/1.1.0.md)。**许可证：** Apache-2.0。

1.1.0 的作者路径是 `rust/` 核心、`deck-tools/` 生产工具、`frontend/` 中由 `deck serve` 提供的 WebUI，以及 `deck-skill/` 中的 Codex Skill。从普通材料目录即可开始，无须 PPT Master 后端或页面库。旧 Python 工作台（`src/deck_master/` 的 `deck-master`，以及 `skills/` 下四个 Skill）只做维护。

## 适用人群

Deck Master 服务于需要讲清商业方案的人：解决方案架构师、顾问、提案者、竞标者和演讲者。工作流程覆盖材料理解、主线组织、制作、审查与改稿。

## 安装

需要 Rust 1.88 或更新版本，最低版本由 Cargo 检查。生产工具使用 Python 3.11 或 3.12（CI 与 `scripts/install.sh` 使用 3.12）。`deck-tools` 的包元数据允许 3.13，排除 3.14。

从源码安装：

```bash
./scripts/install.sh
```

脚本会构建 Web UI，把 `deck` 装到 `~/.local/bin/deck`（`--prefix` 时为
`<prefix>/bin/deck`，不是 `<prefix>/deck`），用 Python 3.12 在
`<prefix>/share/deck/venv` 建立独立的 deck-tools 环境，并把 `deck-skill/`
链接到 `~/.codex/skills/deck`。不执行托管 Python 发行版的激活或回滚。

可选参数：`--prefix DIR`、`--skill-dir PATH`、`--dry-run`。若
`<prefix>/bin` 不在 PATH 中，请加入，或直接运行 `<prefix>/bin/deck`。
Skill 路径必须是新的，或已经是指向本仓库 `deck-skill/` 的同一链接。
指向其他位置的软链接会使脚本退出 2，并提示「已存在且指向其他位置」；
只删除该软链接后再运行。步骤见
[安装说明](docs/getting-started.md#install-from-source)。

安装后用 `deck new ./my-deck --title '方案标题'` 新建作品目录。链接的
Skill 说明首跑命令。

新装用户不用设置 `DECK_TOOLS_PYTHON`：`deck` 使用安装前缀里的 venv。
`cargo install --force` 会换掉 `PREFIX/bin` 里已有的 `deck`。deck-tools 是对当前
checkout 的可编辑安装，移动或删除这份 checkout 后，该 venv 会无法导入 deck-tools。

在 worktree 中开发（不要共用另一个 checkout 的 venv）：

```bash
uv venv --python 3.12 --seed .venv
.venv/bin/python -m pip install -e "./deck-tools[dev]"
export DECK_TOOLS_PYTHON="$PWD/.venv/bin/python"
(cd frontend && npm ci && npm test && npm run build)
(cd rust && cargo test)
```

旧 Python 工作台仍可用 `pip install -e ".[dev]"` 安装，命令为 `deck-master`。
该线只做维护，见 [AGENTS.md](AGENTS.md) 第 12 节。

## 迁移旧项目

把旧 Python 项目迁到新目录，旧目录保持原样：

```bash
deck-master legacy-export <project> <out>
deck import <out> <new>
```

`<out>` 必须在 `<project>` 之外。导入后的原图和 SVG 以 `basis` `imported` 写入，总览里这些页显示为依据已变。`deck export pptx` 会报告 `input_changed`。未写入 purpose 的 `visual_spec.intent`，以及当前修订以外的旧修订，会出现在 `unmapped`。

最近 PPTX 清洗成功后才可下载，保留其自身的页序和讲稿。清洗失败或缺工具时，
正文仍可导入、编辑；报告中的 `last_export:false` 与 `unmapped` 会说明最近 PPTX
未迁入的原因及下一步。未清洗文件仍留在旧项目和迁移档案中。

v0.9.x 运行目录仍按[迁移说明](docs/migration-to-rebuilt-core.md)处理。

## 快速开始

使用自己的完整材料与任务说明。请用命令实际返回的路径和 ID 替换占位符，不能直接将尖括号内容作为参数。示例假定 `scripts/install.sh` 之后 `deck` 已在 PATH 中。

```bash
# 1. 新建作品目录，只添加作者指定的材料。
deck new ./my-deck --title '方案标题'
deck --project ./my-deck material add ./materials/brief.pdf
deck --project ./my-deck material text m1

# 2. 读取、修改并保存。put 按 --base 比较，只写入改动过的单元。
#    冲突时退出码 5，当前版本不变。
deck --project ./my-deck get > ./my-deck/current.json
deck --project ./my-deck put --base <version> ./my-deck/patch.json
deck --project ./my-deck show
deck --project ./my-deck export md > ./my-deck/manuscript.md

# 3. 出图、重建 SVG 或导出 PPTX 前检查本机工具与所选字体。
deck --project ./my-deck doctor --fonts 'Source Han Sans SC'

# 4. 先原图再 SVG，然后构建 PPTX。Host 每次调用 ImageGen 前先登记。
deck --project ./my-deck run start image --pages p1,p2
deck --project ./my-deck run call <run> p1
deck --project ./my-deck run result <run> p1 ./page.png
deck --project ./my-deck run start svg --pages p1,p2
deck --project ./my-deck run result <run> p1 ./page.svg
deck --project ./my-deck build
deck --project ./my-deck export pptx

# 5. 打开本机界面，只绑定 127.0.0.1。
deck serve ./my-deck
```

`deck-skill/` 中的 Skill 说明判断方法和该调用哪条命令。可运行示例如
[commands.md](deck-skill/references/commands.md)。
页上意见：`deck review add` / `list` / `resolve`。用 `deck restore <version>`
把历史稿恢复为新版本（不删除后来的文件、run 与 build）。

## 工作台

`deck serve <project>` 为该项目启动本机界面，打印回环地址，并提供嵌入的 WebUI。
Host 或 Origin 不是本次进程的本机地址时一律拒绝。不设登录或会话。

界面提供总览与画廊（原图、编译预览、过期标记）、正文与讲稿编辑、待处理意见、
run 状态与停止、候选比较与手动采用、构建与 Markdown/PPTX 下载、版本恢复。
浏览器不启动生图或 SVG 任务；Host 在 CLI 上使用 `deck run`。一次 `deck serve`
只服务一个项目，没有项目列表。

请保管打印出的地址。服务只绑定 `127.0.0.1`。

## 能力边界

1. 生成的 PPTX 含可编辑的形状和文本。表格和图表由形状与文本组合，不是 Office 原生数据对象。
2. 不完整作品可以保存、导出 Markdown 并构建。缺 SVG 或 SVG 已过期的页列在下载旁，不拦截导出。
3. 取消后的结果、以及依据已变的结果只保存、不自动采用。同一 run 页的后续结果作为显式候选。
4. 渲染器与字体缺口以退出码 3（`needs_tool`）报告实际原因。
5. 意见绑定添加时的版本。界面写入人工意见；CLI 的 `self_check` 只表示当前 Host 自检。

2026-11-04 维护者核对见[1.1.0 发版说明](docs/releases/1.1.0.md#maintainer-acceptance-2026-11-04)。

## 诊断

```bash
deck doctor --fonts 'Source Han Sans SC'
```

检查 deck-tools 解释器、`soffice`、`pdftoppm`、`fc-match` 和指定字体。缺工具时保留实际原因，不回退到测试 fixture。

## 项目文档

从[文档导航](docs/README.md)查找使用指南、继承工程规格与带日期的证据。历史报告不能证明当前源码线已通过，详见[归档索引](docs/archive/README.md)。

- [安装、首次运行、Host 要求与已知限制](docs/getting-started.md)
- [1.1.0 发版说明](docs/releases/1.1.0.md)
- [Rust 重写开发稿（现行架构）](docs/specs/rust-rebuild/README.md)
- [核心理念：从业务判断到商业表达](docs/product-philosophy.md)
- [下一轮商业表达能力：总方案与开发卡](docs/specs/deck-master-business-expression-20261029/README.md)
- [Agent 入口](AGENTS.md)
- [新 Skill](deck-skill/SKILL.md)
- [旧 Python 任务索引](docs/agent-task-index.md)
- [旧线恢复手册](docs/agent-recovery-playbook.md)
- [v0.9 迁到上一版重建核心](docs/migration-to-rebuilt-core.md)
- [支持与反馈](SUPPORT.md)
- [Issue 维护](docs/issue-maintenance.md)
- [贡献指南](CONTRIBUTING.md)
- [安全政策](SECURITY.md)
