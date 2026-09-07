# SC-1.1 Q0｜复用 vs 重写（reuse-vs-replace）

## 提取为 native 内核（单一实现，物理迁移 + HD 薄 re-export）

| 源模块（high_density/） | 行数 | 内部依赖 | 处置 |
|---|---|---|---|
| `pptx.py` | 1308 | python-pptx、ElementTree、subprocess（渲染探测） | `git mv` → `native_pptx/compiler.py`；保留函数签名 |
| `svg_native.py` | 807 | contracts、svg_paint | `git mv` → `native_pptx/svg_native.py` |
| `svg_paint.py` | 210 | contracts | → `native_pptx/svg_paint.py` |
| `svg.py` | 1337 | blueprint、subprocess、ElementTree | → `native_pptx/svg_tools.py`（SVG 解析/规范化/绘制管线） |
| `visual.py` | 944 | blueprint、contracts、platform | → `native_pptx/visual.py`（渲染/视觉检查） |
| `contracts.py`、`blueprint.py` | 共享 | — | 随迁（无 Run/项目语义，纯 IO/hash/清单辅助） |

- 高密度 `engine.py`/`content.py`/`blueprint.py`（业务编排/MBB/内容锁）**留在 high_density**：属于编排层，不是编译内核。
- `high_density/` 下被移动的模块名改为薄 re-export shim（`from native_pptx.compiler import *` 等），保证 engine.py、测试与外部 import 不破坏——**同一实现，两处入口**，满足"不能复制两套"约束。
- python-pptx 是 pyproject 已声明依赖；无新第三方依赖需要吸收。subprocess 调用（渲染器/系统工具）保留，但 native 就绪探测不得调用外部 PPT Master 目录/命令。

## 重写/新增（不是提取）

| 新对象 | 职责 |
|---|---|
| `native_pptx/api.py`（NativeCompileRequest/NativeCompileResult facade） | 哈希校验、路径安全（跨 Run/逃逸拒绝）、engine_version/subset_version/trace 输出 |
| `build/native_engine.py` | Run adapter：Package/Lock/Scene → 编译输入 → artifact/build/render/lineage 写回；env 修正错误码 NDC_* |
| `build/build_route.py` | build_route.v1 固定与解析（engine_id/authoring_mode/density/library_mode/origin_run_mode） |

## 不重写

SC-1 的 Context/Research/Solution/Narrative/Page Package/Diagram/质量/反馈全保留；PPT Library 索引算法、第二技术栈（PptxGenJS）、通用 SVG 浏览器均为非目标（spec 00 §0.4）。
