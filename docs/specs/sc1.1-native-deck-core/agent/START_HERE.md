# 给 Codex 的执行说明｜SC-1.1 Native Deck Core

你正在继续MainQuestAI/Deck-Master。基础是PR #30 @ `4977f89573d18a282c605360dc55f751443a2b21`，不是回到PR29或重做SC-1。

**最重要的产品修正：原SC-1 D04“必须保留PPT Master默认后端”已被本包00正式撤销。用户要求取消该产品的必选依赖；默认路线是批准内容→图片蓝图→宿主视觉模型重建SVG→内置原生PPTX→回读。不要再让用户安装或绑定完整PPT Master作为开工/验收前提。**

## 开工顺序

读仓库AGENTS、再读本包00、01、02、tasks/DELIVERY_PLAN和acceptance映射。执行Q0，确认本地HEAD/未提交修改/真实调用图。将本包按仓库惯例放入建议目录`docs/specs/sc1.1-native-deck-core/`，写实际映射；该路径是建议，是否已存在需要你核验。

随后按ND-01→ND-02→ND-03→ND-04→ND-05实施。基于PR30后继做增量，不撤销其Context/Research/Solution/PagePackage/质量/反馈成果。若PR30尚未合并可stacked开发，不能为了开工擅自合并或force push。

## 必须贯彻

编译器优先从现有high_density代码提取，不能只是目录改名、复制两套或将整库静默捆绑。新默认route不得查询外部PPT Master绑定；保留显式旧Run兼容。doctor报告实际本次必需工具；缺ImageGen如实报告，不能静默切direct_svg/fixture。

检查并补CLI none、PagePackage ready_for_build一致性、公共Narrative→ContentLock/MBB单向投影、semantic精确类型、实际package内容指纹、next-step缺语义的动作、原子action提交和失败预算。不要把PR描述或函数注释当作已经通过的实际行为。

不要要求用户提供逐页稿、重做已确认主线或风格。专业工作由Agent执行；真实范围与最终文件批准仍由用户。新模型与图片能力用实际host probe证明，不硬编码模型名当可用性。

## 验收与交付

先固定原测试基线并加失败用例，随后补真实native两页/七类/8—12页全链路和桌面编辑。客户素材缺失只影响客户L3；合成内容真实工具L2仍需完成。对不能执行项准确标blocked/not_run。

每个增量提交输出：文件与调用方、相关验收ID、测试命令/结果、产物和hash证据、仍未实现/未验证、兼容及回滚。完成前重读旧88项映射，禁止遗漏未冲突SC-1要求。

不得擅自删旧Skill/后端/资产、重写events、伪造provider/quality receipt、降低门禁或把旧批准给新文件。全部本地事实、工具、测试和效果由你核验；没有证据不得填写passed。
