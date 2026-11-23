Decision needed: 请 Los 一次拍板三件事：① 批准下表 D1–D5 五项对开发稿 v1.2 / AGENTS.md 的偏离；② Q1 选 A（“待补”在草稿页面上醒目标出）还是 B（只放讲稿备注 + 缺口清单），未答前 PR-D 阻塞；③ 批准本轮 Host 实跑上限 20 次（SWE 自测 ≤6，核验 + 修复 ≤14）。可选确认：修复由 SWE 做、Codex 只核验（默认如此，Los 不回复即按默认执行）。

# Deck Master · 内容质量轮 PRD 切片 r2（2026-11-20）

## 偏离清单（相对开发稿 `docs/specs/rust-rebuild/README.md` v1.2 与 `AGENTS.md` @ `865092`；需 Los 批准）

| # | 偏离 | 违反或触及的条款 | 防的真实故障 | 未批准时的影响 |
|---|---|---|---|---|
| D1 | 新增持久字段：`brief.decision`、`brief.concerns[]`、`brief.narrator{role,tone}`、`framing.storyline[]`、`page.kind`、`page.argument`（名字以架构师设计为准） | AGENTS §11（新增持久字段须先问）；开发稿 §3.3 | 不知道写给谁、要对方拍什么板就开写；论证链无处存放 | AC-01/02/03 无法落地，PR-B、PR-C 不开工 |
| D2 | `FORMAT_VERSION` 6→7，不兼容的持久格式变化。新程序能打开 v6 库；旧程序打开 v7 库会提示“请升级 deck” | AGENTS §11、AGENTS:80 | 新字段被旧程序的 `deny_unknown_fields` 报 serde 错误 | 与 D1 绑定 |
| D3 | `run start image\|svg\|native` 新增两条输入拒绝：① 框架或主线为空；② 判断页有未标注的**证据**缺口。`deck put` 和 `build` 不拦 | AGENTS §6（新增检查须说明它防的故障）；开发稿 §2.2（保护只限 8 条，新增须老板同意） | 没有主张和依据就花 ImageGen 调用，画出无依据页面；编造证据 | AC-01/03 退化为提示，PR-B、PR-C 只能做提示版 |
| D4 | 新增“出稿审稿”review 记录，绑定导出版本。`build`/`export` 返回只读字段 `content_review{status, methods, version_id, unreviewed_pages[]}`。**不在代码里汇总通过或不通过**，六项结论只作为记录内容 | AGENTS §11（新增机制）；开发稿 §2.1（禁止“审阅 pass 汇总”，本设计不做汇总）；§3.5/§3.6 | 未审或审后又改的稿被当成已审交出（同类：`stale_pages` 有记录而 `warnings` 为空） | AC-06 无法落地，PR-E 不开工 |
| D5 | `deck get`/`deck show` 输出新增 `writing_brief`（由 narrator、decision、concerns 拼出），以及标题连读 `outline`、缺口清单（由 `todo` 加 `evidence.gap` 计算，不新增手填字段） | AGENTS §11（新增输出与机制） | Host 写作时拿不到讲述人约束，退回模型默认的过度防御语气 | AC-05 产品层失去可验证的落点 |

- 开发稿 §3.3、§3.5、§3.6 在**同一个 PR** 里随代码修改（AGENTS:114），不另建 spec 目录。
- Q1-A 若获选，还会改动开发稿 §5.1/§5.2、`rust/src/prompts.rs:157`、`deck-skill/deck-content/SKILL.md:45` 的“缺口不上屏”设计。这一项单列为 Q1，不在 D1–D5 之内。

## 0. 文件身份、授权与替代关系

- **本文件供执行使用，替代** `/workspace/_specs/deck-master-prd-cut-20261120-content-quality.md`（r1，SHA-256 `b1d412eae0d78ee59c1fc881ddef1842a0fe50acb774d6b19c0ee833b99ddbb8`）。r1 原件保留、不改，仅作历史；两者冲突时以 r2 为准。
- 依据的评审：
  - Reviewer：`/workspace/backups/reviewer-specs/content-quality-cut-review-20261120.md`（`db27f22bce439e62cc2fa800821fed6edcb426380592e2218340f3321f416fe3`）
  - CodeManger：`/workspace/_specs/content-quality-eng-review-20261120.md`（`fc68a3eb12439419b760cc2ae5b6e510b44e4b492b429461b329fa6338243dc2`）
- 夹具原件不改：`/workspace/_specs/content-quality-fixtures-20261120/`。各文件 SHA 与 r1 第 0 节一致，CodeManger 已核对。口径补充与分离后的输入放在 `/workspace/_specs/content-quality-fixtures-20261120-r2/`：
  - `scoring-caliber-supplement-r2.md`：`47d781639bd26be54909aa3752d6ce2d3c3d88ce1df91f250ff9e6e932200a90`
  - `inputs/CQ-F1/material.md`：`49db58e165f1a635ad6a1b59cea992e4e413161a0f148cddc2a89502b5cecd89`；`task.txt`：`1c4172a907db201708846a2fcf88331596d4897d62c24c82866ef2118f34b979`
  - `inputs/CQ-F2/material.md`：`13b782232cac2a7753bc2633ac4ca78f21d62c1898c7cada217b74f2f8f69ad8`；`task.txt`：`dd3b81a0c684b0a7e68b3936102e63a2691ace417af8e732259455504bf3a442`
  - `inputs/CQ-F3-HOLDOUT/material.md`：`7fabef7f4e6487cddc18187a2d920f465e27ac750a7764338c13020c3ee8c5af`；`task.txt`：`e621224ad2e16afd761a94a40c1801cffe2746518b00a57bc499ac2b6b9b914c`
- Los 原话：
  - 2026-11-20 20:49（北京时间）：「我不是做投标啊。。。我们是做专业的商用 deck」
  - 2026-11-20 21:27（北京时间）：「可以，你整理好所有开发方案，然后让 @Reviewer @CodeManger 评审，修改完毕以后让 @SWE 开始开发，然后评审。完成这一轮所有开发迭代之后，让 @Codex 完整，然后继续修复，直到完成这一轮的所有迭代交付」
  - PM 的理解：21:27 这句授权的是**流程**，不是逐条认可上表的偏离。因此本轮除 PR-A 外，开发要等 Los 批准 D1–D5。合并到 main、打 tag、发 GitHub Release、发 PyPI 以及任何外发，都须 Los 另行同意。
- 基线：main `865092226246aa57820aa4cdec291648aa3ddee0`（tree `c5e22979f269b619dcd5872394ce3250641b6295`，CodeManger 已核对，无漂移；main **未开分支保护**）。正式 tag `v1.1.3` 为 `718fdc01e88121644cb2fb0966ed63eb79ac4cc1`。
- 历史文件（AC-07 核对不变，附绝对路径）：
  - `/workspace/_specs/deck-master-prd.md`：`e3433f32…d5e979`
  - `/workspace/_specs/deck-master-prd-cut-20261116-yuyuan-baseline-first-run.md`：`3369cee0…43cd1b8`
  - `/workspace/_specs/deck-master-prd-cut-20261120-yuyuan-followup-DRAFT.md`：`3a3cd12e…0e130e0`
  - `/workspace/_specs/yuyuan-ab-pm-closeout-20261120.md`：`e5f0fd39…6c36a8e`
  - `/workspace/deck-master-assessment-20261120/汇总评估.md`：`4ce204a3…a64c2e9`
  - `/workspace/deck-master-assessment-20261120/按影响排序整改建议.md`：`e4c10a70…f9b43`
  - 完整 SHA 见 r1 第 0 节；r1 本身也纳入核对。
- 切片日期：2026-11-20。Los 未设截止日期。CodeManger 估算开发 7–10 人日，不含 Host 实跑和评审往返。

## 1. 一句话成果与 r1 更正

**成果：** 在同一份合成材料上，候选版先锁定读者、待决事项和讲述人，再按主线写出判断句标题页。关键主张带论证链，证据缺口被标出且不编造，语气是资深顾问而不是过度防御。出稿审稿要绑定导出版本。盲评结果优于当前 main。

**更正 r1 第 1 节：** humanizer 并没有要求“保留一切限定词”。它只防止“丢失必要限定”（`expression-review-humanizer.md:16,23,25,32`），缺的是反方向检查：同一限定重复、堆叠，以至压过结论。`AGENTS.md:115` 已经写了“限定只在需要处写一次”。

**本轮处理顺序：** 事实与必要限定 > 结论先行 > 去重。
- 去防御只删除**重复和堆叠**的限定，保留第一次出现的必要限定。
- 适用范围只限读者可见的标题、正文、图表注和页脚；讲稿备注和附录可以完整展开。
- 去重在写作阶段、`deck put` 之前完成。`prompts.rs:9`（生图时逐字上屏）**不改**。
- 在 humanizer 校准表中按 CodeManger 第三节新增两行例外：“重复免责只留首处”和“稀释标题改判断句、条件移入正文”。不改 M10 定位。

## 2. 范围（2026-11-20 起本轮）

### 范围内
沿用 r1 第 2 节第 1–9 项，有以下修订：
- **“页面生成”的定义：** 仅指 `run start image|svg|native`。`deck put` 保存草稿、`build` 都不拦。
- **生成门只拦未标注的证据缺口**（防编造）。推理、反驳与边界缺失归审稿门和 D4 发现，生成时不硬拒，也不允许用“推理：待补”绕过（Reviewer 建议①）。
- **工程腔只指复合说法**（“验证门槛”“阻塞于…”“过闸”等）。“验证”“待验证（假设）”是正常用语。
- **去防御计数器、数字溯源、内部备注候选列表**都只放在**核验脚本**里，不进产品 CLI 和发布包（CodeManger B3）。
- **AC-06 只要求三件事：** 记录存在、按 method 区分、绑定导出版本。代码不汇总通过与否。
- **AC-07 运行与基线：** 6 次 Host 实跑由 **Codex** 执行。main 基线用官方 `install.sh` 从 `865092` **全新安装**到独立 prefix，与候选版用同一口径；不沿用 11-16 的历史安装 `b222f2dd…`。安装被测产品本身不算“安装未授权软件”。
- **前端：** 本轮 UI 不支持编辑新字段，在 PR 描述里写明“UI 未覆盖”（S12）。

### 范围外
沿用 r1 全部范围外条目，包括：
- 不把真实客户材料放进公开仓库、云端或 release；
- 未经 Los 另行同意不合并、不发版；
- 不做事实核查引擎，不做投标专用功能；
- 视觉通过与否只由 Los 或他指定的人判定；
- 不改历史切片和封存件，不针对 F3 调参。

另增：
- 不在产品里做禁词计分或数字配额（开发稿 :52、AGENTS:99）；
- 不做页型自动分类；
- 不新建审批状态或回执协议；
- 不把“Host 未阅图”当作代码 FAIL 退回 SWE。

## 3. 验收（8 条）

**证据类型（6 类）：** screenshot | SHA | fixture id | API JSON | **核验人判读记录**（页码 + 原句 + 结论）| **日志或文本摘录 + SHA**。

**通用规则：**
- BLOCKED 不算 PASS；执行人不得核验自己执行的 AC；只有 SWE 自测不算通过。
- 核验在集成分支 `rust/content-quality-20261120` 的头 SHA 上进行，并写全 SHA。
- `fixture id` 写夹具名，加实际 `material.md` 的 SHA（取自 r2 inputs 表）。
- 判分口径以 `scoring-caliber-supplement-r2.md` 为准。

### AC-01 受众、决策与讲述人在生成前锁定（PR-B）
- **Proof：** API JSON + fixture id（F1、F2）+ 判读记录。
- **QA 通过条件：**
  - 有机读字段，包含读者（沿用 `brief.audience`）、待决事项、关注点 1–3 个、讲述人身份与语气。
  - 在 F1、F2 的 Host 运行中，这些字段已填写，且由核验人判定与任务一致。
  - 字段为空时 `run start` 返回明确拒绝（`Error::Input`，退出码 2，信息写明缺什么）；`deck put` 和 `build` 不受影响。
  - v6 库能用新程序打开；旧作品新增页面时，Host 能补填字段，或得到可据此处理的提示，不是无从下手的硬拒。
  - 旧程序打开 v7 库时提示“请升级 deck”。

### AC-02 主线先于页面；标题连读（PR-B）
- **Proof：** API JSON（`outline`、版本历史）+ SHA（`export md`）+ 判读记录 + fixture id。
- **QA 通过条件：**
  - 主线已保存，且由版本历史证明它早于第一页正文。
  - 主线 5–8 句由核验人判定；代码只检查非空。
  - 核验人逐页列出页型、标题、是否为话题式标题；在判断页上**话题式标题不超过 1 个**。
  - 核验人只读 `outline` 就能复述出与主线一致的故事。
  - 豁免页逐页抽查是否被误归类；判断页被标成说明页即判 FAIL（S4）。
  - 以上都是核验口径，不做成产品里的配额。

### AC-03 论证链（PR-C）
- **Proof：** API JSON（逐页 `argument`、负例）+ 判读记录 + fixture id。
- **QA 通过条件：**
  - 每个判断页有机读论证链：理由 2–3 条、证据（`ref` 或 `gap`）、推理、反驳与边界。主张直接取标题，不重复存放。
  - F1 R1、R2 和 F2 R1 的推理由核验人判定没有出错。
  - **负例一：** 判断页有一条证据既没有 `ref` 也没有 `gap`，`run start` 拒绝，并指出页和证据项。
  - **负例二：** 同一条证据标为 `gap` 后放行，并出现在缺口清单中。
  - 推理或反驳缺失时不拒绝生成；这类问题须出现在审稿记录或核验发现中，列明页码。
  - 页型由核验人逐页核对（S4）。

### AC-04 证据具体、缺口标注、零编造（PR-C 缺口清单 + PR-D 文本；**PR-D 部分等 Q1**）
- **Proof：** API JSON（缺口清单）+ SHA（PPTX、预览、`export md`）+ 判读记录 + fixture id；Q1-A 另加 screenshot。
- **QA 通过条件：**
  - **硬性缺口**（只限材料明示或可直接推出的：F1 G1、G3；F2 G1、G3；F3 G1–G3）全部出现在缺口清单中，并按 Q1 选定的口径标注。每个缺口只在承载它的主页标注一次。
  - F1 G2、F2 G2 只作 D5 参考。
  - **事实性**数字、案例、引语都能追溯到材料，或者是标明算式的推算（算式可放在注释或讲稿里）。
  - 结构性数字、明确写成“建议/拟…”的方案参数豁免，但不得冒充事实。
  - 自编目标（如 F2 的 Q4 目标）任何一处出现即 FAIL。
  - F3 A1 中的形容词不作为论点上屏。
  - 溯源先由核验脚本列出候选，再由人判定。
- **Q1 两种口径：**
  - **Q1-A（待补上屏）：** 草稿页面统一用“待补：…”标出，`todo` 仍是缺口清单的来源；同步改 `prompts.rs:157`、开发稿 §5.1/§5.2、`deck-content/SKILL.md:45`。Proof 加标注页的 screenshot。代价是交付前要人工清理，且 AC-07 盲评受限（见补充第 7.8 节）。
  - **Q1-B（不上屏）：** 维持现行“缺口不上屏”。“醒目”改为讲稿备注 + 缺口清单 JSON + `export md` 中的显式条目。Proof 不需要 screenshot。D5 按讲稿备注和缺口清单评分。

### AC-05 讲述人表达，不删必要限定（PR-D）
- **Proof：** 日志摘录 + SHA（Host 会话 jsonl 中含 `writing_brief` 的工具返回）+ API JSON（`deck get`/`show` 中的 `writing_brief`）+ 核验脚本 JSON + 判读记录 + fixture id。
- **QA 通过条件：**
  - **产品层：** `deck get`/`deck show` 输出 `writing_brief`，内容由 narrator、decision、concerns 拼出。
  - **观察层：** 每次候选版运行的 Host 会话 jsonl 中，能摘出包含该文本的工具返回。
  - 真实不确定项（U1）在相关处有说明，不在无关页重复，也不压过结论；执行摘要和详情页各说一次可以接受；缺口清单、脚注、附录、讲稿备注不计次数。U1 完全消失即 FAIL。
  - 主线风险不超过 2 条，每条带应对。
  - F2 J1 已改写为管理层语言，读者可见页面没有复合工程腔。
  - 判断页标题没有稀释主张的限定词，除非该页本身就是不确定项的说明处。
  - 核验脚本只列候选，最终由人判定。

### AC-06 出稿审稿绑定导出版本（PR-E）
- **Proof：** API JSON（审稿记录、`content_review`）+ SHA（PPTX、各页预览、审稿记录）+ 判读记录 + fixture id。
- **QA 通过条件：**
  - 每份导出前都有一条出稿审稿记录：写明 `method`，绑定导出时的 `version_id` 和**各页预览 SHA**，并逐项写出六项检查的结论和页码。六项结论只作为记录内容，代码不汇总。
  - `build`/`export` 返回 `content_review{status: unreviewed|reviewed|stale, methods, version_id, unreviewed_pages[]}`，HTTP 通过 `X-Deck-Status` 带出，与 `warnings` 分开。
  - **负例一：** 没有审稿记录时导出，`status=unreviewed`。
  - **负例二（反例）：** 审稿后修改一页再导出，该页出现在 `unreviewed_pages` 中。
  - **产品侧“看过最终页”的证据：** 审稿记录里列出的预览 SHA 与最终导出的预览 SHA 一致。**核验人自己的截图不能作为这一项的证据。**
  - **Host 是否真的打开了图：** 由 Codex 从 jsonl 中找读图动作，找不到就记“Host 未阅图”，作为观察结论报告，不退回 SWE，也不计入连续 3 轮 FAIL。
  - **内部备注（F1、F2、F3 的 N1）：** 由核验人逐页判读（脚本列候选，口径见补充第 6 节）。这项判读可以附核验人截图。

### AC-07 前后对照（核验活动，不改产品）
- **Proof：** SHA（两版安装指纹、`material.md`、每份 PPTX 和预览、`ab-mapping.json`）+ API JSON（评分 JSON）+ screenshot（预览拼图）+ 日志摘录（运行登记）+ fixture id。
- **QA 通过条件：**
  - **运行：** Codex 在同一环境、同一 Host 设置下，对 F1、F2、F3 用 main 全新安装版和候选头各跑 1 次，共 6 次，全部登记，不挑选。
  - 每次运行的 `material.md` SHA 与 r2 inputs 表一致；判分底稿不进入 input。
  - **盲评：** 按补充第 7 节执行——评分人为 Claude 加一位全新会话评分人，Reviewer、SWE、Codex、PM、CodeManger、架构师都不评分；CodeManger 对每个夹具单独随机分配 X/Y，并在评分前封存映射的 SHA；评分人提交“猜测哪份是候选版”作为披露；N/A 规则和两人取均分按补充执行。
  - **判定：**
    - 每个夹具上，候选版每维均分不低于 main 均分减 0.5；
    - 至少 2/3 的夹具（必须包括 F3）上，候选版总分严格高于 main；
    - 候选版 D7 两位评分人都给 2。
  - **回归：** `cargo test`、`deck-tools` 的 pytest、`examples/first-run` 中英文首跑全部通过。
  - 第 0 节列出的历史文件 SHA 不变。
  - **修复后重跑：** 只重跑候选版（环境和 Host 设置不变时，main 不重跑），换新的候选头，重新匿名，并换一位新的全新会话评分人。
  - 任何一次运行因环境原因失败，本条记 BLOCKED。

### AC-08（可选）页内 `cNvPr/@id` 唯一（PR-A）
- **Proof：** API JSON（findings 中的 `duplicate_cnvpr_id`、负例）+ SHA（回归用 PPTX）+ fixture id（合成的“形状+表”“图+表”两页）。
- **QA 通过条件：**
  - `sanitize` 按幻灯片部件重新编号，并同步更新引用这些 id 的属性（连接线 `stCxn/endCxn`、动画 `spTgt@spid` 等，具体落点由 SWE 确认）。
  - 用 `build`/`export pptx` 生成整稿后，同一页内 id 唯一，名称不再被改写成同一个“形状-N”。
  - 只用 XML 检查判定；LibreOffice 重编号不算修复。
- 可以推迟（记 DEFERRED，但不算 PASS）。

## 4. 分支、PR、角色与解锁顺序

**分支与 PR：**
- 集成分支 `rust/content-quality-20261120`，从 `865092` 拉出。各 PR 的 base 都是集成分支。
- 每个 PR 由 Reviewer 评审，没有阻塞项才能进集成分支。
- 最后从集成分支向 main 开 PR，**只开不合**。main 未开分支保护，任何人不得点合并，等 Los。

| 顺序 | PR | 分支 | AC | 前置 |
|---|---|---|---|---|
| 1 | PR-A | `tools/unique-cnvpr-ids` | AC-08 | r2 生效即可开工（不涉及 D1–D5） |
| 2 | PR-B | `rust/decision-frame-storyline` | AC-01、AC-02 | 架构师设计 + Los 批准 D1–D3、D5；负责 FORMAT_VERSION 7 迁移 |
| 3 | PR-C | `rust/argument-chain-gate` | AC-03、AC-04 缺口清单 | PR-B 已进集成分支 |
| 4 | PR-E | `rust/content-review-record` | AC-06 | Los 批准 D4；**在 PR-B 的迁移上追加，不再单独升版本** |
| 5 | PR-D | `skill/consultant-voice-and-gaps` | AC-04 文本、AC-05 | **阻塞到 Los 回答 Q1**；引用 PR-B/C 的字段名 |

**角色：**
- PM（产品经理）：负责范围、夹具和口径；不写代码，不评分。
- CodeManger：协调；负责 X/Y 匿名化和指定评分人；不评分。
- 架构师：在 SWE 开工 PR-B/C/E/D **之前**交出字段与门的设计（名称、JSON 结构、错误信息、迁移方式），作为本切片附件；设计须落在已批准的偏离范围内。
- SWE：开发和修复。
- Reviewer：评审 PR；不评分。
- Codex：AC-01…08 的完整核验，以及 AC-07 的 6 次实跑；不修代码。
- 评分人：Claude 和一位全新会话评分人。
- 视觉终判：只能由 Los 或他指定的人做；本轮不需要。

**解锁顺序：**
1. r2 交 Los。
2. PR-A 和架构师设计可以并行开始。
3. Los 批准 D1–D5 后：PR-B → PR-C → PR-E。
4. Los 回答 Q1 后：PR-D。
5. 全部 PR 进集成分支后，Codex 一次性完整核验 AC-01…08，含 AC-07。
6. 修复循环：
   - FAIL 退回 SWE，经 Reviewer 评审后，Codex 复核受影响的 AC，并重跑 AC-07 的候选部分。
   - 出现以下任一情况即停止，交 Los：
     - 同一 AC 连续 3 轮 FAIL（“Host 未阅图”这类观察项不计）；
     - 需要超出范围；
     - BLOCKED 必须由 Los 解除（登录、额度、费用）；
     - Host 额度用完。
7. 交付物交 PM，PM 再交 Los：集成分支头 SHA、对 main 的 PR 链接（未合并）、Codex 报告、评分 JSON 与映射、6 份及以上稿件的 SHA、额度使用情况。

**独立性：**
- 若 Los 指定由 Codex 修复，则 Codex 修过的 AC 改由 Reviewer 核验。
- 评分人不得接触任何候选版产出，直到拿到匿名稿。

## 5. Host 实跑额度（待 Los 批准，见第一行 ③）

- **总上限：** 20 次。其中 SWE 开发自测 ≤6 次（只用 F1、F2），Codex 核验加修复回归 ≤14 次（首轮 6 次，之后每轮 3 次）。哪一项先用完就停下，问 Los。
- **计数规则：**
  - 只要实际启动了 `codex exec` 的 Host 会话，就计 1 次；失败、超时、中止、没有产物的都计入。
  - 没启动 Host 就失败的（安装失败、doctor 不通过）不计，但记为 BLOCKED。
- **执行规则：**
  - 单次硬超时 90 分钟。超时计次，记 FAIL 或 BLOCKED，不自动重试。
  - 串行运行；每次用新的工作目录；按 11-20 的做法披露 CODEX_HOME 的副作用。
- **报告：**
  - 每条交接消息都带“已用 N/20”。
  - 用到**第 16 次**时提前告知 PM，由 PM 转告 Los。
- **账号：** 额度来自本机已登录的 Codex 账号；遇到限流按 BLOCKED 处理。

## 6. 变更控制

- 本 r2 替代 r1 用于执行，r1 保留。
- 架构师设计作为附件，另存为带日期的文件。
- 之后的改动另立带日期的切片或补充文件。
- 夹具原件与 r2 inputs 冻结，发现错误时新增修订版，不改原件。
- 聊天里提出的要求不直接进入本轮范围。

## 7. 锁定交接模板（原文照发）

### 7.1 致 CodeManger + 架构师（设计，r2 生效即发）
```
【内容质量轮 r2 · 设计】依据 /workspace/_specs/deck-master-prd-cut-20261120-content-quality-r2.md（替代 r1 b1d412ea 用于执行）。请架构师在 SWE 开工 PR-B/C/E/D 前交字段与门设计（名称、JSON 形状、错误信息、v6→v7 迁移），只覆盖偏离清单 D1–D5，另存日期文件。PR-A（AC-08）可同时分派 SWE。D1–D5 未获 Los 批准前不开工 B/C/E；Q1 未答前不开工 D。集成分支 rust/content-quality-20261120，PR 只进集成分支；对 main 的 PR 只开不合。
```

### 7.2 致 SWE（开发，经 CodeManger 分派）
```
【内容质量轮 r2 · 开发】按 r2 与架构师设计，在各 PR 分支开发，base=rust/content-quality-20261120；不合 main、不打 tag、不发版。开发稿 §3.3/§3.5/§3.6 同 PR 改。自测只用 r2 inputs/CQ-F1、CQ-F2 的 material.md/task.txt，不打开原夹具（含判分底稿），不碰 CQ-F3。Host 自测 ≤6 次，消息带“已用 N/20”。生成门只拦未标注证据缺口；去重限定在 deck put 前完成，prompts.rs:9 不改，首处必要限定保留；禁词计数不进产品；AC-06 不做通过汇总。UI 未覆盖写进 PR 描述。自测证据不算核验；环境不足记 BLOCKED 并停。
```

### 7.3 致 Codex（完整核验 + AC-07 实跑）
```
【内容质量轮 r2 · 完整核验】在集成分支头（写全 SHA）上按 r2 AC-01…08 核验，证据限 r2 六类，口径按 scoring-caliber-supplement-r2.md。AC-07：用官方 install.sh 从 865092 全新装 main 到独立 prefix，与候选同口径记安装指纹；F1/F2/F3 每版各 1 次，全部登记，material.md SHA 须等于 r2 inputs 表；单次 90 分钟超时；带“已用 N/20”，第 16 次告知 PM。评分不由你做：交 CodeManger 逐夹具随机 X/Y 并封存映射 SHA，评分人为 Claude + 一位新会话评分人。你不修代码；FAIL 写页/对象/原句/期望退 SWE；“Host 未阅图”只报观察不退回；核验人截图不能证明产品审稿门；BLOCKED 不算 PASS；不做视觉放行；核对第 0 节历史 SHA。
```

### 7.4 致评分人（CodeManger 发，匿名稿就绪后）
```
【内容质量轮 · 盲评】只看 X/Y 匿名稿、rubric.md、原夹具判分底稿与 scoring-caliber-supplement-r2.md。每维 0/1/2 附页码与原句；N/A 写原因。交分前写下“我猜哪份是候选版及理由”。不要查看分支、PR、日志或映射文件。
```

## 8. 两位评审之间的分歧及本版取舍

- **评分人人选：** CodeManger 提议 Reviewer + Claude；Reviewer 认为自己审过 PR，应当回避。本版采纳回避：评分人为 Claude 加一位全新会话评分人。均分规则和“每维可落后 0.5”的容差采纳 CodeManger S8。
- **生成门的范围：** CodeManger 的方案是五环都上门，允许标待补后放行；Reviewer 建议只拦证据缺口。本版采纳 Reviewer。
- **“恰好一次”：** CodeManger S6 保留“恰好一次”但排除缺口清单和脚注；Reviewer 建议放宽。本版采纳放宽，同时纳入 S6 的不计次范围。
- **盲评泄露：** Reviewer 要求评分人披露猜测；CodeManger 提议遮盖“待补”后再评分。本版两者并用，遮盖只在 Q1-A 时使用。
