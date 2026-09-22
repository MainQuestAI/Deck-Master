# SC-1 目标契约

七份 JSON Schema 均为 Draft 2020-12 的目标草案，与当前仓库已有契约版本不是同一状态。Codex 必须先做对应 validator/adapter/旧输入兼容，再启用新生产模式。

共同 envelope：schema_version、run_id、run_mode、based_on。based_on 至少包含输入引用+SHA-256和集合指纹；生产/benchmark 对照已创建 Run 的模式，不信任回传自行改模式。input fingerprint 对所需实际输入计算，不接受 Agent 自称“当前”。

## 核心语义校验，Schema 之外必须实现

| 对象 | 必须额外校验 |
|---|---|
| execution plan | 必需能力实际探针、task_ready 与缺项一致、none 不要求 corpus、旧suite状态不可隐藏 |
| context pack | 来源文件/页/片段真实存在、读取覆盖、引文/片段指纹、跨源ID消歧、授权与支持状态不同、冲突可追溯 |
| research task/result | 查询投影已获授权、宿主真实执行与预算、任务结果关联同一输入，不把未知网络状态当成功 |
| solution model | 引用可解析、问题—能力—验收连通、现有事实有来源、拟建设计有理由、阶段无依赖环 |
| narrative plan | solution hash 当前、候选/选择可解析、issue tree 与 beat 依赖无环、beat 证据/方案引用可解析、selected 需决定引用 |
| diagram view | model hash当前，节点成员可解析，关系端点/方向正确，聚合可解释，图文一致 |
| external review | 当前文件实际覆盖、独立执行轨迹、具体观察、关键问题压过summary、旧输入报告不得当当前 |

## 来源位置

line/page/slide/paragraph 使用1起始闭区间；character 使用0起始半开区间。region 使用所在页/图的定位与 detail 中明确的像素范围、源画布和解释；工程正式落库时优先把 region detail 升级为受控 bbox 结构并做范围校验。不得只写“见文件”就宣称精确引用。

文本引文核对已解析的版本和片段；图片/扫描件的视觉观察绑定原图哈希与区域，观察文字不能假装成已存在的机器可提取原文。对 PDF 表格的单位/期间和脚注，需要同时保留定位。

## v1 到 v2

保留旧原始导入载荷及其指纹供审计，继续支持原有读取路径。新的必填来源覆盖、精确定位、review provenance 不得用虚构默认值补造。旧数据缺这些字段时维持 legacy/unresolved，并要求真实补充后才能满足新策略。对 source_type 的枚举映射、原 origin_path 及其字段保留由迁移表说明，不能静默丢失旧内容。

`specs/09-contracts-and-cli.md` 与 `EXTENSION_DELTAS.md` 定义既有对象的目标扩展。新的完整 Schema 与已有源码出现命名/版本冲突时，按 Q0 映射递增版本，不削弱语义约束。

运行 `python tools/validate_spec_pack.py` 只验证本包七份合成样例及选定反例，不验证仓库实现、真实模型、真实后端、授权或UAT。
