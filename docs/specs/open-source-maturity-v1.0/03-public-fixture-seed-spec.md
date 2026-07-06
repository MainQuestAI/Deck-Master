# 03 — Public Fixture Seed Spec

## 1. 目标

准备一个可公开、可复现、可截图的 10-12 页 fixture demo run，支撑 README、Quick Start、Review Desk 截图和 M1 preview-gate。

## 2. 数据边界

允许：

1. 公开行业示例。
2. 合成公司名和合成业务背景。
3. repo 相对路径。
4. fixture 标识。

禁止：

1. 作者本机绝对路径。
2. 客户真实名称、真实业务数据、售前底稿。
3. placeholder 文案。
4. 内部 agent 调度痕迹。
5. 需要私有后端才能理解的字段。

## 3. 推荐 demo 主题

建议继续使用公开、低敏的零售数字化转型 brief：

```text
examples/briefs/retail_digital_transformation.txt
```

输出目标：

1. 10-12 页。
2. 至少包含封面、问题诊断、方案架构、实施路线、价值证明、风险控制、下一步。
3. 每页有可审查状态。
4. Review Desk 能完成一页审批。

## 4. 必须修改或新增

| 路径 | 要求 |
|---|---|
| `examples/briefs/` | 公开 brief，无敏感信息 |
| `examples/preview-run/` | 可复现 demo run 或生成说明 |
| `docs/quick-start.md` | 指向公开 demo |
| `README.md` | 指向公开 demo 和截图 |

## 5. 验证

```bash
rg -n "/Users/|/home/|placeholder|客户|售前|internal|agent" examples/preview-run examples/briefs README.md docs/quick-start.md
python scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --run-mode fixture --dev-allow-unsetup --runs-dir /tmp/deck-master-demo --run-id oss-demo
```

## 6. 成功标准

1. fixture demo 能稳定生成 10+ 页。
2. 示例 manifest 不含绝对路径。
3. Review Desk 能打开该 run。
4. 截图可直接用于 README 或 release note。
