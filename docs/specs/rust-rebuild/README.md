# Deck Master Rust 重写开发稿 v1.2

日期 2026-10-31，源码基线 `main@035845f228d1`。本稿合成自三份文件：《DeckMaster Rust 核心与后端全面重构方案》v1.1（PDF）、10-31 合并讨论稿和 Claude 的评审，三份都没有入库。之后又并入了 10-31 对 v1.2 的评审中经过核实的条目。本稿替代 v1.1 作为开发依据；开发规范以 [AGENTS.md](../../../AGENTS.md) 为准，两者冲突时以 AGENTS.md 为准。

## 0. 相对 v1.1 的变化

- 写入：不设单写入服务。CLI 与本地服务调用同一套用例，各自直连 SQLite。
- 工具：复制成独立 Python 包，旧线文件不改；同时处理 v1.1 与讨论稿都没列出的 `export_sanitize → icons` 依赖。
- SVG 的文字编号只由工具计算，Rust 不重复实现。
- 首切片由 Codex 会话主导；界面按钮直接触发生成，等验证 `codex app-server` 能调用 ImageGen 后再做。
- 改字后按原图和新正文重建该页 SVG，不重新生图。
- 不移植托管安装；旧项目经旧线一次性导出，再由 Rust 导入。
- 人工保存与生成结果的采用分开处理依据变化（讨论稿）。
- 去掉请求编号：保存与交回结果本身可以安全重试（3.4、3.5）。
- v1.1 的 D01–D16、A01–A20 改为第 2.2 节的 8 条保护和各切片的完成判断。
- 新 Skill 在切换前放在 `deck-skill/`。旧打包钩子会拒绝 `skills/` 下未登记的文件，切换时再改名为 `skills/deck/`。
- 每个切片从 main 开分支、合回 main，不设长期集成分支。新代码放在独立目录，旧线的打包不会把它们收进去。

## 1. 目标

作者围绕一次商业任务，从材料得到可读稿、样页和整套可编辑 PPTX，并能顺畅改稿。

- 核心与后端业务用 Rust 重写。生产工具（SVG 编译为 PPTX、渲染、回读、字体、材料解析、导出清洗）保留为独立 Python 工具包，只处理文件。
- 0 内置 LLM Provider。推理与生图由 Host 执行，首个 Host 是 Codex。
- 首切片：作者在 Codex 会话里提要求，Codex 经 Skill 调用 `deck` 命令；界面用于看稿、改字、停止和下载。
- 方法卡 M01–M10 与案例 E01–E06 保留，按需读取。

## 2. 边界

### 2.1 不做，实现时也不要加回

- 资格判断、方向批准、代理授权、writer 等级、冻结方法清单与 SHA 核对、方法应用证明
- 通用读集、操作信封、请求编号、通用恢复引擎、租约与代次、审阅 pass 汇总、审阅者独立性判定
- 内容寻址版本、对象仓库、跨存储事务、单写入服务、实例锁、服务发现、跨进程业务锁
- 讲稿码点分段、强制估时、`table_roles`、`design_policy`、Narrative 节点映射、材料证据等级
- 工具协议版本、能力协商、插件平台、沙箱、托管安装的激活与回滚事务
- 数字配额（模块数、行数、schema 行数、命令比例、零协议词、零确认点、点击数）、复杂度棘轮测试、固定措辞断言、整组验收门
- 同页自动合并、每次读取都重新校验全部文件
- 项目级"结果未知"冻结、attempts 表、build 对缺页或过期页的硬拒、新旧产物逐份对比、扩展旧线的边界测试或豁免清单

SQLite 自身的写锁属于存储层，照常使用。禁止的是业务层的锁、租约和代次。

### 2.2 保留的保护（每条对应一种真实故障）

| 保护 | 防止的故障 |
| --- | --- |
| 版本只追加，可恢复到任一历史版本 | 丢稿 |
| 保存时按单元比较基线（3.4） | 覆盖别人更新的内容 |
| run 取消后，迟到结果不自动采用（3.5） | 取消后仍生效 |
| 生图调用先登记，设上限，记录"已发出、结果未知"（3.5） | 重复的外部消耗 |
| 依据已变的生成结果不自动采用（3.5） | 把旧图当成新稿 |
| 附件先完整落盘，再提交引用 | 中断后出现悬空引用 |
| 本地服务只绑定 127.0.0.1，并校验 Host / Origin（3.7） | 跨站请求篡改作品 |
| 导出清洗（路径、内部 ID、图片元数据） | 交付文件泄露本机信息 |

## 3. Rust 后端

### 3.1 目录与技术

```
rust/                 Cargo 包 deck（一个二进制 + lib）
  src/model.rs        作品类型（serde）
  src/store.rs        SQLite 与 files/
  src/ops.rs          用例：保存、恢复、run、build、导出、审阅
  src/tools.rs        调用 deck_tools 子进程
  src/prompts.rs      生图与 SVG 任务文本
  src/export.rs       Markdown 导出
  src/cli.rs、src/server.rs
deck-tools/           Python 包 deck_tools（第 4 节）
deck-skill/           新 Skill（第 6 节）
```

- Rust stable，edition 2024，提交 Cargo.lock。依赖：clap、serde、serde_json、rusqlite（bundled）、tiny_http、thiserror、sha2、tempfile。本地服务用同步请求线程，不引入异步运行时。
- 先在一个包内按文件分模块，出现真实需要时再拆。
- `rust.yml` 在 PR 和 `main` push 上自动执行 AGENTS.md 第 3 节的 Rust 检查与 deck-tools pytest；pytest 用 `-m "not render"` 排除 67 条需要 rsvg-convert/soffice 的用例，合并前须在本机全量运行。`rebuild.yml` 执行旧线检查，只在 `main` push 后自动运行，旧线的 PR 在合并前本地执行第 3 节的命令。两者都保留手动入口，功能分支 push 不单独触发 CI。
- 旧线按本次主干更新的 before/head 差异分流：只涉及 `rust/`、`deck-tools/`、`deck-skill/`、本开发稿目录或 `rust.yml` 时，跳过旧线测试并由 Group report 返回不适用；其他或混合路径仍执行旧线单元、渲染、浏览器和安装验证。日常单元使用 Python 3.12 / Node 22，手动触发时运行完整 2×2 矩阵。分流失败、适用检查失败或意外跳过，Group report 均返回失败。

### 3.2 存储

```
<project>/.deck/deck.db         SQLite
<project>/.deck/files/<sha256>.<ext>   原件、抽取文本、原图、SVG、预览、PPTX
<project>/.deck/work/<run_id>/  交给 Host 的任务文件夹，可删除
```

| 表 | 字段 |
| --- | --- |
| versions | id 自增、created_at、summary、deck_json |
| runs | id、kind（image/svg）、status（open/done/cancelled）、max_calls、calls_used、created_at |
| run_pages | run_id、page_id、basis、status（pending/started/done/unadopted）、result_file |
| builds | id、version_id、input_digest、pptx_file、findings_json、missing_pages、created_at |
| reviews | id、version_id、page_id、reviewer、method（self_check/other_model/human，界面显示为 自检/另一模型检查/人工意见）、text、status（open/resolved）、created_at |

- 当前作品就是 id 最大的那个版本。
- 写入使用短事务（BEGIN IMMEDIATE），并设 busy_timeout，让 CLI 与服务能同时打开同一个库。
- 文件按 sha256 命名，同一文件重复加入不会产生新文件。
- 格式版本记在 `PRAGMA user_version`：库的版本比程序高时，提示升级 deck；比程序低时，按迁移代码升级。

### 3.3 作品模型（deck_json）

```json
{
  "brief": {"title": "", "audience": "", "task_type": "", "goal": "", "constraints": [], "page_limit": null},
  "materials": [{"id": "m1", "name": "", "file": "<sha>", "text_file": "<sha>", "status": "read|needs_tool"}],
  "framing": {"thesis": "", "pillars": [{"title": "", "points": []}], "facts": [], "assumptions": [], "questions": []},
  "style": {"canvas": {"width_px": 1280, "height_px": 720, "slide_width_in": 13.333, "slide_height_in": 7.5},
            "palette": [], "fonts": [], "assets": [{"id": "logo", "file": "<sha>"}]},
  "pages": [{"id": "p1", "purpose": "", "layout": "", "content": {}, "notes": "", "todo": [], "refs": [],
             "image": null, "svg": null, "preview": null}]
}
```

- `task_type` 是自由文本（首提、竞标、改稿、培训……），Skill 据此决定加工重点。
- `content` 与旧 page.v2 的 `customer_visible` 同形：title、subtitle、body_blocks（paragraph / bullets / table）、labels、footnotes、callouts。块与条目的字段见 `src/deck_master/resources/contracts/page.v2.schema.json`。回读工具和旧项目导入都直接使用这个形状。
- 块与条目（包括表格的列、行和单元格）缺少 id 时，由保存补齐；页内出现重复 id 时，由保存重新分配，不因此拒绝保存。模型不手写 id。
- 新作品的画布默认是 1280×720 px，即 13.333×7.5 in 乘以 96。这样 SVG 的 px 换算成 PPT 的 pt 只需乘 0.75。旧项目导入时保留原画布。
- `todo` 记录本页待补项，`refs` 记录可选的材料出处，例如"m1 第 3 页"。两者只用于展示，不阻止任何动作。
- 作者字段（purpose、layout、content、notes、todo、refs）只由保存写入；产物字段（image、svg、preview）只由 run 写入，两者互不冲突。
- image 与 svg 记为 `{file, basis}`，basis 是生成时的依据摘要（3.5）。过期标记在读取时比较 basis 与当前依据得出，不落库。
- image 过期只是提示：小幅改字只需重建 SVG；内容或布局大改时，由作者决定是否重新生图。

### 3.4 保存

`deck get [--pages p3,p4]` 返回 `{version, deck}`。`deck put --base N file.json` 只提交改动过的单元，没有出现的单元视为未改。因此只取了几页的 Host 也能安全保存。

比较单元：brief、framing、style、order（页集合与顺序）、每页的作者字段。materials 与产物字段不参与比较。增删页时，同时提交该页和新的 order。

对每个单元取三个值：基线 B（版本 N）、提交 S、当前 C。

| 情况 | 处理 |
| --- | --- |
| S = B | 本单元未改，保留 C |
| S ≠ B，C = B | 采用 S |
| C = S | 已是目标值，不动 |
| S ≠ B，C ≠ B，C ≠ S | 冲突 |

- 合并按单元进行：每个单元各自取 S 或保留 C，不整份覆盖。
- 有冲突时整次保存不写入，返回冲突单元及其当前值。界面保留作者输入，并显示当前内容。
- order 中删掉的页如果在 B 之后被别人改过，算作 order 冲突。
- 没有冲突且有改动时写一个新版本；没有改动时直接返回当前版本号。
- 由此，不同页作者字段的修改都能保存；同页冲突可见；双方对 order 做了不同的改动时冲突；重试同一提交不会重复写入。界面编辑走同一个用例。
- 每个写操作（put、restore、run 的每一步）都在一个事务内完成读取、判断和写入；附件在事务开始前就已落盘。
- `deck restore <version>`：把该版本的作品复制为一个新版本。已产出的文件不删除，run 与 build 不回滚。

#### S1 命令与 JSON

`deck new <project> [--title 标题]` 新建空作品；其他命令以当前目录为项目，也可用全局参数 `--project <project>` 指定。S1 的命令输出默认为 JSON，`export md` 直接向 stdout 输出 Markdown，调用方可以重定向到文件。

- `show` 返回 `{version, title, thesis, materials, pages, history}`。materials 只有 `id/name/status`；pages 只有 `id/title/purpose/todo`，不展开正文；history 按新到旧列出 `id/created_at/summary`。
- `get` 返回 `{version, deck}`，deck 是 §3.3 的完整作品，另带从 pages 计算出的 `order: [page_id, ...]`。`get --pages p3,p4` 保留 brief、materials、framing、style，只返回选中的页，并省略 order，防止局部改稿误删未读取的页。
- `put --base N file.json` 接受 deck 对象，也接受 get 的完整输出。顶层可以只交 brief、framing、style、order 或 pages；brief、framing、style 各自是完整单元，省略的内部字段按空值或默认值处理。pages 是带 id 的页列表，每页省略的作者字段沿用基线；同页作者字段仍作为一个单元比较。materials、image、svg、preview 即使回传也不写入。成功返回 `{version, deck}`；发生冲突时退出码为 5，stderr 中附 `{unit, current}` 列表。
- 新增页必须同时交该页及包含它的 order；删除页必须同时交该页（`{id}` 即可）及去掉它的 order；只重排时交 order 即可。块、条目、列、行和单元格的 id 由保存补齐或去重，表格列引用随之修正。
- `material add <file>` 保存原件，再从该不可变副本解析，返回 `{version, material, extraction}`。extraction 保留工具的 text、locators、tables、image_pages、detail、status；`pending_visual` 表示 Host 仍须读图，material 的 `read` 只表示文件已解析。缺解析工具时保留原件并记录 `needs_tool`，退出码为 3；安装工具后重新 add 可补齐文本。相同文件重复加入不新增材料或版本。
- `material text <id>` 返回 `{id, status, path}`，path 是抽取文本的本地路径；未完成解析时退出码为 3。持久作品只记录相对文件名，不记录材料源路径。
- `restore <version>` 返回新版本的 `{version, deck}`。`export md` 包含任务、主张、页面正文、讲稿、待补项和可选出处，不要求作品完整。

开发时先按 AGENTS.md 创建本 worktree 的 venv，安装 `./deck-tools[dev]`，再设置 `DECK_TOOLS_PYTHON`。Rust 的跨语言命令测试也使用此解释器，不跳过缺依赖的测试。安装 CLI 可以使用 `cargo install --path rust --root ~/.local`，通过 `~/.local/bin/deck` 调用，无需修改 shell 配置。S1 只建立 versions 表；后续切片在引入实际用例时增加其所需表和格式迁移。

### 3.5 后台工作（run）

run 用于需要 Host 执行、作者可以中途停止的工作：生图（image）和按原图重建 SVG（svg）。每一类同时最多有一个 open 的 run；已有同类 open run 时，start 报错并给出那个 run。

1. `deck run start image --pages p3,p4 [--max-calls N]`：记录每页当时的依据，写好 `work/<run_id>/` 下的提示词与附件。`max-calls` 默认为页数 × 2，作者可以改。
2. `deck run call <run> <page>`：run 已取消或已达上限时拒绝；否则计数加一，该页标为 started。Host 在每次调用 ImageGen 之前执行这一步。该页已有结果未知的调用时，要加 `--retry` 才会登记，避免盲目重发。
3. `deck run result <run> <page> <file>`：保存文件。run 仍为 open 且该页依据未变时，自动采用到页面；否则只保存，标为 unadopted，界面写明原因，作者可以用 `deck run adopt` 手动采用。
4. `deck run cancel <run>`：直接改状态，不需要填写说明。之后的 call 被拒绝，迟到的 result 只保存、不自动采用。
5. `deck run show [<run>]`：列出每页状态。started 但没有结果的页显示为"结果未知"，是否重试由作者或 Host 决定；重试同样计数。

依据的组成：image 取该页的 content、layout、purpose 与 style；svg 取该页的 content、image 文件与 style。

svg 类没有外部付费调用，不需要 `run call`，也没有 max_calls。它的 result 先经过 `deck_tools check-page`：

- 编译失败：不保存，返回出错的元素与原因，Host 修改后重新提交。
- 编译成功：保存 SVG、单页预览 PNG 和回读发现。回读发现只报告，不阻止采用。

全部页面都已采用时，run 自动变为 done。

### 3.6 构建与导出

- `deck build`：取每页当前的 SVG，调用 `deck_tools build`（编译、回读、清洗），并记录输入摘要：页序，加每页 svg 与 notes 的哈希。缺 SVG 的页不进入 PPTX；SVG 已过期的页照常编入，回读会报出文字不一致。
- `deck export md`：任何时候都可以导出可读稿，包括未完成的作品，待补项照常显示。
- `deck export pptx`：给出最近一次构建。该构建的输入摘要与当前作品不一致时给出提示。不用版本号判断，因为 restore 会产生编号更大、内容更旧的版本。
- build 和 export 的输出里，以及界面的下载按钮旁，都列出缺 SVG 的页和 SVG 已过期的页。
- 编译只在执行 `deck build` 时发生。读取、摘要、列表都不会触发编译。
- 构建是一次本地命令，需要中断时用 Ctrl-C，不经过 run 机制。

### 3.7 本地服务与界面

`deck serve <project>`：只绑定 127.0.0.1，端口由系统分配，启动时打印地址；Host 或 Origin 不是本机的请求一律拒绝。不设登录或会话。

服务与 CLI 共用 ops，各自直连 SQLite。服务不缓存作品状态，界面按版本号轮询变化。

接口：`GET /api/deck`、`PUT /api/deck?base=N`、`POST /api/runs/{id}/cancel`、`POST /api/build`、`GET /api/files/{sha}`（sha 只接受 64 位十六进制）、`GET /api/export/{md|pptx}`、`GET|POST /api/reviews`（S5 起用）、`POST /api/restore/{version}`。接口以 S4 完成判断所需为限；手动采用被拒收结果的接口（对应 `deck run adopt`）随 S5 补；导出只列出缺失和过期的页，不拦截（见 2.1、3.6）。

界面使用 #250 的新版 WebUI（React 18 + Vite，`frontend/`，设计为 S00–S07 八个工作区与 U01–U05 五个共用容器）。#250 目前是不调用任何接口的演示稿，数据在 `constants/data.js` 里。

S4 必须能用的最低要求：整稿浏览（原图、预览、过期标记）、改正文与讲稿（冲突时保留作者输入）、run 状态与停止、构建与下载、版本历史与恢复。S4 只接通支撑这几项以及第 7 节完成判断的界面，其余界面在 S4 里隐藏入口，或置灰且不显示假数据；#250 `constants/data.js` 里的演示数据不得与真实作品同屏出现。依赖 S5 的部分（页上意见、单页重做、候选比较）在 S5 后接入。以下不接，隐藏或不做：S00 所有项目矩阵（服务一次只服务一个项目，没有项目列表接口）、S04 的阶段推进状态与规范检测列表、S06 的身份切换、S05 的导出门禁交互。旧线 v2 的 api.js、images.js、collaboration-desk 及依赖它的 insight-reading、evidence-reading 不迁移。

顺序与 PR：S4 拆成两个 PR。先做 `deck serve` 与上述接口（含静态文件服务）并合入；#250 在接口可联调后由老板决定合入；再在 `frontend/` 上接数据层。

构建与分发：`deck serve` 提供构建后的前端静态文件，随二进制发布，不依赖磁盘上的相对路径（`cargo install --path rust` 之后也能用）；嵌入方式与依赖在 S4 开工时定。S4 把 `npm ci` 与 `vite build` 加入 `rust.yml` 和 AGENTS.md 第 3 节的检查清单。开发期 Vite 通过代理访问 `deck serve`，代理改写 Host 与 Origin 并读取 `deck serve` 启动时打印的地址，不放宽 Host 与 Origin 检查。

首个后端 PR 使用 `rust/web-dist/` 作为静态构建目录，当前仅含占位首页；`build.rs` 用标准库遍历目录，生成 `include_bytes!` 资源表，不增加嵌入依赖。前端 PR 再接入构建、CI 与上述命令清单。Host 只接受 `127.0.0.1:<本次端口>` 或 `localhost:<本次端口>`；Origin 可以省略，提供时只接受对应的 `http://` 本机地址。重复 Host/Origin 也拒绝，不返回 CORS 放行头。

后端接口供前端联调的返回形状：

- `GET /api/deck` 返回 `{version, deck, artifact_status, runs, history}`，在同一 SQLite 只读事务中读取。`artifact_status` 含 `missing_pages/stale_pages/stale_images`；runs 含每页状态、未采用原因及 `result_file`，不含本地工作路径；history 按新到旧列出 `id/created_at/summary`。run 状态独立于作品版本变化，轮询时应同时刷新。
- PUT 接受与 CLI 相同的裸 patch，成功返回 `{version, deck}`。冲突返回 HTTP 409 与 `{exit_code:5, base, submitted, conflicts:[{unit,current}]}`，整次不写入；`submitted` 原样保留裸 patch，界面也须保留编辑输入。
- `POST /api/build` 返回 `{id, url, findings, missing_pages, stale_pages}`，url 是该次构建文件的 `/api/files/<sha>`。`GET /api/files/<sha>` 只在当前项目的 files 目录内查找，含扩展名的存储引用取点号前的 sha 用于 URL；文件响应禁止脚本执行。
- `GET /api/export/md` 与 `GET /api/export/pptx` 直接返回下载内容，文件名为 `deck.md/deck.pptx`。`X-Deck-Status` 是 JSON（非 ASCII 字符使用 JSON 转义），含 `missing_pages/stale_pages`；PPTX 另含 `id/input_changed/warning/build_missing_pages`。
- cancel 返回 `{runs:[目标 run]}`，restore 返回 `{version, deck}`。输入错误为 HTTP 400；非本机请求 403；文件或接口不存在 404；缺工具 503；工具执行失败 500。错误响应含 `error`，仅 HTTP 409 冲突附带 CLI `exit_code:5`。

### 3.8 错误

- 退出码：0 成功；2 输入错误；3 缺工具或依赖（soffice、字体等）；4 工具执行失败；5 保存冲突（附冲突内容）。
- 错误信息写明哪一步失败、原因和下一步该做什么。
- 对外部输入和工具结果不使用 unwrap / expect。
- 工具失败就报失败，不用整页图片之类的替代产物顶替。

## 4. 生产工具包 deck-tools

### 4.1 来源（从 035845f2 复制，旧线文件不改）

| 目标 | 来源 | 改动 |
| --- | --- | --- |
| `compiler/` | `src/deck_master/compiler/` 的 svg、geometry、paint、api、native | 删除 api.py 的两处 Node 分支（`:87-88`、`:122`），因为生产路径没有传 node_executable（`pipeline.py:500`）。`resources/compiler/native.mjs` 不复制 |
| `resources/icons/lucide/` | 同名目录，26 个文件 | 放在 `deck_tools/resources/` 下，`compiler/api.py:108` 的相对路径因此仍然有效 |
| `render.py` | `pipeline.py` 中按符号复制：executable、run、NeedsTool、RendererError、resolve_fonts、renderer_environment、render_deck、readback，以及它们用到的纯函数 | artifact、page_asset_paths、preview_svg_bytes、_current_svg_preview、preview_svg_page 依赖 Store，不复制 |
| `readback_text.py`、`readback_relations.py` | 原样 | content 的导入改为 `atoms.py`。native.py 对 `_native_grid_shape` 的相对导入不用改 |
| `atoms.py` | `content.visible_atoms` 及 `_atom_id / _pointer / _stable_id / _collect_items / _collect_table` | 不带 models；`NeedsNormalization`（未知块类型）改为本地定义 |
| `sources.py` | 原样 | 3 个错误类改为本地定义 |
| `sanitize.py` | `export_sanitize.py` | OperationError 改为本地定义。两处 Lucide 许可分支（`:296-299`、`:375-379`）直接读工具包内的 `resources/icons/lucide/LICENSE.txt`。`icons.py` 不复制，它对每个文件的哈希复核也不保留 |
| `doctor.py` | 新写 | 旧 `doctor.py` 依赖 method_resources 与 pipeline，不复制。新的只检查 soffice、pdftoppm、fc-match、指定字体和当前解释器 |
| `__main__.py` | 新写 | `python -m deck_tools <命令>` 的入口 |
| `tests/` | `tests/rebuild/` 中只测工具的文件：test_compiler_api、test_svg_parser、test_svg_compiler、test_geometry、test_paint、test_drawingml、test_text、test_readback、test_render、test_renderer_environment、test_native_table_geometry、test_native_table_path_evidence、test_rc3_table_text_slack、test_deep_quality_compiler、test_deep_quality_render、test_main_iteration_sources，以及 `hostenv.py` | 只改导入。conftest 新写，因为旧的导入了 models 与 Store。依赖旧 Store、models 或 Node 的单个用例删除（例如 `test_svg_compiler.py:20-24`、`test_deep_quality_compiler.py:108-111`），其余保留 |

- `deck-tools/pyproject.toml` 按实际导入声明依赖，包括 python-pptx、Pillow、lxml。系统工具：soffice、pdftoppm、fc-match。
- 工具包不导入 deck_master。
- 保留下来的测试通过，就视为与旧实现等价；S3 的第一份真实整稿构建是第二道检验。不另做新旧产物的逐份对比。
- 两套代码共存期间，编译问题只在 deck-tools 里修。旧线的编译器冻结，除非问题属于 AGENTS.md 第 12 节的四类。

### 4.2 命令

调用方式：`python -m deck_tools <命令> <job.json>`。结果以 JSON 写到 stdout，大文件只传路径，退出码同 3.8。

| 命令 | 输入 | 输出 |
| --- | --- | --- |
| read-source | 文件路径 | text、locators、tables、status |
| atoms | 页 content | 文字编号与对应文字 |
| check-page | 单页 SVG、页投影、画布、字体名、素材路径 | 编译错误；或预览 PNG 与回读发现 |
| build | 各页 SVG、页投影、画布、字体名、素材路径 | 清洗后的 PPTX 与回读发现 |
| sanitize | 文件路径 | 清洗后的文件 |
| doctor | 可选的字体名列表 | soffice、pdftoppm、fc-match、字体和当前解释器的可用情况 |

- 字体名由工具用 fc-match 解析为文件。
- 页投影为 `{page_id, customer_visible: content, speaker_notes: notes, visual_spec: {}}`，由工具内一个固定的适配函数根据 Rust 传来的 id、content 和 notes 生成。回读需要两份输入：编译 manifest 里的 pages（已实测可以直接使用），以及这份页投影。只传 content 时，关系检查会出错，文字检查会被静默跳过。
- Rust 用 `DECK_TOOLS_PYTHON` 找解释器。没有设置时，使用安装脚本建好的固定 venv；两者都没有就报错（退出码 3），并给出设置方法。不默认使用 `python3`：本机的 `python3` 是 3.15，没有装 deck_tools。开发时按 AGENTS.md 第 3 节装进本 worktree 的 venv。

## 5. 交给 Host 的任务

### 5.1 生图提示词（prompts.rs）

保留旧提示词中已经验证有效的要求，去掉其中的协议说明：

- 画布像素与物理尺寸；本页目的与 layout。
- content 逐字上屏，不增删事实、数字或单位。
- 风格：配色与字体；选中的素材以附件形式传给 ImageGen，不用文字替代。
- 按信息关系选择表达：比较或查阅用表格，时序用步骤或时间线，流程用连线与分支，分工用泳道或分区。不要把非比较内容画成表格（#226、#227）。
- 文字、连线和主要业务对象要能拆成可编辑元素；照片、logo、复杂插画可以占有边界的位图区域，但不承载正文。
- 不编造数字、日期或客户数据；页面文案不含缺口说明；缺口在 todo，不上屏，不放页脚，不画示意数据。

### 5.2 SVG 任务（`work/<run_id>/<page>/`）

文件夹内容：本页 content、atoms 输出、原图、画布与字体、可用素材、SVG 支持子集说明，以及字号换算：`pt = font-size × 元素及其祖先 transform 的缩放 × k × 0.75`，其中 `k = min(slide_width_in × 96 / width_px, slide_height_in × 96 / height_px)`，新画布下 k ≈ 1。回读把小于 6pt 的文字判为不可读。

Host 的做法：

1. 按原图的布局、层级和关系写 SVG；正文取自 content，每段文字带上对应的 `data-atom-id`。页面文案不含缺口说明；缺口在 todo，不上屏，不放页脚。
2. 交回后，对照预览与原图检查端点、方向、分支、层级、侧栏和阅读顺序（#229、#231）；有问题就修改后重交。

SVG 支持子集说明由 S3 依据 `compiler/svg.py` 实际接受的元素与属性整理，放入 Skill 的 references。至少写明以下几点：

- 数值（包括 font-size）不带单位。
- 未列出的属性（包括 class）以及 filter、mask、clip-path 都会报错。
- style 里只接受有限的几项。
- `<g>` 只向下继承颜色与字体，`data-atom-id` 要写在文字元素本身上。
- 文字不支持非等比缩放。

重建时使用 [SVG 子集与关系样例](../../../deck-skill/references/svg-subset.md)：箭头用显式几何；表格分隔线用完整的 line 元素并与外框相接；侧栏限定保留在正文中。原图出现正文之外的装饰文字时，以 content 为准，不能把装饰文字变成新事实。单页回读发现保存在 run 工作目录，`run show` 给出可用路径；工作目录删除后可重新检查。

### 5.3 上下文

Host 按需读取：`deck show`（摘要）、`deck get --pages p3,p4`（指定页，外加 brief、framing、style）、`deck material text m1`（抽取文本的路径）。不一次性展开历史审阅或全部材料（#217、#242）。

## 6. Skill（deck-skill，切换时改名为 skills/deck）

- 步骤：作者任务 → 材料与主张框架 → 逐页内容 → 原图 → SVG → 构建 → 改稿 → 导出。每一步写明做什么判断、调用哪条命令。
- 内容方法：
  - 区分事实、建议、假设和缺口。只为影响方向的缺口补问，其余照常写。
  - 先定本页目的与信息关系，再定写法。
  - 不编造数字。
  - 按需读 M01–M10 和 E01–E06。
- 把 `skills/deck-master/references/` 中仍然有用的方法复制到 `deck-skill/references/`，删去其中的协议、writer、冻结清单等段落。此后新线只改这一份。
- 出错时按 CLI 的错误信息处理。
- 开发期：用软链接把 Skill 装进 Codex；用 `cargo install --path rust` 安装 `deck` 命令。

## 7. 切片

每个切片一个 PR（S4 例外，分两步提交，见 3.7），从 origin/main 开分支、合回 main，做法见 AGENTS.md 第 4 节。deck-tools 可以与 S1、S2 并行开发。表中的"完成判断"是可以直接观察的行为；没做到的记在 PR 里，不阻止后续切片开工。

| 切片 | 内容 | 完成判断 | 对应 issue |
| --- | --- | --- | --- |
| S0 入口 | AGENTS.md 改写为新的开发规范，CLAUDE.md 只指向它；本稿入库；`.gitignore` 加入 `.deck/`；首条任务的材料由老板指定 | Codex 在 `rust/` 开工时不会再按旧任务卡或旧门禁行事 | #222 #246 |
| S1 作品核心 | model、store、ops；`deck new / material add / material text / show / get / put / restore / export md`；deck-tools 的 read-source；`show` 与 `get` 的 JSON 字段在本切片定下 | 不完整作品可以直接改、增删和重排页；两路改不同页都能保存，同一页冲突可见；重复提交不产生新版本；restore 之后历史可追溯；在真实项目目录下跑通 | #218 #243 #223 #248 |
| S2 内容主链 | Skill 前半；Codex 用真实材料写 brief、framing 和逐页内容 | 老板阅读 md 稿，判断主张与框架是否成立；首提与竞标按各自需求取舍 | #219 #244 #228 #227 |
| S3 工具与成品 | 先用一份真实整稿（只在本地，不入库）跑通工具链；deck-tools 的其余部分；`deck run` 全套、`build`、`export pptx`、`doctor`；生图与 SVG 任务；`deck asset add`（logo 等素材） | 用真实材料产出整套 PPTX；取消后迟到的结果不自动采用；依据已变的结果不自动采用；结果未知的调用不自动重发；logo 从选择到 ImageGen 附件、再到 PPT 能一一对应；故意改错一处连线端点，Host 的比对能够发现。如果整稿仍要逐页人工修 SVG，先补 §5.2 的约束与样例，再做 S4 | #226 #231 #229 #164 #237 #141 #233 #217 #242 |
| S4 界面 | `deck serve` 与 API；接入 #250 的新版 WebUI（`frontend/`），范围与顺序见 3.7 | 无需理解协议即可改字、停止和下载；浏览器存储不可用时停止照样生效；从总览或原图空态可以直接进入制作；窄屏下可读、可操作 | #136 #232 #220 #234 #224 #235 #236 |
| S5 改稿与审阅 | 页上意见（reviews）；Host 读取未处理意见、改稿并标记已处理；单页重做 | 只改讲稿或第 3 页时，其他页和已有成品不动；作者自检显示为自检，不合成为通过 | #230 #239 |
| S6 迁移与切换 | 旧线 `legacy-export`、`deck import`；安装脚本；全稿回归 | 老板指定的旧项目可以打开、编辑和导出，旧目录不变；按 README 新装后能完成首跑；#226 的 22 页整稿复核 | #221 #245 #225 #240 #241 #238 |

## 8. 旧线、迁移与切换

- 旧线 `src/deck_master/` 不再加能力，只修数据丢失、重复消耗、打不开或导不出、真实安全问题。
- 若重建期间旧线还要出真实客户稿，就把 `production.py:532` 的表格默认改为按内容关系判断，作为 #227 的止血；否则旧线不动。
- PR #247、#249 按各自的内容和状态另行决定，不属于本稿。
- issue 在新路径解决后逐条关闭，不随旧代码退役而批量关闭。
- 迁移：
  - 旧线新增只读命令 `legacy-export <project> <out>`，复用 `Store.load_document` 与对象读取，导出中性 JSON 和文件，包括 brief、材料、framing 摘要、页 content、讲稿、原图、SVG 和最近一次导出。旧审阅与授权记录原样附带，供查阅。现有的 `export --purpose engineering` 只复制对象树，不产出中性 JSON，所以不能直接拿来代替。
  - `deck import <out> <new>`：目标已存在时报错；无法映射的内容逐项列在报告里；在途调用或结果未知的调用只列出，不恢复。
  - 只迁移老板指定的项目。旧目录不变，所以回退就是继续使用旧目录。
- 安装（S6）：一个脚本，负责安装 `deck`、把 deck-tools 装进独立 venv、把 Skill 链接给 Codex。不移植托管安装的激活与回滚。先支持 macOS，CI 在 Linux 上跑。
- 切换：老板判定新路径可以替代旧线后，`deck-skill/` 改名为 `skills/deck/` 并成为默认 Skill，安装不再携带旧的四个 Skill。是否删除旧代码另行决定。

## 9. 未验证

- 带表格、图标、图片素材的页面，以及 22 页规模，在新工具包上的表现（S3 验证）。
- `codex app-server` 能否调用 ImageGen。这决定界面能否直接触发生成。Host 不能生图时，作者可以用别的工具出图，再经 `deck run result` 交回。
- SQLite 项目文件放在 iCloud 等同步目录时的表现（S1 在真实项目位置试）。
- 旧线全量测试本轮没有跑，不影响新线开发。
- 已确认：本机 rustc / cargo 1.99.1 与 sqlite3 可用。
