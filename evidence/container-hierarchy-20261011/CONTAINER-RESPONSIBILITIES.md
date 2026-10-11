# 正式 UI 容器职责整改

基线：5172626ce899a8e3b82e548075caf7ad3999dba2。范围只包括 DOM 展示职责、CSS 与无障碍标题；业务 API、schema 和持久化规则不变。

## 逐页职责

| 页面/子区 | 布局与分节 | 保留边界及理由 | 主要实现 |
|---|---|---|---|
| 入口、创建、登记恢复 | 项目列表无外卡；表单直接置于唯一弹窗 | 项目条目是独立对象；输入是控件 | launcher-ui.js（既有结构保留） |
| 总览、批量配置、核对、恢复 | 批量操作与恢复为普通分节 | 优先待办强调、矩阵和对象选择边界 | batch-actions.js、overview.css |
| 内容概览、顺序、计划、笔记 | contentPanel 明确为 section；材料编辑、上传、影响采用分隔线 | 材料、页面目标与原文/改文比较仍可区分 | content-edit.js、content-sources.js、workspace.css |
| 画廊阅读、筛选、选择 | 工具区取消装饰外壳 | 作品缩略图、选中态、比较视口 | v2/studio.css、gallery.js |
| 单页六层、五工具面 | 意见、试作、图标、笔记、制作依据明确为 section | 单一工具外壳、图像视口、候选对象 | annotations.js、trial-actions.js、icon-workbench.js、drafts.js、production-view.js、request-view.js |
| 风格两路线四阶段 | 阶段、摘要、左右分栏、展开工具与计划均不再套卡；阶段名称视觉只出现于导航 | 参考图、目标页、规范与候选对象 | style-calibration.js、style-phases.js、workspace.css |
| 任务、决定、版本、文件 | 子区外框、候选集合外框、版本身份卡、用途框转为分节 | 单项候选、固定文件结果、版本选择控件 | run-desk.js、candidate-desk.js、delivery-desk.js、delivery.css |
| 弹窗、备份、冲突 | 共用 modal 一个外壳；嵌入普通分节不继承装饰 | 左右差异比较和独立备份记录有真实对象职责 | dom.js、personal-recovery.js、changeset-desk.js |

`data-container="section"` 在组件创建处声明职责，保留 `.panel` 作为原有选择器兼容点；没有全局取消 `.panel`。未声明为分节的对象卡继续保留边框、圆角、选中态。阶段标题保留语义 h2，视觉隐藏，操作与状态位于独立 div，不再嵌入标题节点。

风格分栏使用容器查询：可用内容宽度低于 840px 才堆叠，不根据整个窗口宽度猜测。目标卡片保留至少 180px 的列宽与 44px 标签区域。

## 验证入口与证据边界

- `tests/rebuild/test_container_hierarchy_browser.py`：五视口、工作面/子区、两风格路线四阶段、六内容层五工具面；检查溢出、分节边界、目标卡与响应式排列，并保存截图。
- `tests/rebuild/test_studio_style_browser.py`：规范、试作、候选采用、扩展的真实本地服务路径，Host 回执明确为合成测试数据。
- `tests/rebuild/test_navigation_usability_browser.py`：顶部 scrollY=0 首屏、画布和保存动作、固定阅读与焦点回归。
- 其它业务保护由现有完整浏览器与非浏览器门禁验证；不能从本文件推定所有视觉状态通过。

证据在工作树 `output/container-hierarchy/`。`baseline-counterexample.log` 在原始源码确认阶段边框反例（1px）；`before-capture-only.log` 为关闭断言的基线截图采集，不是通过的回归验证。首次基线取证缺少方法资源的环境错误单独保留。

原 98 组操作编号继续沿用 `output/playwright/studio-audit-20261011/98-action-status.csv`。本轮没有删动作或修改绑定；最终回归、安装身份与逐项画面裁决须以本轮最终记录为准，不继承上一轮视觉通过结论。
