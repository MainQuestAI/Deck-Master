# SC-1.1 验收追踪（acceptance-tracking）

数据源：`acceptance/cases.json`（64 项）+ `acceptance/SC1_SUPERSESSION_MAP.json`（原 88 项映射：72 retain / 12 clarify / 4 replace，全部 verification_status=unverified 起步）。

状态口径：pass（工程测试证明）/ blocked（环境缺真实工具）/ not_run（未执行）/ deferred_to_uat。禁止未执行标 pass。

## 总览（2026-09-07，ND-01—ND-04 工程交付后）

| 组 | 数量 | 本轮状态 |
|---|---|---|
| GOV（治理） | 4 | GOV-02 工程：依赖闭包=pyproject 现有依赖，无新增分发组件（dependency-closure）；发布锁登记与许可核验待 release 构建执行（blocked） |
| CMP（编译内核） | 10 | CMP-06/07 工程通过（单一实现身份断言 + 无 HOME/ppt-master 探测 + 注入验证器 fail-closed + pin-hash 阻断）；CMP-01/02/03 经引擎链证明（两页真实编译+回读，`test_sc1_1_native_engine`）；CMP-04/05/08/09/10（七类页差分/字体/gradient/表格边界）由既有 HD 回归通过覆盖部分，**专项七类差分矩阵用例 not_run** |
| IND（独立性/就绪） | 8 | IND 探针（干净环境 ready/degraded_ready、env 不能伪报、public 摘要脱敏、指纹漂移失效）pass；IND-02/03 路由默认通过；安装/发布树 required 策略改造未完成（blocked） |
| CNT（内容链） | 7 | CNT-01 场景从同一 Lock/Package 投影（engine 单一事实源加载）工程通过；其余随文档/接线 pending |
| HST（宿主真实工具） | 7 | **not_run（blocked）**：本宿主无 ImageGen/视觉工具（host-capability-probe 实测）；机制面（awaiting 派发 envelope、绝不静默降级）已测试 |
| WF（工作流） | 8 | WF-05（revision 指针/CAS/失败不移动指针）工程通过；其余部分由既有 envelope 测试覆盖，部分待接线 |
| QA（质量门） | 8 | QA-02（external_visual 不得冒充语义门，含有效 hash 反例）工程通过；逐文件内容指纹当前性部分实现（index sha + pin-hash） |
| MIG（迁移） | 6 | not_started（旧 HD/standard 只读分流与 dry-run CLI 未实现——本轮未动旧 Run 路径，无破坏） |
| UAT | 6 | UAT-01/02（8—12 页真实全链）**not_run**：需真实 renderer/ImageGen/桌面编辑软件；客户 L3 依赖素材（outcome_pending 通道） |

## 已执行证据索引

- `tests/test_sc1_1_native_kernel.py`（单一实现/无外部探测/注入验证器）
- `tests/test_sc1_1_native_routing.py`（路由默认/legacy 映射/none/build 消费 ready_for_build）
- `tests/test_sc1_1_native_probe.py`（真实探针/失败封闭/脱敏/指纹漂移）
- `tests/test_sc1_1_gates_and_revisions.py`（语义门精确匹配/revision 指针/失败预算）
- `tests/test_sc1_1_native_engine.py`（两页真实 native 编译+回读/HST awaiting 诚实/无包阻断）
- HD 既有测试全绿（提取前后同一实现），全量套件结果见提交记录
