# PR127 完成后的实施接手

## 当前状态

本规格包已编制；产品实现尚未开始。PR127 本次观测仍为 Draft，实施基线尚未冻结。不要把 `02627c17` 自动当作最终版本，也不要从较旧主工作区直接开始改代码。

## 读取顺序

1. 当前 checkout 的 `AGENTS.md`、`docs/agent-task-index.md`、`docs/agent-recovery-playbook.md`。
2. 本目录 [BASELINE](BASELINE.md)、[SPEC](SPEC.md)。
3. `DESIGN.md` 及其指定现行产品语言。
4. 本目录 [UI-SPEC](UI-SPEC.md)、[API-SPEC](API-SPEC.md)。
5. [TASKS](TASKS.md)、[ACCEPTANCE](ACCEPTANCE.md)、[traceability.json](traceability.json)。
6. PR127 最终源码中的活动合同、资源清单和工程/内容回执。原资源 ZIP 不再是需要重新下载的前提。

## 第一个动作：WU00

只读核对 PR127 最终 head、完成状态、required checks、包证据及变更范围，填写 BASELINE 中的执行账本。若 PR 仍在实现，报告具体未完成项并保留本计划，不自动启动产品修改。

如果 final head 与 Spec 的观察版本不同，重点复核：

- selected_resource_ids 的最终 CLI/HTTP/service 参数及冻结规则。
- 资源 catalog、默认指南、旧 Task 兼容和 writer floor。
- Narrative/Review/Page/content_requirements 的实际字段。
- direction 决定、proposal-adoptions 的 payload、回执和 adapter evidence。
- Studio 是否已经有同等 UI；有则整合，避免重复入口。

核对完成后，从最终适用基线创建独立 `codex/` 分支。当前文档所在主工作区存在其他未提交内容，迁移时只携带本规格包及本事项 context，不带入无关文件。

## 执行

按 WU00→WU08 接续。增量 A 先完成 WU01–WU05；增量 B 完成 WU06–WU07；WU08 统一安装与运行验收。

每卡只在执行账本记录实际结果，不直接把计划内的 NOT_RUN 批量改 PASS。如要以多个 PR 交付，描述中明确本 PR 覆盖哪几卡、剩余哪些卡；只有整轮 AC 覆盖齐全才能称本轮工程完成。

本轮网页高级方法选择是“准备与交接”，不是新的生产派发入口；不得借实现 UI 增加自动模型调用、脚本执行或旧任务补卡。

## 验证命令入口

以下为文档检查入口，不是产品测试：

```bash
python3 docs/specs/deck-master-webui-content-methods-20261020/tools/validate_spec.py
```

产品测试在实际实施分支选择：先运行各卡新行为与受影响现有测试，再用真实浏览器和最终隔离安装检查。实际 Host 调用使用项目现有任务/授权协议；用户专业认可单列。

最终交付至少包括：

- 变更与卡片完成表、准确源码 SHA。
- 50 项 AC 的实际结果及证据。
- 浏览器主路径与三视口记录。
- 最终包的构建/安装/资源身份记录。
- 实际 Host、专业阅读、人类体验的独立状态。
- 未解决限制、回退办法及下一项需要用户判断的事项。

## 可直接复制的接续请求

> 请先读取 `docs/specs/deck-master-webui-content-methods-20261020/README.md` 和 `HANDOFF.md`，完成 WU00：核对 PR127 是否已完成、最终 head 与集成基线，再复核 Spec 的接口差异。门槛满足后，在独立分支按 WU01–WU08 实施这轮 Web UI；保留现有五工作面、不可变历史和范围约束。每卡完成相称检查，最后按 50 项 AC 输出工程、浏览器、安装、实际 Host 与人类验收的分层结果。不要自动合并 PR127、发布或激活真实 HOME。

以上文字是未来接续模板，不是本轮已发送给其他会话的消息。
