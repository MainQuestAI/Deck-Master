# 外部 PR 评审(Request Changes)修复记录 2026-09-23

基线:PR #32(codex/rebuild-mainline-v1)HEAD 1280dd5 收到外部 Request Changes 评审,8 组 P1 + 3 条附加全部经主代理实证确认(探针/代码/CI 日志)。按 A→B→C→D 四轮修复,全绿后提交。

## 轮 A:统一失败与出口判断(P1-01/02/07)

- P1-01:evaluate_current 消费硬事实(`_output_facts`):render_report fail→fail;缺 report/页槽缺口→not_evaluated;review 导出不受影响;delivery/UI/continue 同一解释。
- P1-02:finding 级延续——同维度全部当前 review 的 open must_fix 按 finding_id 聚合,仅合规 closing review 逐条关闭;无 replaces 的新 pass 不清旧问题;实质门槛:content/blueprint_content/blueprint_fidelity 的 pass 要求非 tool reviewer,全部 kind 的 pass 要求 observations 非空,违反记 not_evaluated 带机读原因。
- P1-07:依赖解析统一:source 按 document sources 解析;artifact/style 缺失即 stale(删除"已知前缀放行");policy 对文档规范字节;无法解析的保守 stale。

## 轮 B:接收与原图边界(P1-03/04 + 附加×3)

- P1-03:operation_id 绑定 task;journal 前校验;completed 仅幂等重放;artifact_specs 按 scope_pages + kind 角色白名单。
- P1-04:reference_regions 保存进永久 Artifact;blueprint derived_from 禁止指向预览/派生类 artifact(自我回灌拒绝)。
- 附加:repair_no_progress 改比"修复候选对象内容 sha"(SVG 修复是真实进展);evidence_level 仅认带签名回执,invocation_ref 不再自动升级;usage_events 先结算后采用(内容拒收调用事实仍保留)。

## 轮 C:成品检查与设计依赖(P1-05/06)

- P1-05:readback 必要 atom 级可读性(unreadable_text 定位 atom+字号);edge 双端校验(reversed_arrow/edge_not_connected,8px 容差);装饰 run 不误报。
- P1-06:style_font_fingerprint——字体解析后实际文件 artifact sha 进入 _rendering_state 与 review 依赖 digest;同 font_id 换字体文件正确失效相关页、旧 pass 转 stale。

## 轮 D:CI 与声明(P1-08)

- 支持口径放宽 >=3.11,<3.14(pyproject/README/AGENTS/doctor/CI 五处一致);修复 3.11 f-string 不兼容;`render` pytest marker 分组(unit 381/render 12);硬编码 .venv 路径清零;字体走 hostenv 候选链;setuptools 预置与 build_meta 子进程化。
- 3.11 与 3.12 双解释器全量各 393 passed;ruff 全过。

## 受影响卡片

T07(区域保存/回灌)、T11(R02/R10/C05)、T12(S03 边界/无进展守卫)、T15(R09 出口)、T10(K10/K08 readback 语义)按新语义重验,关闭依然成立且更严格。测试 368 → 393。
