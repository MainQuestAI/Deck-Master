# PR124 完整 CI 导航修复

`ff59ea5c` 的[PR运行](https://github.com/MainQuestAI/Deck-Master/actions/runs/39258531644)与[push运行](https://github.com/MainQuestAI/Deck-Master/actions/runs/39258524157)均完成失败：八个单元组合各3380通过、2项已有跳过，两套渲染各133通过、1项已有跳过；两套浏览器各494通过、1失败。失败均为原24页压力用例重复进入“任务与交付”后，30秒内找不到“待决定”。后续安装步骤未执行，组汇总失败；原日志和实际终态完整保留。

本机原单例修复前通过，不能据此把远端失败称为环境偶发。真实请求时序发现，同目的重复点击发出两次项目读取，加载期间后台控制刷新又每3秒叠加请求；两个项目请求分别耗时约17/19秒，任务、历史接口不足0.5秒，约25秒后才渲染。观察器额外5秒候选行断言失败与初次采集错误单列保留，不冒充原CI30秒失败。

生产仅改 `project.js`：导航同步记录目的地，合并同目的待完成读取及排队的 hashchange，导航期间先跳过被该读取覆盖的被动控制请求。不同目的、显式初始路由和 current 仍读取；只有匹配 generation 才清理 pending，失败可重试，后续控制刷新恢复。协议、授权、journal 未改。

四个新增真实浏览器回归持有并随后交付实际项目响应，覆盖排队/加载中与成功/503失败；修复前直接断言出两次重复读取，修复后4通过。原24页用例和九项相关导航/控制用例另10通过。原用例函数逐字节未改，原断言、30秒点击超时及等待限制保留。

干净源 `2a8bef16f2807b5841c09c87a5928346933b8486`，tree `d54463ec964f9d6191c78c2d4f272bb6dd964cf1`，source_dirty=false；release identity `2a8bef16f280-9df19d761a6c`。wheel SHA256 `9df19d761a6c19c11d72915c21d8280fed51ca363a65c68c0f60976c8fbbaa7d`；sdist SHA256 `926ec1a29db81dbc1f62fd5a7301bbc28d138af209da501faafeb99518686b36`。

全新 prefix 在 checkout 外以隔离 Python 实际运行：原24页与四个新例合计5通过，使用真实系统 Chromium；两个候选进程、275包文件、90源码 Python 模块及 `project.js` SHA256 `21e7cca5783410e1243dc7cb10f1eb93a01bd9c1a60be098872b9c33118b7758` 均核验，guard违规0。N2的 Python 产品及测试保持97源字节，新 wheel另执行254项安装回归全部通过；原309源码和47退出窗口保留原执行身份。

详情见[导航证据](Integration-pressure-navigation-repair.json)、[最新N2安装回归](Installed-review3-final-N2.json)和[资源身份](Installed-resource-identity.json)。截图仅内部检查，交付包不含截图。唯一70项台账保留失败历史，组装时新证据头完整CI尚未启动；后续终态由PR checks与最终候选 `CI-terminal.json` 提供。指定复审、用户本地效果及可信Host回执仍分别处理。N6不重跑，未合并、清分支、发版、部署、改授权或激活真实HOME。
