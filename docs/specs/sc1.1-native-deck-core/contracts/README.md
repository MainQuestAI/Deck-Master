# 目标契约与接口

本目录四份 JSON Schema 是本轮需要实现的窄接口，不代表 PR #30 已有这些接口。其余 Context/Narrative/Page Package/Scene/Content Lock/Blueprint/Review/Render 等继续复用现有合同，必要字段见 [EXTENSION_DELTAS](EXTENSION_DELTAS.md)。不把整个仓库所有schema重写一遍。

| 目标合同 | 用途 | 持久化/调用边界 |
|---|---|---|
| deck_build_route.v1 | 固定引擎、authoring模式、密度和原运行模式 | request中的build_route；Runtime拥有 |
| deck_native_compile_request.v1 | 单次确定性SVG编译的输入集合 | Run adapter→compiler；只读已批准文件引用 |
| deck_native_compile_result.v1 | 编译结果、逐页对象摘要与trace | compiler→Run adapter；不能授权导出 |
| deck_task_readiness.v1 | 按任务区分必需、未知和可选依赖 | doctor/status等共用投影 |

所有文件引用相对明确的Run/bundle根，需检查路径真实解析、symlink逃逸、run_id/hash/版本/批准；JSON Schema 只做结构校验，不能代替文件存在和语义检查。

四份合同不需要新的外部服务，既有Runtime负责生成与接受。目标文件名可按仓库惯例调整并登记，但枚举/必要字段/边界和验收不能丢失。现有manifest/schema若additionalProperties:false，必须同步版本/引用/消费方；不能假设新增键天然兼容。

`examples/`中的文件均为合成结构示例；其中的hash、receipt和路径未对应真实产品产物，仅验证Schema。真实smoke必须重新生成并记录真实文件。
