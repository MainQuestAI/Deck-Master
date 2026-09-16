# 拟实施往返命令与结果（全部为协议例）

`staging/`中的文件代表被分配operation的临时目录内容；实施时复制到任务返回的实际staging，不能直接把本Spec目录声明为批准写入范围。

```bash
# create或continue返回真实task/operation/produced_against；下列尖括号不是可运行值。
deck-master task start --project <项目> --task-id <任务> --execution-ref <真实Host执行>
# 若本次需要调用图像工具，必须先取得调度分配的名额：
deck-master task call begin --project <项目> --task-id <任务> --allowance-id <分配名额> --execution-ref <真实Host执行>
# 执行真实工具后结算；未实际执行不得填consumed或伪调用ID。
deck-master task call settle --project <项目> --task-id <任务> --allowance-id <名额> --outcome consumed --report <真实报告.json>
deck-master task accept --project <项目> --task-id <任务> --operation-id <本次操作> --produced-against <真实依赖hash> --result <信封.json>
```

预期：合法compose/repair结构经全部语义与引用校验后原子产生新Page；相同operation/相同内容再投返回already_applied、同一revision；同operation不同结果或旧输入返回conflict/late_result，current不变。首次正文被采用后主Skill自动view --open，然后继续制作。

blueprint.json/reconstruct.json展示“格式成立但不足以证明工作已完成”：未执行真实图像工具、缺真实原图或正文不完整，不能因为信封合法就回填任务成功。reconstruct-with-reference.json补齐引用形状，但仍未经过真实视觉/完整性检查。review.json的not_evaluated必须保留。invalid-path-escape与invalid-type-discriminator在信封层拒绝，引用不存在或同页scope冲突在跨对象层拒绝。

使用既有五合同校验最终对象；这些信封不是第六个长期schema。所有Response的file/ref/hash由接收器实际写入后计算，Host不得提交一串伪hash证明成功。

## 完整引用正例

reconstruct-complete.json与minimal-page.json、project当前Document、staging/complete-page.svg组成自洽的三atom正例：源图是独立的合成用户参考SVG，输出SVG另有正文绑定。complete-roundtrip-expected.json列接收后的预期。此例可以进行格式/字节/全文映射核验，但没有执行实际编译、图像渲染或Host制作；不能冒充ImageGen路径验证。
