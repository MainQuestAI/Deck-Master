# T2 — Packaging And CI

## 1. 目标

新增标准 Python 包装入口，让外部用户和 CI 都使用同一套安装命令。

## 2. In Scope

1. `pyproject.toml`
2. `.github/workflows/ci.yml`
3. `requirements.txt` 的兼容说明
4. console script：`deck-master`

## 3. 必须实现

1. `[build-system]`
2. project metadata
3. Apache-2.0 license metadata
4. `dev` extra：`pytest`、`jsonschema`、`playwright`、`coverage`
5. CI 使用 `python -m pip install -e ".[dev]"`

## 4. 验证

```bash
python -m pip install -e ".[dev]"
deck-master --help
python -m unittest discover -s tests
```

## 5. 成功标准

外部用户不需要手工猜测试依赖，CI 和 README 的安装方式一致。
