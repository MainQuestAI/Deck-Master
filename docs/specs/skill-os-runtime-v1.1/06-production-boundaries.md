# Production Boundary Contracts

## 1. Deck Sourcing

### 输入

- approved Planner Handoff；
- page tasks；
- claim / evidence graph；
- material inventory；
- PPT Library candidates；
- project reference assets。

### 输出

- `sourcing_plan.v2.json`；
- optional candidate review pack；
- source / evidence gaps。

### 禁止

- 写最终页面标题和正文；
- 生成 HTML/PPTX；
- 把低权威来源静默当成已批准证据；
- 未记录权限就复用客户或第三方资产。

## 2. Deck Producer

### 输入

- accepted Sourcing Handoff；
- approved Brief / Narrative / Page Tasks；
- sourcing_plan.v2；
- style / brand / customer-visible policy。

### 输出

- required pages 的 `page_package.v1`；
- page package index；
- generation result v2 / preview refs；
- unresolved page-level blockers。

### 禁止

- 装配整套交付文件；
- 修改已批准 Narrative，而不创建回退 Handoff；
- 把 internal-only 字段混入 customer-visible；
- 以缺少证据的推断冒充事实。

## 3. Deck Builder

### 输入

- accepted Producer Handoff；
- valid Page Packages；
- certified PPT Master Backend；
- output profile。

### 输出

- build manifest v2；
- HTML / PDF / PNG / PPTX；
- artifact manifest；
- render result；
- build warnings。

### 禁止

- 新增业务主张；
- 改写页面观点；
- 读取 internal-only 字段进入客户文件；
- production 直接消费旧 preview manifest；
- backend 不可用时降级成 contract-smoke 并宣称完成。

## 4. Deck Quality

### 输入

- completed Builder Handoff；
- final artifact bundle；
- page packages / claims / evidence；
- customer visible policy。

### 输出

- artifact validation；
- customer-visible safety；
- evidence / brand / confidentiality / render / delivery findings；
- repair owner stage。

### 禁止

- 代表用户批准风险；
- 修改最终 Artifact；
- 把质量 pass 直接转换为 client export approval。

## 5. Deck Review

### 输入

- Quality Handoff；
- final artifacts；
- findings；
- page decisions；
- final readiness facts。

### 输出

- review decision；
- repair handoff 或 final approval；
- export queue；
- delivery record。

### 禁止

- 未绑定 Artifact hash 的批准；
- 未解决 P0 时导出；
- 用 Preview Approval 替代 Final Artifact Approval。

## 6. 外部能力 Adapter

### PPT Library

现有 selection 输出可由 Deck Master Adapter 归一化为 Sourcing Plan v2。第一阶段不要求 PPT Library 内核改造。

### PPT Deck Pro Max

必须能够输出或引用 Page Package。过渡期可通过 Generation Result v2 中的 `page_package_ref` 接入。

### PPT Master

必须声明对 Build Manifest v2 的兼容或由 Deck Builder Adapter 转换。完整 Backend 的 capability manifest 必须声明 supported contract versions。

### PPT Quality Gate

Findings 必须带 repair owner stage 或由 Deck Master Adapter 归一化。
