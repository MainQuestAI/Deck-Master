# SC-1.1 Q0｜宿主能力实测（host-capability-probe）

- 执行日期：2026-09-07；宿主：ZCode Agent（macOS arm64，darwin 25.6.0）

| 能力 | 探测方式 | 实测结果 |
|---|---|---|
| 文本推理/材料读取 | 本会话实际执行 | 可用（Agent 能力） |
| Python 3.12 venv | `.venv/bin/python --version` | 3.12（已装 `.[dev]`） |
| python-pptx | import | 可用（pyproject 依赖） |
| `ppt-lib` CLI | `which ppt-lib` | `/Users/dingcheng/.local/bin/ppt-lib`，2.0.1.dev0（可选 Library，非 native 必需） |
| PPT Master | 目录探测/PATH | **未安装/未绑定**（正是本包默认路线不需要的对象） |
| ImageGen（宿主图像生成） | 真实 host probe | **本会话未提供图像生成/视觉理解工具** → 默认 image_blueprint 模式下 host_tools 报缺失（doctor 须如实报，不得静默切 direct_svg/fixture；IND-08） |
| SVG/PPTX 渲染器（readback 视觉链） | HD visual.py 的 renderer 探测 | 需在 ND-01 差分时实测本地 renderer 可用性（记录于编译差分报告） |
| 桌面编辑软件（原生编辑检查） | 演示软件实际打开 | 本环境不可自动验证——UAT/桌面编辑用例标 not_run（真实宿主限制，不虚报） |

**对本轮的含义**：L2 验收中"真实编译/渲染/回读/原生编辑"可在本机完成的部分照常执行；需要 ImageGen 的 HST 组用例在当前宿主如实 blocked/not_run——不得以合成 SVG 冒充图片重建路径完成（ND-03 明确禁止）。客户素材缺失仅影响 L3。
