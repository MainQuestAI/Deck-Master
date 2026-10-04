# 冻结版本打包、隔离安装及离线 UI 验证（修前证据）

以下记录对应 visual-style 迟到响应资源泄漏修复前的 `ece47b3`。后续生产代码已变化，这批结果保留为历史证据，不能作为当前最终包门禁通过；修后版本须重新构建和验收。

2026-10-04，冻结提交 `ece47b3c5df3da43c454c6b5eea683ba893a2b46` 的包验收通过。官方构建 manifest 记录 `source_dirty=false`，版本为 `1.0.0.dev2`。这是当前开发包工程检查，不是 RC 发布或用户视觉认可。

## 构建与资源

| 验证 | 实际结果 |
|---|---|
| 官方 `tools/build_release.py` 构建 wheel 和来源 manifest | 通过；固定完整源码 SHA，构建前工作树 clean |
| 同一冻结源码的 sdist，再由 sdist 构建 wheel | 通过 |
| 两个 wheel 的全部 `deck_master/` 代码与资源 | 204 个文件摘要全部一致，其中 143 个资源文件 |
| 新截图能力的五份 schema | `style-input.v2`、`style-proposal.v2`、`style-recipe.v2`、`visual-style-spec.v1`、`style-reference.v1` 均可读 |
| 安装后的方法及 UI | `visual-reference.md`、`visual-style.js`、比较画布 JS/CSS、导航可用性 CSS 均可读，与 wheel 摘要一致 |
| 冻结源码保持 | 验收结束再次核对源码、唯一公共 Skill 与打包配置的逐文件摘要，无变化 |

Wheel SHA-256：`b0f58e71d9399ad5004308fb9d6d5940087b9cee5856e80b138ba0fcec792189`。  
Sdist SHA-256：`b09605984033daa1f7d2d4add7172c1a0028fd8576058253ffcc8a3d4e820474`。

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

旧 release：`6996a29b1792-4272688c3429`。  
新 release：`ece47b3c5df3-b0f58e71d939`。

## 证据及剩余边界

构建日志、两套 wheel、sdist、官方 manifest、安装记录、逐文件资源摘要、独立 venv、离线 HAR、下载 ZIP 和截图保存在本轮私有包验收证据中。没有提交生成物到仓库。

本机原生目录选择成功/取消、最终 PR head CI、完整核心与长跑、真实业务闭环及用户新版 UI 的视觉确认分别由主验收链记录。本报告不把这些未在本子任务执行的项目计为通过；也没有自动合并、打 tag 或发布 RC。
