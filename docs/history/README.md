# Deck Master 历史文档保全

固定源码基线：`62dfcfc5637f0bee2358074c4458047689dd5299`。这是历史材料索引，不代表当前测试、安装或发布状态。

- [离线归档](main-62dfcfc5637f-documents.zip)：包含2868份原始文件及一份内嵌清单。
- [逐文件清单](manifest.csv)：原路径、Git blob SHA、SHA256、原始字节数、文本行数与固定提交永久链接。
- ZIP SHA256：`2d7d6c704e4bce869edc62687cabae114dd3a7427f9a99de613d7519a9838317`。
- 当前使用见[文档导航](../README.md)；继承合同见[Spec索引](../specs/README.md)。

## 离线查阅

先在manifest.csv中按原路径查找，再把ZIP解压到一个独立目录；不要覆盖当前工作树或用户项目。
ZIP条目沿用原仓库路径，原始JSON、日志、图片、旧方案及其失败/未执行状态均逐字节保留。
ZIP内部的ARCHIVE-MANIFEST.csv与外部清单相同，可用标准解压工具读取，不需要运行归档脚本或联网服务。
永久链接方便在线阅读；离线阅读不依赖GitHub或额外上传。

测试直接读取的原始向量现位于[fixtures/history](../../tests/rebuild/fixtures/history/)，其原SHA与断言保持不变。
旧CLI仍直接读取的[历史manifest](../archive/pre-rebuild/product-capability-manifest.v09.json)继续原位保留。
活跃文本减少不等于信息删除，压缩归档仍计入仓库字节和文件统计。
本轮实施及验收状态见[逐卡台账](../iterations/MAIN-ITER-20261027/ledger.json)。
JSON/CSV保留的历史路径由[机器引用映射](machine-references.json)逐项追溯同SHA原件。真实消费者需要的[W12记录](../reports/workbench-v3-execution-20260926/W12.md)保留原位。
