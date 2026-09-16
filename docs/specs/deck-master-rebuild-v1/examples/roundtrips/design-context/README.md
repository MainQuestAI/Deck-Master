# 制作配置往返

当前Document rev_design_002保存4:3逻辑/物理画布、指定字体名、Logo对象Ref、两套style。p09使用default，p10使用alternate。前一版本rev_design_001可比较：只改default的accent，正文和p10有效配置未变。effects.json给出预期影响，不是实际生成结果。

字体声明没有附带文件，不能据此断言目标环境可用。实现应解析实际文件指纹；缺字体报告，既有媒体仍可打开。Logo/icon等已有字节跟随project移动；不回读本机旧绝对路径。测试者应在实现后分别核验prompt、PPT实际尺寸、UI和局部修改，不只检查Document字段。
