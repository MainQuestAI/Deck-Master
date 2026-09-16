# 本包来源与核验边界

- 本轮通过GitHub connector查询branches与完整递归tree，固定B0 `2a866cf138f6359f853db35e0a926ad79391b691`；tree报告未截断。scripts清单177项来自该tree，与附件统计一致。文件存在不证明执行正确。
- 本轮读取B0 pyproject：setuptools；Python>=3.11,<3.14；当前旧console为deck_master:main、scripts布局；本包src布局/接口属于新增设计。
- K0 `2c5a4c50048b2641739356e72ddc1d6fea1d962f` 是上一轮已读取并比较的提取来源，未在本轮重新执行；不能假设已合并B0。
- sources/其他四份为用户材料与上一轮判断副本；保留其事实/候选/运行边界。原始客户图像/日志等未挂载部分不能视为本轮实测。
- 本包没有下载并执行完整仓库、未修改代码、未激活安装、未生产真实Deck。示例和schema检查只检查文档包。

固定源码入口：
- https://github.com/MainQuestAI/Deck-Master/tree/2a866cf138f6359f853db35e0a926ad79391b691
- https://github.com/MainQuestAI/Deck-Master/tree/2c5a4c50048b2641739356e72ddc1d6fea1d962f

本地HEAD、实际安装及所有后续实施和运行结果：需要 Codex 核验。
