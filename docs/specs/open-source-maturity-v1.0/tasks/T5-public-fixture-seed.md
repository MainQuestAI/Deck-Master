# T5 — Public Fixture Seed

## 1. 目标

生成或固化 10-12 页公开 fixture demo run。

## 2. In Scope

1. `examples/briefs/`
2. `examples/preview-run/`
3. `docs/quick-start.md`
4. README demo 截图说明

## 3. 必须实现

1. 公开 brief。
2. 可复现 demo run。
3. 无 placeholder。
4. 无作者本机绝对路径。
5. 无客户敏感信息。

## 4. 验证

```bash
rg -n "/Users/|/home/|placeholder|客户|售前|internal|agent" examples/briefs examples/preview-run README.md docs/quick-start.md
python scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --run-mode fixture --dev-allow-unsetup --runs-dir /tmp/deck-master-demo --run-id oss-demo
```

## 5. 成功标准

Review Desk 能打开该 run，且可完成一页审批。
