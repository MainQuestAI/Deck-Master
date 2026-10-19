# 05 验收、证据与完成标准

## 1. 验收对象

本包包含 **70 条增量 AC**。具体 Given/When/Then 只在六张任务卡维护；本文件规定汇总、环境、跨卡验证和关闭方式。以下全部是待执行开发要求，不是当前通过记录。

| Owner | 唯一判据文件 | AC 区间 | 数量 |
|---|---|---|---:|
| N1 | [N1-operation-recovery.md](task-cards/N1-operation-recovery.md) | AC-N1-01 ～ AC-N1-12 | 12 |
| N2 | [N2-install-recovery.md](task-cards/N2-install-recovery.md) | AC-N2-01 ～ AC-N2-12 | 12 |
| N3 | [N3-content-review.md](task-cards/N3-content-review.md) | AC-N3-01 ～ AC-N3-12 | 12 |
| N4 | [N4-context-and-history.md](task-cards/N4-context-and-history.md) | AC-N4-01 ～ AC-N4-14 | 14 |
| N5 | [N5-docs-and-release.md](task-cards/N5-docs-and-release.md) | AC-N5-01 ～ AC-N5-10 | 10 |
| N6 | [N6-quality-improvement.md](task-cards/N6-quality-improvement.md) | AC-N6-01 ～ AC-N6-10 | 10 |

traceability.json 必须与上述卡片逐项对应；每条只有一个最终 Owner。一个测试或正常任务可以为多个 AC 提供证据，每个 Owner 对自己的判据负责；不能把共用证据拆成多次重复实验。

## 2. 唯一状态台账

从 [execution-ledger.json](templates/execution-ledger.json) 复制一份作为具体候选的执行记录，建议置于仓库本轮 report 目录。不要在原模板中填具体 PASS 后继续分发为模板。

| 状态 | 使用条件 |
|---|---|
| NOT_RUN | 尚未执行该候选所需验证；模板初始状态 |
| PASS | 适用判据已被当前实现或可证明仍适用的证据满足，包含准确 SHA/环境/对象 |
| FAIL | 实际执行结果不符合判据；保留失败与后续修复链 |
| BLOCKED | 有真实缺失能力/材料/访问等，无法完成所需验证；说明已完成部分和可执行下一步 |
| NOT_APPLICABLE | 该具体情形在本次范围确实不适用，必须有具体范围依据；缺工具、赶时间或未执行不构成不适用 |

N1/N2/N3 核心修复、N4协议与可信查询、N5活动入口、N6实质方法变更和实际应用是本轮承诺，不能整卡用 NOT_APPLICABLE 代替。例如 content_only 没有视觉改动，可以在 N6-07 记录视觉分支不适用，但仍要完成内容产物及其检查。

模板没有实际候选 SHA/输出/证据，所以不能出现 PASS。Spec 本身通过结构校验不改变其中任何产品 AC 状态。

## 3. 证据必须说明什么

每条证据至少记录：准确代码 SHA/tree、环境、命令或实际动作、输入/产物身份、观察结果、范围和限制。当前候选的方法、Task manifest、安装资源与所用模型/工具身份按真实可观察信息记录；未知项留 unknown，不推断。

| 本包证据标识 | 可证明内容 | 不可替代 |
|---|---|---|
| STATIC_REVIEW | 某 SHA 的结构、调用关系和合同定义 | 实际运行结果 |
| SYNTHETIC_ENGINEERING | 合成项目中的事务、恢复、结构、入口和计数正确性 | 正常模型应用或客户效果 |
| INSTALLED_RUNTIME | 真正构建/隔离安装后的入口、资源和恢复行为 | 用户本机已经激活 |
| NORMAL_TASK | 实际 Host 在完整任务中应用方法、形成稿件及修订 | 人类认可或普遍因果提升 |
| ARTIFACT_CHECK | 当前约定成果/实际 SVG/PPT/notes 的检查 | 未执行的桌面编辑/真人使用 |
| HUMAN_FEEDBACK | 实际获得的用户或专业人员反馈 | 不存在的默认必需门槛 |

这些标识仅用于本包离线记录，不重定义已有 L0–L6、F0–F3 或专业 AC/CQ。未执行人类检查不填写伪造身份，不因其缺席阻止普通任务。

证据能引用原对象即可，不复制大型原件进入 Git。公开/中性材料标明性质；私有客户材料继续使用项目已有私有保管方式，仓库只保留允许的索引。路径和 hash 可验证性需要由执行 Codex 核验。

## 4. 测试层次和执行命令

### 4.1 聚焦开发验证

执行者先根据卡中入口和当前文件验证测试名。示例：

```bash
rg --files tests/rebuild
python -m pytest --collect-only -q tests/rebuild/test_package_boundary.py
python -m pytest -q tests/rebuild/test_package_boundary.py
```

其他卡按对应聚焦集合执行，不机械要求每改一段文档就跑全矩阵。可新增的恢复/结构用例必须能证实实际状态、字节、事务和调用边界，而非只断言新 helper 被调用。

### 4.2 最终候选必要工程 gate

以下命令来自固定基线工作流，执行时**需要 Codex 核验**工作流是否仍相同。沿现有 CI 的 Python 3.11/3.12 × Node 22/24 单元矩阵、真实 renderer 和 required browser职责运行，不新增一套重复矩阵。

```bash
python -m ruff check src/deck_master tests/rebuild
python -m pytest -q tests/rebuild -m "not render and not browser"
python -m pytest -q tests/rebuild -m render
python -m pytest -q tests/rebuild -m browser --require-browser
```

不同命令由对应具备工具的 job/环境执行，不能在缺 renderer/browser 的同一机器运行后将 required 用例随意 skip。最终报告需要真实分组结果与实际 skip 原因，不以“进程退出 0”代替当前质量判定。

现有 browser job 的隔离 wheel 与离线回归也须保留。以下由已安装候选且具备相应依赖的独立环境执行：

```bash
python examples/workbench/w12_offline_browser.py --require-installed \
  --font 'DejaVu Sans' --out /tmp/deck-master-rc4-offline
python examples/workbench/w12_installed_regressions.py \
  --out /tmp/deck-master-rc4-offline/installed-regressions.json
```

先使用现有流程在临时环境构建/安装该候选 wheel；不能在用户当前解释器里随手卸载活动包。installed 证据必须证明从安装资源读取，不借 editable checkout。

### 4.3 N2 的真实进程失败测试

在独立临时 prefix/Host root 中使用子进程注入 KeyboardInterrupt、正常异常和不可捕获退出；至少含动作已生效但 step_state 尚未写回、prepared 已写而 pending 未写、补偿再死亡等窗口。

不能只将 Exception 改成 BaseException 就称已完成，不能杀共享服务或操作用户真实 HOME。真实 HOME 激活状态不从合成安装用例推导。

### 4.4 N4 的性能验证

先证明 v1/v2 完整内容等价和 resolver 开关对照，再看成本。报告实际序列化字节、正文重复次数、snapshot JSON解码、读取和stat计数。

- v2 full：每一相同资源正文只返回一份，关系/版本不丢。
- 冷态 canonical 负查询：每份可达 snapshot 最多解码一次，无二次全链扫描。
- 同 head 热态：负查询历史 JSON 解码 0；正查询最多重新解码命中 Document 1 次。
- 增量：只解码新增 Δ snapshot，加上命中核验需要的至多一份。

这些是确定性读次数指标。耗时、费用和 token 可以真实观测，但不设没有基线支持的毫秒或百分比门槛。不允许把工作移到未计数 helper/线程规避计数。

### 4.5 N6 的实际应用与成品

至少一项有具体缺陷依据的 canonical 方法变更，实际应用到一项完整正常任务；保留首份完整稿/修改前稿身份、真实改动、受影响内容与复核结论。材料可公开或中性，但模型应用不能用脚本固定答案替代。

任务是 content_only 时验其完整内容包；是 full_deck 时验约定 PPT 和真实渲染。视觉或 notes 有变化时，只重做受影响产物。不要为内部验证扩张用户已给出的范围。缺少真正必要的 Host/renderer 能力时该项 BLOCKED，继续不受影响工程，整轮完成状态不虚报。

## 5. 必要跨卡接受条件

下面是集成主题，引用原 AC，不产生新的重复编号或第二 Owner。

| 集成主题 | 主要 AC |
|---|---|
| 新旧输入回执、旧 log-only no-op、索引开关 | AC-N1-02、AC-N1-06、AC-N1-12；AC-N4-11、AC-N4-14 |
| 固定 head、损坏历史与跨入口查询 | AC-N1-10、AC-N1-11；AC-N4-12、AC-N4-13 |
| Task producer、旧任务与 v1/v2 等价 | AC-N3-05、AC-N3-09、AC-N3-10、AC-N3-11；AC-N4-01、AC-N4-04、AC-N4-07 |
| writer floor、安装/回退和方法身份 | AC-N2-01、AC-N2-04、AC-N2-12；AC-N3-12；AC-N5-08 |
| 方法实际改进和本轮应用 | AC-N6-03、AC-N6-04、AC-N6-06、AC-N6-10 |
| 文档、schema 镜像和唯一状态 | AC-N5-01、AC-N5-03、AC-N5-07、AC-N5-10 |

## 6. 旧证据复用与回归终止

旧结果保留准确版本，不把新候选的模板预填成 PASS。对于没有变化的稳定底层行为，可以记录依赖未变依据后复用历史证据；新增回执、协议、方法、安装资源和本次实际效果必须有当轮证据。

候选变动后先做影响分析：代码逻辑、schema、方法字节、构建安装、实际产物分别判定。补受影响用例与必要对照即可，不重新生产所有无关页面、不重复组织真实模型实验。证据已经足以消除具体风险且必要 gate满足后，停止可选验证，进入交付。

## 7. 关闭判定

### 7.1 单卡完成

适用 AC 全部满足，必要回归有真实结果，接口消费者已接受，版本/对象/证据定位清楚。文件写完、代码合入或测试存在均不是单独完成条件。

### 7.2 工程候选完成

工程实现、适用工程类判据与当前必要 CI 成立；N6 有实质方法变更，但真实应用可能未完成。若如此，只能称“工程候选已完成，实际应用待完成”，并逐项列出尚未关闭的 N6 和共用正常任务的 AC-N5-02 等条目；不能暗示 N5 整卡已经验收。

### 7.3 本轮完整完成

全部六卡的适用 AC 成立，N6 实质改进在完整正常任务中应用并检查，最终候选和安装资源一致，文档/台账/限制可读可追踪。

正式发布或用户本机激活如果不在授权范围，可作为后续动作说明，不要求为了“完整”进行未授权外部操作。反过来，发布或安装成功也不能代替本轮效果与兼容验收。

## 8. 本 Spec 包的校验

交付前运行：

```bash
python tools/validate_spec.py
```

该命令检查文件、相对链接、JSON、AC/Owner覆盖、依赖无环、模板状态和文档围栏；若提供固定仓库路径，还可检查固定SHA链接的代码路径及行界。它不运行 Deck Master，不会将70条产品AC改成PASS，也不会上传或发布内容。

具体已执行结果见 [VALIDATION.md](VALIDATION.md)。

