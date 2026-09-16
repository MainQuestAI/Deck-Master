# Codex执行入口

开发任务卡已按本清单拆分：见[25张任务卡与执行顺序](task-cards/README.md)及[126个子任务CSV](task-cards/subtasks.csv)。任务卡及正式Spec已同步修正验收归属和工程试行依赖；当前均未实施。

## 当前授权

本包是实施输入；不是已经实施、测试或发布的产品。先确认当前会话已有相应实施授权。仅获方案授权时，只核验并落文档，不修改产品代码或激活安装。

## 第一次读取

1. 先读CHANGELOG-v1.1.md，再读specs/00、01、02和14，明确B0/K0、同仓src新建、取用边界与删除顺序。
2. 读inventory/old-files.csv、new-files.csv、root-and-config.csv、task-list.csv、acceptance-matrix.csv。
3. 对本地固定HEAD运行只读materialize_inventory.py，输出到仓库外；核对未知/差异路径，记录实际安装版本。需要Codex核验；不能reset工作树。
4. 以WP01开始，按start_after/early_delivery交错早期切片；depends_on是整项完成依赖。T13.min先于首次外部调用，T05.min在首次正文自动打开UI。T08/T09在接口固定后可并行。不要整包合并PR31或把旧OS复制进新src。
5. 每次完成给真实变动、命令、结果及未执行项；先交能工作的完整链，随后默认切换，最后删旧源码。

## 不得改变的实现方向

宿主负责原文理解、专业内容与视觉制作；代码负责文件/转换/真实检查。SVG是唯一手写制作源，IR派生。Document/current唯一当前事实，CLI/UI用同一view。原图与业务输入不能由结果反向定义。没有外部PPT Master/Library/工作区平台前置。旧run只读导入或固定旧版继续，原件不改。

普通内部取舍按本包执行，不原样交还用户；遇到源代码事实使某项设计不可行，给具体证据和最小替代，不扩大为新治理平台。实现、安装与发布结果只能按真实执行描述。
