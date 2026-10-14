# RC3-01-S01：逐字稿段类型与前审返修关闭

## 触发与范围

真实 E1 的 Q1 A/B 逐字稿包含讲述、停顿和学员练习。原产品要求每个
`speech_segments[].kind` 都等于 Task 的 `speech_kind=verbatim`，从而拒绝诚实标注
`cue` 的非口播段。先前格式修正把 cue 改标 verbatim 后，独立内容审阅仍发现 F2：
非口播互动不能当成实际口播计时。原始输出、拒收与首次失效保留，S01 不改写它们。

另一缺陷是前审状态累计仍适用的开放 finding，却没有消费正式 receiver 已支持的
`Review.replaces` 关闭记录；独立复审的合法 `accepted_variance` 已接纳后仍被旧项阻塞。
中央 `finding_closed` 对 `fixed` 默认要求当前 PPTX，也使真实制作前的稿件返修无法
在尚未制作 PPTX 时关闭。

这张必要补充卡只修改 `content_production`、`content_review` 和中央 review 的上述
消费边界，新增正式 API 回归。不涉及导出、设计、默认 writer、Skill 发布或权限实现。

## 原规范与边界

已分段全文读取 v1.2 `SPEC.md`、`CONTRACTS.md` 及原 RC3-01 卡，核对实际
Page/Review schema、模型语义、receiver 与中央 closure。ACCEPTANCE 读取相关
AC-M02/M03/M05 和审查分层部分。原文件保持不变。

| 来源 | SHA-256 |
| --- | --- |
| SPEC.md | `07f8f05d29d5bfb3ef3a076799723bbea1ee9d3067e4d974592c5f0f273636ae` |
| CONTRACTS.md | `488055f07f512a21721b0b198241808ea108675021a0c485d7c56a52d912deff` |
| ACCEPTANCE.md | `7a04df70ac4d90dc253f712a108587a25a69f7cc33526c10874d03b73f64e9d1` |
| RC3-01.md | `fd76ecef219f2c999073018cc50971562ea2f1626943b45311b05a3f759faedc` |

`CONTRACTS §11.3` 已定义逐段 `cue | verbatim`，没有要求整页所有段同类型。
`SPEC §9/§10.2` 及 AC-M02/M03 要求完整可说的逐字内容，并区分讲述、停顿、练习
与问答。S01 因而允许 verbatim Task 保留诚实 cue 段；每个更新页仍必须有非空白
verbatim 内容。此项只是防止全 cue 冒充逐字稿的最低记录要求，不能证明语义完整、
cue 分类真实、自然可说或估时可行。没有字数比例、固定语速或实测时间兜底。
cues Task 仍只接纳 cue；none、固定 Page Ref、范围、完整映射与估时要求保持。
派发指令同时说明这个现有字段合同，避免迫使 Writer 改标签过检。

`CONTRACTS §6.3/§11.6` 要求在制作前审查完整稿件，复用既有 Review 的 replaces
语义。S01 的前审查询使用同一个 `finding_closed`，不引入新 supersede 字段或第二套
状态。只有显式替换同一 review_id/kind/stage 和 finding_id/page，当前主体与完整当前
依赖、实际 observations/evidence 满足原中央规则，才关闭旧 finding。
`accepted_variance` 仍只用于原 `needs_judgment`，必须给理由；不能把 must_fix 接受为
差异。新 pass 若没有合法 replaces，不能抹去仍适用的旧开放 finding。

中央 `fixed` 对 `preproduction` 不要求先存在 PPTX；仍要求实际同页稿件变化、当前
Page、当前依赖、observations 和 evidence。`page_visual` 的当前预览要求，以及
`final` 的当前输出变化要求保持原样。未改变稿件而仅重贴 fixed 标签仍拒收。
审查来源认证、实际独立执行、作者排除、请求/权限与 CAS 继续通过原正式路径校验。

## 验证与证据限制

新增 `tests/rebuild/test_rc3_01_gate_repair.py` 共 26 个回归案例，使用正式
dispatch → 显式 synthetic L1 provider receipt → service accept → 当前状态查询。
其中包含 mixed 逐字稿正例、段类型/映射/估时/范围原子拒收、单个及多 finding
关闭、无 replaces 新 pass 的阻塞、错误逻辑审查/阶段/页面/主体/依赖/关闭理由/证据/
独立通道的负例，以及无 PPTX 的真实稿件变化 fixed 正例和未变化 fixed 负例。

与 `test_t03_review_fixes.py`、`test_content_preproduction_review.py`、`test_review.py`、
`test_compose_v2_phases.py` 合跑：**118 passed，6.64 秒**。既有中央 final 与
page_visual closure 的正反回归包含在该结果中。Ruff 与 `git diff --check` 通过。
首轮测试有一个新 fixture 将单页数组与完整两页 page_order 混用，按原 complete
page-copy 合同修正 fixture 后通过，产品没有为此放宽协议。

这些 fixtures 只证明 L1 协议，不代表真实模型评阅、人类 Owner/受众认可、实际计时、
桌面备注验证或 RC3 整体通过。S01 独立代码 review 和新安装后的真实运行由主控另记。

method-only B 的 `1fb3ddacbb75a2d891b5a14d955cf23db9460931` 安装及其首轮 E1
保留不变；A 的已安装 `575eca2c82a5f43d72d491f888e36c0183d88c73` 同样保留。
S01 形成新的软件版本；后续公平 A/B 需以相同 S01 核心修复分别新建隔离安装，A
继续保留旧方法，B 保留 RC3-01 新方法。不能把补充修复后的运行冒称原 B 首次生成
效果，不能修改冻结 driver/protocol 或已领取 Task 来绕过 basis 检查。
