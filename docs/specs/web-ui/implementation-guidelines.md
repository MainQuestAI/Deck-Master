# Deck Master Review Desk Implementation Guidelines

日期：2026-06-23  
适用范围：`scripts/preview/static/`、`scripts/preview/server.py`

## 1. 入口边界

- `webui-redesign-v2` 是本轮 UI 主线来源。
- `webui-redesign` 和 `elegant-fermi-4ed023` 视为已被覆盖的历史中间线，不再单独合入。
- UI 改动只移植 `index.html`、`style.css`、`app.js` 及它们落地必需的接口行为。

## 2. 结构锁定

- 顶部必须是状态带，承接阶段、下一步、阻断、导出与项目切换。
- 左中右三栏必须分别服务：任务目录 / 当前页舞台 / 当前处理决策。
- 底部抽屉承接 run 级信息，避免把首屏再次塞满 run 级卡片。
- 右侧动作区收敛为单一主动作主导，次动作围绕返修和审批展开。

## 3. 契约守则

- 运行时真源仍在当前 `main` 的 workspace API 和 preview server。
- UI 只能消费现有契约，必要时只补兼容行为，不能推翻：
  - `final_readiness`
  - `customer_visible_safety`
  - `deck-builder`
  - setup readiness
- planned run / no-preview shell 的接口必须返回安全 payload：
  - 不白屏
  - 不返回绝对路径
  - 不把缺 `preview_manifest.json` 直接暴露成内部报错

## 4. 文案守则

- 用户读到的语言优先是阶段、阻断、返修、交付语义。
- `Render / PPT Master` 在用户侧统一表达为 `Build / Deck Builder`。
- 没有真实双语前，语言切换只保留禁用态提示。

## 5. 不带入主线的内容

- `.gstack/qa-reports`
- 截图集和视觉基线
- 临时设计素材
- 根目录 `AGENTS.md` 和 `DESIGN.md`
- 未完成的真实 i18n 实现

## 6. 验证要求

- UI 改动至少覆盖：
  - `tests/test_preview_static_contract.py`
  - `tests/test_review_cockpit.py`
  - `tests/test_preview_server.py`
- 验收重点：
  - 首屏进入当前页审查台
  - planned run / no-preview shell 不白屏
  - delivery preview 可进入
  - P0 / P1 阻断、审批、导出状态文案与主线契约一致
