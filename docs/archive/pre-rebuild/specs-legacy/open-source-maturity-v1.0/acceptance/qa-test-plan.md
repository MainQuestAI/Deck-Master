# QA Test Plan

## 1. M1 命令集

```bash
python -m pip install -e ".[dev]"
deck-master --help
python -m unittest discover -s tests
python -m pytest tests/test_skill_manifest.py tests/test_stage_contract_registry.py tests/test_workflow_state.py tests/test_stage_validation.py tests/test_skill_handoff.py tests/test_workflow_approval.py tests/test_workflow_questions.py tests/test_sourcing_plan_v2.py tests/test_page_package.py tests/test_build_manifest_v2.py tests/test_workflow_autopilot_v2.py tests/test_workflow_cli.py tests/test_skill_doc_contract.py tests/test_skill_os_migration.py tests/test_skill_os_release_contract.py -q
python scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --run-mode fixture --dev-allow-unsetup --runs-dir /tmp/deck-master-demo --run-id oss-demo
python scripts/deck_master.py preview-gate --run-dir /tmp/deck-master-demo/oss-demo --expect-unconfigured-backend-ok
```

## 2. M1 静态扫描

```bash
git ls-files .gstack
rg -n "Users/|home/|/private|placeholder|真实客户|客户名称|售前|internal agent|agent_dispatch" README.md docs/quick-start.md docs/known-limitations.md examples/briefs examples/preview-run
rg -n "glass-panel|backdrop-filter|方案项目工作台|border-radius:\\s*(1[2-9]|[2-9][0-9])px" scripts/preview/static
```

## 3. 后端负向测试

必须覆盖：

1. 无 backend 配置。
2. backend 配置路径不存在。
3. backend 配置存在但缺 manifest。
4. generation bridge 未配置。
5. production 命令在未配置 backend 时阻断。

## 4. M2 命令集

```bash
python scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc --benchmark-dir benchmarks --skip-browser-smoke --force
python scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc-browser --benchmark-dir benchmarks --require-browser-smoke --force
```

## 5. QA 报告要求

QA 报告必须包含：

1. 日期。
2. git SHA。
3. 环境信息。
4. 命令输出摘要。
5. 失败项与复现步骤。
6. M1/M2 Go 建议。
