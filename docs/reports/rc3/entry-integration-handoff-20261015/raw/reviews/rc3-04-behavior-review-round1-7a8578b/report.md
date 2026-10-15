# RC3-04 R1 独立行为复核：REQUEST_CHANGES（候选整体）

固定 HEAD `7a8578baa210a92b92ae98922ff3236edf4d5975`，tree `4b7c5a931998ced2de624ee0ec29ff4a9e023139`。本 reviewer 的有界行为样本**未发现新增 must-fix**，12 条最终有效轨迹通过；固定候选仍不能给整卡 PASS：独立 code reviewer 已保留 F1/F2/F3/F4/F6 的实际失败，Root另有UI F5。本文引用这些独立原件，不把它们改称本 reviewer 自己复跑。它们的编号不是原规范严重度 F0–F3，也不改变原AC/CQ Owner。

这是工程行为复核，不是全 RC3、实际专业内容、真实 native reviewer、人类、Owner/听众、目标桌面或发布验收。没有修改产品、tests、产品 fixture、唯一台账或固定源码；没有 patch gate、伪造 trusted/native/human context 或 spawn。

## 候选、安装与执行身份

- HANDOFF SHA256：`4325a45365469c228ce9298b0d3281abacfaaabef1e499fc50bb539571555e95`。
- 当前候选 manifest：`50d1e8ce8ac3614757c8d1ad5f3dbb220a61cd3302a302fd9326f17664cab27e`；wheel：`8d52fd31f7d7321876973e0980401d8a834edfa744cd0bcf5f1b908d1b88e8ee`。
- **所有探针进程**实际运行 `/workspace/work/rc3/candidate-04-7a8578b/prefix/.deck-master/releases/7a8578baa210-8d52fd31f7d7/venv/bin/python -I -B`。`run1/runtime-identity.json` 保存运行 Python、`1.0.0rc3` 和实际安装 module origins；`run7/cli-create-raw.json` 另保存真实 installed CLI 子进程命令/stdout/stderr，实际工作单资源路径均指候选 site-packages。
- 独立脚本在本目录运行，未导入产品 tests/conftest/helpers，未加源码 PYTHONPATH。公开 SDK 是运行主面；CLI 真实子进程与使用原 WorkbenchHandler 的 loopback HTTP 也实际执行。HTTP 仅私有 CSRF transport token，不产生用户身份、受信 context 或人类能力。
- shell 显式 `PIP_NO_INDEX=1 PIP_FIND_LINKS=/workspace/work/rc3/wheelhouse TMPDIR=/tmp/rc304br1`。未跑宽 suite/render/ruff/browser/benchmark、模型/图像或安装激活；这些由Root另线承担。
- Root提供的3610 tracked before清单 SHA256 `5c380286fdaa93b39e1e768ed4050164de7c1566a3e75b906d34b7921d2ccf2f` 已核对；本次 `source-after.json` 逐文件重新hash，**3610/3610相同、changed=[]**。安装 manifest hash仍相同；本次未另重跑269 canonical+1generated的严格安装字节审计，Root的独立审计不是本 reviewer 的运行结果。

## 12组计划的实际覆盖与限界

| 计划组 | 本次实际运行 | 最终原始证据 | 没有据此宣称的范围 |
|---|---|---|---|
| G01 原子default/入口 | 默认SDK与CLI首次可见rank13、真实source、compose.v2/no grants；旧cap claim拒绝且Document不变；末页非法create不发布半项目。真实HTTP show/eligibility及wrong-project404、public context403，读/拒绝前后全树相同 | run1 results/default-visible/old-claim-*；run7 cli-create-raw/http-before/http-after/events | Studio创建宽路径、并发publish故障注入未由本 reviewer重复；import越scope失败引用code F1 |
| G02 migration/writers | 固定rank12无region历史对象：describe全树不写；import/inputs/edit三族正式旧写拒migration；apply一次升rank13，保留旧Page、request=null、无批准/授权；原base/op精确replay | run4 results/migration-*/legacy-* | 非全writer穷举；旧wheel回退、unreadable/unknown/in-flight迁移矩阵未由本 reviewer重跑 |
| G03 四层与事务 | 真实create→framing→argument→方向决定/采用→page_copy→新request/明确inputs更新→四层组合input_revision。实际Narrative语句、Plan角色/links、Page title、notes/Unicode segments同步改变，input_alignment=current，同一业务parent；重复Plan及末层speech夹正文均Document完整回滚；exact replay无新revision。合法merge/split新ID按冻结source scopes通过；预算放宽反例完整回滚、未选页保留、derivation精确 | run2 results/events/four-layer-*；run8 results/events/{split,merge}-* | 未逐个重复四单层；来源存在校验缺口按code F3阻塞，组合通过不抵消F3 |
| G04 正常退出 | plan_only有Narrative/planned Plan提案；write_only复用固定imported mapping；speech_only无Narrative写notes且正文不变；content_full实际分phase写Page/Plan。四条均completed/closed_reason=completed，连续continue同revision且pending=[] | run1 results/events与各*-completed-before；speech-only-before/after | write_only本样本为已有确认稿的合法立即完成；并非四条实际Host方法应用或专业检查质量证明 |
| G05 variants | 明确两variant声明；第一份真实content review export固定；第二份fresh Plan/pages/outputs且同Narrative，生成独立Plan/Page/export、单current；从第一revision/export窄notes edit，两个历史export全树hash不变 | run6 results/events/variant-*及实际两个export目录 | 本次是content-only真实text/HTML/manifest文件，不是两份完整制作PPTX或两种用途效果验收；共享总费用/第三版矩阵未重跑 |
| G06 still-running stale费用 | **明确历史L1** Task仍running、原produced_against匹配、audience basis陈旧，本次late accept带合法原allowance证据。先committed consumed/host_reported/invocation/evidence，再StaleInputContext；稿件/控制不变 | run5 results/events/hist-still-running-before/after | 不是实际模型/货币费用，也不是current-RC3受信native执行。run3真实公开P2修改保留P1 Task freshness，证实那个初选输入没有命中stale，未报缺陷 |
| G07 祖先撤回/最后额度 | run3公开单allowance reserve/begin与scope许可可从事件复核；**本组目标未完成，NOT_RUN** | run3 running-stale-before-late/events | 不宣称parent撤回/remaining0 accept/adopt或实际计费已由本 reviewer通过 |
| G08 replay/capability/restore | exact terminal replay、旧Host缺cap拒新Task；merge/split新ID lineage见G03 | run1/run2/run8 | restore/cancel/祖先费用不回滚全矩阵本 reviewer NOT_RUN，不借局部成功关闭整组 |
| G09 lineage/reviewer | page_copy作者P经speech作者S修改后两者仍在实际作者排除集合；明确新full_deck请求缺真实reviewer，cap三项false、needs_reviewer并返回完整Narrative/Plan/所选页正文+notes packet，不新派伪review Task | run4 lineage-after-speech；run5 lineage-verification-* /results/events | 没有实际独立native/human正例；packet实际键是manuscript，不将早期探针读错键当产品错误 |
| G10 strict/import | fileset与project严格evaluate源全树/current/cache/log不写，源内output和symlink拒绝；外部固定Page报告普通host_self/needs_review显式import精确映射成功；wrong Page mapping、JSON independent身份提升均拒且Document不变 | run1 external-source/external-report/events；run4 report-* /results/events | 普通report只保留原证据等级；本次SDK报告返回正确不代表adapter gap状态正确，CLI/HTTP needs_reviewer映射由code F4反证；不伪造受信正例 |
| G11 实际最终文件 | 实际PPTX+中文/emoji notes经sanitize导出；pptx_notes与pure_reading最终raw SHA不同，逐页回读分别原注/空注；exact file describe只读且准确命中选定hash，changed bytes拒绝；工程未齐诚实blocked、policy=false不宣称human | run7 projection-readback/selected-output-query-*；run6 actual-projection及两个真实PPTX exports | 原关联为显式L1 seeded engineering association，不冒充完整生产。没有人类正例、历史current policy/review全矩阵；发布期间pause race由code global F6反证 |
| G12 安装/方法/适配 | 实际installed module与CLI工作单方法路径/hash；同候选HTTP Runtime投影/拒绝/只读一致 | run1 runtime-identity；run7 cli-create-raw/events/results | 四Skill真实Host16路径、安装links生命周期与独立UI由Root另安排，不以字节加载冒充Host已应用 |

## 初次探针失败如何保留

共有23条case执行记录：12条最终有效PASS，11条初选输入/场景/断言失败全部保留。它们没有被统计为产品must-fix，也未从原文件删除：

- run1 input patch错用 `mode=edit`；改活动接口允许的 `auto` 后run2四层通过。
- run3：无关P2公开修改正确保持P1 freshness，故不是要测的stale分支；read_alone/none下直接写speech被正确拒绝；edit直接compose被正确拒绝；legacy inputs缺reason先报shape；外部文件不能借用项目page_ids。随后分别采用显式历史stale facts、正式speech_only、合法content_ops与正确输入。
- run4 lineage断言误读packet的 `subjects`；实际packet含 `manuscript`，run5核对完整稿并通过。
- run5 fresh第二版移除可选content_plan键，探针应使用get；notes_policy真实枚举为pure_reading，不是none。run6采用正确字段/枚举。
- run6纯阅读notes回读仍给每页一条空文本记录，不能要求列表为空；run7检查每页notes为空并通过。
- run7换Request后原direction不能被假定自动适用于新派生请求；补真实、明确且有界的L1方向决定后run8的merge/split通过。原拒绝及所有输入均保留。

`probe_behavior_run1_original.py` 保存首次执行前的原脚本字节；`probe_behavior.py`后来只修正探针自身mode，非产品修改。各轮JSON与events从不覆盖；修正后的脚本单独命名、单独run目录。运行结果中PASS只属于相应断言范围，不是业务/专业AC总通过。

## 仍阻塞R1的独立原件

只读核对了 `../rc3-04-code-review-round1-7a8578b/report.md`，并按Root要求不重复其反例。该报告保留：F1 import实际写集合超scope删除P2；F2旧来源重建request/credit key；F3 input_revision虚构SourceLink进current；F4 needs_reviewer HTTP/CLI映射错误；global F6等待导出锁期间pause后仍发布delivery。其脚本、原结果与实际文件均在原目录，本文 `external-evidence.sha256` 固定引用字节身份。全局UI F5仅由Root通报，本 reviewer未复核其原件或自行关闭。

因此本轮结论是 **REQUEST_CHANGES（固定候选整体）**；本 reviewer自编有效轨迹未新增must-fix。修复后的新head必须再次固定并复审相关失败与必要合法正控；R1成功样本不能直接给新head签PASS。不能为了得到整卡PASS，把缺口挪到05、人类后置或仅扩大测试数量。

本 reviewer现停止，等Root新的固定head/tree/环境与受影响范围。原37AC/13CQ、12 flow、实际Owner/听众、professional human、目标PowerPoint和发布权限均保持原分工与未运行边界。
