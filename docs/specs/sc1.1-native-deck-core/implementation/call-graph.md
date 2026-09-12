# SC-1.1 Q0｜调用图（call-graph）：新默认入口 → 实际函数

## 现状（基线 4977f89 实测，file:line）

1. `deck_master.py run_build/build prepare` → `runtime/build.py` → **`_assert_builder_backend_available()`（:137-142）最先执行**：`builder_backend_status()`（外部 PPT Master 绑定检查）+ `backend_render_runtime_ready()`（F-N02：native 路由必须先于外部状态查询；当前不存在 native 路由分支）。
2. `runtime/build.py prepare_build` → page_packages 分支 `_prepare_build_from_packages`（PR-05 新增）→ `build/manifest.py build_manifest_v2`；preview 路径仍为 fixture/dev 输入。
3. HD 链：`deck_master.py --profile high_density` → `high_density/engine.py`（fixture/dev 自动 MBB，:599-628；production 等 agent，:940-1022）→ `high_density/pptx.py:876 compile_pptx` → `:1107 readback_pptx`。
4. `runtime/next_step.py`：`_high_density_artifact`（:104）优先探测 HD 目录；`needs_builder_backend` 写死 ppt-master（:64）；gate 缺项映射（:120-125）render → delivery/customer_visible_safety → **else "render"（缺 semantic_review 时返回 render gate，F-N06 确认）**。
5. CLI：`--library-mode choices=["auto","real","fixture"]`（deck_master.py:3052，无 none，F-N07 确认）；`--ppt-lib-command` 默认 None（评审修复后）。
6. Page Package 状态：schema enum `[draft, blocked, ready_for_build, stale]`（page-package.v1）；`production/page_package.py STATUS_READY="ready_for_build"`；**但 `page_builder.py` 写字面 `"ready"`、`build.py _page_sources_from_packages` 检查 `== "ready"`（F-N08 确认：自洽但偏离 schema）**。
7. `quality/gate_policy.py`：semantic_review 必需门经 `_report_satisfies_gate` 用 `external_*` 前缀匹配（F-N09 确认）；`_semantic_review_input_current` 只比 index 文件哈希。
8. `workflow/actions.py commit_action_result`：先全量校验后逐文件 copy+rename，无跨文件 revision 指针；`check_action_budget` 只数已提交（F-N10 确认）。
9. 安装：`installer.install_managed_backend`（:1420）复制整包后 note 要求 `backend bind`（F-N01 确认）；release 锁/capability lock 不区分 native 内置能力。

## 目标调用图（实施后应成立）

`build prepare/run --profile native` → `build/native_engine.py`（Run adapter：锁/Scene/SVG/资产哈希校验）→ `native_pptx/api.compile_svg_deck/render_pptx/readback_pptx` → artifact/render/readback/gates（无需 builder_backend_status 查询）。旧 HD → `high_density/*` 薄 re-export → 同一 native_pptx 实现。
