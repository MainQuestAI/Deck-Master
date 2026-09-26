# W04：缩略图与个人画廊状态核心

基线 `f3c9b617b868748ea09765ff072858f563f65b8f`（W03 前端 PR #46）。本切片增加共享读取、缓存和个人状态；画廊界面在核心合入后接线。W04 未整卡验收。

画廊状态保存固定版本、图层、2/3/4 列、网格/连续/比较模式、最多 4 个 page_id、章节/状态筛选、阅读锚点、缩放及个人参考原图。引用必须属于对应版本和页面；切换顺序不会改变选择身份。文件独立于 Document 与 Recipe，CAS 冲突不覆盖另一个窗口，同内容重放返回原回执。参考文件后来丢失时保留已保存状态及诊断，允许删除失效参考后继续保存。

缩略图以逻辑项目身份、原图 hash 和派生算法版本为键。首次画廊读取启用缓存，此后新入库的栅格 Artifact 由两个本地后台线程尽力预热；既有图片按读取渐进生成。队列最多等待 64 项，前台读取可提升待执行预热的优先级。中断的派生在下次访问重建，不追加 Host 调用，不改变业务任务调度。PNG/JPEG/WebP 缩至最大 480 像素；SVG 需要本层已记录的栅格预览，未添加隐式渲染。

派生前校验对象路径、文件类型、大小与原图 hash；原图上限 64 MiB / 3200 万像素。缓存验证项目归属、schema、来源文件签名及派生字节 hash。先原子写图片，再发布清单。损坏缓存有明确失败和重试，重建只修改派生文件。原图、版本和内容身份保持不变。

| 接口 | 行为 |
| --- | --- |
| GET/POST `/api/gallery` | 读取/条件保存个人状态；只读样例允许个人状态写入 |
| GET `/api/thumbnails?path=…&sha256=…` | 返回 ready / queued / running / busy / failed / unsupported；显式 `retry=1` 重建 |
| GET `/api/thumbnail-file?cache_key=…` | 只读取已验证派生，按不可变键缓存 |

新增 `ui-gallery.v1`、`thumbnail.v1` 活动 schema，规格目录镜像保持字节一致。接口沿用 Host、Origin、实例 token 和体积限制；健康响应新增能力列表。CSP 仅为图片增加 `blob:`，脚本仍限同源、object 禁用。真实 Chromium 已验证恶意 SVG 经 Blob 图片解码后不执行脚本、不发起其中的外部请求。

显式 `samples.create_gallery_sample` 提供 24–300 页混合样例：三个章节，2 页偏离、2 页缺原图、2 页失效 PPT 预览，且旧版原图完整保留。SVG 和 PPT 预览分别绘制并标注 synthetic，未伪造 PPT 文件、Candidate、Attempt、Host 调用或专业通过。用户 30 秒定位观察尚未进行。

## 验证及限制

核心/HTTP/旧读取/schema/边界组合 98 passed；加入丢失参考恢复后，任务回执、生成协议、原生流水线等相关组合 89 passed / 2 render deselected。混合样例加入并修正一个错误预览分配后，最终新增测试文件 20 passed。Ruff 和 diff 检查通过。

```sh
PYTHONPATH=src python -m pytest -q tests/rebuild/test_gallery_core.py
PYTHONPATH=src python examples/workbench/w04_core.py --out /tmp/w04-core-example
```

[可复现脚本](../../../examples/workbench/w04_core.py)与[原始检查](w04/core/checks.json)：7 项检查通过；30 张 960×540 原图派生至 480×270，后台并行峰值 2。macOS 27.0 arm64、Python 3.12.12、Chromium 149.0.7827.55；核心批次冷读取 0.107 秒、热读取 0.026 秒。这不是浏览器首屏指标。平色样例在抗锯齿后 PNG 总字节反而增加，因此不据此声称传输量下降。

前端共享网络/解码队列、LRU、筛选、并排、矩阵与两视口测试留给下一切片；完整 300×5×3 压力待 W07 真实 Candidate 契约后补证。30 页热首屏 ≤2 秒仍待浏览器测量，W10 负责 20 分钟内存验证。未更改默认入口、真实 HOME 或发布状态。
