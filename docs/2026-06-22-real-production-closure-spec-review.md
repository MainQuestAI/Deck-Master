# Deck Master Real Production Closure Spec 审查结论

## 1. 结论

这份 `deck-master-real-production-closure-spec-pack` 可以进入仓库，作为 `v0.9.14 → v0.9.16` 下一轮开发的**规划基线**使用。

我已核对当前主线基线：

- `Deck-Master` 当前 `main` HEAD 为 `14fc43dc6e955928100f02f0e82af5b833c29177`
- 与本包声明基线一致

因此，这份包的业务目标、阶段拆分和验收方向可以成立，适合作为下一轮开发总纲。

## 2. 使用边界

这份包当前适合承担三件事：

1. 作为下一轮开发的目标定义。
2. 作为 Stack A / B / C 的任务拆分依据。
3. 作为后续 `implementation spec` 的上游规划输入。

进入实际开发时，分支内的实现事实仍应以下列目录为准：

```text
docs/specs/real-production-closure/implementation/
```

当规划包与实现事实出现差异时，应在分支内写 `spec-deviation-log.md`，并以实现文档为评审基线。

## 3. 开发前必须先对齐的 3 项

### 3.1 CLI 名称先冻结

包内若干命令名与当前仓库入口还未完全一致，A0 必须先收口成一张映射表，再进入功能开发。

当前包里提到但现仓库尚未形成统一入口的一组名称包括：

- `contract-validate`
- `release-build`
- `release-smoke`
- `final-readiness`
- `build prepare/run/status`
- `artifact-status`

当前仓库已经存在并可复用的一组相关入口包括：

- `suite-build-release-tree`
- `render`
- `render-status`
- `validate-generation-result`
- `validate-render-result`
- `generation-session create/status/import-results`
- `benchmark-rc-report`

建议：A0 先明确“保留旧名并扩展”还是“新增目标命令并保留兼容别名”，然后一次性冻结。

### 3.2 状态语义先冻结

规划包中已经引入新的状态表达，例如：

- `awaiting_agent_execution`
- `needs_generation_execution`
- `needs_build`

当前仓库已有的运行态主线仍以这些状态为主：

- `needs_generation_session`
- `generation_running`
- `needs_generation_import`
- `needs_preview_refresh`
- `needs_render`
- `needs_draft_gate`

建议：A0 先产出一张状态迁移表，明确：

- 旧状态是否保留
- 新状态是否替换
- `run-state`、`next-step`、工作台 UI 如何保持同口径

### 3.3 模块落点先冻结

规划包中有几处目标路径还带有“未来实现位”的色彩，若直接照写，容易形成平行目录。

需要先对齐的重点有：

- `scripts/validation/*` 与当前 `scripts/validators/*`
- `scripts/runtime/build.py` 与当前 `scripts/runtime/render.py`
- `product_capabilities/ppt-master/runtime/` 与当前 `product_capabilities/ppt-master/contracts/`
- 新 schema 放在 `docs/contracts/`、`skills/deck-master/schemas/`、`product_capabilities/*/contracts/` 的职责边界

建议：A0 只做一次 canonical source 决策，避免同一 contract 出现多份真源。

## 4. 审查判断

### 可以直接接受

- 这轮业务目标收得准：真实产物、状态可信、可发行、可证明。
- Stack A / B / C 的顺序合理。
- `placeholder` 清零、artifact truth、single final readiness、release tree、real benchmark 这五个目标都成立。
- 真实 benchmark 和 RC checklist 的方向正确，适合做版本门槛。

### 需要在 A0 处理

- CLI 命名统一。
- 状态机统一。
- contract 与模块路径统一。

这些项当前属于“开发前置对齐项”，还不构成对整体方向的否定。

## 5. 建议的下一步

下一步建议直接进入 **A0：Baseline & Contract Freeze**，先交付：

1. `baseline-lock.json`
2. `implementation-spec.md`
3. `implementation-spec.json`
4. `spec-deviation-log.md`
5. CLI 名称映射表
6. 状态迁移表
7. contract 真源目录决策

在 A0 完成前，不建议直接进入 A1/A4/B1 代码实现。
