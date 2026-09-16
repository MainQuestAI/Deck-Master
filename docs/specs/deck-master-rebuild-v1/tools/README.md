# 只读清单展开工具

```bash
python tools/materialize_inventory.py \
  --repo /实际/Deck-Master仓库 \
  --ref 2a866cf138f6359f853db35e0a926ad79391b691 \
  --out /tmp/deckmaster-rebuild-inventory
```

该提交必须已经在本地；工具不联网、不fetch、不checkout。只读Git树和CLI源码AST，不执行产品代码。输出目录必须在仓库之外，包含逐跟踪文件处置、静态CLI字面量和未分类路径。

REVIEW项、prefix项的具体消费者、缺失目标是否应新建，以及所有删除前置仍需要Codex核验。工具绝不输出或执行自动删除脚本；行数不等于无效代码量。root文档中拟建路径在旧树缺失是允许情况，不能因此伪称文件已存在。


## 文档包与合成示例校验（v1.1）

```bash
python tools/validate_spec_pack.py --pack /解压后的/Deck_Master_Rebuild_Spec_Pack_v1.1_20260916
```

需要复现v1.0的未知原件哈希冲突、并比较原始依据和旧路径清单是否保留时：

```bash
python tools/validate_spec_pack.py \
  --pack /解压后的/Deck_Master_Rebuild_Spec_Pack_v1.1_20260916 \
  --baseline-zip /历史文件/Deck_Master_Rebuild_Spec_Pack_v1.0_20260916.zip
```

依赖`jsonschema`。只读文件，JSON结果输出到stdout；退出码0表示本工具检查通过。存在`FILES.sha256`时还会核对清单覆盖及文件字节；`--baseline-zip`可选，不联网、不安装依赖、不访问产品仓库。

工具检查五Schema与合成对象、具体文件引用、样例设计配置、稳定atom、Review替换关系、临时信封、静态额度算例、任务依赖及文档关联。负例中有些故意通过JSON Schema、但在例级跨对象检查中失败，不能把两种检查混为一谈。

它不调用产品代码、模型、编译器、浏览器、安装器或真实外部工具；未验证并发原子性、实际字体、UI自动出现、视觉保真或业务价值。实施后仍需Codex运行对应验收，不能把这个脚本变成替代产品测试的门禁。
