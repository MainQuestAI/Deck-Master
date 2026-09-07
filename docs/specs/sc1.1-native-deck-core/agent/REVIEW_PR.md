# 独立评审指令

以本轮实际执行后的Spec+明确偏差记录为基线；本包已正式替换SC-1 D04。不要再以“缺PPT Master绑定”否决native路径，也不要因为该绑定要求取消就放过实际编译与质量检查。

核对：默认CLI/Agent/doctor/next-step/preview/final-readiness是否同一路由；是否真的未读取外部目录；compiler是否内置且无隐藏调用；图片是否真实生成；Scene/SVG/ContentLock是否同源；公共MBB是不是派生；PagePackage状态/Schema一致；缺语义时是否执行正确任务；external_visual不能满足semantic；改package不改index仍使审查过期；逐文件中断能否保持完整版本；失败是否耗预算；作用域和取消/迟到是否被执行；当前批准是否绑定实际文件。

要求真实干净安装、真实编译/渲染/编辑、真实宿主两页/完整deck和旧Run迁移证据。测试数量不是产品效果指标。仅抽测内部helper不足以证明调用方已接线。

将发现分成产品裁决违背、确定性bug、接线欠缺、证据未执行与未来建议。前三类必须给文件/行、触发条件、影响、修复建议、测试；未执行不写成确定故障，未来建议不自动扩大本轮。

检查所有原SC-1 88项retain/replace/clarify映射。旧测试不再适用应写superseded及新case，不当passed。批准本PR工程里程碑与宣布整轮accepted分开。
