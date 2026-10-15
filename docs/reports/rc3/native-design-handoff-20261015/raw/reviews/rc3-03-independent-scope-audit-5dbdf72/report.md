# RC3-03 原卡独立覆盖审计：5dbdf72

**结论：REQUEST_CHANGES。** 本结论只覆盖固定候选 RC3-03 的原卡范围审计，不是整体 RC3 ready、发布或人类验收结论。正式接口替换已有风格决定后，会阻断设计解析；同一路径还有审计 Ref 混入语义消费比较的问题（F9-A/B）。Root 已接收缺口并交实施 Owner 修复；本报告不预判未冻结的新修复。

候选 source `5dbdf72089d6625449a23a52ef3e23859c597b4e`，tree `1b69a05050c63d0a2fbc4aaac86350611ad9f504`。只读快照为 `../rc3-03-code-snapshot-5dbdf72`，实际解释器固定为候选 release `5dbdf72089d6-94f6f31fcadf/venv/bin/python -I -B`。本审计没有修改产品、安装、实际项目，也没有图像调用；所有探针项目和编辑副本均在本审计目录。

## 阻断与可复现输入

### F9-A：正式替换决定后，历史 Ref 被误收为当前适用决定

位置：`src/deck_master/production.py:149–158`、`design_requirements.py:212–216`，关联 `dependency_slices.accepted_decision()`。

在隔离项目通过正式 SDK 建立 accepted/direct_user 的 `topic=style`、`decision_id=audit-stable-style`、`value={"palette":"blue"}`、scope=p1 的决定；建立并派发初始设计配方；随后通过 `collaboration.record_decision` 原 payload 加 `replaces=旧Ref` 更新同一决定，甚至无需改变任何实际值。该公开操作成功，紧接着 `production.resolve_generation_design()` 报：

```text
design_requirements/decision_refs/0: decision is not the current version in the selected snapshot
```

`resolve_generation_design()` 遍历 region 中所有历史决定 Ref；`accepted_decision(old_ref)` 会追到新的 head，因此历史 retirement Ref 和新 head 都被收集。`_decision_slices()` 又要求每个传入 Ref 本身是 current head，于是拒绝历史 Ref。用户合法更新颜色、密度取舍等决定后，作用范围内的新生产准备被卡住。这是当前产品缺口，不应留给 RC3-04/05 代修。

### F9-B：相同有效语义的 Ref 外壳污染消费比较

位置：`production.py:165–169`、`design_requirements.py:223,292–298`。

在上例的 after Document **只读副本**中，仅过滤 historical refs、留下真实新 head，以隔离 F9-A。两版 Page、所有非 basis 设计字段、完整 `content_requirements` 均相同，registered effective decision SHA 同为 `1d3b6e9a4158626e3dbcb0dbb49d0601eb4b2b2901b44fd7909c77810134d598`，但 `consumed_design(old) != consumed_design(new)`：`content_basis.consumed.decision_slices[*].decision_ref` 仍被保留在比较中。该 Ref 应作追踪依据，不应绕过 registered semantic SHA 进入失效判定。

边界说明：本复现时旧 Task 仍被 `content_identity` 快速通道判 current；本报告**不声称已复现旧 Task stale**。F9-A 的公开解析阻断与 F9-B 的直接消费投影不等均已确认。修复应保留历史 basis 的真实 Ref，同时对当前 head 的 value、scope、状态、接受与否、request 等真实变化保持正确判定。

可重放脚本：`probe_decision_audit_ref.py`；结构化结果：`decision-audit-ref-result.json`；两版完整上下文：`decision-audit-ref-before.json`、`decision-audit-ref-after.json`。该探针使用明确 synthetic authority fixture，仅证明实际安装 SDK 行为，不是实际用户授权或模型质量证据。首次未捕获的错误日志和后来过严的旧 Task stale 断言失败均保留；最终脚本已纠正为验证上述两项实际观察。

## 原卡逐项覆盖

完整机器映射、公开入口、测试源和后续责任见 `coverage.json`，共 19 行；下表是原卡七项实施工作及专业条件的审计结果。

| 原要求 | 最终实现、入口与已确认工程证据 | 尚未关闭的层 |
|---|---|---|
| 工作1：CONTRACTS §11.4.1 投影/权威/fidelity | `design_requirements` 从固定 Page/Plan/recipe/适用决定派生；`production.project_prompt` 完整序列化要求、正文、单元格、nodes/edges；`generation.prepared_input/freeze` 保留同一上下文。fidelity 缺角色/profile/rationale 为 null，不补 Narrative。实际 P04 prompt 与原 callback 逐字相等。 | **F9-A/B 阻断**；不能把其余字段通过当本项全通过。 |
| 工作2：无旧图的初始样页与零调用可行性 | v3 initial_design 绑定真实 Page，允许无 blueprint/reference；feasibility 支持真实 Narrative/Plan，拒绝派发生产。公开 styles propose/confirm/plan→changes commit 有明确边界。 | 真实 P04 初始图已见；无参考图调用来自8057905，5db下游保留身份。本例不代替原 Q4/P05 全套判据。 |
| 工作3：风险覆盖与准确候选/授权 | `page_profiles/sample_targets/coverage_risks/uncovered_cases/tradeoffs` 保存实际规划；首批 v3 可显式1或2页，测试反序到达仍仅候选。采用/维度决定/扩范围走各自现有事务与额度。 | 完整矩阵/机制/数据/架构的真实风险矩阵和选择效果未完成。一个 P04 不能证明所有风险已覆盖；决定更新先修F9。 |
| 工作4：逐层关系与主要编辑性 | 实际固定 Page→冻结 prompt→原始 PNG→5db重建工单上下文→SVG→原生 PPTX→真实 render 已有原件。独立重算 readback pass，35文字run/59原生形状/0图片；审计编辑副本可修改原生文字后重开。 | Root 正式 page_visual 原始完成与结果绑定仍待接收；本审计没有提交项目 review。不是人类桌面编辑或整稿通过。 |
| 工作5：语义/几何配对与页级失效 | 语义投影保留单元格身份、归属、节点/方向、单位；布局/notes分开。定向原生检查识别同全文错行、反向箭头，同关系真实 transform 通过；无关Plan密度与未消费字体不使本页失效。 | **F9-B** 的审计决定 Ref 仍破坏消费等价。实际模型负例/完整E3尚未由本审计关闭。 |
| 工作6：定位后定向修复，保留示意边界 | readback 给出 Page/atom/cell/node/edge 定位；continue 保留失败并进入 repair/no-progress。prompt 与方法明确缺数据回内容阶段，禁止装饰性数量图；实际 P04 保留人工提交和未知限定。 | 规则、合成负例和一份正确成品不证明各种真实模型失败都已定向修好；须保留后续实际失败与返修原件。 |
| 工作7：固定正文E2、逐层E3、原件与失败保留 | 实际 P04 的旧安装生成和新安装下游各有身份；原始PNG未重编码，SVG/PPT/渲染可逐层追踪；本审计比较没有补写正文。 | **正式公平E2未执行；E3只有单页工程子集。** 原卡此项保持未完成，RC3-05负责正式比较与汇总，可复用本卡合格原件。 |
| AC-D01 / CQ-03 / I04 | 有实际初始样页及完整冻结投影；fidelity空字段、Plan/recipe/当前Page约束有代码和定向检查。 | F9需修；P04工程变体不能直接关闭原Q4/P05和专业效果AC/CQ。 |
| AC-D02 | 候选在call settlement不自动采用/扩展；代码与受控正式SDK测试分开采用和扩展。 | F9影响合法维度决定更新；真实“颜色可以”/拒绝/后续扩展完整交互未在本审计原件中关闭。 |
| AC-D03 / CQ-04 / CQ-05 / I05 | typed配方、页级依赖、语义/几何工程配对、实际P04原图与成品、可编辑原生对象已有具体证据。 | F9需修；全部页型、密度冲突的真实模型效果、完整E3和人类层不作PASS。 |

## 指定重点的核对

**全局版式与字体资产。** 四个独立零调用探针通过公开 `create/update_design/import_asset/continue` 消费实际安装：全局 `layout_notes` 逐字进入prompt；真实 DejaVu 字体文件通过允许资产 Ref 暴露；body/heading及其fallback闭包被消费，unused font被排除。global layout、已消费fallback、同font_id文件字节变化使任务不再current；unused font变化保留current；Page正文均不变。原生P04的Noto Regular/Bold实际字体文件也有hash。这里只证明请求和原生链消费，不承诺图像模型逐像素使用某字体。

**StyleRecipe参数。** `design_recipe.effective_parameters/compile_design` 执行palette、typography及五项布局规则；只有许可的page_rules/overrides可替换并显示差异。规划说明不成为参数真相，recipe不能修改Page事实。实际P04的 `recipe_parameters` 在projection、冻结input及5db重建 `page_design_contexts` 中相等；下游不回退default/latest recipe。

**初始与restyle参考顺序。** initial真实P04调用没有参考图。定向正式SDK测试验证restyle目标当前原图在首位，独立原始JPEG和PNG按选定顺序在后；冻结拒绝以JPEG preview替原始字节或改执行参数。该restyle测试的controller明确synthetic，不是实际模型restyle效果证明。

**G12实际image链。** 本审计直接读取原callback、raw tool return、不可变Request/Attempt、call settlement、原始PNG和execution identity，未读取/复制Root私有controller key。`prompt`、参数、空refs、输出hash均相符；调用consumed且无自动采用/扩展。图像执行安装是 **8057905162f20926cfc1a0a96252bc6745f4e700**；5db只读重建上下文保留旧Request，不重标旧调用。原PNG SHA `8cf79c6ada8476c72ebc13f822821a6e02d5ffa7215bfad1984c74fd52eb147c`，实际1672×941，请求canvas1600×900，差异据实保留；model/seed/平台invocation/美元成本保持未知。保证层为host_attested真实controller观察，非平台签名/人类确认。

**实际原生文件。** 在保留的实际P04 SVG上重新parse、对实际PPTX重新readback，结果与Root原始readback逐字段相同。SVG SHA `1223a9d6c9c89bb998434395e58dfee8c77c3d95d918fca7b8a613c54739a00b`，PPTX SHA `c93179007f6e478a3ac8736d712e18a709519ddc7a027550228745619274a4ae`。审计员查看原始模型PNG和最终PPT渲染：四节点方向、两行异常表归属、人员正式提交和未知限制可见；最终渲染显示固定的主链适用限定。独立编辑只写审计副本，原件9份hash前后相同。

**构建、安装与方法包。** `setup.py→tools/build_hook.py` 以唯一canonical Skill打包；`method_resources.resolve_root` 不借当前cwd。逐文件比较未发现source package与installed package差异；14份canonical Skill文件与installed packaged bytes一致。实际CLI的capabilities、blueprint/reconstruct/review方法全文、design阶段方法及styles/requests帮助均可读，返回release身份准确。它证明方法字节可消费，不证明Host已应用全部方法或完成RC3-04全入口集成。

## 验证、原件与界限

24个选择性工程用例通过，见 `targeted-tests.xml`；测试选择、日志和全部产品模块导入身份分别保存在 `targeted-selection.json`、`targeted-tests-rerun.log`、`targeted-import-identity.json`，foreign product modules为空。候选runtime本身没有pytest，第一次尝试的“No module named pytest”日志保留；随后仅复用本地已有pytest作为runner依赖，预先载入installed package，并核验全部 `deck_master.*` 模块都来自固定候选。没有安装依赖或大规模重跑全suite。

上述测试的authority、controller和部分输入为明确synthetic工程材料；不当成实际模型、人类或公平比较证据。实际模型证据只引用本报告直接验证的原始callback/对象/PNG/下游实际文件。其他审计报告的结论不构成本报告依据。

`immutable-baseline.json` 与 `immutable-after.json` 对比：snapshot **3203**份文件、installed package **340**份文件无变化；集合hash分别为 `5c48a30277b1467b4e5b711c5a6d20a762a2d17b0ca8136e11b8308809c53c53`、`7da60e938e563d6dd3939b4f66ff15c74bc49425dd91eb4ed2c9355b79d28185`。coverage列出原始规范和本地证据hash。所有结论只约束这个固定候选。

RC3-04承接完整三入口/四Skill、导入迁移、恢复/只读和最终安装集成；RC3-05承接公平E2/E3、全部适用风险和实际效果、最终AC/CQ证据汇总。它们不承接F9产品修复。真实Owner、听众、计时、人类桌面编辑和适用professional policy按用户授权明确延后，保持NOT_RUN；不因延期而阻塞无关研发，也不能由模型扮演补齐。

本卡工程范围仍需F9新候选修复及独立复审；原卡D01–D03/CQ-03–05整体保持未关闭。Root正在进行的正式page_visual绑定列为pending，不判作产品缺陷，也不提前记作完成。
