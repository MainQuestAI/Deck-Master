# 验收证据的只读核验

`scripts/uat/evidence_validation.py` 核对已有证据包的候选源码、当前输入修订、实际文件和哈希。它复用 `validation.json`、`durable-evidence-manifest.json`、release/parity summary、JUnit 与 CI 捕获文件；运行输入来自现有不可变修订，当前产物来自 canonical render result。不会复制材料、恢复投影、写验收状态或批准交付。

源码 checkout 中运行：

```bash
python3 scripts/deck_master.py verify-evidence \
  --evidence-root <evidence_dir> \
  --candidate-sha <full_git_sha> \
  --run main=<current_run_dir> \
  --run cold=<other_current_run_dir>
```

CLI 仅输出 JSON。核验无工程证据问题时退出 0，仍可能有 `human_pending`；存在 `stale`、`missing` 或 `failed` 时退出 2。退出 0 不等于工程验收完成或可交付。

独立模块入口 `python3 -m scripts.uat.evidence_validation` 接受相同参数，适用于无需加载主 CLI 的只读核验。

供正式 CLI 集成的函数：

```python
verify_evidence_bundle(
    evidence_root,
    candidate_sha,
    run_dirs={"main": current_run_dir, "cold": other_run_dir},
    release_summary_ref=None,
    parity_summary_ref=None,
) -> dict
```

`candidate_sha` 必须为调用者指定的完整 40 位 SHA。`run_dirs` 的键对应 parity pages 中的 `run` 标签；未提供当前 run 时，历史包完整也不能证明输入新鲜。summary 默认位于 `release-<recorded_sha_prefix>/summary.json` 和 `actual20-<recorded_sha_prefix>/summary.json`；函数参数可指定其他包内相对路径，页数按当前 run 核验，不固定为 20。

返回 `candidate_sha`、`status`、`counts`、逐项 `checks` 和 `read_only`。文件检查包含 `observed_sha256` 与已记录的 `expected_sha256`；缺绑定时仍只读收集实际哈希，供调用方检查后归入原 manifest。这些是本次观察结果，不是新的运行或批准状态模型。

| 状态 | 含义 |
|---|---|
| `passed` | 本项记录与指定 SHA、当前输入或文件一致，且相应结果检查通过 |
| `stale` | SHA/修订/哈希不一致、结构无效、路径不安全，或核验期间证据发生变化 |
| `missing` | 缺文件、缺哈希绑定、未完成执行，或没有当前运行可验证新鲜度 |
| `failed` | JUnit、CI、release 或页级保真记录明确失败；保留失败，不包装成过期 |
| `human_pending` | 现有声明表明用户复核或最终文件批准仍待完成 |

聚合状态按 failed、stale、missing、human_pending、passed 的顺序反映尚未通过的检查；完整明细和各状态计数始终保留。

## 证据范围

- `durable-evidence-manifest.json` 使用已有 `source_sha`、`file_count`、`files[{path, sha256}]` 结构。引用必须是包内相对路径；拒绝绝对路径、路径穿越及软链接，包括中间目录软链接。
- manifest 应包含 release 和 parity 的 summary/证据，以及 `ci.json` 与各 Python 的 metadata。缺这些哈希会显示 missing。JUnit 和日志同时核对 validation 中的独立哈希。
- JUnit 含 testcase 明细时，failure/error 直接记为 failed，总数或 skipped 与汇总矛盾记为 stale；旧版仅有 testsuite 汇总的记录仍可核对非负计数及执行结果，但不据此声称已验证逐项执行明细。
- 根 manifest 和 validation 由调用者选择作为核验入口；哈希检查不能独立证明外部工具实际执行，也不是来源签名。该能力不替代 `release-smoke`、真实渲染、视觉复核或独立代码审查。
- native parity 复核现有记录中的 SSIM ≥ 0.97、几何误差 ≤ 0.75pt 和 P0/P1 标记；不会重新计算图像，也不会采用记录中放宽的阈值。当前运行的 SVG、Scene、最终 PPTX、页预览和页集合必须匹配。图片→SVG 内容/视觉评分仍由既有独立评审流程处理。
- 检查结束前再次核对已读文件。核验期间发生变化则返回 stale，要求调用者重新读取；不在本工具中修复状态。
- `human_visual_review` 和 `final_file_approval` 的 passed 字符串不是批准凭证。若只有这类声明，返回 missing，继续由既有验收台账、`final-readiness --no-write` 与 workflow approval 检查正式证据。本工具不创建或代填人工通过。

`sc1_1_engineering_matrix.py` 继续负责已有验收条目和执行记录。本核验器不修改 matrix，也不会把历史记录或映射自动变成当前通过；最终工程收口仍由完整验收范围及用户复核共同决定。
