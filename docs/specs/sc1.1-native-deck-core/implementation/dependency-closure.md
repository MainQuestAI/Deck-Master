# SC-1.1 Q0｜依赖闭包（dependency-closure）

## native_pptx 提取闭包（实测 import 图）

```
pptx.py          → python-pptx, ElementTree, subprocess, stdlib
svg_native.py    → .contracts, .svg_paint, ElementTree
svg_paint.py     → .contracts, ElementTree
svg.py           → .blueprint, binascii, secrets, subprocess, ElementTree, stdlib
visual.py        → .blueprint, .contracts, platform, subprocess, ElementTree
contracts.py     → stdlib only
blueprint.py     → stdlib only（manifest/schema 常量）
```

- **第三方**：python-pptx（已在 `pyproject.toml` dependencies；本项目 venv 已装）。无新增第三方包需要吸收——七类样例回归是缺项裁决的最终依据（spec 03 §3.1：仅当样例证实缺项才按最小依赖闭包吸收上游）。
- **系统工具**：渲染/探测 subprocess 调用随 visual.py 迁移；native 就绪状态只依赖本次引擎版本/依赖/renderer/字体 probe（spec 05 §5.2），不得探测外部 PPT Master。
- **许可证**：python-pptx（MIT）、jsonschema（MIT）、Pillow/Numpy（pyproject 现有）；无新增分发组件——GOV-02 以"实际分发的必要组件"清单在 release 锁登记（ND-02 落地）。
- **字体**：中英文渲染依赖系统字体清单；fallback 记录在视觉检查报告中（未验证 fallback 不得通过标题/关键段回读）。

## 高密度模块对 native 的反向依赖（迁移后）

`high_density/engine.py` 经 shim re-export 使用 native_pptx 实现；`engine.py` 对 `build/manifest.py`（v2 投影）、`production/page_package.py` 的既有依赖保持不变（PR-05 已消费）。
