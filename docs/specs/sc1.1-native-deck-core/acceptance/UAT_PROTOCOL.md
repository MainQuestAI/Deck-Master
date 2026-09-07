# 真实UAT与证据操作规程

## A. 先证明不依赖外部产品

创建隔离用户目录与运行环境；保留宿主必要工具授权但隔离旧Skill、PPT Master repo、绑定文件和后端PATH。记录允许存在的基础依赖。安装发布树而非只从开发checkout运行；隐藏checkout后运行一次。不得通过复制全套上游仓库到新的“native”目录来满足隔离。

先用已批准合成内容测试compiler和真实render；再用同类内容实际调用ImageGen、图像理解/SVG重建，完成两页默认生产。记录文件/进程访问，确认没有旧后端发现与调用。没有客户素材不能成为跳过该步骤的理由。

## B. 验证编译与真实编辑

七类页面与复杂中文/路径/透明度样例先做差分，再在实际支持的演示软件打开PPTX。修改一个中文标题、一个架构group、一条箭头/路径及一项颜色，保存再开并渲染，确认不是图片或隐藏覆盖。记录软件/版本/OS/字体，不推断其他平台支持。

SVG→PPTX保持既有固定环境测量门；图片→SVG按五维视觉量规评分，保留实际图与逐页理由。critical文字和业务关系任何错误都不能被平均分掩盖。材料/图源使用授权范围；公开报告只含脱敏hash和摘要。

## C. 原材料完整生产与修订

准备8—12页的合成授权业务场景，输入是原材料/目标/边界，而非逐页稿。材料后部放关键约束；设一个可公开研究缺口和一个不能靠公开研究得到的客户事实。让Agent完成Context→Solution→Narrative→Package→图片/SVG/PPTX→审查/修复；观察是否仍反复要求用户提供专业内容。

在明确的用户批准动作后导出。再只修改某页配色/文字，验证无关页hash与业务决定保留；再改跨页组件关系，验证完整影响集。每次新文件最终批准不复用；旧批准文件保持。

## D. 三类真实客户效果

继续原SC-1三类样本×两次配对，冻结首次完整稿，记录主动阅读/补写/纠错/审批时间、新增字符、无谓澄清、改写页数、首稿可保留页和六维评分。不能用返修后的稿当首稿；失败/所有重试保留。

对照条件包括材料、宿主模型、授权工具、预算与风格范围。旧标准后端无法运行时，不为满足旧身份要求强行绑定PPT Master；使用可验证的历史实际流程/旧HD，明确非等价条件。缺可比对照不得算提升；继续报告outcome_pending。

## E. 证据文件最小字段

case_id、source_sha、environment、install_manifest_hash、run_id_safe、origin_mode、engine/subset版本、authoring_mode、input_hashes、output_hashes、tool_observation、actual_commands、result、failure/retry_counts、reviewer与范围、approval_revision、限制、私有证据位置引用（公开报告脱敏）。

本包JSON样例不能导入作为真实smoke/审批；代码测试可用其结构，必须单独构造test evidence。状态必须区分not_run、blocked、failed、passed；“未执行”不写成“发现运行故障”，也不写成passed。
