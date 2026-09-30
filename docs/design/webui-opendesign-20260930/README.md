# Deck Master 最新设计收讫

来源：OpenDesign MCP 项目 **Deck Master · 全链路生成工作台 v3**，项目ID `deck-master-generation-workbench-v3-20260926`。收讫日期2026-09-30；用户要求以此作为本轮Web UI设计。

完整接收17个源文件（1,871,399字节）：15个文本逐字节对照MCP返回；2个PNG从MCP返回的resolvedDir读取，大小与MCP元数据匹配，字节hash见 [manifest](manifest.json)。没有修改OpenDesign项目，也没有发起新的设计生成。

- [正式设计体系](design-system.html)：基础token、产品覆盖、组件、图标、文案、状态、表格与候选比较规则。
- [产品语言](product-ui-language.md)：术语、动作、状态与能力边界。
- [当前原型](index.html)：项目、制作总览、内容与来源、整稿画廊、风格校准、任务与交付及共享单页。
- [六状态原型](states.html)：正文、保存未知、冲突、批量部分返回、结构调整和历史恢复；仅规范参考，不进入生产导航。
- `original-v2/` 为项目中附带历史源文件，不作为本轮覆盖优先级。
- 两个PNG为项目内已有截图，未声称本轮重新拍摄。

原始文件完整保留；这是可交互设计样本，内部localStorage、硬编码页数、任务模拟、导出清单并非真实服务。实施继续使用Python核心与ES Modules；从本目录迁移视觉和交互，不能直接将app.js整体当产品入口。

产品视觉以design-system的Deck Master产品覆盖、product-ui-language和当前原型共同为准；冲突按 [规范适配决策](../../specs/deck-master-webui-v4-20260930/DESIGN-ADAPTATION.md) 处理。原型“生成/导出未连接”属于样本能力说明，运行产品应显示实际可用能力。
