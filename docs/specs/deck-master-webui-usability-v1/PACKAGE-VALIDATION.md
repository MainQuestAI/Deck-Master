# 冻结版本打包、隔离安装及离线 UI 验证


2026-10-04，完成资源泄漏、新 origin 恢复和历史比较布局修复后重新冻结，提交 `05b0d875d2cc890966ab10d730bf62d072ae871b` 的包验收通过。官方构建 manifest 记录 `source_dirty=false`，版本为 `1.0.0.dev2`。这是当前开发包工程检查，不是 RC 发布或用户视觉认可。

## 构建与资源

| 验证 | 实际结果 |
|---|---|
| 官方 `tools/build_release.py` 构建 wheel 和来源 manifest | 通过；固定完整源码 SHA，构建前工作树 clean |
| 同一冻结源码的 sdist，再由 sdist 构建 wheel | 通过 |
| 两个 wheel 的全部 `deck_master/` 代码与资源 | 204 个文件摘要全部一致，其中 143 个资源文件 |
| 新截图能力的五份 schema | `style-input.v2`、`style-proposal.v2`、`style-recipe.v2`、`visual-style-spec.v1`、`style-reference.v1` 均可读 |
| 安装后的方法及 UI | `visual-reference.md`、`visual-style.js`、比较画布 JS/CSS、导航可用性 CSS 均可读，与 wheel 摘要一致 |
| 冻结源码保持 | 验收结束再次核对源码、唯一公共 Skill 与打包配置的逐文件摘要，无变化 |

Wheel SHA-256：`d10981b45c0dc4e7f8799b3d3cb2faa9b1a94b50b5dc24b7fc0ce8aa3ce62413`。
Sdist SHA-256：`a0928946fde497f264d4dcd40afbe366f45fb7d29af78090a11b1c039a1e0e51`。

## 隔离安装和离线 UI

创建全新的 wheel venv，安装实际 wheel，未采用 editable 安装；移除 `PYTHONPATH`，实际 `deck_master` 来自该 venv 的 `site-packages`。将验证入口和依赖脚本复制到独立工作目录运行，`w12_offline_browser.py --require-installed` 的来源断言通过，没有借用源码模块。

另建全新 sdist venv，安装由 sdist 重建的 wheel；模块也来自该 venv 的 `site-packages`，`doctor --step compose/render/view` 均通过。该 wheel 的全部代码和资源与直接构建 wheel 一致，因此没有把两次构建之间的差异作为未验证假设。

离线浏览器拦截并拒绝所有非 loopback 请求，保持本机项目服务可用。执行结果：

- 1440×900、1280×800 的交付入口焦点和页面溢出检查通过，并保留真实截图。
- 浏览器实际生成并下载审阅、正式交付、内部工程三个 ZIP；固定版本、包摘要及每个 manifest 文件摘要均核对通过。
- 安装包内全部 v2 静态资产返回 200 且字节一致；品牌许可、字体加载、ESM 元数据检查通过。
- 当前入口返回新版 UI；旧路由返回 404，读取不改变项目当前状态。
- `external_requests=[]`、`page_errors=[]`。未发现 CDN、外部字体或运行时请求。

离线 UI 的七项检查全部通过。工程使用合成内容、零模型调用；这不代替真实 Host、客户内容、视觉认可或真实业务三用途导出。

## 正常安装器、激活与回滚

使用正常 `deck-master install candidate/activate/rollback`，所有安装内容只位于本轮私有测试 prefix。每次激活、回滚及重新激活均显式传入 `--no-host-registration`，实际结果为 `host_unregistered`；没有执行真实 HOME 安装或改变原有安装入口。

1. 从真实 `main@6996a29` 源码构建旧 wheel，完成候选安装及真实原生编译、渲染探针。
2. 当前冻结版本完成候选安装及真实原生编译、渲染探针。
3. 依次激活旧版本、新版本，再回滚到旧版本；验证实际 current 目标和私有 launcher 的模块来源。
4. 重新激活当前冻结版本，作为最终私有测试状态。

旧 release：`6996a29b1792-535f1db36c4d`。
新 release：`05b0d875d2cc-d10981b45c0d`。

## 证据及剩余边界

构建日志、两套 wheel、sdist、官方 manifest、安装记录、逐文件资源摘要、独立 venv、离线 HAR、下载 ZIP 和截图保存在本轮私有包验收证据中。没有提交生成物到仓库。

本机原生目录选择成功/取消、最终 PR head CI、完整核心与长跑、真实业务闭环及用户新版 UI 的视觉确认分别由主验收链记录。本报告不把这些未在本子任务执行的项目计为通过；也没有自动合并、打 tag 或发布 RC。

## 修前历史证据

此前三轮均完成同范围包检查。后续产品源码发生修复，故只保留历史事实，不作为当前门禁；本次结论来自 05b0d875 上的新构建、新 venv、新离线浏览器工程和新安装 prefix。

| 轮次 | Wheel SHA-256 | Sdist SHA-256 | 用途 |
|---|---|---|---|
| ece47b3 | `b0f58e71d9399ad5004308fb9d6d5940087b9cee5856e80b138ba0fcec792189` | `b09605984033daa1f7d2d4add7172c1a0028fd8576058253ffcc8a3d4e820474` | 资源泄漏修复前历史 |
| 230ffd4 | `87d88f02bd1b5f879880c74d74044a1521b2406cb30fe99e531b32a2b81fad13` | `0be8b6f67c02bdfd263b3f547fbea627901aae8514881e148367f0b48fbbd6c2` | 新 origin 恢复修复前历史 |
| 88da633 | `91b6a189e7dba04c2eecb90bbd90ca329b1025a4730e767e685538890b52044e` | `b9845e283470d1ced542a7859508e4c35a84efdbaea7dc9f5d8dcb0d59ebe282` | 历史比较布局修复前历史 |

| 05b0d875 | `d10981b45c0dc4e7f8799b3d3cb2faa9b1a94b50b5dc24b7fc0ce8aa3ce62413` | `a0928946fde497f264d4dcd40afbe366f45fb7d29af78090a11b1c039a1e0e51` | 本次最终包门禁 |

## 真实业务副本的安装 UI 复核

另用最终安装 wheel 打开已有真实 30 页工程的独立副本；没有源码模块、localStorage 种子或新增模型调用。浏览器首次冷打开画廊至作品画布就绪为 **909.55 ms**，低于 2 s 门槛；这是本机单次实际样本，不替代性能长跑。

原图、SVG 与实际 PPT 读取的是各自制作链图层。关闭浏览器上下文和项目服务后，在新端口与新上下文中显式恢复项目个人草稿，以及已有的真实 v2 截图规范，已确认规范、固定参考、目标与单页预览入口恢复成功。读取和恢复仅写个人草稿与阅读状态，Page、产物、任务、配方、候选、意见及修改引用保持不变。390×844 画廊为单列，无水平溢出；实际截图已人工查看。

两次指定内容修改和两次 SVG 修改均可在分页历史定位，并固定当前版本。88da633 的人工截图复核发现 SVG/PPT 并排历史中候选入口占用作品列的 P2；05b0d875 最小 CSS 修复后，本轮新增双侧同一行及从左到右几何断言，分别验证两次真实 SVG 修改及两次真实 PPT 编译版本，完整比较画布截图人工确认通过。该修复的历史负例和前次包事实保留。

原生目录选择成功与取消由主验收链在 88da633 的安装 wheel 实测。最终 wheel 的 `launcher.py`、`local_runtime.py`、`launcher-ui.js` 与该轮 wheel 逐字节一致；三文件摘要记录在 `native-picker-byte-equality.json`，无需重复打开同一原生窗口来获得相同实现证据。最终安装的其它 UI 已在本轮新 venv 和新业务副本复验。
本次不创建或采用新业务候选，不代替真实 Host 连续制作、恢复后重新编译导出或用户视觉确认。此前三次脚本未完成运行及截图完整保留：前两轮等待条件未绑定实际图层/历史加载，第三轮在异步规范恢复完成前即时判断按钮；最终运行收紧这些等待后通过数据与恢复检查，最终历史布局修复后重新完成全部上述浏览器检查，没有遗留该缺陷。
