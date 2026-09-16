# 拟实施CLI使用示例（不是当前可运行教程）

```bash
# 实施后由主Skill在自然语言任务内调用，不要求用户逐项执行。
deck-master create --brief ./任务.md --source ./企业资料.md --out ./demo-project --design ./design.json --json
# Host读实际任务后提交完整稿：
deck-master task accept --project ./demo-project --task-id <返回ID> --operation-id <操作ID> --produced-against <实际输入hash> --result ./result.json --json
# 首份正文被接收：以下动作由主Skill自动执行，不是用户额外操作。
deck-master view --project ./demo-project --open --json
# 拿到健康检查通过的URL后继续；更新仍使用同一项目入口。
deck-master continue --project ./demo-project --json
deck-master edit --project ./demo-project --page p09 --instruction ./修改要求.md --json
deck-master check --project ./demo-project --json
deck-master export --project ./demo-project --purpose review --out ./review-delivery --json
```

create/accept返回成功不等于专业稿已完成；具体UI无浏览器/服务不可启动如实返回。原生图表“编辑数据”不在首版承诺内。外部工具调用前后遵循08.6的call begin/settle；没有调用不填回执。

信封判别字段唯一为kind，完整分支、文件和冲突/重复响应见[roundtrips/result-envelope/README.md](roundtrips/result-envelope/README.md)。这不是第六类永久对象。临时文件由task返回的staging解释，不能写成任意路径。
