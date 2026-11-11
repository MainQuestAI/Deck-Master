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

**版本：** `1.1.2`（Rust 命令 `deck`、Python 生产工具包 `deck-tools`、WebUI）。源码版本、构建产物、当前安装和公开 GitHub Release 分别记录。使用前请阅读[安装与首次运行指南](docs/getting-started.md)。本版改动与已知限制见[1.1.2 发版说明](docs/releases/1.1.2.md)。**许可证：** Apache-2.0。

现行作者路径是 `rust/` 核心、`deck-tools/` 生产工具、`frontend/` 中由 `deck serve` 提供的 WebUI，以及 `deck-skill/` 中的 Codex Skill。从普通材料目录即可开始，无须 PPT Master 后端或页面库。旧 Python 工作台与官方导出器已移出仓库。

## 适用人群

Deck Master 服务于需要讲清商业方案的人：解决方案架构师、顾问、提案者、竞标者和演讲者。工作流程覆盖材料理解、主线组织、制作、审查与改稿。

## 安装

需要 Rust 1.88 或更新版本，最低版本由 Cargo 检查。生产工具使用 Python 3.11 或 3.12（CI 与 `scripts/install.sh` 使用 3.12）。`deck-tools` 的包元数据允许 3.13，排除 3.14。

从源码安装：

```bash
./scripts/install.sh
```

脚本先在 `<prefix>/share/deck/installations/` 准备完整组件目录：含内嵌前端的 CLI、
非 editable 的 deck-tools venv、四个职责 Skill 及共享资源副本。`<prefix>/share/deck/current`
指向选中的目录，`<prefix>/bin/deck` 解析一次物理目录后执行真实二进制。
准备失败不切换当前安装，旧进程继续使用旧目录工具；venv 在最终位置创建，不移动。
安装不依赖源码 checkout；Python、字体、渲染器和外部 Host 仍需环境提供。

默认把 `deck-master`、`deck-content`、`deck-design`、`deck-review` 四个完整职责目录
软链接到 `~/.codex/skills`，让 Codex 能发现入口。每个目录有真实的 `SKILL.md`，
并链接到共享 `references/` 与 `assets/`。`--skills-root DIR` 更换技能根目录，
`--prefix DIR` 指定 CLI 安装根，`--dry-run` 只打印计划、不写入。
不再安装兼容入口 `deck`，`--skill-dir` 已取消。

再次安装会只删除指向本源 `deck-skill/` 的旧 `deck` 软链接，并把仅含三条托管链接的
旧职责包装目录升级为整目录软链接；已有的新形态链接保持原样。
包装目录里有其他文件，或同名路径被外来入口占用时，脚本会在任何写入前退出 2，
打印路径和目标。若是旧 Python 线留下的同名软链接，先移走该链接（只删链接，
不删它指向的目录）再安装。非本源管理的 `deck` 会保留，并提示可能抢触发。
新开的会话沿用自己的 PATH。`command -v deck` 若不是 `<prefix>/bin/deck`，请直接运行 `<prefix>/bin/deck`，或把 `<prefix>/bin` 放到那个结果之前。非默认 prefix 会把这个绝对路径写进安装后的 commands.md。步骤见
[安装说明](docs/getting-started.md#install-from-source)。

安装后按[快速开始](#快速开始)制作第一份方案。

标准安装和升级都使用 `scripts/install.sh`，不用设置 `DECK_TOOLS_PYTHON`。
无法确认归属的 CLI 入口保留并报冲突；旧 Cargo 安装通过安装记录及关联构建产物一致性判断，不执行未知二进制。
迁移时保留旧 venv 和源码供旧进程使用；停止旧进程后可另行处理，不自动删除。

在 worktree 中开发（不要共用另一个 checkout 的 venv）：

```bash
uv venv --python 3.12 --seed .venv
.venv/bin/python -m pip install -e "./deck-tools[dev]"
export DECK_TOOLS_PYTHON="$PWD/.venv/bin/python"
cargo install --path rust --root "$PWD/.dev-prefix"
export PATH="$PWD/.dev-prefix/bin:$PATH"
(cd frontend && npm ci && npm test && npm run build)
(cd rust && cargo test)
```

## 导入已有档案

旧 Python 工作台、`deck-master` 命令及其 `legacy-export` 导出器已删除，旧项目不再提供官方导出。历史说明见已发布的 [1.1.0 发版页](docs/releases/1.1.0.md#upgrade-and-migration)。

`deck import <archive> <new>` 仍可把已有的 `legacy-export.v1` 档案导入新目录，不改写档案。

## 快速开始

1. 在本仓库目录运行 `bash scripts/install.sh` 安装，详见[安装](#安装)和[安装指南](docs/getting-started.md#install-from-source)。确保 `deck` 已在 PATH 中。
2. 在本仓库目录打开 Codex，输入：

   > 用 examples/first-run/zh/material.md 按 examples/first-run/zh/brief.md 做一份 6 页方案，放在 ./first-deck。

   [样例](examples/first-run/README.md)完全由合成材料构成。四个 Skill 会处理所需命令。
3. 运行 `deck serve ./first-deck` 查看草稿。服务绑定 `127.0.0.1`，并打印可打开的 URL。

`deck-master`、`deck-content`、`deck-design`、`deck-review` 共用同一份
`references/` 和 `assets/`，都调用 `deck`。其余命令见
[commands.md](deck-skill/references/commands.md)。

## 工作台

`deck serve <project>` 为该项目启动本机界面，打印回环地址，并提供嵌入的 WebUI。
Host 或 Origin 不是本次进程的本机地址时一律拒绝。不设登录或会话。

界面提供总览与画廊（原图、编译预览、过期标记）、正文与讲稿编辑、待处理意见、
run 状态与停止、候选比较与手动采用、构建与 Markdown/PPTX 下载、版本恢复。
浏览器不启动生图或 SVG 任务；Host 在 CLI 上使用 `deck run`。一次 `deck serve`
只服务一个项目，没有项目列表。

请保管打印出的地址。服务只绑定 `127.0.0.1`。

## 能力边界

1. 生成的 PPTX 含可编辑的形状和文本。带 `data-native-table="true"`、完整直线网格与归属绑定的支持表格可成为原生 PPT Table；普通绘制表格仍是形状和文字。图表不保证成为 Office 原生数据图表。
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
- [1.1.2 发版说明](docs/releases/1.1.2.md)
- [Rust 重写开发稿（现行架构）](docs/specs/rust-rebuild/README.md)
- [核心理念：从业务判断到商业表达](docs/product-philosophy.md)
- [下一轮商业表达能力：总方案与开发卡](docs/specs/deck-master-business-expression-20261029/README.md)
- [Agent 入口](AGENTS.md)
- [deck-master](deck-skill/deck-master/SKILL.md)、[deck-content](deck-skill/deck-content/SKILL.md)、[deck-design](deck-skill/deck-design/SKILL.md)、[deck-review](deck-skill/deck-review/SKILL.md)
- [支持与反馈](SUPPORT.md)
- [Issue 维护](docs/issue-maintenance.md)
- [贡献指南](CONTRIBUTING.md)
- [安全政策](SECURITY.md)
