# PR124 指定评审修复记录

评审基于 `53021ac8e9d5a782d8033c976eff8cc02a5f2d17`，结论 Request changes。原 inode P1、固定 RC3 基线获取、显式历史浏览器夹具以及 N6 内容路径已由审查者关闭，本轮保留其保护。此报告和唯一台账分别记录修复证据与实际状态，不以旧 CI 通过抵消新反例。

| Finding | 修复状态与证据 | 受影响 AC |
| --- | --- | --- |
| P2-1 准备阶段原 ID 重试卡住 | 已用首个 `.after`、首个 `.witness` 后真实 child exit91 复现；同 UUID 两次均 unavailable/unknown。已在任何准备物前持久冻结preparing请求/旧状态/意图；同ID和无ID接续后精确重放，未确定归属的残留保持原身份。 | N2-03、N2-10：PASS（实际定向证据），干净新构建已验证；最终CI待完成 |
| P2-2 symlink Host skills 目录 | 同 fixture 基线 a08 成功，530 发生 ENOTDIR/recovery_conflict；真实目录用于内部锁/计划与发布，原访问链仍核验，CLI logical路径兼容；基线对照、死亡恢复、访问链替换保护、历史receipt及旧prepared兼容通过。 | N2-01：PASS（实际定向证据），干净新构建已验证；最终CI待完成 |
| P2-3 旧覆盖异常不回退 | 缺失/符号链接旧不可达快照反例修复前2FAIL2PASS；只在旧覆盖验证边界失效缓存后走既有 canonical scan。四例通过，最终受影响169PASS、缓存关闭共享101PASS；9个正式链损坏控制仍unknown。源/tests/证据已冻结，见 [N4补充报告](N4B-review-P2-cache-fallback.md)。 | N4-12、N4-14：PASS（实际定向证据），干净新构建已验证；最终CI待完成 |
| P2-4 台账汇总矛盾 | `tools/summarize_iteration_ledger.py` 仅从已有逐项判定生成计数、未解决 ID、每卡状态、CI/构建 gate 和非空说明；不修改任何 AC 判定、证据或延期观察。 | N5-10：PASS（实际报告一致性证据），最终 CI 单列 |

P2-4 回归：对原真实报告运行 `tests/rebuild/test_iteration_ledger.py`，先得到1FAIL4PASS；更新派生字段后5PASS。FAIL/BLOCKED/NOT_RUN 三种开放判定均保持原值并进入未解决清单；全部组件 PASS 的控制场景仍将未完成 CI 标成 BLOCKED。真实用户本地效果/可用性与可信 Host 验收观察保留延期，不变成 PASS，也不作为新增 content_only gate。

当前可复核命令：

```bash
python tools/summarize_iteration_ledger.py docs/reports/rc4/iteration-20261019/execution-ledger.json
python -m pytest -q tests/rebuild/test_iteration_ledger.py
```

安装最终回归290PASS（20个新增针对case），47个实际child91断点恢复为42completed/5rolled_back且witness匹配。preparing额外4个越界/伪造迁移负例证明外部树与损坏记录不被修改；不会凭文件名或链接目标认领残留。准确命令/源码与raw hash见 [N2证据](N2-install-recovery-evidence.json)。文档/唯一台账守卫12PASS，原失败记录保留。

四项修复已冻结，随后固定新源提交、干净 wheel/sdist、隔离安装身份及最终精确提交 CI。未合并、发版、部署、改授权或激活真实 HOME。

## 修复候选与安装身份

修复源提交 `3167f123487c3a2ea91848d0bec705743fbec2e3`，干净构建 `source_dirty=false`，版本 `1.0.0rc4`，release identity `3167f123487c-93ce9a2d453a`。新 wheel SHA256 `93ce9a2d453aff96a371db78a8309f06b629e5bf066c9187f550b91765997d9d`；sdist SHA256 `ec9bf88635226a91221c76dc4501aec302e0aa92c0d0a5536dc53a41f71f884e`。全新隔离安装核验23份canonical资源、四Skill、69schema、275package成员与90source模块；见 [安装身份](Installed-resource-identity.json)。N6原实际内容应用身份仍保留，不重标为此安装版运行。

唯一台账保留实际反例的FAIL历史，再依各项修复/新安装证据恢复相关判定；completion由同一逐项状态派生。最终CI为另一个工程gate，组装时仍pending；实时精确head检查与PR最终交接记录其后续终态。用户本地真实验收继续延期，不虚标通过。

## 最终完整浏览器跟进

53021ac8 的完整 required-browser job 实际为489PASS/2FAIL，非取消。两项历史 import fixture 调用当前Task构造器后保留RC4 manifest，运行时正确拒绝无collaboration旧Document。后续仅在该历史构造中剥离manifest/policy并冻结实际RC3选择摘要；完整搜索/详情/只读断言、required-browser、timeout与业务writer边界保持。真实系统Chromium聚焦3PASS/0skip；本地临时浏览器路径适配和原失败完整保留在 [修复记录](Integration-browser-legacy-repair.json)。此项为CI后续测试数据修复，与指定四个P2分别记录；完整新head CI仍须终态核验。Runtime/Skill/构建输入保持3167源字节，干净wheel身份不重标。

后续2b6867c5完整PR浏览器得到490PASS/1FAIL，原两个历史import case已通过。新增失败是样式plan测试的真实fetch回调完成竞态，独立于指定四项P2。命令级1秒非阻塞延迟在原source精确复现assert held为空；仅用测试完成事件和已有expect默认超时同步后，同注入四参数4PASS、未注入四参数及原完整截图流程5PASS。Runtime/Skill/构建输入与干净3167包仍一致；证据见 [同步修复记录](Integration-style-plan-sync-repair.json)。新的完整精确head CI仍须通过。
