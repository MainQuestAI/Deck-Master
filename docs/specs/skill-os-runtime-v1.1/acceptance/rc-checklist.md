# Skill OS RC Checklist

## Runtime

- [ ] Manifest 1.1.0 与 Stage Contracts 一致。
- [ ] 9 个 Stage Contract 通过 schema + semantic validation。
- [ ] Workflow State 可重建。
- [ ] Handoff append-only、幂等、可 stale。
- [ ] Approval 与 Fingerprint 绑定。
- [ ] Final export 不可预授权。

## Production Boundary

- [ ] Sourcing Plan v2 全页覆盖。
- [ ] Page Packages 全 required pages 覆盖。
- [ ] Builder 只消费 whitelist projection。
- [ ] Legacy Preview Adapter 只显式使用。
- [ ] PPT Deck Pro Max / PPT Master contract versions 固定。

## Autopilot

- [ ] interactive / preauthorized / quick / repair / review-only 全覆盖。
- [ ] 高影响 Gate 正确停止。
- [ ] 自动 Gate 正确推进。
- [ ] final export 必停。
- [ ] Evidence report 完整。

## Review Desk

- [ ] Stage Rail。
- [ ] Handoff summary。
- [ ] Approval actions。
- [ ] Stale reason。
- [ ] Next Skill。
- [ ] 主界面无命令和绝对路径。

## Compatibility

- [ ] Legacy Run bootstrap。
- [ ] `ppt-*` wrappers。
- [ ] external full real directory。
- [ ] external full symlink。
- [ ] adapter-only blocked for production。
- [ ] rollback。

## Release

- [ ] Full unit tests。
- [ ] Integration tests。
- [ ] 3 E2E。
- [ ] Codex temp HOME。
- [ ] Claude temp HOME。
- [ ] release archive + SHA256SUMS。
- [ ] RC report 无 required failure。
- [ ] docs / release notes / migration guide 更新。
