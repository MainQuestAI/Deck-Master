# WU08 接续关闭记录

此前 27 个工程欠项已继续执行，当前只剩 **AC49 最终 head CI / 独立 Draft PR 回执 PENDING**。不是以清单替代实施。当前产品/包源码 `3baf6caa060d95b0f59bc2a3b973b7edc122c553`；准确运行结果见 [DELIVERY](DELIVERY.md)。原 89a4db38 文档保留此前欠项及 API 错误历史。

## 新增验证映射

以下测试均在 `tests/rebuild/test_webui_acceptance_matrix.py`，相关旧族同时回归；52 个参数展开用例不等于 52 AC。

| AC | 主要证据场景 |
|---|---|
| 06/07 | unreachable_cross_project / pagination_remains_fixed |
| 09/11/12/13 | old_manifest、task_method_ui_old_record_and_damage；真实冻结清单与无 manifest 空态 |
| 10/17/22 | narrative_text_alternatives_xss_and_fixed_intent / late_argument；write_only/speech_only |
| 14 | unknown_call_reading_never_allocates_retries_or_dispatches + generation unknown 守卫 |
| 23/25/37 | table_atom、imported_page_missing_mapping、long_semantics_and_bullet_atoms；损坏来源 reader 组 |
| 28/29 | Review v1/v2 状态矩阵、deck/changed Page、浏览器诚实状态与无猜测定位 |
| 30/31/33 | review_handoff_real_plan_commit_and_failure_recovery；none/commit_ack/stale/scope；speech/design/source；草稿恢复/导入/最后输入 |
| 35 | neutral_purpose_keeps_user_input_intent_and_speech_policy + Studio intake 回归 |
| 36 | requirements 唯一冻结任务/多任务歧义/derived；RC3 resolver |
| 40/42/43 | method_role_stage_change、saved IDs/body drift、all_example_variants_and_script、revision_drift、大小与 UTF-8 损坏 |
| 45 | 经营诊断/方案权衡/教学实际 Host 三场景 + 副本 Review browser（显式 synthetic Review） |
| 46 | 三视口完整键盘主要路径、modal 焦点、原生选字、长正文与安装版无横溢 |
| 47/48 | 精确 SHA 包、隔离服务；真实 baseline→upgrade→rollback，legacy/future writer 拒写，业务 hash 不变 |

AC18/20 原有固定比较/采用两 UUID 回执丢失与并发组继续通过，本轮增加有效决定 D1→拒绝→D2 后新采用只用 D2。原 pending payload 的恢复不被替换。

## 真实剩余项

- **AC49 / PENDING**：父线程负责最终分支 head required CI 和独立 Draft PR 回执。当前任务的 gh GraphQL 访问错误仍未恢复，未重试/换通道；父线程曾确认当时无 PR。旧分支 CI 和 PR127 CI 不代填。
- **professional_review / NOT_RUN**：没有独立专业审阅；当前作者的内容、fixture Review、工程测试不代填。
- **human_acceptance / NOT_RUN**：须实际用户反馈；浏览器自动化和代理看图不代填。

AC50 仅验收分层回执是否诚实，不表示上述认可已发生。没有自动合并、发布或向真实 HOME 激活。
