# RC3-01-S01 独立核心复审：第三轮

结论：**PASS**，固定核心候选 `cc6150da513ce38060b0a8ad045ea5159a56cae6`。第一轮 F-S01-01 和第二轮 F-S01-02 均已关闭，本审查范围无剩余阻塞 finding。

本结论是代码、L0/L1 的独立审查通过，可作为主控继续新安装及实际消费验证的依据；没有替主控 merge，也不宣布 RC3-01 整卡、原 AC/CQ、真实内容效果或人类验收通过。

## 固定范围与历史

- 审查执行者：`/root/rc3_01_code_review`，未参与实现。
- 方法候选基线：`1fb3ddacbb75a2d891b5a14d955cf23db9460931`。
- 第一轮 core：`5deb222c77cadbdb835c695b17224d4e312d2395`，REQUEST_CHANGES / F-S01-01，旧报告原件保留。
- 第二轮 core：`e1d42878093382254507448732ac0b1c6052a0ba`，REQUEST_CHANGES / F-S01-02，旧报告原件保留。
- 最终审查 core：`cc6150da513ce38060b0a8ad045ea5159a56cae6`，PASS。
- 最終审查覆盖 4 个 core 文件、70 例新增测试文件、S01 报告。`editing._current_artifact_digests` 的临时解释扩展由 root 明确授权，未新增 schema/持久状态或改 future export/design/defaultflow。
- 同步修改的 METHODS/ledger/anchor 文档不属于这个纯核心固定提交；旧方法-only A/B 安装、原始结果、旧校准/CI 身份没有回写。
- 专用 Python 为 env-01；结束时再次核对上述 6 文件工作字节与固定 HEAD 一致。

## 逐项复核

1. **逐字与 cue**：显式 verbatim 允许实际非口播 cue，仍拒 all-cue、仅空白 verbatim、错类型、缺估时、范围缺口、未知论证节点和越界正文写。cues 请求仍拒扩为 verbatim。结构最低门槛不代替真实语义完整性/估时可行性。
2. **F-S01-01**：当前 pass freshness 与历史开放 finding 存续分离；同页或其他页的正文/notes 改动加无 replaces 新 pass 均不能清除旧项。完整历史替换链含 stale 中间版本，current endpoint 仍经中央显式 closure；合法退役页、查询范围外页和不再 required 的单位不误阻当前范围。
3. **F-S01-02**：仅 `preproduction + page_id=null` 增加整稿 closure。候选必须完整引用并声明当前 Plan、当前所有 Page 及存在时的 Narrative；仍用同逻辑 review/kind/stage/finding/null page 的显式 replaces。variance 仅用于 needs_judgment，需要当前依赖、observations、evidence 和具体理由；must_fix 不能接受为 variance。
4. **实际变化**：null fixed 的变化依据来自真实不可变 Narrative/Plan/Page 对象的临时解释，不将对象 hash 改变直接视为内容修复。非 speech 解释排除仅 notes/segments；speech 保留实际口播与段数据。外壳 version/previous_ref、顶层 Narrative/Page refs 和 page_links、源 locator 审计、制作说明、layout_hint、问题 resolution 等不构成这一内容变化。hash 是最低变化证据，语义正确仍由实际独立 Review 判断。
5. **其他阶段及身份**：原 final 当前输出变化和 page_visual 当前同页 preview 条件保留；null 专用路径不适用于这些阶段。提交认证、独立 provider receipt、作者排除、current subject/dependency、CAS/范围没有改为 caller 自签或 label 通过。

## 独立验证

```text
/workspace/work/rc3/cards/env-01/bin/python -m pytest \
  tests/rebuild/test_rc3_01_gate_repair.py \
  tests/rebuild/test_t03_review_fixes.py \
  tests/rebuild/test_content_preproduction_review.py \
  tests/rebuild/test_review.py \
  tests/rebuild/test_compose_v2_phases.py -q
162 passed in 11.83s

Ruff（4 core + 新 tests）：All checks passed!
git diff --check 1fb3ddac..cc6150da：exit 0
```

额外独立探针（`rc3-01-s01-independent-round3-probes.json`）：

- 正式 synthetic L1 API 重跑第二轮的 null argument `accepted_variance`：现正式接纳且当前 gate=pass，旧 finding 原件仍留存。
- L0 helper 层从真实 immutable objects 构造仅 Narrative/Plan version/previous_ref、Narrative 指针、Page mapping pointer、Plan page_links 的重绑解释：4 个对象 Ref 都改变，语义 hash 都不变；真实 current Document 未修改。此为 helper 静态解释验证，不冒称正式 adopted 工作流。
- 有一次准备探针把 argument phase 错写成 envelope variant=argument，schema 正确拒绝；该准备错误已记录，不当作产品 finding 或通过的 Runtime 路径。

固定字节身份见 `rc3-01-s01-independent-round3-identity.json`。第一轮/第二轮失败与各自测试结果保持原版本，最终 PASS 不改写它们。

## 仍待后续执行

root 的广泛回归/当前 CI、新 A/B 同 core 的公平隔离安装、实际 native 消费和专业复审关闭须按新候选另记。方法-only `1fb3` 的旧运行不能改名为本次新核心效果。真实 Owner/目标受众、完整试讲、桌面文件验收继续按用户安排 NOT_RUN，模型和本审查不代替这些人类证据。
