# 开发执行记录 2026-09-20

接续 [development-progress-20260916.md](development-progress-20260916.md)。

## 阶段 0：环境修复

- `.venv` 补装 `setuptools`，修复 test_install.py 两个打包用例的环境性失败；`tests/rebuild` 全绿口径统一为 137 passed。

## T08 整卡关闭：纯SVG接口与派生IR

- 新建 `tests/rebuild/test_svg_parser.py`（43 项，全部通过）：`test_svg_to_ir` 覆盖 spec 06.2 全部正向条目（基本几何含 path M/L/H/V/C/S/Q/T/A/Z 绝对/相对、嵌套变换 translate/scale/rotate/matrix、linear/radial gradient 含 stop-opacity、中文多行 tspan、symbol/use 含 viewBox 缩放、批准 PNG 三种 preserveAspectRatio、直线端点方向、data-atom-id 绑定、无关 data-* 属性放行）；`test_unsupported_and_unsafe` 36 个参数化反例，断言 SvgError 且诊断含 page/element 定位与 recovery，不静默删图。
- 修复 3 处实现 bug（均在最早出错层，未削弱既有拒绝行为）：
  1. `src/deck_master/compiler/geometry.py` `_parse_path`：arc flags 经 `int()` 截断，`sweep=0.5` 被静默当 0；改为严格校验 in (0.0, 1.0)。
  2. `src/deck_master/compiler/svg.py` text 分支：x/y/font-size/letter-spacing/dx/dy 裸 `float()` 解析，nan/inf 静默入 IR；新增与 `num()` 同措辞的有限性检查。
  3. `src/deck_master/compiler/svg.py` style 预处理：缺冒号声明抛裸 ValueError；改为显式 `malformed style declaration` 可定位诊断。
- AC-K09（不支持与安全）与 AC-B06（单手写源）由本卡关闭；AC-K01 实际隔离 PPT 生成仍归 T10。
- 验证：`.venv/bin/python -m pytest tests/rebuild/test_svg_parser.py -q` → 43 passed；`tests/rebuild` 全量 → 180 passed（原 137 + 新 43）。
- 状态同步：`task-cards/tasks.json` 与 `subtasks.csv` 中 T08 及 T08.01–T08.05 标记 `implemented_verified`；T08.md 交接回填已记录。
- 工作树待提交变更：`src/deck_master/compiler/geometry.py`、`src/deck_master/compiler/svg.py`、新建 `tests/rebuild/test_svg_parser.py`（用户确认后提交）。

## 下一动作

T09 已关闭（见下节）。WP02 余下大卡为 T10（真实渲染与首段完整闭环）。

## T09 整卡关闭：绘制缺陷逐项修复

- 修复 3 处 DrawingML 写出缺陷（`src/deck_master/compiler/native.py`）：
  1. shape spPr 子元素顺序错误（fill 落在 ln/effectLst 之后，违反 DrawingML 序列，桌面 PowerPoint 会判需修复文件）→ geom→fill→ln→effectLst；
  2. text rPr 子元素顺序错误（fill 落在 latin/ea/cs 之后）→ fill→latin→ea→cs；
  3. 旋转文本双重变换（预定位块 + sh.rotation，探针实测盒子漂移出负坐标）→ 删除预定位，glyph 旋转只由 sh.rotation 承担一次。
- 测试：新建 `tests/rebuild/test_text.py`（5 项，字体经 fc-match 解析本机 Hiragino Sans GB，含 fallback 与缺字体报错契约）；扩充 `test_geometry.py`（+5：正/负斜率与反向线端点方向、旋转圆 190500×190500 EMU、旋转椭圆解析极值、等比缩放圆角与图标描边、非等比带描边显式 SvgError）；扩充 `test_paint.py`（+2：fill/stroke opacity=0 写入、组 opacity 相乘含 0）。全部经 compile_deck 真实 PPT 解包 slide XML 读回。
- AC-K02–K07 六条由本卡关闭；桌面 PowerPoint 实际打开编辑仍归 T10/T23 人工层。
- 验证：定向 20 passed；`tests/rebuild` 全量 193 passed（180+13）。
- 状态同步：tasks.json/subtasks.csv 中 T09 及 T09.01–T09.05 标记 `implemented_verified`；T09.md 交接回填已记录。
- 工作树待提交变更：`src/deck_master/compiler/native.py`、`tests/rebuild/test_geometry.py`、`test_paint.py`、新建 `test_text.py`。
