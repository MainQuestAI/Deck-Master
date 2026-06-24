# QA Test Plan

## 1. Unit

- Manifest / Stage Contract loader。
- Entry / Exit validator。
- Fingerprint / stale propagation。
- Handoff lifecycle / idempotency / locking。
- Approval / preauthorization / expiry / revoke。
- Question resolver / Decision Log。
- Sourcing Plan v2 validation。
- Page Package customer/internal boundary。
- Build Manifest v2 projection。
- Legacy bootstrap。

## 2. Integration

- Manifest → Router。
- Stage Contract → Workflow State。
- Exit validation → Handoff → Approval → downstream entry。
- Sourcing → Producer → Builder。
- Builder → Quality → Review。
- Review finding → Repair Handoff。
- Review approval → Export。

## 3. E2E

### E2E-1 New Production Run

```text
init
→ brief
→ approval
→ planner
→ approval
→ sourcing
→ approval
→ producer
→ builder
→ quality
→ review
→ final approval
→ export
```

### E2E-2 Legacy Run

```text
legacy artifacts
→ workflow bootstrap
→ inferred state
→ required confirmation
→ page package migration
→ review
```

### E2E-3 Repair

```text
quality P1/P0
→ repair owner stage
→ repair handoff
→ revalidation
→ new final approval
```

## 4. Mutation Tests

- 修改 brief 后 planner/downstream stale。
- 修改 sourcing plan 后 page packages/downstream stale。
- 修改 page package 后 final approval stale。
- 修改 final PPTX 后 export blocked。
- 删除 approval log line 后 transition blocked。

## 5. Security / Safety

- path traversal。
- absolute path 主界面泄漏。
- internal_only leakage。
- private source excerpt leakage。
- forged approval / wrong hash。
- expired preauthorization。
- client export preauthorization attempt。

## 6. Platform

- Ubuntu CI。
- macOS local smoke。
- temp HOME Codex。
- temp HOME Claude Code。
- moved release tree。
- upgrade / rollback。

## 7. Browser

最少场景：

- early stage no preview；
- awaiting brief approval；
- sourcing blocked；
- agent execution waiting；
- builder backend missing；
- quality blocked；
- repair handoff；
- final approval pending；
- ready to export；
- stale after artifact mutation。
