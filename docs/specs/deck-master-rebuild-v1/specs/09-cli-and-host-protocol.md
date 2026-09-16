# 09｜CLI与Host执行协议

## 09.1 主命令的最终语义

以下为拟实施的公开接口，不是现有CLI。`--project`接自动建立的产物目录；允许兼容`--run-dir`别名，但内部一律同义。所有命令支持`--json`；默认人类输出简洁，Host默认使用JSON。

| 命令 | 必要输入 | 实际动作/返回 |
| --- | --- | --- |
| `deck-master create --brief task.md --source file1 --source file2 --out project [--design design.json]` | task文件/文字、资料、输出位置 | 创建最小Document、来源与明确design_context；已有完整稿可用`--draft`省compose；返回待Host任务，不宣称生成完成；桌面主Skill首次接收到页即自动view --open |
| `deck-master continue --project project` | 项目 | 运行可执行的本地动作，返回稳定的下一批Host任务或当前检查/成品；不重新询问已经确认内容 |
| `deck-master edit --project project --page p09 --instruction changes.md` | 范围与修改要求 | 创建修订任务，返回task与影响范围；没有Host运行不能显示修改完成 |
| `deck-master view --project project --open` | 项目 | 启动/复用loopback审阅服务并打开当前任务；浏览器不可开则给实际URL |
| `deck-master check --project project` | 项目 | 执行当前适用的实际文件检查；需语义/视觉阅稿则产生review任务 |
| `deck-master export --project project --purpose review|delivery --out target` | 用途与本地目标 | 输出当前文件、预览/说明；review可未通过且标识，delivery遵循07章 |

不给用户增加六个必须顺序手动执行的阶段。主Skill通过create/continue/task accept在同一个任务内完成正常链路，用户只需要给任务或修改意见。

## 09.2 必要辅助命令

- `task accept --project ... --task-id ... --operation-id ... --produced-against <hash> --result result.json`：接收Host结果，校验并原子应用。
- `task start/status/cancel --project ... --task-id ...`：start带`--execution-ref`实际认领，另一执行者冲突；查看/用户停止不冒充执行。cancel可有原因但不强制长表单。
- `task call begin --project ... --task-id ... --allowance-id ... --execution-ref ...`：调用前原子取得一次许可；重复请求返回already_started，不允许重发外部调用。
- `task call settle --project ... --task-id ... --allowance-id ... --outcome consumed|not_sent|unknown --report report.json`：结算真实调用观察；报告不是永久第六对象，状态由service推导，详见08.6。
- `import asset --project ... --asset-id logo-main --kind logo --file ./logo.svg --external-use allowed`：保存真实媒体为asset Artifact；登记不等于所有页面自动使用；同ID换字节形成新版本。
- `design update --project ... --input design.json --expected-revision ...`：规范化制作配置并提交新Document；不接受任意运行脚本或外链资源。
- `task retry --project ... --task-id ...`：明确对失败/取消任务建立新尝试，沿用真实输入、保留历史，不清零原记录。
- `import draft --project ... --input draft.json`：接收完整Page列表；可用不含旧run的create --draft。
- `import legacy --input old-run --out new-project`：读取/副本导入，原run不写；先inspect dry-run再实际导入，不执行旧脚本。
- `history list/restore --project ... --revision ...`：查看/恢复为新版本，不删除历史。
- `doctor --project ... --step compose|blueprint|compile|render|view|export`：只核实该步实际依赖与安装来源。
- `install/rollback`：维护入口，实际参数由11章指定；不能作为每份成稿前置。

旧93命令不全部搬过来。少量明确别名在下面列出，其余返回旧命令已退出说明与正确的新用例，不执行旧OS，也不自动操作旧数据。

## 09.3 JSON响应与退出码

通用响应：`status, project_id, revision_id, requested_action, result_refs, pending_tasks, findings, next_action, review_url, view_status, evidence_level`。view_status包含service/browser状态及具体原因；无效服务不得输出伪URL。无值用null/空数组，不伪造URL和文件。

| exit code | 含义 |
| --- | --- |
| 0 | 本次请求的本地动作已成功（例如任务成功创建）；须读status区别整稿状态 |
| 2 | 无效命令/参数/输入契约；具体字段与修复方式 |
| 3 | 执行型continue/check因外部Host、工具或真实决定暂不可继续；status awaiting_host/needs_input/needs_tool |
| 4 | 实际执行或检查失败，保留失败产物与位置 |
| 5 | 输入版本冲突/旧结果/已取消，不改当前 |

创建/取消/查看可返回0，而整稿仍pending；自动化不得用进程exit0写“成稿通过”。单独`check`有must_fix返回4，未执行关键审阅返回3。JSON中ready结论统一来自view/review。

错误至少有code、message、page_id/element_id（适用时）、expected/actual、next_action。不从英文异常字符串猜测业务身份，不吞异常后返回空成功对象。

## 09.4 Host输入和输出

Task的Host种类为compose/blueprint/reconstruct/review/repair；compile/render/check是service自己执行的本地动作，不派给Host补“运行回执”。

Task.inputs是实际可读Ref；response另外提供从同一Document解析的工作内容、resolved_design_context、当前允许资产路径及本次安装的method资源路径，避免宿主只能看manifest hash。原图任务直接提供图像路径/引用，Host实际看图。每个任务有scope_pages和produced_against，不能由Host自行缩小必要输入或修改自己的预算证明。

compose.result：完整Page v2数组、明确页面顺序、来源映射及任务相关说明。blueprint.result：实际图片文件、可得工具调用/实际prompt、观察。reconstruct.result：SVG文件和必要绑定；不提交手写Scene。review.result：Review v1观察和具体发现。repair.result按目标Page/SVG/Review输出相应新对象。

`result.json`只是接收信封，判别字段固定为`kind`（不再混写type）；files声明临时文件，其他有效载荷按下文09.7解释；不新增永续结果schema平台。程序根据Task.kind校验对应Page/Artifact/Review，文件必须在该operation批准的staging或显式用户选择路径，不允许借result写任意项目路径。

## 09.5 宿主执行循环与默认工作台出现时机

1. 读取任务和既有决定，create或继续已有项目；有完整稿直接导入。桌面正常任务不要求用户额外手动执行view。
2. **create --draft、import draft或compose结果第一次成功形成至少一页后，主Skill必须立即自动调用`view --open`，在继续逐页制作前给出实际工作台入口。**service响应返回需呈现工作台的next_action；Skill执行该动作，不把任务丢回用户。正文已存在但制作失败，也必须看得到。
3. 同项目后续修改/继续复用原服务和URL，不每次开新端口或重复弹窗。仅服务失效时重启并更新实际URL；不能为了“相同URL”声称失效地址有效。已有有效服务由本安装健康检查确认。
4. 读Task全部相关正文、源资料、实际图片及解析配置，应用本次kind的方法；外部调用前按08.6分配/begin，结果实际结算，不伪造工具行为。执行真实工作并submit；冲突读取新输入，失败按具体错误修改。
5. continue推进实际制作/当前检查；需要Host审阅就实际看原图与产物。每次稿件更新与首份完整候选交付都提供该项目现用入口与相关页链接。零产物、失败、待Host、未评估如实显示。

纯CLI批处理允许`--no-open`：不调用浏览器，但应返回view_available/可执行查看方式，若已启动服务则给真实地址。无桌面浏览器但可提供本地服务时仍启动并返回真实loopback URL，明确它只在该主机可达；禁止自动公网暴露。无权限/端口/进程能力导致服务不可启动时view_status=unavailable、review_url=null并说明原因，保留文件路径，不伪装完整桌面交互已验证。

服务启动请求有界等待/健康检查，不以看不到UI为由无限阻断正文和编译；失败明确进入待修功能。没有后台Host进程，工作台只记录反馈并等待Host，不能假称AI会自行完成。用户可从持久化Task继续，不需每阶段回复“继续”。

## 09.6 旧命令映射

| 旧入口 | 新处理 |
| --- | --- |
| import-plan（完整稿） | 转换v1→v2后import draft，源数据不改；不能丢未知字段 |
| build prepare/run/status | 新项目映射continue/view派生状态；旧项目要求legacy import或固定旧版 |
| next-step/run-state/final-readiness | 新项目返回同一ProjectView；不运行旧state resolver |
| export（本地文件） | 明确purpose；旧approved queue不能代替当前产物 |
| start-conversation/build-brief/build-claim-map/autoplan | 给出create/现有完整稿导入指引；不隐式生成规则稿 |
| search-library/decide-sourcing | 新核心不实现整页库流程；提示用来源文件或显式旧工具 |
| 旧workflow/handoff/approval/team/learning/RC命令 | 明确退役，不转成新任务前置 |
| 其他旧命令 | 受控提示，不继续调用旧main；清单工具列出需要映射的所有真实命令 |

以旧run路径调用新写命令时先识别格式；不得自动就地迁移、初始化新pointer或误把旧completed当新通过。

## 09.7 临时结果信封的唯一形状与采用顺序

信封字段固定为：kind、files、pages、page_order、artifact_specs、reviews、usage_events、notes。可省略当前kind无关字段；未知字段返回具体输入错误，不静默忽略。不是第六个持久schema；解析器按Task.kind进行分支校验，最终只保存五类对象。

- files：`file_id,path,media_type`。path相对于该Task.operation_id的staging，不能包含`..`或跨根符号链接；显式用户外部导入另走import能力，不借Host结果写任意文件。file_id是信封内标识，不是假hash。
- pages：完整Page v2；compose需要全页数组及完整page_order，单页repair只能包含授权scope_pages。不能借更新p09省略其他页将其删除。
- artifact_specs：`file_id,role,page_id,derived_from,provenance,reference_regions?,limitations?`；source实际文件来自files，artifact_id、字节hash和依赖由service核验生成。provenance中提交prompt可以用`submitted_prompt_file_id`引用本信封文件；生成后替换为真实Ref。generated_from_page用已持久化Page Ref，不能补写旧图当时使用新正文。
- reviews：完整Review v1，subjects必须指已保存且实际核查的对象；不能用未知临时别名或自己生成的输出清单代替源预期。
- usage_events：`allowance_id,outcome,invocation_ref,evidence_file_ids`；只报告已有名额的实际观察，不授予额度、不接受覆盖call_allowances。调用事实即使产物接收失败也应通过settle保留，不能把业务事务回滚当作调用没发生。
- notes：普通说明，不进入对外正文或默认质量通过。

接收顺序：校验CLI的task/operation/produced_against与scope→规范化文件/正文/引用并预校验全部结果→保存不可变对象→在项目锁中重新核对依赖、取消与幂等→一次切换当前文档。相同operation同内容返回already_applied；结果不同或输入过期返回5且current不变；仍可结算已经发生的外部调用。

完整compose、blueprint、reconstruct、review及repair信封和往返结果见`examples/roundtrips/result-envelope/README.md`。这些是合成协议范例，不是API已实现或Host已执行。
