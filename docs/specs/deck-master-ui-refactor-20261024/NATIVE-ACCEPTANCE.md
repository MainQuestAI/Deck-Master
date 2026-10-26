# 原生验收与待审收口 · 2026-10-24

产品提交 `44fc6a23824d3e8f9a9aa6e80fcd1cc6ef791ecb`，完整 CI 对应提交 `12fd87f9dfe91a9861653feee4aebfcdc4e7dde1`。本次只更新验收文档，不改产品、测试或 workflow。此前锁屏/待回读记录保留为历史；当前状态以本补证和更新后的验收矩阵为准。

## AC02：真实目录选择与取消

- 隔离 wheel 的真实 Chrome 页面填写项目名、用途、受众、保存位置和新目录名。点击真实“选择保存文件夹”，选中返回后路径回填，其他字段保留。
- 用户明确报告“已点取消”。工具不能绑定 osascript 承载的原生面板，因此取消动作记为用户协助，不能写成 Agent 自动点击或以 stub 代替。
- 取消后独立回读真实 Chrome：新项目表单仍在，五项字段均与取消前最近一次回读一致；选择按钮恢复可用，无错误提示。
- 独立 registry API 回读项目数为 0；两个可能目标位置均不存在新项目目录。没有点击创建或启动模型。
- 创建成功但打开响应失败的恢复由既有浏览器/真实 API 套件覆盖，包含在最终 577 项浏览器通过结果中。

结论：`PASS_NATIVE_ASSISTED`。原生动作和状态回读的证明人分开记录。

## AC29：Mac 原生键盘补证

真实桌面 Chrome / 独立 wheel：Tab 可达“准备上下文”。直接 Down → Enter 没有改变选择；Space 展开原生菜单后 Down → Enter 切到“独立阅读”，页面显示“准备已核对”。随后 Tab 到筛选字段及复选框、Space 选中 content-m04，Tab → Enter 打开方法正文，焦点进入阅读区。项目 revision 前后相同。

筛选文本使用原生 accessibility setValue 输入；不宣称键盘粘贴通过。本次是单桌面视口实测，不冒充 Mac 三视口自动化重跑。三视口布局、控件尺寸、主行动与焦点回归以 Linux 完整浏览器 577 passed、既有计算样式与 30 张产品截图证明。此前 Mac 的三个失败保留，已用真实原生操作解释差异，没有跳过测试或修改阈值。

结论：`PASS_ENGINEERING`；不表示用户认可全部视觉细节或专业交付签收。

## CI 与范围

- [push CI 40018706952](https://github.com/MainQuestAI/Deck-Master/actions/runs/40018706952) 和 [PR CI 40018715950](https://github.com/MainQuestAI/Deck-Master/actions/runs/40018715950) 的全部 14 个检查回读为 SUCCESS。
- 四组 Python 3.11/3.12 × Node 22/24 单元各 3528 passed / 2 skipped；渲染 133 passed / 1 skipped；浏览器 577 passed / 0 skipped；独立安装恢复 257 passed。
- PR 测试合并提交 `abdcc8fe7fa3e66faa7e85df5753b8f818e8ca6d` 与 `12fd87f9` 的文件树相同。安装证据的 84 个模块均来自 site-packages；9 项离线检查、三个真实 ZIP 的哈希已核对。
- 验收矩阵为 26 PASS_AUTOMATED + 1 PASS_NATIVE_ASSISTED + 1 PASS_ENGINEERING + 2 PARTIAL。AC14 的真实 Host 专业风格判断、AC18 的 #186 外部报告/返修闭环继续由原责任卡承担；两项不以 UI 工程验收关闭。
- 本轮 UI 实现和必要依赖没有发现新的阻断问题，可转正式待审。未合并、未改默认安装、未关闭原修复 Issues、未宣称用户视觉认可或专业交付通过。

机器记录与本机截图 checksum 见 [native-acceptance.json](evidence/native-acceptance.json)。截图包含浏览器其他标签页标题，保留在本机验收目录，不提交到仓库。
