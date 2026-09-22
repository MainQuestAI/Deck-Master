# 验收记录

## 场景与证据

| 编号 | 场景 | 验证入口 | 结果 |
| --- | --- | --- | --- |
| AST-01 | 新建、局部修改、诊断、客户交付、软件发布正确路由 | `test_astra_task_routing.py::test_task_route_with_incomplete_run_preserves_intent` | 6 组真实 CLI 调用通过，run 文件不变 |
| AST-02 | 局部修改沿用高密度 profile、保留设计和其他页面 | `test_astra_task_routing.py::test_selected_page_retry_preserves_style_storyline_and_other_page` | 两页 PPTX 实际生成并重建；P001 SVG 恢复，P002 package/scene/SVG、style lock 和 storyline receipt 字节一致 |
| AST-03 | 项目内发现、项目外隔离、18 个真实链接 | `test_project_skill_installation.py::test_project_install_discovery_isolation_and_uninstall` | 通过；嵌套目录可发现，项目外未安装，显式 project-root 可检查 |
| AST-04 | 中央升级与回退后链接仍有效 | `test_project_skill_installation.py::test_project_links_survive_central_activation_and_rollback` | 真实 release tree 校验/激活/回退通过；测试解释器复用于隔离 smoke |
| AST-05 | 全局兼容和外来文件保护 | `test_project_skill_installation.py::test_explicit_global_scope_and_foreign_link_preservation` 及既有安装套件 | 通过；显式 global 不受项目 CWD 影响，外来链接保留并报告 |
| AST-06 | 独立生产版 PPT Master 不被覆盖 | 项目 install/uninstall 与既有 full-package preservation 测试 | 通过；项目不创建同名入口，卸载保留真实目录 |
| AST-07 | Skill 结构、实际参数和引用兼容 | `test_skill_doc_contract.py`、通用 `quick_validate.py` | 19 个入口通用校验通过；仓库契约测试通过 |
| AST-08 | 当前候选 release 构建与 smoke | `release-build`、`release-smoke --release-root <isolated>` | 2026-09-07 通过：19 个 skill 自包含打包，临时 Python 3.12.12 环境，5 项 smoke 命令全部返回 0，无 errors/warnings |

## 合并前检查（2026-09-07）

- 下方主回归命令：156 passed、13 subtests passed；全程使用隔离 HOME。
- 补充 stage contract registry、Skill OS migration、release contract：24 passed。
- 仓库全量 `ruff check scripts tests`、改动 Python 文件编译、`git diff --check` 通过。
- 隔离 release smoke 覆盖 help、suite-status、workflow status、next-step、CI 级
  rc-gate；临时目录完成后删除，没有激活本机 release 或恢复全局入口。
- 基线与当前 `origin/main` 均为 `1864a0e`，无分叉；本地检查未发现合并阻断。
  本轮仅提交分支，不合并 main。远端 CI 和模型自动选择行为不计为已验证。

## 验证层级

- 静态验证：frontmatter、manifest/契约、实际 CLI 参数、ruff、py_compile、diff 检查。
- 真实执行：隔离目录实际软链接、release 激活/回退、CLI 路由和两页 PPTX 渲染重建。
- 行为验证：局部页源和既有决策保持、项目发现边界、只读路由与校验、所有权保护。
- 未验证：模型面对自然语言时的自动 skill 选择准确率，Codex 新任务在真实全局
  切换后的发现行为，真实客户素材与 Provider 端到端交付。本轮不以文字匹配测试
  替代这些结果。

## 回归命令

```bash
.venv/bin/python -B -m pytest tests/test_skill_doc_contract.py tests/test_skill_manifest.py tests/test_skill_route.py tests/test_project_skill_installation.py tests/test_skill_installation.py tests/test_setup_install_suite_regression_001.py tests/test_setup_enforcement.py tests/test_release_runtime.py tests/test_workflow_cli.py tests/test_astra_task_routing.py -q -p no:cacheprovider
.venv/bin/python -B -m ruff check scripts/skills/installer.py scripts/skills/validator.py scripts/runtime/skill_route.py scripts/deck_master.py tests/test_project_skill_installation.py tests/test_astra_task_routing.py tests/test_skill_doc_contract.py
git diff --check
```

## 迁移待办

- 2026-09-07：用户已移除本机中央 suite、全局 Deck/PPT 入口及两个工作坊目录。
  本分支不恢复它们；安装与回退测试仅使用隔离临时目录，不依赖原本机安装。
- 实际项目安装与 Codex 新任务发现验证暂不执行，需用户另行授权恢复安装。
- 独立生产版 PPT Master 的说明精简和内部依赖治理不属于本分支。
- 客户交付仍依据当前 run 的最终产物质量和交付授权。
