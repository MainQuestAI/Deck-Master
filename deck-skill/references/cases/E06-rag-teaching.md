# E06｜方法讲解与取舍

性质：synthetic 教学案例的方法讲解；输入与前后稿均为虚构或手写编辑示范，不是模型实验结果。

[输入](../../assets/content/examples/E06-rag-teaching/input.md) · [普通稿](../../assets/content/examples/E06-rag-teaching/before.md) · [改进稿](../../assets/content/examples/E06-rag-teaching/after.md)

主要调用：M03、M05、M09、M10。


## 分析摘要
保留Gemini最有价值的反差、近似反例、类比失效点和操作示范。将技术结论改为待比较的路线；把台风“自动免责”改成多条件判断，并补迁移题及反馈。

## 取舍
受众已有RAG基础，删除重复定义历史；保留定位粒度与阅读粒度的解释，因为它改变工程判断。原例0.51仅作为虚构输入；不保留0.93改进或“彻底消灭”承诺。

## 审阅要点
[Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)是可参考的工程方式，不证明本例必获同样效果。测试配置、真实召回与回答表现需要Codex核验。输入原文与生成索引文本分别追溯；完整来源也不等于已证明答案正确。


这些文件是同一案例的不同用途，按当前任务需要读取；案例事实不得成为新客户项目来源。
