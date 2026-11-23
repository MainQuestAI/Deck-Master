> 历史背景副本，已移除私有来源信息。本文中的待批准、额度、运行顺序和旧状态规则均不作为当前执行指令；当前范围、行为与验收统一见[现行开发稿](../rust-rebuild/README.md#当前内容质量增量2026-11-23)。原 SHA 仅为历史引用，不是净化副本的内容校验值。

# Deck Master 内容质量切片 · 实现可行性评审（CodeManger，2026-11-20）

- 评审对象：`deck-master-prd-cut-20261120-content-quality.md`，SHA-256 实算 `b1d412eae0d78ee59c1fc881ddef1842a0fe50acb774d6b19c0ee833b99ddbb8`，与 PM 给的值一致。
- 夹具：`content-quality-fixtures-20261120/` 下 5 个文件实算 SHA 与切片第 0 节冻结值全部一致。第 0 节列出的 6 份历史文件，当前 SHA 也全部一致（文件在 `_specs/` 和 `deck-master-assessment-20261120/` 下）。
- 基线：用 cursor-github `get_branch` 复核，`MainQuestAI/Deck-Master` main = `865092226246aa57820aa4cdec291648aa3ddee0`，tree `c5e22979f269b619dcd5872394ce3250641b6295`，**没有漂移**。另外看到 **main 没有开分支保护**（`protected: false`）。
- 读源码的方式：优先用现成证据（`codex/cloud-review/architecture-evidence.md` 的 EV 卡、`architect/07`、`汇总评估.md`）。缺的地方按锁定 SHA 单独读了公开文件，没有 clone，也没有扫全库。读过的文件：`AGENTS.md`、`docs/specs/rust-rebuild/README.md`（开发稿 v1.2）、`rust/src/{model,ops,prompts,export,cli,server,store,error}.rs`、`frontend/src/api.js`、`deck-tools/src/deck_tools/sanitize.py`、`deck-skill/{deck-master,deck-content,deck-review}/SKILL.md`、`deck-skill/references/{expression-review-humanizer,writing-profiles,page-writing,narrative-patterns}.md`。下文行号都按 `865092` 计。
- 没做的事：没改代码，没开 PR，没跑 Host，没启动云端。M01/M08、method-review 全文、前端组件、native/render.cjs 没有逐行读；涉及这些的地方标为“落点待 SWE 确认”。

---

## 结论先说

切片的方向和拆法没问题，大部分 AC 能落地，估计开发 **7–10 人日**（不含 Host 实跑和评审往返）。但有 **5 个阻塞**，需要 PM 写一份补充文件，再请 Los 做一次确认，才能交给 SWE。其中 3 个是 AC 跟仓库现行规范打架，2 个是 AC 写法本身没法验，或者会被夹具误判。AC-08（cNvPr）和 AC-01/02 的数据部分不受这些阻塞影响，可以先开工。

---

## 一、阻塞（不改，SWE 开工后会被 Reviewer 按仓库规范退回，或 AC 没法判）

### B1 · AC-01/02/03/06：新增持久字段、生成门和审稿记录，碰到了仓库“最高开发规范”的先问条款
- **证据**
  - `AGENTS.md:5`：本文件是最高开发规范。
  - `AGENTS.md:61-64`：新增检查、字段、状态之前，先说清它防的真实故障。数据与消耗保护只限开发稿 §2.2 的 8 条，新增要老板同意。§2.1 列出的机制（含“审阅 pass 汇总”“数字配额”）不要加回。
  - `AGENTS.md:121-127`（§11 先问再做）：新增开发稿里没有的机制或持久字段、做不兼容的持久格式变化，都要先得到老板答复。
  - 开发稿 `docs/specs/rust-rebuild/README.md:48`：禁止“审阅 pass 汇总、审阅者独立性判定”。
  - 开发稿 `README.md:132`：todo/refs “只用于展示，不阻止任何动作”。
  - `AGENTS.md:114`：设计变化要和代码在同一个 PR 里改开发稿。
- **理由**
  - Los 21:27 授权的是“评审 → 开发 → 核验 → 修复”这个流程，没有逐条认可这些具体偏离：新增 Brief/Framing/Page 字段、reviews 表结构、`run start` 新增两道拒绝门、导出“未审”字段。
  - AC-06 的“六项检查逐项结论”如果实现成通过/不通过汇总，就正好是开发稿 §2.1 禁止的“审阅 pass 汇总”。
  - 不先解决这一条，Reviewer 按 AGENTS.md 审 PR 时只能退回。
- **建议改法**
  - PM 在补充文件里列一张“相对开发稿 v1.2 的偏离清单”，请 Los 一次性点头。清单内容：
    1. 新字段：`brief.decision`、`brief.concerns[]`、`brief.narrator{role,tone}`、`framing.storyline[]`、`page.kind`、`page.argument`。
    2. `run start image|svg|native` 新增两条输入拒绝：框架/主线为空；判断页五环缺失且没标待补。这两条都算 §2.2 的新增保护，防的故障是“没有主张和论证就去花 ImageGen 调用、画出无依据页面”。
    3. reviews 增加一种“出稿审稿”记录，导出时增加只读的 `content_review` 字段。
    4. `FORMAT_VERSION` 6→7。
  - AC-06 措辞改成“记录存在、按 method 区分、绑定到被导出的版本”，**不在代码里算通过/不通过**。六项结论只是记录内容，程序不汇总、不判。
  - 每个 PR 同步改开发稿 §3.3/§3.5/§3.6，不另建 spec 目录（`AGENTS.md:114`）。

### B2 · AC-04 / Q1：“待补上屏”会推翻三处现行设计，不能按默认值直接做
- **证据**
  - 开发稿 `README.md:313`（§5.1）和 `:323`（§5.2）：页面文案不含缺口说明，缺口记在 todo，不上屏，不放页脚。
  - `rust/src/prompts.rs:157`：SVG 的 task.md 原文写着“页面文案不含缺口说明；缺口在 todo，不上屏，不放页脚”。
  - `deck-skill/deck-content/SKILL.md:45`：“待补放 `todo`，不上屏”。
- **理由**：`AGENTS.md:124`（§11）要求改开发稿里的设计决定要先问。Q1 现在写的是“有默认值、不阻塞”，等于用默认值改掉一个设计决定。另外，这一改会直接影响 AC-07 的盲评（见 S7）。
- **建议改法**
  - Q1 要等 Los 明确回答，不走默认值。只卡 PR-D（文本与提示词），不卡 PR-A/B/C/E。
  - 如果 Los 选上屏：在 prompts.rs:157、开发稿 §5.1/§5.2 和 deck-content SKILL 把“不上屏”改成“草稿阶段统一用‘待补：…’标出，缺口清单另行输出”。`todo` 仍然是缺口清单的来源，不新建字段。
  - 如果 Los 选不上屏：AC-04 的“醒目标注”改为讲稿备注加缺口清单，screenshot 证据换成 `export md`/缺口清单 JSON。

### B3 · AC-05：Proof 要求产品输出“限定词/免责计数、工程腔命中”的 API JSON，跟仓库规则和 humanizer 本身冲突
- **证据**
  - 开发稿 `README.md:52`：禁止数字配额（零协议词等）和固定措辞断言。
  - `AGENTS.md:99`：不写固定措辞断言。
  - `deck-skill/references/expression-review-humanizer.md:11`：不能按词表或句式一律判错；`:19`：不照搬禁词。
  - `deck-skill/references/writing-profiles.md:25`：不要机械禁词计分。
  - 切片 AC-05 自己也写了“关键词命中不能单独判定”。
- **理由**：把词表计数器做进产品 CLI，就是在产品里加一个禁词评分器。产品规范明确不要这个；AC 自己也承认它不能判 PASS/FAIL。放进产品只增加维护成本，没有拦截作用。
- **建议改法**
  - 计数器放在**核验工具**里，作为 Codex/Reviewer 的核验脚本，跟评估目录里现有的 scripts 一样，不进产品 CLI，也不进发布包。
  - AC-05 的 Proof 改成“核验脚本 JSON + 核验人判断”。
  - 产品侧只负责把讲述人约束写进 Host 会读到的指令（见 B4）。

### B4 · AC-05 第 5 点：“Host 实际收到的写作指令”在现有架构里没有定义，现在写法下没法验
- **证据**
  - `rust/src/prompts.rs:86-166`：`task.md` 只在 `run start image|svg|native` 时生成，是**出图/重建阶段**的任务，内容由已经写好的 `content` 组成。
  - 正文写作发生在更早的阶段：Host 读 `deck-skill/*/SKILL.md` 和 references，再用 `deck put` 保存（`deck-content/SKILL.md:41-47`）。
  - EV-ENT-001-SKILL / EV-HO-001：代码不会拉起或观察 Host 读了哪个 Skill。
  - `deck-master/SKILL.md:40`：代码不拦截 Host 改写提示词。
- **理由**：把讲述人约束塞进 task.md 管不到写作，因为字已经写完了；只写在 SKILL.md 里，又没法从产品侧证明 Host “收到了”。
- **建议改法**：定义成两层证据。
  1. 产品层（确定性）：`deck get`/`deck show` 的 JSON 里带一段由 `brief.narrator`、`decision`、`concerns` 拼出的 `writing_brief` 文本。Host 每次取上下文都会在工具输出里拿到这段话。
  2. 观察层：核验时从 Host 会话 jsonl（`codex exec --json` 的记录）里摘出包含这段文本的工具输出，附 SHA。
  - AC-05 第 5 点改成“`writing_brief` 出现在 Host 会话的工具返回里”。这样可以验，也不依赖 Host 自觉。

### B5 · AC-04/AC-05 的判据和夹具本身打架，会误报
- **证据与理由**
  - **“验证”**：切片 §2 第 6 条把“验证”列为工程腔。但 CQ-F2 判分底稿 R2（`CQ-F2-qbr-coo.md:21`）的标准答法正是“价格原因只能作为**待验证**假设”。按 AC-05 第 3 点查，正确答案会被判成工程腔。
  - **“每个数字都能追溯到材料或给出算式”**（AC-04 第 2 点）：顾问稿合理的**方案参数**会被判 FAIL。比如 F1 建议“首批 20 家里 8 家直营、12 家加盟试点”，F3 建议“首批 50 家店试 8 周”。这些不是材料事实，也不是编造，而是建议。
- **建议改法**
  - 工程腔示例改成成组的说法：“阻塞于…门槛”“过闸”“验证门槛”，并注明“待验证（假设）属于正常的管理层用语”。
  - AC-04 加一类例外：**明确写成建议或方案参数的数字**（例如“建议…”“拟…”）不算事实主张，但不能写成已发生、已测得。CQ-F2 G3 那类“自编 Q4 目标”仍然判 FAIL，因为它冒充了目标事实。

---

## 二、逐条 AC：落点、工作量、拦截性质

“拦截性质”分三类：**门** = 确定性代码拒绝（CLI 非 0 退出或 HTTP 错误）；**提示** = 机读字段或告警，不阻断；**人/Host** = 只能靠 Host 自觉或核验人阅读。

| AC | 源码落点 | 类型 | 工作量 | 拦截性质 |
|---|---|---|---|---|
| AC-01 受众/决策/讲述人 | `rust/src/model.rs:7` 的 `Brief` 增加 `decision`、`concerns`、`narrator`（`audience` 已有，沿用为“读者”）；`ops.rs:754-844` 的 `run_start` 在 `ops.rs:775` 读 snapshot 之后加空值拒绝（`Error::Input`，退出码 2，见 `error.rs`）；`export.rs:86-101` 输出；`store.rs:13` 的 `FORMAT_VERSION` 6→7，加迁移和“旧库能打开”测试（`AGENTS.md:80`）；`deck-content/SKILL.md:43`、`deck-master/SKILL.md:36` | 代码+技能 | **中**（约 1–1.5 天）：字段简单，主要量在格式升级、兼容测试和开发稿改写 | 字段为空时 `run start` 是**门**。“内容与夹具任务一致”是**人**判。 |
| AC-02 主线先于页面 | `model.rs:25` 的 `Framing` 增加 `storyline: Vec<String>`；`run_start` 同一道门检查主线非空；标题连读输出加在 `ops::show`（`ops.rs:139-177`）或 `get` 里，列出 `outline:[{page,kind,title}]`；“主线早于正文”用**现有**版本历史即可证明（`ops.rs:144` 的 `show.history`，加 HTTP `/api/versions/{id}`，见 `server.rs:233`） | 代码+技能 | **小**（约 0.5 天） | 主线为空是**门**。5–8 句、话题标题 ≤10%、复述一致都是**人**判，不能做成代码配额（开发稿 `README.md:52`）。 |
| AC-03 五环 | `model.rs:270` 的 `Page` 加 `kind`（judgment/reference/explanation/teaching）和 `argument{reasons[],evidence[{text,ref|gap}],reasoning,rebuttal}`，主张直接取 `content.title`，不重复存；`PagePatch`（`model.rs:315`）与 `apply`（`:334-337`）、`Page::author` 同步；`run_start` 对 `kind=judgment` 的页检查五环，每环要么有值、要么带待补标记，拒绝信息写明缺哪一环；缺口清单由 `todo` 加 `evidence.gap` 计算出来，不手填；技能改 `page-writing.md:7/91`、`methods/M03-argument.md`（M03 落点待 SWE 确认） | 代码+技能 | **中偏大**（约 2–3 天）：页模型、门、测试、技能示例都要动 | 缺环且未标注时 `run start` 是**门**。R1/R2 推理对不对，只能靠**人**判。漏洞：Host 把判断页标成 `explanation` 就能绕过门，核验时要查 kind 标得对不对（见 S4）。 |
| AC-04 证据/缺口/零编造 | 缺口清单输出与 AC-03 共用（`get`/`show`/`export md`）；上屏方式取决于 Q1（B2），改 `prompts.rs:9,157`、开发稿 §5.1/§5.2、`deck-content/SKILL.md:45` | 主要是技能/提示词，少量代码 | **小到中**（约 1 天，不含 Q1 答复等待） | 缺口清单是**提示**。“零编造”“形容词不当证据”只能靠 **Host 自觉 + 人**判。数字溯源可以由核验脚本先比对材料原文，列出候选，再由人判（见 B5 的例外）。产品没有能真正拦住编造的门，切片也没把它写成拦截，这点没问题。 |
| AC-05 讲述人/去防御 | `writing-profiles.md`（“高管决策”段）、`expression-review-humanizer.md`（加校准行，见第三节）、`deck-content/SKILL.md`；`writing_brief` 输出（B4）在 `ops::get`/`show` | 主要是技能，少量代码 | **小到中**（约 1 天） | 全部是 **Host 自觉 + 人**判。计数器放到核验工具里（B3）。 |
| AC-06 审稿门/内部备注/看过 | `ops::review_add`（`ops.rs:226-259`）增加出稿审稿记录（`--kind release --checks <json>`，具体名字由架构师定），`reviews` 表加列（`store.rs:118`，和 AC-01 一起做格式升级）；`ops::build`（`ops.rs:1809-1864`）和 `export_pptx`（`:1934-1966`）返回 `content_review:{status:"unreviewed"|"reviewed"|"stale", methods:[…], version_id}`；HTTP 通过已有的 `X-Deck-Status` 头带出（`server.rs:274-289`）；`deck-review/SKILL.md:38-44` 写六项 | 代码+技能 | **中**（约 1–1.5 天） | “未审”是独立字段，属于**提示**，**不能阻断导出**（`AGENTS.md:65` 不让审阅状态挡住作者，开发稿 §2.1 禁止 build 硬拒），切片也只要求标出，这点对。内部备注不上屏、最终页被看过，只能靠 **Host 自觉 + 人**判，见 S5。 |
| AC-07 前后对照 | 不改产品，是核验活动 | 核验 | Host 实跑 6 次以上，见第四节 | **人**（盲评） |
| AC-08 页内 cNvPr 唯一 | `deck-tools/src/deck_tools/sanitize.py:505-514`：现在保留原 id，名称改写为 `"形状-"+id`（`:512`）。在这里按幻灯片部件重新编号，是两条构建链共同经过的点：`compile_job` 走 `jobs.py:59-62`，`assemble` 走 `native/__init__.py:740-743`（EV-EX-001）。重新编号时要同步改引用这些 id 的属性（连接线 `stCxn/endCxn@id`、动画 `spTgt@spid` 等，**落点待 SWE 确认**）；findings 加 `duplicate_cnvpr_id`；回归夹具用合成的“形状+表”“图+表”两页 | 代码 | **小到中**（约 0.5–1 天） | 修复后是确定性的结构保证；findings 报重复属于**提示**。 |

合计约 **7–10 人日**，Reviewer 往返另算。PR-D 要等 Q1 答复。

---

## 三、与 humanizer “保留限定”的冲突：位置、原文、处理

**先更正一个事实**：仓库里**找不到“保留所有限定词”这句原文**。实际的写法都是“必要限定”：
- `expression-review-humanizer.md:16`：“保留影响使用的来源说明、限定和操作边界。”
- `expression-review-humanizer.md:23`：每个发现要列出“必须保护的事实与限定”。
- `expression-review-humanizer.md:25`：改后逐项对照“…否定、预计/条件/不确定性…；新增无依据或**丢失必要限定**均需纠正。”
- `expression-review-humanizer.md:32`（校准表）：删掉“预计”“仅限”“未验证”“不自动写回”属于必须拒绝的处理。
- `rust/src/prompts.rs:9`（生图 task.md）：“逐字呈现可见文字，保留事实、数字、单位和限定。”
- 另外 `AGENTS.md:115` 已经写了“限定只在需要的地方写一次，不堆叠免责声明”。这本来就是去过度防御的方向。

所以问题不在于规则要求“保留一切”。humanizer 只防“丢限定”，**没有反方向的“同一限定重复出现、压过结论”这类检查**。切片第 1 节 L42 说它“偏向保留一切限定词”，说重了，建议 PM 在补充文件里改成上面这个说法。

**处理建议**
1. **优先级**：事实与必要限定 > 结论先行 > 去重。去防御只**删重复和堆叠**，不删第一次出现的必要限定。
2. **范围**：只管读者能看到的标题、正文、图表注、页脚。讲稿备注和附录可以完整展开边界（这也是 AC-03 安排反驳与边界的位置）。
3. **例外写法**（加进 humanizer 校准表，各一行）：
   - 原稿：“该数据**可能**存在偏差……（第 3、5、7 页重复同一免责）”→ 可接受：只在数据第一次出现的页写一次“仅上海两商圈样本”，其他页删掉。必须拒绝：三页全删，或改成“华东租金为 4.5–6.2 万”而不说明样本范围。
   - 原稿标题：“或许可以考虑在一定程度上采用混合模式”→ 可接受：“华东首批宜用混合模式：直营守品质，加盟提速度”，条件放进正文。必须拒绝：把“租金只有上海样本”这个条件一起删掉。
4. **生图提示词**：`prompts.rs:9` 是逐字上屏，不负责去重，**不要改**。去防御必须在 `deck put` 之前的写作阶段完成，否则重复的限定会被原样画上去。这一点要写进 deck-content 的保存前检查。
5. 这样改不涉及 M10 方法卡的定位，也没越出切片“不改方法卡学术定位”的边界。

---

## 四、Host 运行额度：20 次是否合理

**单次时长参考**
- 历史项目 11-16 基线：24 页，5440 秒（1 小时 30 分 40 秒），约 227 秒/页。来源 `历史材料（未公开）`。
- 11-20 本机：4 页，564.933 秒，约 141 秒/页。来源 `汇总评估.md:46`。

CQ-F1/F2/F3 页数自定，商用决策稿按 8–12 页估。候选版多了“先写框架和主线、逐页五环、出稿审稿”几步，按 +20–30% 算，**单次约 20–60 分钟**。本机 4 页那次用量为输入约 437 万 token（缓存 426 万）、输出约 2.1 万 token，10 页左右大致翻倍。这里不折算费用，但要提醒 Los：额度用的是本机已登录的 ChatGPT/Codex 账号，频繁跑可能碰到账号限流，那时按 BLOCKED 处理。

**次数估算（夹具数 × 轮次）**

| 阶段 | 次数 | 说明 |
|---|---|---|
| SWE 开发自测（只用 F1、F2） | 4–6 | 2 夹具 × 2 轮，外加 1–2 次失败重启 |
| Codex 首轮核验 | 6 | main 3 + 候选 3 |
| 修复轮回归 | 每轮 3 | 只重跑候选；只要环境和 Host 设置不变，main 基线不重跑 |
| 合计 | 常见 13；两轮修复 16–18；三轮修复 19–21 | 第 3 轮同一 AC 还 FAIL 时，按切片 §4.5 停下交 Los |

**建议**
- 上限 **20 次合理**，但要拆开计：SWE 开发自测 ≤6 次，核验加修复回归 ≤14 次。哪边先用完就停下问。
- **计数口径**：只要实际启动了 `codex exec`（Host 会话），就计 1 次。失败、超时、中途中止、跑了但没产物都计入。没启动 Host 就失败的（安装失败、doctor 不通过）不计，但记 BLOCKED。
- 单次硬超时 90 分钟，超时计入次数并记 FAIL/BLOCKED，不自动重试。
- 每次交接消息都带上“已用 N/20”。用到 16 次时提前告诉 PM。
- 串行跑。每次用新的工作目录，并照 11-20 的做法披露 CODEX_HOME 的副作用（generated_images、sessions、SQLite 缓存）。

---

## 五、分支与 PR

**需要集成分支。** main 没有开保护（`get_branch` 返回 `protected:false`），PR 直接对 main 开，误点合并就会进 main。CI 对任意 base 的 `pull_request` 都会触发（`.github/workflows/rust.yml:3-7`），所以以集成分支为 base 不影响 CI。

- 集成分支：`rust/content-quality-20261120`，从 `865092…` 开。命名按 `AGENTS.md:47` 的 `<类型>/<简述>`。
- 各 PR 的 base 都是集成分支。Codex 在**集成分支头 SHA** 上核验，这就是切片说的“候选头”。最后从集成分支对 main 开一个 PR，只开不合，等 Los。

| PR | 分支 | AC | 主要改动 | 风险 |
|---|---|---|---|---|
| PR-A | `tools/unique-cnvpr-ids` | AC-08 | sanitize 重新编号 + findings + 回归夹具 | 低，跟其他 PR 无关 |
| PR-B | `rust/decision-frame-storyline` | AC-01、AC-02 | Brief/Framing 字段、FORMAT_VERSION 7 迁移、`run start` 框架门、outline 输出、开发稿 §3.3 | 中（持久格式） |
| PR-C | `rust/argument-chain-gate` | AC-03 + AC-04 的缺口清单 | Page.kind/argument、五环门、缺口清单计算 | 中偏高（页模型与门） |
| PR-E | `rust/content-review-record` | AC-06 | 出稿审稿记录、`content_review` 字段、HTTP 头、deck-review 技能 | 中（跟 PR-B 共用一次格式升级，**要协调**：B 先进集成分支，E 在 B 的迁移上追加，不再单独升版本） |
| PR-D | `skill/consultant-voice-and-gaps` | AC-04 文本、AC-05 | writing_brief、humanizer/writing-profiles/page-writing/M03、prompts.rs 缺口上屏（看 Q1） | 中（直接影响作品），**要等 Q1** |

合并进集成分支的顺序：**A（随时）→ B → C → E → D**。D 放最后，因为它引用 B/C 的字段名，而且要等 Q1。每个 PR 都由 Reviewer 审，无阻塞才进集成分支。AC-07 只在全部 PR 进集成分支之后跑一次，不在单个 PR 上跑。

---

## 六、分工

默认安排（Codex 只核验、SWE 修复、Reviewer 审 PR）**基本保留**，补四点：
1. **AC-07 的 6 次 Host 实跑由 Codex（核验方）执行，不由 SWE 执行。** 实现者不应该自己产出对照稿，否则就有挑稿的空间。本机 Host 授权在共享盒子上，Codex 能直接用。文档里把“Host（codex CLI，被测产品的执行者）”和“Codex（核验 agent）”分开写，免得混。
2. **盲评至少两位评分人**：Reviewer 和 Claude。两人都不是 SWE、Codex 或 PM，Claude 已做过本轮作品质量审阅。每维取两人均分。CodeManger 只负责匿名化，不评分。
3. **架构师**在 SWE 开工前交出字段与门的设计：名称、JSON 形状、错误信息、迁移，作为 PM 补充文件的附件。这正是 B1 要给 Los 的偏离清单内容。
4. **AC-07 的 main 基线要重装。** 用候选版同一个安装脚本，从 `865092` 新装到一个独立 prefix，两个版本的安装指纹同口径。不要沿用 11-16 的历史安装（b222f2dd…）：Reviewer 已经说明那份安装和 865092 的对应关系没有重新独立构建验证过。安装被测产品本身不算“装未授权软件”，建议补充文件里明确写上。

---

## 七、建议（不阻塞，建议 PM 在补充文件中一并处理）

- **S1（AC-01）把“页面生成”定义清楚**：指 `run start image|svg|native`，**不包括** `deck put` 保存草稿（`page-writing.md:91` 和 `AGENTS.md:65` 都要求草稿随时能存），**也不包括** `build`（开发稿 §2.1 禁止 build 硬拒）。
- **S2（AC-02）阈值改成人判标准**：“话题标题 ≤10%”在 8 个判断页的稿子里等于一个都不许有（1/8=12.5%），建议直接写“判断页话题式标题 ≤1 个”。“5–8 句”只当核验标准，代码只检查非空。两者都不要做成代码配额。
- **S3（AC-02）证据类型**：“核验人复述”和 AC-05 的“会话摘录”都不在切片限定的四类证据里，建议加一类“日志/文本摘录 + SHA”。
- **S4（AC-03）判断页可以被绕过**：`kind` 由 Host 填，标成说明页就能躲开五环门。核验时要逐页确认 kind 标得对，标错就记 FAIL。代码不做自动分类，自动分类只能靠模型，不是确定性检查。
- **S5（AC-06）“最终页被看过”写清楚判什么**：现在写的是“日志里有读图动作，**或者**核验人逐页截图”。有了后半句，这一项永远能过，就测不到产品了。建议拆开：①产品只要求 deck-review 技能写明逐页打开最终 PNG；②核验时从 Host jsonl 找读图动作，找不到就记“Host 未阅图”，作为观察结论报告，不当成代码 FAIL 退回 SWE，因为 SWE 改不了 Host 的行为，循环 3 轮只会白白触发停止条件；③核验人自己逐页截图是核验步骤，不证明 Host 看过。
- **S6（AC-04 与 AC-05 计数口径）**：每个缺口只在主承载页醒目标一次，缺口清单是另一份产物，不算重复；不确定项（U1）“恰好一次”不把缺口清单和出处脚注算进去。不定清楚的话，AC-04 的“醒目”和 AC-05 的“只说一次”会互相顶。
- **S7（AC-07 盲评泄密和偏向）**：如果 Q1 选上屏，候选稿一定有“待补：”字样，main 稿按设计一定没有。评分人一眼就能认出 X/Y，而且 D5 天然偏向候选版。建议在评审记录里写明这个局限，或者让评分人先对两份都隐去“待补”标记的版本打 D1–D4、D6，再单独看原稿打 D5。
- **S8（AC-07 样本噪声）**：每个夹具各跑 1 次，0/1/2 分制，18 个“维度×夹具”的比较全都要“不低于”，模型生成的随机波动很容易让其中一项落后，导致无谓的修复循环。建议改成两位评分人取均分，“任一维均分落后不超过 0.5”，保留“总分严格高于 ≥2/3 且含 F3”。
- **S9（格式升级）**：新增字段后，用 865092 的程序打开候选版项目会因为 `deny_unknown_fields` 报 serde 错误（`model.rs:6` 等）。按 `AGENTS.md:80` 把 FORMAT_VERSION 升到 7，旧程序会给出明确的“请升级 deck”（`store.rs:70-73`）。AC-01 的兼容测试要覆盖“v6 库能用新程序打开”。
- **S10（AC-07 历史文件）**：第 0 节只列了文件名和 SHA，没写路径。建议补上绝对路径。我这次实算 6 份都一致。
- **S11（内部备注检查）**：只查原文子串挡不住改写。F2 N1 真正要查的是“没有自编 Q4 目标数字”，而不是“Q4”加数字一起出现就判错：“SSO 预计 Q4 第 6 周上线”是合法表述。核验脚本只列候选，由人判。
- **S12（前端）**：Brief/Framing 在 UI 里按整个单元提交（`frontend/src/api.js` 的 `contextUnitPatch` 用 `structuredClone` 整体回传），JS 侧会原样带回新字段，不会被清空；页面草稿只提交 `draftPatch` 里列出的 6 个字段，也不会覆盖 `argument`。本轮不要求 UI 能编辑新字段，在 PR 描述里写明“UI 未覆盖”即可。

---

## 八、无问题

- 夹具和量表 SHA、历史文件 SHA 都和冻结值一致。main 没有漂移。
- AC-08 的修复点只有 sanitize 一处，两条构建链都经过它，改一处就够，属于真正的产品修复候选（PM 复核意见也是这么定性的）。
- AC-06 只要求“未审”显式标出、不阻断导出，跟 `AGENTS.md:65` 和开发稿 §2.1（禁止 build 硬拒）一致。
- 框架门和五环门放在 `run start`，也就是外部调用之前，符合 `AGENTS.md:66`“检查放在真实的读写、外部调用和导出处”，也跟 `page-writing.md:91` 原来靠 Host 自觉的约定方向一致，只是变成了程序强制（前提是 B1 拿到 Los 同意）。
- AC-02 的“主线早于正文”用现有的只追加版本历史就能证明，不需要新机制。
- CQ-F3 留出、PM 不评分、执行人不核验自己、同一 AC 连续 3 轮 FAIL 就停：这些安排合理，不算过度防御。
- 范围外清单（不碰真实客户材料、不合 main、不发版、不做事实核查引擎）清楚，可以执行。

---

## 九、下一步（CodeManger 视角）

1. PM 写补充文件，处理 B1–B5 和 S1–S12；B1 的偏离清单和 B2 的 Q1 一起给 Los，一次确认。
2. 补充文件定稿前，可以先分派 SWE 做 **PR-A（AC-08）**：它不涉及新字段或新的门。
3. Los 确认后，按 B → C → E → D 的顺序分派，架构师的字段设计先交。
