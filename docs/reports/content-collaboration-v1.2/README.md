# T00+T01 实施记录：内容协作与交付语义 v1.2（首批两卡）

状态：**T00 与 T01 按 TASKS.md 完成，等待逐条验收核验**。本目录是 T00 的交付证据；T01 的代码与测试在仓库 `src/deck_master/delivery_eligibility.py`、`tests/rebuild/test_delivery_professional_gate.py` 及相关入口。日期：2026-10-12（Asia/Shanghai）。

## 任务卡提交模板

```text
Task: T00（内容原型与评价锚点）+ T01（人类专业交付谓词），两卡独立提交

Implementation commit / source baseline:
  - 规范基线：1c266c86（PR106 head，文档）
  - T01 代码提交：243eaa045d334310a97e9d373e2452158bd4a25e
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
    16 个负例三入口一致拒绝）；test_export.py 的 _review helper 显式化，
    seed="human" 错误正例删除。
  T00（本目录）：
  - fixtures/：Q1–Q4 固定材料包可重用化 + manifest（SHA/行号 locator/预期行为）
  - prototype/q1-content-prototype.md：理解稿、两张决定卡、Narrative（N/E）、
    页职责与预算、完整六页逐页稿与 verbatim、口播三分支、设计可行性、真实返修
    演示、篇幅冲突预案
  - anchors/content-anchors.md：F0/F1 可判定定义、三类任务十个正反锚点、
    校准规则
  - evaluation/：两位独立评价者完整初判 + 裁决记录（分歧 3 项、修复 17 项）
  - baseline.md：AC-B01 基线记录（SHA、锚点漂移、全量回归、环境差异）

AC IDs and status:
  - AC-B01：pass（结构层证据：baseline.md；安装包 digest 明确 not_run）
  - AC-B02：pass-with-evidence（完整原型 + 决定卡 + 两位评价者独立初判与
    分歧记录；均声明为 AI 评价，非 L3 人类审查）
  - AC-B03：pass-with-evidence（评价者确认全部已标明反例可发现、正确限定
    未被误判；本轮为锚点自校准，T08 陌生实例迁移未跑）
  - AC-P01：pass at L1（正式 review envelope 提交人类凭据正例，export/
    handoff-check/final-readiness 三入口一致满足；受信适配器为受控 L1
    fixture，CONTRACTS §12.1 边界内，不声称真实人类已阅）
  - AC-P02：pass at L1（host_self/tool/independent_host、not_evaluated/
    needs_review/not_applicable、错 kind、空/过期依赖、空观察、开放
    must_fix、重放/篡改凭据、旧 PPTX 主体、新 fail 掩盖旧 pass——全部拒绝
    且命名缺口；无 delivery 输出产生）
  - AC-P03：pass at L1（policy=false 不声称人类认可；blocked 时审阅稿可得
    且标注"records no human approval"；final-readiness 分别展示工程状态/
    专业证据/交付状态）
  - AC-P01–P03 的 L2+ 证据（真实身份通道）依 TASKS 归 T07/T08

Actual commands, environment, inputs and outputs:
  - .venv/bin/python -m pytest tests/rebuild -q → 1752 passed / 3 failed，
    3 个失败归因与修复见 baseline.md §4（其中 2 个为 T01 schema 镜像同步、
    1 个为规范提交 1c266c86 引入的审计文档 retired 引用）；修复后目标测试
    复跑通过
  - git ls-remote origin main / codex/skill-flow-review → 基线 SHA 核实
  - CONTRACTS §10 全部 11 个源码锚点与 base af9fd7a6 逐一比对 → baseline.md §2
  - fixtures/manifest.json 由脚本生成，含全部文件 SHA256；评价者B 独立复核
    10/10 相符

Evidence layer for each claim:
  - L0（结构/静态）：schema、锚点比对、manifest 哈希、门禁测试存在性
  - L1（Runtime 行为）：三入口正负矩阵全部经正式 API（export/handoff-check/
    final-readiness/service.accept_result）验证；受控适配器 fixture 明确标注
    synthetic/unit（CONTRACTS §12.1），不升级为真实人类证据
  - 本轮不产生 L2–L6 证据（真实 Host/人类审查/用户认可/听众/文件工程）

Failing examples and repair performed:
  - 评价发现的 17 项修复全部落实（adjudication.md §3 对照表），含原型自身
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
  - P6 阅读稿可见解析块：T03 内容写作输入（已登记）
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
│   └── content-anchors.md       ← 三类任务十个正反锚点 + 可判定等级定义（AC-B03）
└── evaluation/
    ├── evaluator-a.md   ← 评价者A完整初判（事实/证据视角，PASS-with-repairs）
    ├── evaluator-b.md   ← 评价者B完整初判（可用性/表达视角，PASS-with-repairs）
    └── adjudication.md  ← 分歧裁决（3 项）与修复对照（17 项）
```

## 与规范的对照说明

- 本轮产物未先新增 Runtime 合同（T00 要求）；Narrative/Plan/Page 等对象以可读文档承载，字段化归 T02。
- Q4 fixtures 是内容级单元 fixture，明确不含伪图片/PPT；工程验收所需的真实 SVG/PPT/回读产物按 TASKS 归 T05/T06/T08，不得用占位文件兜底。
- 固定样例全部为合成材料；不包含、不引用任何真实客户资料。
