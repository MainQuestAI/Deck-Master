# 方案项目工作台状态与数据契约 Spec

日期：2026-06-21  
状态：v0.2  
适用范围：Deck Master localhost Web UI 聚合接口

## 1. 目标

前端主渲染只依赖单一工作台聚合接口，页面级处理和交付预览走补充接口。

## 2. 接口清单

### 2.1 项目工作台聚合接口

`GET /api/workspace/:run_id`

返回：

- 项目基础信息
- 当前阶段
- 页面队列
- 焦点页
- 项目级健康状态
- 风险摘要
- 审批摘要
- 交付预览摘要

### 2.2 页面处理接口

`GET /api/workspace/:run_id/page/:page_id`

返回：

- 页面 hero 信息
- 页面定位
- 来源说明
- 依据列表
- 风险列表
- 审批记录
- 备注

### 2.3 项目活动流

`GET /api/workspace/:run_id/activity`

### 2.4 项目动作接口

`POST /api/workspace/:run_id/actions`

支持：

- `submit_approval`
- `approve_approval`
- `reject_approval`
- `mark_delivered`

### 2.5 页面动作接口

`POST /api/workspace/:run_id/page/:page_id/actions`

支持：

- `approve`
- `reject`
- `request_evidence`
- `submit_approval`
- `add_note`

### 2.6 交付预览接口

`GET /api/workspace/:run_id/delivery-preview`

返回：

- `render_status`
- `render_result_path`
- `artifact_path`
- `artifact_ready`
- `artifact_url`
- `created_at`
- `delivered`
- `delivered_at`

## 3. 前端核心对象

- `WorkspaceSummary`
- `WorkflowStage`
- `PageQueueItem`
- `PageInspector`
- `EvidenceItem`
- `QualityRisk`
- `ApprovalTask`
- `DeliveryPreview`
- `ActivityEvent`

## 4. 阶段映射

内部运行状态允许保留在后端，前端只接受翻译后的阶段：

- `待准备`
- `生成中`
- `待审阅`
- `待补依据`
- `待审批`
- `可交付`
- `已交付`
- `风险冻结`

## 5. 交付预览契约

交付预览以 PPT Master 产物为唯一标准来源：

- `render_results/render_result.json`
- `rendered/index.html`

前端依据 `artifact_ready` 决定显示：

1. 交付级 iframe 预览
2. 缺失提示
3. 建议动作

## 6. 失败态契约

以下情况必须可区分：

1. `render_result.json` 缺失
2. `artifact_path` 缺失
3. `index.html` 缺失
4. 项目存在但未形成页面
5. 页面存在但无预览
