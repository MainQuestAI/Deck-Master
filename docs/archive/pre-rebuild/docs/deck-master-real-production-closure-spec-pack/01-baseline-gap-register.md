# Baseline & Gap Register

## 1. 基线

### 已确认基线

- Deck Master：`origin/main @ 14fc43dc6e955928100f02f0e82af5b833c29177`
- 当前 suite version：`0.9.13`
- Required capabilities：
  - deck-master
  - deck-planner
  - deck-review
  - ppt-master
  - ppt-library
  - ppt-deck-pro-max
  - ppt-quality-gate
- 当前 Provider policy：`zero_builtin_llm_provider`
- 当前 CI：compileall、全量 unittest、fixture autoplan smoke
- 当前工作台：方案项目工作台，支持页面、风险、审批、交付状态。

### 关联仓库基线

- PPT Deck Pro Max：当前公开主线已包含 Expert Mode、Visual Composition、Asset Pipeline 和 image-led HTML assemble 能力。
- PPT Library：当前公开主线为本地优先 PPTX 资产库 CLI，支持页级搜索、版本治理、关键页、复用追踪和 compose。
- 具体开发起点 SHA 必须由 Codex 在任务 A0 中重新核验并写入 capability lock。

---

## 2. 当前成熟能力

| 区域 | 当前事实 |
|---|---|
| Run OS | request、context、brief、claim、narrative、page task、sourcing、generation、review、quality、render、export 已有状态骨架 |
| Suite | 可构建 release tree、安装 required skill、检查 readiness、迁移 legacy skill |
| Generation Session | 有 run_id/session_id 绑定、result import、preview refresh |
| Quality | Draft、Evidence、Brand、Confidentiality、Render、Delivery 等 Gate 已有 |
| Review Workspace | 页面动作、来源、风险、审批、交付预览和截图审计已有 |
| Benchmark | case、runner、report、RC report 机制已有 |
| CI | 单测和 fixture smoke 已有 |

---

## 3. P0 Gap

### G-P0-01：Production Generator 仍可伪造完成

当前 bundled adapter 会把普通文本写入 `.pptx` 和 `.png` 文件，然后输出 completed result。

**影响**：

- 业务完成态不可信；
- artifact extension 与真实格式不一致；
- 后续 Gate 可能被伪产物穿透。

**本轮处理**：A2、A3、B1、B5。

### G-P0-02：PPT Master 仅有 fixture-safe HTML

当前 render 只能输出简单 HTML，不能代表真实客户交付。

**本轮处理**：A4。

### G-P0-03：Delivery Parse Failure 未强阻断

当前交付验证在 PPTX 解析异常时可能继续，不一定产生 P0。

**本轮处理**：B1、B2。

### G-P0-04：Release Tree 仍依赖 Git Checkout

当前安装脚本生成的 launcher 指向原始仓库脚本。

**本轮处理**：C1、C2。

### G-P0-05：没有单一 Final Readiness

Run state、Review readiness、Export、Delivery 和 Benchmark 存在不同判断口径。

**本轮处理**：B3、B4。

---

## 4. P1 Gap

| Gap | 影响 | 任务 |
|---|---|---|
| Generation result 缺 checksum / source fingerprint | 无法判断伪造和过期 | A1、B1 |
| Build 和 Render 边界不清 | 产物状态混乱 | A4 |
| PPTX editability 未声明 | 用户预期失真 | A4、B2 |
| Production / fixture 边界不够硬 | 演示能力可能混入交付 | A3、B5 |
| Cross-repo 版本未锁 | 同一 release 不可复现 | A0、C1 |
| PPT Deck Pro Max handback 非 canonical | 需要人工拼接 | A2 |
| PPT Library 真实检索 readiness 与 suite readiness 可能分离 | Source 决策质量不可控 | A5、B3 |
| 真实 benchmark 缺失 | 无法证明业务成熟 | C3 |
| 浏览器动作 smoke 不完整 | UI 回归风险 | B4、C4 |

---

## 5. 不在本轮解决的 Gap

- Planner 仍有 generic template 骨架；
- Team / Enterprise 只是本地合同原型；
- Native editable PPTX 质量可能仍依赖外部 build adapter；
- 复杂 PDF、飞书和 OpenViking ingestion 仍可通过外部流程；
- PPT Library 模型、OCR 和 embedding 的效果不由 Deck Master 本轮重写。

---

## 6. 开发前必须核验

以下内容必须由 Codex 在 A0 中核验：

1. Deck Master 当前全量测试数和结果。
2. `origin/main` 是否仍为 14fc43d。
3. PPT Deck Pro Max 当前 main SHA。
4. PPT Library 当前 main SHA。
5. 当前本机 suite status。
6. 当前 installed skill symlink / real directory 冲突。
7. Playwright、LibreOffice、python-pptx / PptxGenJS 可用性。
8. 真实 benchmark 项目的可用范围和脱敏规则。

核验结果写入：

```text
docs/specs/real-production-closure/implementation/baseline-lock.json
```
