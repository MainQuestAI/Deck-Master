# RC3-03 F9 独立复审 R7

**PASS，仅限 F9 修复及其受影响边界。** 原审计的 F9-A（公开替换决定后解析阻断）和 F9-B（审计 Ref 混入语义消费）在本冻结候选上已关闭。未发现本轮范围内需再改产品的缺口。此结论不关闭整个 RC3-03、正式 E2/E3、人类验收、F05 工程 helper 的物理画布检查或整体 RC3 readiness。

- Source：`cf61e5e717fc852263b5a5baf4d97a07e126362b`
- Tree：`96188d691ced737113019aea4a61a769812f6794`
- 固定 snapshot：`../rc3-03-code-snapshot-cf61e5e`
- 安装 release：`cf61e5e717fc-a8d812c66ca3`
- Manifest SHA256：`673ba5c39f11d3c53f08d19990bfd9ddbf89a28376d23b3ee813176ed1b12f82`
- Wheel SHA256：`a8d812c66ca36c8d47a435b9a77b7967368878c68d6cbe56afb124b464c2a2c3`

实际探针和测试运行于上述固定 installed Python，带 `-I -B`。242份source package文件及14份canonical方法文件与安装字节一致；所有测试载入的 `deck_master.*` 模块均在这个候选安装内。pytest只使用专用环境已有的本地runner依赖，没有安装新依赖或重跑fullsuite。Owner提供的349项结果不是本报告独立通过数。

## 修复和原复现

产品delta只涉及 `production.py`、`visual_dependencies.py`、`candidates.py`、`styles.py`，另加一份F9测试，精确hash见 `source-delta.json`。

`resolve_generation_design()` 现在按真实 `decision_id` 找current head、去重，再按head的topic/scope/接受有效性选适用决定。`consumed_design(..., store=store)` 保留原始 `content_basis` 不变，只在比较投影中将Decision规范化为实际identity+registered effective SHA并排序。现代blueprint在manuscript identity快速通道前比较实际消费；历史candidate的编码只在当前语义与它自身owned frozen preparation相同后，复用该原始preparation的审计外壳。

独立重走原公开复现：建立accepted style决定→确认配方→派发p1任务→同一ID以原值连续两次 `record_decision(replaces=旧Ref)`。结果：

1. 完整公开解析成功，当前basis只记录一次真实新head，旧basis仍保留旧Ref。
2. Page、完整投影与manuscript content identity不变；语义消费相等，原任务仍current。
3. 可正式claim并冻结原prepared input；新Request保留原任务的准确输入，没有重建或改写旧依据。
4. 篡改冻结basis的Decision SHA会被正式freeze拒绝，业务指针不变。

证据：`independent-public-matrix.json`、`original-repro-before.json`、`original-repro-after.json`、`original-repro-frozen-request.json`。未使用原复现中的head-only workaround。

## 独立正负对照

| 检查 | 结果与证据 |
|---|---|
| 同ID同值换版、多级历史head | 通过；收真实新head且不重复，旧Ref继续可追溯，不使本页重生。 |
| value、scope、layers、style→speech、style→tradeoff、reject、withdrawn、不同identity相同value | 相关消费变化正确判为不current，即使manuscript content identity保持原值，也不能通过旧快速通道。withdrawn仅在隔离项目作明确schema-valid状态注入，因为公开record接口只创建active。 |
| p2→p1、speech→style | 新head变为适用后进入本页消费，旧任务不current；没有按历史head元数据漏收。 |
| p2 style或p1非design speech的无关更新 | 本页basis仍无这些决定，语义与任务current保持。 |
| foreign project、错误Page scope、非design topic、basis两处Ref不一致 | 四种只读context故障均被拒绝，规范化没有抹掉真实身份与归属校验。 |

上述为13个独立公开SDK场景、4个只读规范化负控和1个正式freeze篡改负控，均通过。authority fixture明确synthetic，只证明实际安装SDK行为，不是实际用户决定或模型质量。

## 真旧安装候选的确切兼容边界

独立在本审计目录用**真正固定5db安装解释器**建立了一份synthetic工程候选，然后退出旧进程，用cf安装在其隔离副本中读取、换版决定与采用。不是手工声明一个“旧digest”，也未触及实际P04项目。

- 旧5db候选准确design digest为 `79d931ae95e29e1f55c8bc2b2cd19046838250e8d115f1253635f9595f4b7715`。
- 同值决定换版后，cf仍产生**同一个旧准确digest**；candidate对象、Request、旧Decision和结果artifact原始字节不变；显式plan/adopt成功，没有新call。
- 规范化后的另一编码digest为 `41d1543d158e4f4b8d2b0951380dadd33234e6ac72ab8b60d13b0f6bbbef4052`。在隔离副本仅把candidate digest换成这个值，adoption plan被 `candidate_basis_changed` 拒绝。没有宽泛接受两个hash。
- 真实value变化同样拒绝采用；外来Request Ref被 `candidate_invalid` 拒绝。拒绝均未改变Page、采用状态或额度事实；原始owned对象保持不变。

原始旧安装种子与新安装对照分别见 `old5db-candidate-seed.json`、`cross-version-candidate-check.json`。受控PNG/controller/authority全部是synthetic；这里的“旧安装”描述实际SDK身份，不描述实际图像模型调用。

## begin后调用事实与consumer边界

另有5个独立begin→换版→settle场景：value或scope变化后分别settle为consumed、unknown；同值换版settle为consumed作正控。真实语义变化的native proof与晚到result被拒绝，但原allowance和Attempt各只保留一次，`used/remaining`不恢复，unknown继续unknown、费用继续not_reported，原Request和Page不变。同值换版可接回候选，仍不自动采用。证据：`independent-fee-facts.json`。

本轮另运行47项选择性原始测试，均PASS：其中包含新F9配对，以及已采用现代context的reconstruct/repair/page_visual消费、相关与无关变化、foreign/corrupt lineage、旧generation shape在RC3 writer floor下仍保持legacy、内容前审可先审当前正文、历史闭合执行不被新reader重新认证。测试导入身份无外来产品模块，见 `targeted-tests.xml`、`targeted-import-identity.json`。没有把这些受控测试计为实际模型或人类验收。

另用旧5db和新cf安装成对执行相同classic公开路径：两者都不添加generation协议、能力、generation_input或content_requirements，notes-only编辑后同一蓝图任务都保持current，既有编辑写入的writer metadata也相同。见 `independent-classic-boundary.json`。两次初始classic探针分别错误假定必有compatibility键、以及编辑后该metadata必不变，失败项目和错误记录保留；配对验证修正的是审计断言，没有修改产品。

## 实际P04的只读新reader复核

使用cf installed SDK，对实际项目一次选定固定revision `eea9ee0eb41242a59d3e75d687426527` 进行只读解析：

- `resolve_page_design(require_current=True)` 返回的完整上下文，与旧5db重建工单和原始不可变Request中的context逐字相同，包括原audit Refs。
- 实际图像执行身份仍为 `8057905162f20926cfc1a0a96252bc6745f4e700`；旧重建方法身份仍为 `5dbdf72089d6-94f6f31fcadf`；cf只作为本轮reader，没有新模型调用、重建、编译、渲染或review提交。
- 已完成的page_visual Task `89aefcb92514` inputs_current为true；blueprint_content、blueprint_fidelity、readability三项既有review的当前依赖均无问题。
- 原PNG、SVG、PPT、旧readback、render及身份等9份保留实际文件hash全部与前审计相同；实际项目pointer在本轮读前后相同。

证据：`actual-p04-readonly-requalification.json`。这是新reader兼容性与依赖复核，不新增独立视觉、人类、F05物理尺寸或完整E2/E3结论。

## 不可变性与结论范围

`immutable-baseline.json`→`immutable-after.json`：cf snapshot3207份、cf安装340份、旧5db snapshot3203份、旧5db安装340份，文件集合hash均未变。旧5db的 `report.md` SHA `c2410176962b0526e6d035984bdbc8011d2de327cb893d1d66ea87e59ce82d74` 和 `coverage.json` SHA `19bdbdb2a01597d797079e096f4c2229a20cf4a9fad279fdf0e65c8da667d909` 也保持原样；原候选RQ不会被新候选PASS覆盖。

本轮审计外部图像调用0、实际项目写入0、产品修改0；所有写入仅限此审计目录的可丢弃项目、副本、日志和报告。原缺陷F9-A/B在cf61e5e候选上有限范围关闭；原卡剩余真实覆盖、公平比较与用户明确延后的人类验收继续按原台账执行。
