# B5 — Fixture Isolation & Regression

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `B5` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | A3, B1-B4 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

彻底隔离 fixture/dev 与 production，防止测试能力进入正式交付。

## 3. In Scope

- fixture adapter relocation。
- runtime guards。
- test markers。
- CI scans。
- production E2E failure tests。

## 4. Out of Scope

不删除 fixture 能力。

## 5. 必须实现

1. Fake generator 移至 tests/fixtures。
2. Production import fixture source P0。
3. `--allow-fixture-*` 在 production 无效。
4. CI 扫描 production runtime 中 placeholder token。
5. 示例路径显式 run_mode=fixture。
6. Regression test 覆盖 legacy commands。

## 6. 允许 / 预期修改路径

- `tests/fixtures/`
- `examples/`
- `scripts/capabilities/`
- `.github/workflows/ci.yml`
- `tests/test_fixture_boundaries.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- source scan。
- production fake execution。
- fixture allowed。
- dev explicit allowed。
- benchmark real case forbidden。
- legacy regression。

## 8. 成功标准

- Production 路径 0 placeholder。
- CI 自动阻止回归。

## 9. 风险

字符串扫描可能误报文档，需要限定 runtime paths。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
