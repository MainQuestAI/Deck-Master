# T00+T01 实施记录：内容协作与交付语义 v1.2（首批两卡）

RC3 历史标记：下列既有 AC 结论属于当时版本，不自动关闭 R2/CQ/RC3 新条件。活动 R2 锚点与旧评价原件的身份见文末及 `evaluation/README.md`。

状态：**T00 与 T01 按 TASKS.md 完成，等待逐条验收核验**。本目录是 T00 的交付证据；T01 的代码与测试在仓库 `src/deck_master/delivery_eligibility.py`、`tests/rebuild/test_delivery_professional_gate.py` 及相关入口。日期：2026-10-12（Asia/Shanghai）。

## 任务卡提交模板

```text
Task: T00（内容原型与评价锚点）+ T01（人类专业交付谓词），两卡独立提交

Implementation commit / source baseline:
  - 规范基线：1c266c86（PR106 head，文档）
  - T01 代码提交：243eaa045d334310a97e9d373e2452158bd4a25e
  - T01 初审修复提交：bd8ea877（fail 依赖不完整仍保持阻断 + replaces 信任收窄 + 豁免收窄，PR107 一审 P1-1/P2-1/P2-2/P2-3）
  - T01 二轮修复提交：cbd7abbb（F01：全部声明依赖按统一当前性规则校验）、29a94858（F02：只有有效重审才解除专业失败）、边界显式注册表（审查裁决 IV.1）
  - T00 二轮修订提交：6e26176a（q4a 真实替代、q4b 确定性承诺、锚点 12 条、cues/阅读分支补齐、manifest v2）+ 本轮复核修复（SPEC §10 引用、cues 过渡、AN-Q1-4 定级 F0、q4a 归因测量与决定请求、q4b 成对措辞统一、manifest v3）
  - 边界守卫豁免提交：35f33ffefce50b8171782232dbc0f2824ea1fd5b
  - 本文档提交：见 git log（提交时生成）
  - 分支：impl/t01-t00-content-collab（基于 origin/codex/skill-flow-review）

Changed paths and resulting behavior:
  T01（详见该提交说明）：
  - src/deck_master/delivery_eligibility.py（新增）：统一 professional 谓词
    （professional_use kind + final 阶段 + 显式 pass + 受信适配器人类身份凭据
    + 精确当前 PPTX 主体 + Runtime 计算的完整依赖集 + 实质观察 + 无未关闭
    must_fix + 未被替代；当前未替代 fail 阻断任何 pass）。
  - exports.py：_gate 移除 "status != fail" 与 "kind==professional_use OR
    human" 错误谓词；_facts 附带统一结果与命名 gaps。
  - handoff.py / cli.py(final-readiness)：同一政策结果，工程状态单独展示。
  - review.v1.schema.json：新增可选 reviewer.identity_receipt；spec 镜像同步。
  - 测试：test_delivery_professional_gate.py（正例走正式 review envelope，
    17 个负例三入口一致拒绝，另 2 个谓词级回归（含审查 P1-1 的 thin
    fail / deck-level fail 放行路径回归）；test_export.py 的 _review helper 显式化，
    seed="human" 错误正例删除。
  T00（本目录）：
  - fixtures/：Q1–Q4 固定材料包可重用化 + manifest（SHA/行号 locator/预期行为）
  - prototype/q1-content-prototype.md：理解稿、两张决定卡、Narrative（N/E）、
    页职责与预算、完整六页逐页稿与 verbatim、口播三分支、设计可行性、真实返修
    演示、篇幅冲突预案
  - anchors/content-anchors.md：当前 R2 统一 F0–F3 适用说明、三类任务十二个正反锚点、
    校准规则
  - evaluation/：历史原字节（身份见 evaluation/README.md）；两轮各两位独立评价者完整初判（evaluator-a/b 初审、evaluator-c/d 二轮复核）+ 裁决记录
  - baseline.md：AC-B01 基线记录（SHA、锚点漂移、全量回归、环境差异）

AC IDs and status:
  - AC-B01：pass（结构层证据：baseline.md；安装包 digest 明确 not_run）
  - AC-B02：pass-with-evidence（完整原型 + 决定卡 + 两轮四份独立评价与
    分歧记录；二轮复核（evaluator-c/d，commit 6e26176a，输入哈希已重算）
    确认 cues 六页与阅读版解析块齐备、修订后无新增内容级 F0/F1；复核建议
    已全部处置。均声明为 AI 评价，非 L3 人类审查）
  - AC-B03：pass-with-evidence（二轮评价者逐条核验十二个锚点：错误候选全部
    属实、等级恰当、正确限定无误删；AN-Q1-4 按复核裁决修正为 F0；T08
    陌生实例迁移未跑，候选投放机制见锚点来源行）
  - AC-P01：pass at L1（正式 review envelope 提交人类凭据正例，export/
    handoff-check/final-readiness 三入口一致满足；受信适配器为受控 L1
    fixture，CONTRACTS §12.1 边界内，不声称真实人类已阅）
  - AC-P02：pass at L1，二轮复审后成立（一审 P1-1 与二轮 F01/F02 均已修复并
    有正式入口回归：thin fail/deck-level fail 阻断、额外依赖过期/不可解析拒绝、
    记录替代≠有效重审；host_self/tool/independent_host、not_evaluated/
    needs_review/not_applicable、错 kind、空/过期依赖、空观察、开放
    must_fix、重放/篡改凭据、旧 PPTX 主体、新 fail 掩盖旧 pass——全部拒绝
    且命名缺口；无 delivery 输出产生）
  - AC-P03：pass at L1（policy=false 不声称人类认可；blocked 时审阅稿可得
    且标注"records no human approval"；final-readiness 分别展示工程状态/
    专业证据/交付状态）
  - AC-P01–P03 的 L2+ 证据（真实身份通道）依 TASKS 归 T07/T08

Actual commands, environment, inputs and outputs:
  - .venv/bin/python -m pytest tests/rebuild -q → 1752 passed / 3 failed，
    3 个失败归因与修复见 baseline.md §3（其中 2 个为 T01 schema 镜像同步、
    1 个为规范提交 1c266c86 引入的审计文档 retired 引用）；修复后目标测试
    复跑通过
  - git ls-remote origin main / codex/skill-flow-review → 基线 SHA 核实
  - CONTRACTS §10 全部 11 个源码锚点与 base af9fd7a6 逐一比对 → baseline.md §2
  - fixtures/manifest.json 由脚本生成，含全部文件 SHA256；评价者B 独立复核
    10/10 相符

Evidence layer for each claim:
  - L0（结构/静态）：schema、锚点比对、manifest 哈希、门禁测试存在性
  - L1（Runtime 行为）：三入口正负矩阵经正式 API（export/handoff-check/
    final-readiness/service.accept_result）。证据分层如实区分：依赖过期/不可解析、
    有效重审解除失败、无效替代不解除失败等专业判定均走正式接纳路径；
    `test_review_binding_replaced_pptx_is_not_current` 为"先正式提交、再模拟
    后续输出替换"的谓词级构造。受控适配器 fixture 明确标注 synthetic/unit
    （CONTRACTS §12.1），不升级为真实人类证据
  - 本轮不产生 L2–L6 证据（真实 Host/人类审查/用户认可/听众/文件工程）

Failing examples and repair performed:
  - 评价发现的 17 项处置（修复/移交 T02–T07/登记不单独立锚，见 adjudication.md §3 对照表与二轮增补节），含原型自身
    的 1 处复核行号错误（分歧裁决：以表格事实源裁定，A 对 B 错）
  - 测试开发中修复 3 处：cli.py final-readiness 的 bool 化与 view 变量、
    适配器防重放语义（同一凭据重复验证不得误报重放，仅拒绝同 event_id
    绑定不同内容）

Preserved state / calls / unaffected pages:
  - 用户主工作区（main）未提交修改未触碰；实施在独立 worktree
  - 测试运行再生的 output/playwright 截图已还原，不入提交
  - 未删除任何旧文件/历史产物；policy 默认 false 语义未变

Not run / blocked evidence and concrete next step:
  - 安装包 digest / HOME 安装切换：T07（源码 checkout 不代替安装验收）
  - 真实身份通道适配器与 source receipts：T07（严格人类政策现诚实地保持
    blocked，具体缺口为 identity_adapter_unavailable / evidence missing）
  - 真实 Host 会话、生图、PPTX 编译与备注回读、用户与听众验证：T08
  - Q4 控制变体 Runtime fixtures（无 ContentPlan 旧项目、1 次额度等）：T02–T04
（P6 阅读稿可见解析块已产出，见原型 6.2；原 T03 登记项撤销。）
  - 本目录评价均为 AI 评价者；不充当 L3 人类专业审查

Scope of this change; next dependent card:
  - T01 关闭谓词缺陷与三入口一致；T02 消费 delivery_eligibility 的统一
    结果并注册协作合同（Review v2、Decision/Authorization、collaboration
    区），T07 补真实适配器。未实施 T02+ 的任何生产路径。
```

## 目录结构

```
content-collaboration-v1.2/
├── README.md            ← 本文件（T00+T01 任务卡结果）
├── baseline.md          ← AC-B01：基线与漂移核实、全量回归、环境差异
├── fixtures/            ← Q1–Q4 固定材料包（可重用合成输入）+ manifest
│   ├── q1/  q2/  q3/    ← EXAMPLES 固定源文本（原样落盘）
│   ├── q4/              ← Q4-A 正确六页 / Q4-B 植入错误六页（内容级 fixture）
│   └── manifest.json    ← SHA256、行号 locator、预期行为、控制变体登记
├── prototype/
│   └── q1-content-prototype.md  ← 完整专业产物原型（AC-B02）
├── anchors/
│   └── content-anchors.md       ← 三类任务十二个正反锚点 + 统一分级适用（AC-B03）
└── evaluation/
    ├── evaluator-a.md   ← 评价者A完整初判（事实/证据视角，PASS-with-repairs）
    ├── evaluator-b.md   ← 评价者B完整初判（可用性/表达视角，PASS-with-repairs）
    ├── evaluator-c.md   ← 二轮复核（事实/证据视角，PASS-with-repairs）
    ├── evaluator-d.md   ← 二轮复核（可用性视角，PASS-with-repairs）
    └── adjudication.md  ← 分歧裁决（一轮 3 项、二轮 1 项）与修复对照（含二轮增补节）
```

## 与规范的对照说明

- 本轮产物未先新增 Runtime 合同（T00 要求）；Narrative/Plan/Page 等对象以可读文档承载，字段化归 T02。
- Q4 fixtures 是内容级单元 fixture，明确不含伪图片/PPT；工程验收所需的真实 SVG/PPT/回读产物按 TASKS 归 T05/T06/T08，不得用占位文件兜底。
- 固定样例全部为合成材料；不包含、不引用任何真实客户资料。

## RC3-01 活动规范与历史记录

活动锚点已接收上传 R2 原件 `3f58b739…`，旧 `42774a70…` 原字节保存在 `anchors/history/`。旧五份评价原件保留不变，按历史版本解释；当前引用及历史 SHA 见 `fixtures/manifest.json`。上文既有 AC pass/pass-with-evidence 是当时记录，不自动关闭 R2/CQ/RC3 新条件。两位评价者统一口径的真实重新评价、完整首稿和方法效果，由当前固定执行档案另行记录；未执行层保持 NOT_RUN。
