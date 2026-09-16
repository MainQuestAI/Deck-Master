# fixed完整往返

1. revision_001引用旧SVG Artifact A0与失败Review R0。Page规定一个必要标签；R0保存实际缺失应怎样描述。
2. repair产生新的SVG A1，旧文件不改。此例只表达该标签的局部变化，不是一份完整可用页面。
3. 针对A1重新检查，生成新Review R1：同review_id/finding_id，replaces=R0，subjects=A1，包含独立Page期待与新SVG/复查记录。
4. revision_002引用A1和R1；旧revision/R0保持失败历史。另两份invalid例即便通过JSON格式，也不能通过实际跨对象/检查规则。

所有SVG、review文字与报告均为合成协议演示。没有真正执行产品repair/check、模型阅图或专业验收；PACK验证只核对格式、hash与例中关联，不能证明真实审阅已经发生。
